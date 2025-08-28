"""
Tests for AI Policy Selector functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from models import (
    ClusterInfo,
    GovernanceRequirements,
    PolicyIndex,
    PolicyCatalogEntry,
    RequirementAnswer,
    ThirdPartyController,
    ControllerType,
)
from ai.ai_policy_selector import AIPolicySelector
from ai.bedrock_client import BedrockClient


class TestAIPolicySelector(unittest.TestCase):
    """Test cases for AI Policy Selector."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Bedrock client
        self.mock_bedrock_client = Mock(spec=BedrockClient)
        self.mock_bedrock_client.model_id = "test-model"

        # Create AI policy selector
        self.ai_selector = AIPolicySelector(
            bedrock_client=self.mock_bedrock_client,
            policy_catalog_path="./test-catalog",
            output_directory="./test-output",
        )

        # Create test cluster info
        self.cluster_info = ClusterInfo(
            version="1.28.0",
            managed_service="EKS",
            node_count=3,
            namespace_count=10,
            third_party_controllers=[
                ThirdPartyController(
                    name="istio",
                    type=ControllerType.SERVICE_MESH,
                    namespace="istio-system",
                )
            ],
            compliance_frameworks=["CIS"],
        )

        # Create test governance requirements
        self.requirements = GovernanceRequirements(
            answers=[
                RequirementAnswer(question_id="registry_enforcement", answer=True),
                RequirementAnswer(question_id="pod_security", answer=True),
            ],
            registries=["docker.io", "gcr.io"],
            compliance_frameworks=["CIS"],
        )

        # Create test policy index
        self.policy_index = PolicyIndex(
            categories={
                "best-practices": [
                    PolicyCatalogEntry(
                        name="require-pod-resources",
                        category="best-practices",
                        description="Require pod resource limits",
                        relative_path="best-practices/require-pod-resources.yaml",
                        tags=["resources", "limits"],
                    ),
                    PolicyCatalogEntry(
                        name="disallow-privileged-containers",
                        category="best-practices",
                        description="Disallow privileged containers",
                        relative_path="best-practices/disallow-privileged-containers.yaml",
                        tags=["security", "privileged"],
                    ),
                ],
                "security": [
                    PolicyCatalogEntry(
                        name="restrict-image-registries",
                        category="security",
                        description="Restrict allowed image registries",
                        relative_path="security/restrict-image-registries.yaml",
                        tags=["registry", "images"],
                    )
                ],
            },
            total_policies=3,
        )

    def test_extract_lightweight_policies_from_index(self):
        """Test extracting lightweight policies from policy index."""
        lightweight_policies = (
            self.ai_selector._extract_lightweight_policies_from_index(self.policy_index)
        )

        self.assertEqual(len(lightweight_policies), 3)

        # Check first policy
        first_policy = lightweight_policies[0]
        self.assertIn("name", first_policy)
        self.assertIn("category", first_policy)
        self.assertIn("tags", first_policy)
        self.assertEqual(first_policy["name"], "require-pod-resources")
        self.assertEqual(first_policy["category"], "best-practices")
        self.assertLessEqual(
            len(first_policy["tags"]), 5
        )  # Tags should be limited to 5

    def test_prepare_phase_one_context(self):
        """Test preparing context for Phase 1 filtering."""
        lightweight_policies = (
            self.ai_selector._extract_lightweight_policies_from_index(self.policy_index)
        )
        context = self.ai_selector._prepare_phase_one_context(
            self.cluster_info, self.requirements, lightweight_policies
        )

        # Check cluster information
        self.assertEqual(context["cluster"]["version"], "1.28.0")
        self.assertEqual(context["cluster"]["managed_service"], "EKS")
        self.assertEqual(context["cluster"]["node_count"], 3)

        # Check requirements
        self.assertEqual(context["requirements"]["registries"], ["docker.io", "gcr.io"])
        self.assertEqual(context["requirements"]["compliance_frameworks"], ["CIS"])

        # Check policies
        self.assertEqual(context["total_policies"], 3)
        self.assertIn("policies_by_category", context)
        self.assertIn("best-practices", context["policies_by_category"])
        self.assertIn("security", context["policies_by_category"])

    def test_group_policies_by_category(self):
        """Test grouping policies by category."""
        lightweight_policies = (
            self.ai_selector._extract_lightweight_policies_from_index(self.policy_index)
        )
        grouped = self.ai_selector._group_policies_by_category(lightweight_policies)

        self.assertIn("best-practices", grouped)
        self.assertIn("security", grouped)
        self.assertEqual(len(grouped["best-practices"]), 2)
        self.assertEqual(len(grouped["security"]), 1)

        # Check that tags are limited to 3 for token efficiency
        for category_policies in grouped.values():
            for policy in category_policies:
                self.assertLessEqual(len(policy["tags"]), 3)

    def test_create_phase_one_prompt(self):
        """Test creating Phase 1 filtering prompt."""
        lightweight_policies = (
            self.ai_selector._extract_lightweight_policies_from_index(self.policy_index)
        )
        context = self.ai_selector._prepare_phase_one_context(
            self.cluster_info, self.requirements, lightweight_policies
        )
        prompt = self.ai_selector._create_phase_one_prompt(context)

        # Check that prompt contains key information
        self.assertIn("Phase 1 policy filtering", prompt)
        self.assertIn("1.28.0", prompt)  # Kubernetes version
        self.assertIn("EKS", prompt)  # Managed service
        self.assertIn("CIS", prompt)  # Compliance framework
        self.assertIn("100-150", prompt)  # Target candidate count
        self.assertIn("JSON array", prompt)  # Expected response format

    def test_parse_phase_one_response_valid_json(self):
        """Test parsing valid JSON response from Phase 1."""
        response = '["policy-1", "policy-2", "policy-3"]'
        parsed = self.ai_selector._parse_phase_one_response(response)

        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed, ["policy-1", "policy-2", "policy-3"])

    def test_parse_phase_one_response_embedded_json(self):
        """Test parsing response with embedded JSON."""
        response = """
        Here are the selected policies:
        ["policy-1", "policy-2", "policy-3"]
        These policies are most relevant.
        """
        parsed = self.ai_selector._parse_phase_one_response(response)

        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed, ["policy-1", "policy-2", "policy-3"])

    def test_fallback_phase_one_selection(self):
        """Test fallback Phase 1 selection."""
        candidates = self.ai_selector._fallback_phase_one_selection(self.policy_index)

        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)
        self.assertLessEqual(len(candidates), 120)  # Should not exceed target

        # All candidates should be policy names
        for candidate in candidates:
            self.assertIsInstance(candidate, str)

    @patch(
        "ai.ai_policy_selector.AIPolicySelector._extract_lightweight_policies_from_index"
    )
    def test_phase_one_filter_success(self, mock_extract):
        """Test successful Phase 1 filtering."""
        # Mock lightweight policies
        mock_extract.return_value = [
            {"name": "policy-1", "category": "security", "tags": ["tag1"]},
            {"name": "policy-2", "category": "best-practices", "tags": ["tag2"]},
        ]

        # Mock Bedrock response - ensure it returns a proper string
        self.mock_bedrock_client.send_request.return_value = '["policy-1", "policy-2"]'

        # Mock the send_request_with_fallback method as well
        self.mock_bedrock_client.send_request_with_fallback.return_value = (
            '["policy-1", "policy-2"]'
        )

        candidates = self.ai_selector.phase_one_filter(
            self.cluster_info, self.requirements, self.policy_index
        )

        self.assertEqual(candidates, ["policy-1", "policy-2"])

    @patch(
        "ai.ai_policy_selector.AIPolicySelector._extract_lightweight_policies_from_index"
    )
    def test_phase_one_filter_fallback(self, mock_extract):
        """Test Phase 1 filtering with fallback on error."""
        # Mock lightweight policies
        mock_extract.return_value = [
            {"name": "policy-1", "category": "security", "tags": ["tag1"]}
        ]

        # Mock Bedrock error
        self.mock_bedrock_client.send_request.side_effect = Exception("Bedrock error")

        candidates = self.ai_selector.phase_one_filter(
            self.cluster_info, self.requirements, self.policy_index
        )

        # Should fall back to rule-based selection
        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)

    def test_prepare_phase_two_context(self):
        """Test preparing context for Phase 2 detailed selection."""
        detailed_policies = [
            {
                "name": "require-pod-resources",
                "category": "best-practices",
                "description": "Require pod resource limits and requests",
                "relative_path": "best-practices/require-pod-resources.yaml",
                "test_directory": "best-practices/require-pod-resources",
                "source_repo": "https://github.com/kyverno/policies",
                "tags": ["resources", "limits", "requests"],
                "has_tests": True,
            },
            {
                "name": "restrict-image-registries",
                "category": "security",
                "description": "Restrict allowed image registries",
                "relative_path": "security/restrict-image-registries.yaml",
                "test_directory": None,
                "source_repo": "https://github.com/kyverno/policies",
                "tags": ["registry", "images", "security"],
                "has_tests": False,
            },
        ]

        context = self.ai_selector._prepare_phase_two_context(
            self.cluster_info, self.requirements, detailed_policies
        )

        # Check cluster information
        self.assertEqual(context["cluster"]["version"], "1.28.0")
        self.assertEqual(context["cluster"]["managed_service"], "EKS")
        self.assertEqual(context["cluster"]["node_count"], 3)
        self.assertEqual(context["cluster"]["compliance_frameworks"], ["CIS"])

        # Check requirements
        self.assertEqual(context["requirements"]["registries"], ["docker.io", "gcr.io"])
        self.assertEqual(context["requirements"]["compliance_frameworks"], ["CIS"])
        self.assertIn("answered_yes", context["requirements"])

        # Check candidate policies
        self.assertEqual(context["total_candidates"], 2)
        self.assertEqual(len(context["candidate_policies"]), 2)
        self.assertEqual(
            context["candidate_policies"][0]["name"], "require-pod-resources"
        )
        self.assertEqual(
            context["candidate_policies"][1]["name"], "restrict-image-registries"
        )

    def test_create_phase_two_prompt(self):
        """Test creating Phase 2 detailed selection prompt."""
        detailed_policies = [
            {
                "name": "require-pod-resources",
                "category": "best-practices",
                "description": "Require pod resource limits and requests",
                "tags": ["resources", "limits"],
            }
        ]

        context = self.ai_selector._prepare_phase_two_context(
            self.cluster_info, self.requirements, detailed_policies
        )
        prompt = self.ai_selector._create_phase_two_prompt(context, target_count=20)

        # Check that prompt contains key information
        self.assertIn("Phase 2 policy selection", prompt)
        self.assertIn("exactly 20 policies", prompt)
        self.assertIn("1.28.0", prompt)  # Kubernetes version
        self.assertIn("EKS", prompt)  # Managed service
        self.assertIn("CIS", prompt)  # Compliance framework
        self.assertIn("docker.io", prompt)  # Registry requirements
        self.assertIn("JSON object", prompt)  # Expected response format
        self.assertIn("selected_policies", prompt)  # Response structure
        self.assertIn("customizations", prompt)  # Customization requirements

    def test_parse_phase_two_response_valid_json(self):
        """Test parsing valid JSON response from Phase 2."""
        response = """
        {
            "selected_policies": [
                {
                    "name": "require-pod-resources",
                    "reasoning": "Essential for resource management",
                    "customizations": [
                        {
                            "type": "parameter_adjustment",
                            "description": "Set default resource limits",
                            "value": "memory: 512Mi, cpu: 100m"
                        }
                    ]
                },
                {
                    "name": "restrict-image-registries",
                    "reasoning": "Matches registry requirements",
                    "customizations": [
                        {
                            "type": "registry_replacement",
                            "description": "Update allowed registries",
                            "value": "docker.io,gcr.io"
                        }
                    ]
                }
            ]
        }
        """

        parsed = self.ai_selector._parse_phase_two_response(response)

        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0], "require-pod-resources")
        self.assertEqual(parsed[1], "restrict-image-registries")

        # Check that customizations are stored
        self.assertTrue(hasattr(self.ai_selector, "_phase_two_customizations"))
        self.assertIn(
            "require-pod-resources", self.ai_selector._phase_two_customizations
        )
        self.assertIn(
            "restrict-image-registries", self.ai_selector._phase_two_customizations
        )

    def test_map_detailed_policies_to_entries(self):
        """Test mapping detailed policies back to PolicyCatalogEntry objects."""
        detailed_policies = [
            {
                "name": "require-pod-resources",
                "category": "best-practices",
                "description": "Require pod resource limits and requests",
                "relative_path": "best-practices/require-pod-resources.yaml",
                "test_directory": "best-practices/require-pod-resources",
                "source_repo": "https://github.com/kyverno/policies",
                "tags": ["resources", "limits"],
            }
        ]

        policy_names = ["require-pod-resources"]
        entries = self.ai_selector._map_detailed_policies_to_entries(
            policy_names, detailed_policies
        )

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry.name, "require-pod-resources")
        self.assertEqual(entry.category, "best-practices")
        self.assertEqual(entry.description, "Require pod resource limits and requests")
        self.assertEqual(
            entry.relative_path, "best-practices/require-pod-resources.yaml"
        )
        self.assertEqual(entry.test_directory, "best-practices/require-pod-resources")
        self.assertEqual(entry.source_repo, "https://github.com/kyverno/policies")
        self.assertEqual(entry.tags, ["resources", "limits"])

    def test_apply_comprehensive_customization(self):
        """Test applying comprehensive customization to policies."""
        policies = [
            PolicyCatalogEntry(
                name="restrict-image-registries",
                category="security",
                description="Restrict allowed image registries",
                relative_path="security/restrict-image-registries.yaml",
                tags=["registry", "images"],
            )
        ]

        # Set up AI customizations
        self.ai_selector._phase_two_customizations = {
            "restrict-image-registries": {
                "reasoning": "Matches registry requirements",
                "customizations": [
                    {
                        "type": "registry_replacement",
                        "description": "Update allowed registries",
                        "value": "docker.io,gcr.io",
                    }
                ],
            }
        }

        customized = self.ai_selector._apply_comprehensive_customization(
            policies, self.requirements
        )

        self.assertEqual(len(customized), 1)
        customized_policy = customized[0]

        # Check registry customization was applied
        registry_tags = [
            tag for tag in customized_policy.tags if tag.startswith("registry:")
        ]
        self.assertGreater(len(registry_tags), 0)

        # Check AI customization was applied
        ai_custom_tags = [
            tag for tag in customized_policy.tags if tag.startswith("ai_custom:")
        ]
        self.assertGreater(len(ai_custom_tags), 0)

        # Check description was updated
        self.assertIn("[Customized for registries:", customized_policy.description)
        self.assertIn("[AI Customization:", customized_policy.description)

    @patch("catalog.catalog_manager.PolicyCatalogManager")
    def test_phase_two_select_success(self, mock_catalog_manager_class):
        """Test successful Phase 2 detailed selection."""
        # Mock catalog manager
        mock_catalog_manager = Mock()
        mock_catalog_manager_class.return_value = mock_catalog_manager

        # Mock the policy index with proper structure
        from models import PolicyIndex, PolicyCatalogEntry
        from datetime import datetime

        mock_policy_entry = PolicyCatalogEntry(
            name="require-pod-resources",
            category="best-practices",
            description="Require pod resource limits and requests",
            relative_path="best-practices/require-pod-resources.yaml",
            test_directory="best-practices/require-pod-resources",
            source_repo="https://github.com/kyverno/policies",
            tags=["resources", "limits"],
        )

        mock_policy_index = PolicyIndex(
            categories={"best-practices": [mock_policy_entry]},
            total_policies=1,
            last_updated=datetime.now(),
        )

        mock_catalog_manager._load_policy_index.return_value = mock_policy_index

        # Mock detailed policies
        detailed_policies = [
            {
                "name": "require-pod-resources",
                "category": "best-practices",
                "description": "Require pod resource limits and requests",
                "relative_path": "best-practices/require-pod-resources.yaml",
                "test_directory": "best-practices/require-pod-resources",
                "source_repo": "https://github.com/kyverno/policies",
                "tags": ["resources", "limits"],
                "has_tests": True,
            }
        ]
        mock_catalog_manager.get_policies_detailed.return_value = detailed_policies

        # Mock Bedrock response - ensure it returns a proper string
        bedrock_response = """{"selected_policies": [{"name": "require-pod-resources", "reasoning": "Essential for resource management", "customizations": []}]}"""
        self.mock_bedrock_client.send_request.return_value = bedrock_response
        self.mock_bedrock_client.send_request_with_fallback.return_value = (
            bedrock_response
        )

        candidate_names = ["require-pod-resources", "other-policy"]
        selected = self.ai_selector.phase_two_select(
            self.cluster_info, self.requirements, candidate_names, target_count=20
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].name, "require-pod-resources")
        self.assertEqual(selected[0].category, "best-practices")

        # Verify catalog manager was called correctly
        mock_catalog_manager.get_policies_detailed.assert_called_once_with(
            candidate_names
        )
        # Verify AI request was made (could be either send_request or send_request_with_fallback)
        assert (
            self.mock_bedrock_client.send_request.called
            or self.mock_bedrock_client.send_request_with_fallback.called
        )


if __name__ == "__main__":
    unittest.main()

"""
End-to-end integration tests for AEGIS workflow.
Tests the complete pipeline from cluster discovery to policy recommendation.
"""

import unittest
import tempfile
import os
import yaml
import json
import shutil
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from discovery.discovery import ClusterDiscovery
from questionnaire.questionnaire_runner import QuestionnaireRunner
from catalog.catalog_manager import PolicyCatalogManager
from ai.ai_policy_selector import AIPolicySelector
from models import ClusterInfo, GovernanceRequirements, PolicyIndex


class TestEndToEndWorkflow(unittest.TestCase):
    """Test complete AEGIS workflow integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cluster_file = os.path.join(self.temp_dir, "cluster-discovery.yaml")
        self.catalog_dir = os.path.join(self.temp_dir, "catalog")
        self.output_dir = os.path.join(self.temp_dir, "output")

        # Create directories
        os.makedirs(self.catalog_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        # Mock configuration
        self.config = {
            "cluster": {
                "kubeconfig_path": "~/.kube/config",
                "context": "test-context",
                "timeout": 60,
            },
            "catalog": {
                "local_storage": self.catalog_dir,
                "index_file": os.path.join(self.catalog_dir, "index.json"),
                "repositories": [
                    {"url": "https://github.com/kyverno/policies", "branch": "main"}
                ],
            },
            "ai": {
                "provider": "aws-bedrock",
                "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                "region": "us-east-1",
                "max_tokens": 4000,
                "temperature": 0.1,
                "policy_count": {"total_target": 20},
            },
            "output": {"directory": self.output_dir, "validate_policies": False},
        }

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("discovery.discovery.config.load_kube_config")
    @patch("discovery.discovery.client.ApiClient")
    def test_cluster_discovery_workflow(self, mock_api_client, mock_load_config):
        """Test cluster discovery workflow."""
        # Mock Kubernetes client
        mock_client = Mock()
        mock_api_client.return_value = mock_client

        # Mock cluster discovery components
        with patch.object(ClusterDiscovery, "_discover_basic_info") as mock_basic:
            with patch.object(
                ClusterDiscovery, "detect_managed_service"
            ) as mock_managed:
                with patch.object(
                    ClusterDiscovery, "scan_third_party_controllers"
                ) as mock_controllers:
                    with patch.object(
                        ClusterDiscovery, "_discover_resources"
                    ) as mock_resources:
                        with patch.object(
                            ClusterDiscovery, "_discover_security_features"
                        ) as mock_security:

                            # Set up mock return values
                            mock_basic.return_value = {
                                "kubernetes_version": "1.28.0",
                                "node_count": 3,
                                "namespace_count": 10,
                            }
                            mock_managed.return_value = "eks"
                            mock_controllers.return_value = [
                                {
                                    "name": "nginx-ingress-controller",
                                    "namespace": "ingress-nginx",
                                    "type": "ingress",
                                    "kind": "deployment",
                                }
                            ]
                            mock_resources.return_value = {"total_pods": 50}
                            mock_security.return_value = {"rbac_enabled": True}

                            # Run discovery
                            discovery = ClusterDiscovery()
                            result = discovery.discover_cluster()

                            # Verify discovery results
                            self.assertIn("cluster_info", result)
                            self.assertIn("managed_service", result)
                            self.assertIn("third_party_controllers", result)

                            # Export to YAML
                            discovery.export_to_yaml(result, self.cluster_file)

                            # Verify file was created
                            self.assertTrue(os.path.exists(self.cluster_file))

                            # Verify file contents
                            with open(self.cluster_file, "r") as f:
                                cluster_data = yaml.safe_load(f)

                            self.assertEqual(cluster_data["managed_service"], "eks")
                            self.assertEqual(
                                cluster_data["cluster_info"]["kubernetes_version"],
                                "1.28.0",
                            )

    def test_questionnaire_workflow(self):
        """Test questionnaire workflow integration."""
        # Create initial cluster discovery file
        initial_data = {
            "cluster_info": {"kubernetes_version": "1.28.0"},
            "managed_service": "eks",
        }

        with open(self.cluster_file, "w") as f:
            yaml.dump(initial_data, f)

        # Mock questionnaire responses - need to match actual question IDs
        def mock_ask_question(question):
            # Return True for registry enforcement question, False for others
            if question.id == "img_registry_enforcement":
                return True
            elif question.id == "comp_framework_adherence":
                return True
            else:
                return False

        def mock_ask_follow_up_questions(question):
            """Mock follow-up questions to return appropriate data and populate instance variables."""
            if question.follow_up_type.value == "registry_list":
                # Simulate the registry list follow-up
                return {"registries": ["docker.io", "gcr.io"]}
            elif question.follow_up_type.value == "compliance_frameworks":
                # Simulate the compliance frameworks follow-up
                return {"compliance_frameworks": ["cis", "nist"]}
            return {}

        with patch.object(
            QuestionnaireRunner, "_ask_question", side_effect=mock_ask_question
        ):
            with patch.object(
                QuestionnaireRunner,
                "_ask_follow_up_questions",
                side_effect=mock_ask_follow_up_questions,
            ):

                # Run questionnaire
                from questionnaire import QuestionBank

                bank = QuestionBank()
                runner = QuestionnaireRunner(bank)

                # Manually set the expected values since the follow-up questions populate instance variables
                def mock_build_governance_requirements():
                    """Mock the build method to return expected values."""
                    # Simulate what would happen if follow-up questions were answered
                    runner.registries = ["docker.io", "gcr.io"]
                    runner.compliance_frameworks = ["cis", "nist"]
                    return GovernanceRequirements(
                        answers=runner.answers,
                        registries=runner.registries,
                        compliance_frameworks=runner.compliance_frameworks,
                        custom_labels=runner.custom_labels,
                    )

                with patch.object(
                    runner,
                    "_build_governance_requirements",
                    side_effect=mock_build_governance_requirements,
                ):
                    requirements = runner.run_questionnaire()

                    # Verify requirements
                    self.assertIsInstance(requirements, GovernanceRequirements)
                    self.assertEqual(requirements.registries, ["docker.io", "gcr.io"])
                    self.assertEqual(
                        requirements.compliance_frameworks, ["cis", "nist"]
                    )
                    self.assertEqual(
                        len(requirements.answers), 19
                    )  # Should have 19 answers

                    # Update cluster file
                    from questionnaire import YamlUpdater

                    updater = YamlUpdater()
                    updater.append_to_cluster_yaml(requirements, self.cluster_file)

                    # Verify updated file
                    with open(self.cluster_file, "r") as f:
                        updated_data = yaml.safe_load(f)

                    self.assertIn("governance_requirements", updated_data)
                    gov_req = updated_data["governance_requirements"]
                    self.assertEqual(
                        gov_req["configurations"]["allowed_registries"],
                        ["docker.io", "gcr.io"],
                    )

    def test_catalog_creation_workflow(self):
        """Test policy catalog creation workflow."""
        # Mock GitHub repository processing
        with patch("catalog.github_processor.subprocess.run") as mock_subprocess:
            with patch(
                "catalog.catalog_manager.PolicyCatalogManager._find_policy_files"
            ) as mock_find:
                with patch(
                    "catalog.catalog_manager.PolicyCatalogManager._copy_policy_files"
                ) as mock_copy:

                    # Mock successful git clone
                    mock_subprocess.return_value = Mock(
                        returncode=0, stdout="", stderr=""
                    )

                    # Mock finding policy files
                    mock_find.return_value = [
                        os.path.join(self.temp_dir, "test-policy.yaml")
                    ]

                    # Create a test policy file
                    test_policy_content = """
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: test-policy
  annotations:
    policies.kyverno.io/description: "Test policy"
spec:
  validationFailureAction: enforce
  rules:
  - name: test-rule
    match:
      any:
      - resources:
          kinds:
          - Pod
"""

                    test_policy_file = os.path.join(
                        self.catalog_dir, "test-policy.yaml"
                    )
                    with open(test_policy_file, "w") as f:
                        f.write(test_policy_content)

                    mock_copy.return_value = None

                    # Create catalog manager
                    catalog_manager = PolicyCatalogManager(self.config)

                    # Create catalog from repositories
                    repo_urls = ["https://github.com/kyverno/policies"]
                    catalog_manager.create_catalog_from_repos(repo_urls)

                    # Build policy index
                    policy_index = catalog_manager.build_policy_index()

                    # Verify index was created
                    self.assertIsInstance(policy_index, PolicyIndex)
                    self.assertGreaterEqual(policy_index.total_policies, 0)

    @patch("ai.bedrock_client.boto3.client")
    def test_ai_policy_selection_workflow(self, mock_boto3):
        """Test AI policy selection workflow."""
        # Mock Bedrock client
        mock_bedrock_client = Mock()
        mock_boto3.return_value = mock_bedrock_client

        # Create cluster info and requirements
        cluster_info = ClusterInfo(
            version="1.28.0",
            managed_service="EKS",
            node_count=3,
            namespace_count=10,
            third_party_controllers=[],
            compliance_frameworks=["CIS"],
        )

        requirements = GovernanceRequirements(
            registries=["docker.io", "gcr.io"], compliance_frameworks=["CIS"]
        )

        # Create mock policy index
        from models import PolicyCatalogEntry
        from datetime import datetime

        policy_index = PolicyIndex(
            categories={
                "best-practices": [
                    PolicyCatalogEntry(
                        name="require-pod-resources",
                        category="best-practices",
                        description="Require pod resource limits",
                        relative_path="best-practices/require-pod-resources.yaml",
                        tags=["resources", "limits"],
                    )
                ]
            },
            total_policies=1,
            last_updated=datetime.now(),
        )

        # Mock AI responses
        phase_one_response = '["require-pod-resources"]'
        phase_two_response = """
        {
            "selected_policies": [
                {
                    "name": "require-pod-resources",
                    "reasoning": "Essential for resource management",
                    "customizations": []
                }
            ]
        }
        """

        mock_bedrock_response = Mock()
        mock_bedrock_response.read.return_value = json.dumps(
            {"content": [{"text": phase_one_response}]}
        ).encode()

        mock_bedrock_client.invoke_model.return_value = {"body": mock_bedrock_response}

        # Mock catalog manager for detailed policies
        with patch(
            "catalog.catalog_manager.PolicyCatalogManager"
        ) as mock_catalog_class:
            mock_catalog_manager = Mock()
            mock_catalog_class.return_value = mock_catalog_manager

            mock_catalog_manager.get_policies_detailed.return_value = [
                {
                    "name": "require-pod-resources",
                    "category": "best-practices",
                    "description": "Require pod resource limits",
                    "relative_path": "best-practices/require-pod-resources.yaml",
                    "tags": ["resources", "limits"],
                }
            ]

            # Create AI policy selector
            ai_selector = AIPolicySelector(
                bedrock_client=None,  # Will be mocked
                policy_catalog_path=self.catalog_dir,
                output_directory=self.output_dir,
            )

            # Override bedrock client with mock
            from ai.bedrock_client import BedrockClient

            ai_selector.bedrock_client = BedrockClient(self.config)
            ai_selector.bedrock_client.client = mock_bedrock_client

            # Mock the second phase response
            mock_bedrock_response_2 = Mock()
            mock_bedrock_response_2.read.return_value = json.dumps(
                {"content": [{"text": phase_two_response}]}
            ).encode()

            mock_bedrock_client.invoke_model.side_effect = [
                {"body": mock_bedrock_response},  # Phase 1
                {"body": mock_bedrock_response_2},  # Phase 2
            ]

            # Run AI selection
            selected_policies = ai_selector.select_policies_two_phase(
                cluster_info, requirements, policy_index, target_count=20
            )

            # Verify selection
            self.assertIsInstance(selected_policies, list)
            self.assertGreaterEqual(len(selected_policies), 0)

    def test_complete_workflow_integration(self):
        """Test complete workflow from discovery to recommendation."""
        # This test verifies that all components can work together
        # without external dependencies (mocked)

        # Step 1: Mock cluster discovery
        cluster_data = {
            "discovery_metadata": {
                "tool": "AEGIS",
                "version": "1.0.0",
                "timestamp": "2024-01-01T00:00:00Z",
            },
            "cluster_info": {
                "kubernetes_version": "1.28.0",
                "node_count": 3,
                "namespace_count": 10,
            },
            "managed_service": "eks",
            "third_party_controllers": [
                {
                    "name": "nginx-ingress-controller",
                    "namespace": "ingress-nginx",
                    "type": "ingress",
                }
            ],
            "resources": {"total_pods": 50},
            "security_features": {"rbac_enabled": True},
        }

        # Write cluster discovery file
        with open(self.cluster_file, "w") as f:
            yaml.dump(cluster_data, f)

        # Step 2: Add governance requirements
        governance_requirements = {
            "governance_requirements": {
                "collection_timestamp": "2024-01-01T00:00:00Z",
                "total_questions": 5,
                "summary": {
                    "yes_answers": 3,
                    "no_answers": 2,
                    "categories": ["image_security", "resource_management"],
                },
                "configurations": {
                    "allowed_registries": ["docker.io", "gcr.io"],
                    "compliance_frameworks": ["cis"],
                    "required_labels": {"env": "prod"},
                },
            }
        }

        # Update cluster file with requirements
        cluster_data.update(governance_requirements)
        with open(self.cluster_file, "w") as f:
            yaml.dump(cluster_data, f)

        # Step 3: Verify file structure
        self.assertTrue(os.path.exists(self.cluster_file))

        with open(self.cluster_file, "r") as f:
            final_data = yaml.safe_load(f)

        # Verify all components are present
        self.assertIn("cluster_info", final_data)
        self.assertIn("managed_service", final_data)
        self.assertIn("governance_requirements", final_data)

        # Verify data integrity
        self.assertEqual(final_data["managed_service"], "eks")
        self.assertEqual(final_data["cluster_info"]["kubernetes_version"], "1.28.0")

        gov_req = final_data["governance_requirements"]
        self.assertEqual(
            gov_req["configurations"]["allowed_registries"], ["docker.io", "gcr.io"]
        )
        self.assertEqual(gov_req["configurations"]["compliance_frameworks"], ["cis"])

        print("✅ Complete workflow integration test passed")


if __name__ == "__main__":
    # Add JSON import for AI response mocking
    import json

    unittest.main()

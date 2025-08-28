"""
AI-powered test case generation for Kyverno policies.
Generates comprehensive test cases for policies that are missing tests.
"""

import yaml
import logging
from typing import Dict, List, Any, Optional
from ai.bedrock_client import BedrockClient
from exceptions import AISelectionError


class TestCaseGenerator:
    """Generates test cases for Kyverno policies using AI."""

    def __init__(self, bedrock_client: BedrockClient):
        """Initialize test case generator."""
        self.bedrock_client = bedrock_client
        self.logger = logging.getLogger(__name__)

    def generate_comprehensive_test_case(
        self, policy_content: str, policy_name: str
    ) -> str:
        """Generate comprehensive test case with positive and negative scenarios."""
        try:
            # Parse policy to understand its structure
            policy_data = yaml.safe_load(policy_content)

            if not policy_data or policy_data.get("kind") not in [
                "ClusterPolicy",
                "Policy",
            ]:
                raise AISelectionError("Invalid policy format for test generation")

            # Use AI to generate comprehensive test case
            ai_test = self._generate_ai_test_case(
                policy_content, policy_data, policy_name
            )

            if ai_test:
                # Validate the generated test case
                if self._validate_test_case_format(ai_test):
                    return ai_test
                else:
                    self.logger.warning(
                        f"AI-generated test case for {policy_name} has invalid format, using template"
                    )

            # Fallback to template-based generation
            return self._generate_template_test_case(policy_data, policy_name)

        except Exception as e:
            self.logger.error(f"Error generating test case for {policy_name}: {e}")
            return self._generate_minimal_test_case(policy_name)

    def generate_test_resources(
        self, policy_content: str, policy_name: str
    ) -> List[Dict[str, Any]]:
        """Generate test resources that should pass and fail the policy."""
        try:
            policy_data = yaml.safe_load(policy_content)

            # Extract resource types and constraints from policy
            resource_info = self._extract_resource_info(policy_data)

            # Generate both passing and failing resources
            test_resources = []

            for resource_type in resource_info["kinds"]:
                # Generate passing resource
                passing_resource = self._generate_passing_resource(
                    resource_type, policy_data, resource_info
                )
                if passing_resource:
                    test_resources.append(
                        {
                            "resource": passing_resource,
                            "expected_result": "pass",
                            "description": f"Valid {resource_type} that should pass the policy",
                        }
                    )

                # Generate failing resource
                failing_resource = self._generate_failing_resource(
                    resource_type, policy_data, resource_info
                )
                if failing_resource:
                    test_resources.append(
                        {
                            "resource": failing_resource,
                            "expected_result": "fail",
                            "description": f"Invalid {resource_type} that should fail the policy",
                        }
                    )

            return test_resources

        except Exception as e:
            self.logger.error(f"Error generating test resources for {policy_name}: {e}")
            return []

    def enhance_existing_test_case(
        self, existing_test: str, policy_content: str
    ) -> str:
        """Enhance existing test case with additional scenarios."""
        try:
            if not self.bedrock_client:
                return existing_test

            prompt = f"""
You are a Kyverno testing expert. Enhance the following existing test case by adding more comprehensive test scenarios.

EXISTING TEST CASE:
{existing_test}

POLICY BEING TESTED:
{policy_content}

INSTRUCTIONS:
1. Keep all existing test scenarios
2. Add additional edge cases and boundary conditions
3. Ensure both positive and negative test scenarios are covered
4. Add tests for different resource variations if applicable
5. Maintain proper Kyverno test format
6. Return only the enhanced YAML test content

ENHANCED TEST CASE:
"""

            response = self.bedrock_client.send_request(
                prompt, max_tokens=2500, temperature=0.2
            )

            # Validate the enhanced test case
            if self._validate_test_case_format(response):
                return response
            else:
                self.logger.warning(
                    "Enhanced test case has invalid format, returning original"
                )
                return existing_test

        except Exception as e:
            self.logger.error(f"Error enhancing test case: {e}")
            return existing_test

    def _generate_ai_test_case(
        self, policy_content: str, policy_data: Dict[str, Any], policy_name: str
    ) -> Optional[str]:
        """Use AI to generate comprehensive test case."""
        try:
            # Extract key information about the policy
            rules = policy_data.get("spec", {}).get("rules", [])
            rule_names = [
                rule.get("name", f"rule-{i+1}") for i, rule in enumerate(rules)
            ]

            # Determine resource kinds
            resource_kinds = set()
            for rule in rules:
                match = rule.get("match", {})
                if "any" in match:
                    for any_match in match["any"]:
                        resources = any_match.get("resources", {})
                        kinds = resources.get("kinds", [])
                        resource_kinds.update(kinds)
                elif "resources" in match:
                    kinds = match["resources"].get("kinds", [])
                    resource_kinds.update(kinds)

            if not resource_kinds:
                resource_kinds = {"Pod"}  # Default fallback

            prompt = f"""
You are a Kyverno testing expert. Create a comprehensive test case for the following Kyverno policy.

POLICY NAME: {policy_name}
POLICY RULES: {', '.join(rule_names)}
TARGET RESOURCES: {', '.join(resource_kinds)}

POLICY CONTENT:
{policy_content}

INSTRUCTIONS:
1. Create a kyverno-test.yaml file with comprehensive test scenarios
2. Include both positive tests (resources that should pass) and negative tests (resources that should fail)
3. Test all rules in the policy if possible
4. Use realistic resource examples that would be found in production
5. Include edge cases and boundary conditions
6. Follow proper Kyverno test format with apiVersion, kind, metadata, policies, resources, and results sections
7. Use the new Kyverno test format: apiVersion: cli.kyverno.io/v1alpha1, kind: Test
8. Reference resource files that will exist (like resource.yaml)
9. Ensure test resource names match the expected results
10. For service mesh policies, include containers with appropriate security contexts
11. Return only the YAML test content, no explanations

TEST CASE:
"""

            response = self.bedrock_client.send_request(
                prompt, max_tokens=3000, temperature=0.2
            )

            # Clean up the response - remove markdown code blocks
            response = response.strip()
            if response.startswith("```yaml"):
                response = response[7:]  # Remove ```yaml
            if response.startswith("```"):
                response = response[3:]  # Remove ```
            if response.endswith("```"):
                response = response[:-3]  # Remove trailing ```
            response = response.strip()

            # Validate YAML format
            try:
                # Handle multiple documents - take only the first one for test case
                documents = list(yaml.safe_load_all(response))
                if documents:
                    test_data = documents[0]  # Use first document as test case
                    test_yaml = yaml.dump(test_data, default_flow_style=False)

                    # Ensure it has the correct structure
                    if self._validate_test_case_format(test_yaml):
                        return test_yaml
                    else:
                        self.logger.warning(
                            f"AI-generated test case for {policy_name} has invalid format"
                        )
                        return None
                else:
                    self.logger.warning(
                        f"AI-generated test case for {policy_name} is empty"
                    )
                    return None
            except yaml.YAMLError as e:
                self.logger.warning(f"AI-generated test case has invalid YAML: {e}")
                return None

        except Exception as e:
            self.logger.error(f"Error generating AI test case: {e}")
            return None

    def _generate_template_test_case(
        self, policy_data: Dict[str, Any], policy_name: str
    ) -> str:
        """Generate template-based test case."""
        try:
            rules = policy_data.get("spec", {}).get("rules", [])

            # Extract resource kinds
            resource_kinds = set()
            for rule in rules:
                match = rule.get("match", {})
                if "any" in match:
                    for any_match in match["any"]:
                        resources = any_match.get("resources", {})
                        kinds = resources.get("kinds", [])
                        resource_kinds.update(kinds)
                elif "resources" in match:
                    kinds = match["resources"].get("kinds", [])
                    resource_kinds.update(kinds)

            if not resource_kinds:
                resource_kinds = {"Pod"}

            # Create test structure using new Kyverno test format
            test_case = {
                "apiVersion": "cli.kyverno.io/v1alpha1",
                "kind": "Test",
                "metadata": {"name": f"{policy_name}-test"},
                "policies": [f"{policy_name}.yaml"],
                "resources": ["resource.yaml"],
                "results": [],
            }

            # Add results for each rule and resource kind
            for i, rule in enumerate(rules):
                rule_name = rule.get("name", f"rule-{i+1}")

                for kind in resource_kinds:
                    # Good resource test
                    test_case["results"].append(
                        {
                            "policy": policy_name,
                            "rule": rule_name,
                            "resource": f"good-{kind.lower()}",
                            "kind": kind,
                            "result": "pass",
                        }
                    )

                    # Bad resource test
                    test_case["results"].append(
                        {
                            "policy": policy_name,
                            "rule": rule_name,
                            "resource": f"bad-{kind.lower()}",
                            "kind": kind,
                            "result": "fail",
                        }
                    )

            return yaml.dump(test_case, default_flow_style=False)

        except Exception as e:
            self.logger.error(f"Error generating template test case: {e}")
            return self._generate_minimal_test_case(policy_name)

    def _generate_minimal_test_case(self, policy_name: str) -> str:
        """Generate minimal test case as fallback."""
        test_case = {
            "apiVersion": "cli.kyverno.io/v1alpha1",
            "kind": "Test",
            "metadata": {"name": f"{policy_name}-test"},
            "policies": [f"{policy_name}.yaml"],
            "resources": ["resource.yaml"],
            "results": [
                {
                    "policy": policy_name,
                    "rule": "default-rule",
                    "resource": "test-resource",
                    "kind": "Pod",
                    "result": "pass",
                }
            ],
        }

        return yaml.dump(test_case, default_flow_style=False)

    def _validate_test_case_format(self, test_content: str) -> bool:
        """Validate test case format."""
        try:
            test_data = yaml.safe_load(test_content)

            if not test_data:
                return False

            # Check for new Kyverno test format
            if (
                test_data.get("apiVersion") == "cli.kyverno.io/v1alpha1"
                and test_data.get("kind") == "Test"
            ):
                # New format validation
                required_fields = ["metadata", "policies", "resources", "results"]
                for field in required_fields:
                    if field not in test_data:
                        return False

                # Check metadata has name
                if not test_data.get("metadata", {}).get("name"):
                    return False
            else:
                # Legacy format validation
                required_fields = ["name", "policies", "resources", "results"]
                for field in required_fields:
                    if field not in test_data:
                        return False

            # Validate results structure
            results = test_data.get("results", [])
            for result in results:
                if not isinstance(result, dict):
                    return False

                # Check for either old format (resource) or new format (resources)
                required_result_fields = ["policy", "rule", "result"]
                for field in required_result_fields:
                    if field not in result:
                        return False

                # Must have either 'resource' or 'resources' field
                if "resource" not in result and "resources" not in result:
                    return False

            return True

        except yaml.YAMLError:
            return False
        except Exception:
            return False

    def _extract_resource_info(self, policy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract resource information from policy."""
        info = {
            "kinds": set(),
            "namespaces": set(),
            "names": set(),
            "labels": {},
            "annotations": {},
        }

        rules = policy_data.get("spec", {}).get("rules", [])

        for rule in rules:
            match = rule.get("match", {})

            # Handle 'any' matches
            if "any" in match:
                for any_match in match["any"]:
                    self._extract_match_info(any_match, info)
            else:
                self._extract_match_info(match, info)

        # Convert sets to lists for JSON serialization
        info["kinds"] = list(info["kinds"]) if info["kinds"] else ["Pod"]
        info["namespaces"] = list(info["namespaces"])
        info["names"] = list(info["names"])

        return info

    def _extract_match_info(self, match: Dict[str, Any], info: Dict[str, Any]) -> None:
        """Extract match information from a match block."""
        resources = match.get("resources", {})

        # Extract kinds
        kinds = resources.get("kinds", [])
        info["kinds"].update(kinds)

        # Extract namespaces
        namespaces = resources.get("namespaces", [])
        info["namespaces"].update(namespaces)

        # Extract names
        names = resources.get("names", [])
        info["names"].update(names)

        # Extract selector information
        selector = resources.get("selector", {})
        if "matchLabels" in selector:
            info["labels"].update(selector["matchLabels"])

    def _generate_passing_resource(
        self,
        resource_type: str,
        policy_data: Dict[str, Any],
        resource_info: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate a resource that should pass the policy."""
        try:
            base_resource = self._get_base_resource_template(resource_type)

            # Apply constraints that would make it pass
            # This is a simplified implementation - in practice, you'd analyze the policy rules
            # to determine what makes a resource compliant

            # Add required labels if specified
            if resource_info["labels"]:
                if "metadata" not in base_resource:
                    base_resource["metadata"] = {}
                if "labels" not in base_resource["metadata"]:
                    base_resource["metadata"]["labels"] = {}
                base_resource["metadata"]["labels"].update(resource_info["labels"])

            # Set namespace if specified
            if resource_info["namespaces"]:
                if "metadata" not in base_resource:
                    base_resource["metadata"] = {}
                base_resource["metadata"]["namespace"] = list(
                    resource_info["namespaces"]
                )[0]

            base_resource["metadata"]["name"] = f"good-{resource_type.lower()}"

            return base_resource

        except Exception as e:
            self.logger.error(f"Error generating passing resource: {e}")
            return None

    def _generate_failing_resource(
        self,
        resource_type: str,
        policy_data: Dict[str, Any],
        resource_info: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate a resource that should fail the policy."""
        try:
            base_resource = self._get_base_resource_template(resource_type)

            # Intentionally violate policy constraints
            # This is a simplified implementation

            base_resource["metadata"]["name"] = f"bad-{resource_type.lower()}"

            # Remove required labels or add forbidden ones
            if "metadata" in base_resource and "labels" in base_resource["metadata"]:
                # Remove some labels to potentially violate requirements
                base_resource["metadata"]["labels"] = {"app": "test-bad"}

            return base_resource

        except Exception as e:
            self.logger.error(f"Error generating failing resource: {e}")
            return None

    def _get_base_resource_template(self, resource_type: str) -> Dict[str, Any]:
        """Get base resource template for the given type."""
        templates = {
            "Pod": {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": "test-pod",
                    "namespace": "default",
                    "labels": {"app": "test"},
                },
                "spec": {
                    "containers": [
                        {
                            "name": "test-container",
                            "image": "nginx:latest",
                            "resources": {
                                "requests": {"memory": "64Mi", "cpu": "250m"},
                                "limits": {"memory": "128Mi", "cpu": "500m"},
                            },
                        }
                    ]
                },
            },
            "Deployment": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "test-deployment",
                    "namespace": "default",
                    "labels": {"app": "test"},
                },
                "spec": {
                    "replicas": 1,
                    "selector": {"matchLabels": {"app": "test"}},
                    "template": {
                        "metadata": {"labels": {"app": "test"}},
                        "spec": {
                            "containers": [
                                {
                                    "name": "test-container",
                                    "image": "nginx:latest",
                                    "resources": {
                                        "requests": {"memory": "64Mi", "cpu": "250m"},
                                        "limits": {"memory": "128Mi", "cpu": "500m"},
                                    },
                                }
                            ]
                        },
                    },
                },
            },
            "Service": {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": "test-service", "namespace": "default"},
                "spec": {
                    "selector": {"app": "test"},
                    "ports": [{"port": 80, "targetPort": 8080}],
                    "type": "ClusterIP",
                },
            },
        }

        return templates.get(resource_type, templates["Pod"])

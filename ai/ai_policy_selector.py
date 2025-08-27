"""
AI-powered policy selection system for AEGIS.
Orchestrates policy selection, customization, and validation using AWS Bedrock.

This module implements a Two-Phase AI policy selection approach:
- Phase 1: Lightweight filtering of all policies (~370) to ~100-150 candidates
- Phase 2: Detailed selection from candidates to final ~20 policies (to be implemented)

Phase 1 uses minimal metadata (name, category, tags) to efficiently filter large policy sets
while staying within token limits and optimizing AI processing costs.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from models import (
    ClusterInfo, GovernanceRequirements, PolicyIndex, PolicyCatalogEntry,
    RecommendedPolicy, PolicyRecommendation
)
from interfaces import AIPolicySelectorInterface
from ai.bedrock_client import BedrockClient
from ai.category_determiner import CategoryDeterminer
from ai.kyverno_validator import KyvernoValidator
from ai.output_manager import OutputManager
from exceptions import AISelectionError, ValidationError


class AIPolicySelector(AIPolicySelectorInterface):
    """Main AI policy selector that orchestrates the entire selection process."""
    
    def __init__(self, bedrock_client: BedrockClient, policy_catalog_path: str = "./policy-catalog", 
                 output_directory: str = "./recommended-policies", config: Optional[Dict[str, Any]] = None):
        """Initialize AI policy selector."""
        self.bedrock_client = bedrock_client
        self.policy_catalog_path = policy_catalog_path
        self.category_determiner = CategoryDeterminer(bedrock_client)
        self.kyverno_validator = KyvernoValidator(bedrock_client)
        self.output_manager = OutputManager(output_directory)
        self.logger = logging.getLogger(__name__)
        
        # Load configuration for Two-Phase selection
        self.config = config or {}
        self.two_phase_config = self.config.get('ai', {}).get('two_phase_selection', {})
        self.phase_one_candidates = self.two_phase_config.get('phase_one_candidates', 150)
        self.phase_one_max_tokens = self.two_phase_config.get('phase_one_max_tokens', 2000)
        self.phase_one_temperature = self.two_phase_config.get('phase_one_temperature', 0.1)
        self.phase_two_max_tokens = self.two_phase_config.get('phase_two_max_tokens', 4000)
        self.phase_two_temperature = self.two_phase_config.get('phase_two_temperature', 0.1)
        
        # Initialize policy customizer
        from ai.policy_customizer import PolicyCustomizer
        self.policy_customizer = PolicyCustomizer()
    
    def select_policies_two_phase(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                                 policy_index: PolicyIndex, target_count: int = 20) -> List[PolicyCatalogEntry]:
        """Select appropriate policies using Two-Phase AI approach with comprehensive error handling."""
        try:
            self.logger.info(f"Starting Two-Phase AI policy selection for {target_count} policies")
            
            # Validate inputs
            if not policy_index.categories or policy_index.total_policies == 0:
                raise AISelectionError("Empty policy index provided")
            
            if target_count <= 0:
                raise AISelectionError(f"Invalid target count: {target_count}")
            
            # Phase 1: Lightweight filtering with retry and fallback
            max_retries = self.two_phase_config.get('retry_attempts', 3)
            candidate_policy_names = None
            
            for attempt in range(max_retries):
                try:
                    candidate_policy_names = self.phase_one_filter(cluster_info, requirements, policy_index)
                    self.logger.info(f"Phase 1 completed: {len(candidate_policy_names)} candidates selected")
                    break
                except Exception as e:
                    self.logger.warning(f"Phase 1 attempt {attempt + 1}/{max_retries} failed: {e}")
                    if attempt == max_retries - 1:
                        self.logger.warning("All Phase 1 attempts failed. Using fallback candidate selection.")
                        candidate_policy_names = self._fallback_phase_one_selection(policy_index)
                    else:
                        # Wait before retry (exponential backoff)
                        import time
                        wait_time = (2 ** attempt) + 1
                        self.logger.info(f"Retrying Phase 1 in {wait_time} seconds...")
                        time.sleep(wait_time)
            
            # Validate Phase 1 results
            if not candidate_policy_names:
                self.logger.warning("No candidates from Phase 1, using fallback selection")
                return self._fallback_policy_selection(cluster_info, requirements, policy_index, target_count)
            
            # Phase 2: Detailed selection with retry and fallback
            selected_policies = None
            
            for attempt in range(max_retries):
                try:
                    selected_policies = self.phase_two_select(cluster_info, requirements, candidate_policy_names, target_count)
                    self.logger.info(f"Phase 2 completed: {len(selected_policies)} policies selected")
                    break
                except Exception as e:
                    self.logger.warning(f"Phase 2 attempt {attempt + 1}/{max_retries} failed: {e}")
                    if attempt == max_retries - 1:
                        self.logger.warning("All Phase 2 attempts failed. Using candidate policies directly.")
                        selected_policies = self._map_policies_from_index(candidate_policy_names[:target_count], policy_index)
                    else:
                        # Wait before retry (exponential backoff)
                        import time
                        wait_time = (2 ** attempt) + 1
                        self.logger.info(f"Retrying Phase 2 in {wait_time} seconds...")
                        time.sleep(wait_time)
            
            # Ensure we have sufficient policies
            if len(selected_policies) < target_count * 0.5:  # At least 50% of target
                self.logger.warning(f"Insufficient policies selected ({len(selected_policies)}), supplementing with fallback")
                selected_policies = self._supplement_with_fallback(
                    selected_policies, policy_index, target_count, cluster_info, requirements
                )
            
            # Final validation and trimming
            final_policies = selected_policies[:target_count]
            self.logger.info(f"Two-Phase selection completed: {len(final_policies)} policies selected")
            return final_policies
            
        except Exception as e:
            self.logger.error(f"Critical error in Two-Phase AI policy selection: {e}")
            # Ultimate fallback to rule-based selection
            try:
                return self._fallback_policy_selection(cluster_info, requirements, policy_index, target_count)
            except Exception as fallback_error:
                self.logger.error(f"Fallback selection also failed: {fallback_error}")
                # Return basic policy selection as last resort
                return self._emergency_policy_selection(policy_index, target_count)

    def select_policies(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                       policy_index: PolicyIndex, target_count: int = 20) -> List[PolicyCatalogEntry]:
        """Select appropriate policies using AI analysis - orchestrates Two-Phase approach."""
        try:
            # Check if Two-Phase selection is enabled in configuration
            two_phase_enabled = self.two_phase_config.get('enabled', True)
            
            if two_phase_enabled:
                self.logger.info("Using Two-Phase AI policy selection approach")
                return self.select_policies_two_phase(cluster_info, requirements, policy_index, target_count)
            else:
                self.logger.info("Two-Phase selection disabled, using legacy single-phase approach")
                return self._legacy_single_phase_selection(cluster_info, requirements, policy_index, target_count)
                
        except Exception as e:
            self.logger.error(f"Policy selection failed: {e}")
            # Ultimate fallback to rule-based selection
            self.logger.warning("Falling back to rule-based policy selection")
            return self._fallback_policy_selection(cluster_info, requirements, policy_index, target_count)
    
    def determine_categories(self, cluster_info: ClusterInfo, selected_policies: List[PolicyCatalogEntry],
                           requirements: GovernanceRequirements) -> List[str]:
        """Dynamically determine output categories using AI."""
        return self.category_determiner.determine_categories(cluster_info, selected_policies, requirements)
    
    def customize_policies(self, policies: List[PolicyCatalogEntry], requirements: GovernanceRequirements) -> List[RecommendedPolicy]:
        """Customize policies based on governance requirements using PolicyCustomizer."""
        recommended_policies = []
        
        # Read all policy contents first
        policy_contents = {}
        for policy in policies:
            try:
                policy_content = self._read_policy_content(policy)
                policy_contents[policy.name] = policy_content
            except Exception as e:
                self.logger.error(f"Error reading policy {policy.name}: {e}")
                policy_contents[policy.name] = f"# Error reading policy content: {e}"
        
        # Use PolicyCustomizer for batch customization
        try:
            recommended_policies = self.policy_customizer.customize_policies_batch(
                policies, requirements, policy_contents
            )
            
            # Add test content for policies that have test directories
            for recommended_policy in recommended_policies:
                if recommended_policy.original_policy.test_directory and not recommended_policy.test_content:
                    try:
                        test_content = self._read_test_content(recommended_policy.original_policy)
                        recommended_policy.test_content = test_content
                    except Exception as e:
                        self.logger.warning(f"Could not read test content for {recommended_policy.original_policy.name}: {e}")
            
            self.logger.info(f"Customized {len(recommended_policies)} policies using PolicyCustomizer")
            
        except Exception as e:
            self.logger.error(f"Error in batch customization: {e}")
            # Fallback to individual customization
            for policy in policies:
                try:
                    policy_content = policy_contents.get(policy.name, "")
                    if policy_content:
                        recommended_policy = self.policy_customizer.customize_policy(policy, requirements, policy_content)
                        
                        # Add test content if available
                        if policy.test_directory and not recommended_policy.test_content:
                            try:
                                test_content = self._read_test_content(policy)
                                recommended_policy.test_content = test_content
                            except Exception as test_error:
                                self.logger.warning(f"Could not read test content for {policy.name}: {test_error}")
                        
                        recommended_policies.append(recommended_policy)
                    else:
                        # Create basic recommended policy if content reading failed
                        recommended_policies.append(RecommendedPolicy(
                            original_policy=policy,
                            customized_content="# Error reading policy content",
                            validation_status="error",
                            customizations_applied=["Error reading original policy"]
                        ))
                        
                except Exception as policy_error:
                    self.logger.error(f"Error customizing individual policy {policy.name}: {policy_error}")
                    recommended_policies.append(RecommendedPolicy(
                        original_policy=policy,
                        customized_content="# Error customizing policy",
                        validation_status="error",
                        customizations_applied=[f"Customization error: {policy_error}"]
                    ))
        
        return recommended_policies
    
    def validate_and_fix_policies(self, policies: List[RecommendedPolicy]) -> List[RecommendedPolicy]:
        """Run Kyverno tests and fix failures."""
        try:
            # Use the new KyvernoValidator for comprehensive validation
            validation_results = self.kyverno_validator.validate_batch_policies(policies)
            
            # Update policies with validation results and fixes
            validated_policies = []
            for policy, validation_result in zip(policies, validation_results):
                # Update policy status
                policy.validation_status = "passed" if validation_result.passed else "failed"
                
                # Only apply fixes to test cases, never modify policy content
                if validation_result.fixed_content and not validation_result.passed:
                    # Only fix test cases, not policies - log the issue instead
                    self.logger.warning(f"Policy {policy.original_policy.name} failed validation but policy content will not be modified")
                    policy.validation_status = "failed"
                    policy.customizations_applied.append("Validation failed - policy kept as original")
                
                # Only generate test case if missing and no test directory exists
                if not policy.test_content and not policy.original_policy.test_directory:
                    try:
                        generated_test = self.kyverno_validator.generate_test_case(policy.customized_content)
                        policy.test_content = generated_test
                        policy.customizations_applied.append("AI-generated test case added")
                        self.logger.info(f"Generated test case for {policy.original_policy.name} (no existing test found)")
                    except Exception as e:
                        self.logger.warning(f"Could not generate test case for {policy.original_policy.name}: {e}")
                elif policy.original_policy.test_directory:
                    self.logger.info(f"Using existing test case for {policy.original_policy.name}")
                
                validated_policies.append(policy)
            
            return validated_policies
            
        except Exception as e:
            self.logger.error(f"Error in validation and fixing: {e}")
            # Fallback to basic validation
            for policy in policies:
                policy.validation_status = "error"
            return policies
    
    def generate_complete_recommendation(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                                       policy_index: PolicyIndex, target_count: int = 20) -> PolicyRecommendation:
        """Generate complete policy recommendation with all steps."""
        try:
            # Step 1: Select policies using Two-Phase approach
            selected_policies = self.select_policies_two_phase(cluster_info, requirements, policy_index, target_count)
            
            # Step 2: Determine categories
            categories = self.determine_categories(cluster_info, selected_policies, requirements)
            
            # Step 3: Copy policies as-is (NO customization despite method name)
            customized_policies = self.customize_policies(selected_policies, requirements)
            
            # Step 4: Validate policies
            validated_policies = self.validate_and_fix_policies(customized_policies)
            
            # Step 5: Generate validation summary
            validation_summary = self._generate_validation_summary(validated_policies)
            
            recommendation = PolicyRecommendation(
                cluster_info=cluster_info,
                requirements=requirements,
                recommended_policies=validated_policies,
                categories=categories,
                ai_model_used=self.bedrock_client.model_id,
                validation_summary=validation_summary
            )
            
            return recommendation
            
        except Exception as e:
            self.logger.error(f"Error generating complete recommendation: {e}")
            raise AISelectionError(f"Failed to generate policy recommendation: {e}")
    
    def phase_one_filter(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                        policy_index: PolicyIndex) -> List[str]:
        """Phase 1: Filter all policies to relevant candidates using lightweight metadata."""
        try:
            self.logger.info("Starting Phase 1 lightweight policy filtering")
            
            # Get all policies with lightweight metadata from the policy index
            lightweight_policies = self._extract_lightweight_policies_from_index(policy_index)
            
            self.logger.info(f"Phase 1: Processing {len(lightweight_policies)} policies with lightweight metadata")
            
            # Prepare context for Phase 1 filtering
            context = self._prepare_phase_one_context(cluster_info, requirements, lightweight_policies)
            
            # Create Phase 1 filtering prompt
            prompt = self._create_phase_one_prompt(context)
            
            # Get AI response with optimized token usage and fallback mechanism
            fallback_enabled = self.two_phase_config.get('fallback_enabled', True)
            if fallback_enabled:
                fallback_models = self.config.get('ai', {}).get('error_handling', {}).get('fallback_models', [])
                response = self.bedrock_client.send_request_with_fallback(
                    prompt, 
                    max_tokens=self.phase_one_max_tokens, 
                    temperature=self.phase_one_temperature,
                    fallback_models=fallback_models
                )
            else:
                response = self.bedrock_client.send_request(
                    prompt, 
                    max_tokens=self.phase_one_max_tokens, 
                    temperature=self.phase_one_temperature
                )
            
            # Parse candidate policy names from response
            candidate_policy_names = self._parse_phase_one_response(response)
            
            self.logger.info(f"Phase 1: Filtered to {len(candidate_policy_names)} candidate policies")
            return candidate_policy_names
            
        except Exception as e:
            self.logger.error(f"Error in Phase 1 filtering: {e}")
            # Fallback to sampling policies from all categories
            return self._fallback_phase_one_selection(policy_index)

    def phase_two_select(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                        candidate_policy_names: List[str], target_count: int = 20) -> List[PolicyCatalogEntry]:
        """Phase 2: Make final selection from candidates using full metadata."""
        try:
            self.logger.info(f"Starting Phase 2 detailed policy selection from {len(candidate_policy_names)} candidates")
            
            # Get detailed policy information for candidates
            from catalog.catalog_manager import PolicyCatalogManager
            catalog_manager = PolicyCatalogManager(self.config)
            detailed_policies = catalog_manager.get_policies_detailed(candidate_policy_names)
            
            self.logger.info(f"Phase 2: Retrieved detailed information for {len(detailed_policies)} candidate policies")
            
            # Prepare context for Phase 2 selection
            context = self._prepare_phase_two_context(cluster_info, requirements, detailed_policies)
            
            # Create Phase 2 selection prompt
            prompt = self._create_phase_two_prompt(context, target_count)
            
            # Get AI response with higher token limit for detailed analysis
            phase_two_max_tokens = self.two_phase_config.get('phase_two_max_tokens', 4000)
            phase_two_temperature = self.two_phase_config.get('phase_two_temperature', 0.1)
            
            # Use fallback mechanism for better reliability
            fallback_enabled = self.two_phase_config.get('fallback_enabled', True)
            if fallback_enabled:
                fallback_models = self.config.get('ai', {}).get('error_handling', {}).get('fallback_models', [])
                response = self.bedrock_client.send_request_with_fallback(
                    prompt, 
                    max_tokens=phase_two_max_tokens, 
                    temperature=phase_two_temperature,
                    fallback_models=fallback_models
                )
            else:
                response = self.bedrock_client.send_request(
                    prompt, 
                    max_tokens=phase_two_max_tokens, 
                    temperature=phase_two_temperature
                )
            
            # Parse final policy selection from response
            final_policy_names = self._parse_phase_two_response(response)
            
            # Map selected policy names back to PolicyCatalogEntry objects
            selected_policies = self._map_detailed_policies_to_entries(final_policy_names, detailed_policies)
            
            # Apply comprehensive policy customization
            customized_policies = self._apply_comprehensive_customization(selected_policies, requirements)
            
            self.logger.info(f"Phase 2: Selected and customized {len(customized_policies)} final policies")
            return customized_policies
            
        except Exception as e:
            self.logger.error(f"Error in Phase 2 selection: {e}")
            # Fallback to mapping candidate names directly
            from catalog.catalog_manager import PolicyCatalogManager
            catalog_manager = PolicyCatalogManager(self.config)
            policy_index = catalog_manager._load_policy_index()
            return self._map_policies_from_index(candidate_policy_names[:target_count], policy_index)

    def generate_organized_output(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                                policy_index: PolicyIndex, target_count: int = 20) -> Dict[str, Any]:
        """Generate complete policy recommendation with organized output files."""
        try:
            # Generate the recommendation
            recommendation = self.generate_complete_recommendation(
                cluster_info, requirements, policy_index, target_count
            )
            
            # Get validation results for output organization
            validation_results = self.kyverno_validator.validate_batch_policies(recommendation.recommended_policies)
            
            # Organize policies into directory structure
            created_files = self.output_manager.organize_policies_by_categories(
                recommendation, validation_results
            )
            
            # Create deployment guide
            deployment_guide = self.output_manager.create_deployment_guide(
                recommendation, validation_results
            )
            
            # Generate comprehensive validation report
            validation_report = self.output_manager.generate_validation_report(validation_results)
            
            return {
                "recommendation": recommendation,
                "validation_results": validation_results,
                "created_files": created_files,
                "deployment_guide": deployment_guide,
                "validation_report": validation_report,
                "output_directory": self.output_manager.output_directory
            }
            
        except Exception as e:
            self.logger.error(f"Error generating organized output: {e}")
            raise AISelectionError(f"Failed to generate organized output: {e}")
    
    def _prepare_selection_context(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                                 policy_index: PolicyIndex) -> Dict[str, Any]:
        """Prepare context for AI policy selection."""
        # Sample policies for AI analysis (to avoid token limits)
        # Use configuration if available, otherwise default to 50
        max_policies = 50  # Default fallback
        sampled_policies = self._sample_policies_for_ai(policy_index, max_policies=max_policies)
        
        context = {
            "cluster": {
                "version": cluster_info.version,
                "managed_service": cluster_info.managed_service,
                "node_count": cluster_info.node_count,
                "namespace_count": cluster_info.namespace_count,
                "third_party_controllers": [
                    {"name": ctrl.name, "type": ctrl.type.value}
                    for ctrl in cluster_info.third_party_controllers
                ],
                "compliance_frameworks": cluster_info.compliance_frameworks
            },
            "requirements": {
                "compliance_frameworks": requirements.compliance_frameworks,
                "registries": requirements.registries,
                "answered_yes": [
                    answer.question_id for answer in requirements.answers if answer.answer
                ]
            },
            "available_policies": sampled_policies
        }
        
        return context
    
    def _create_selection_prompt(self, context: Dict[str, Any], target_count: int) -> str:
        """Create AI prompt for policy selection."""
        prompt = f"""
You are an expert Kubernetes governance consultant. Based on the cluster information and governance requirements, select the most appropriate {target_count} policies from the available policy catalog.

CLUSTER INFORMATION:
- Kubernetes Version: {context['cluster']['version']}
- Managed Service: {context['cluster']['managed_service']}
- Node Count: {context['cluster']['node_count']}
- Third-party Controllers: {[ctrl['name'] + ' (' + ctrl['type'] + ')' for ctrl in context['cluster']['third_party_controllers']]}
- Compliance Frameworks: {context['cluster']['compliance_frameworks']}

GOVERNANCE REQUIREMENTS ANALYSIS:
- Compliance Frameworks: {context['requirements']['compliance_frameworks']}
- Allowed Registries: {context['requirements']['registries']}
- Requirements Answered Yes: {context['requirements']['answered_yes']}

MANDATORY POLICY REQUIREMENTS (based on "yes" answers):
1. If 'img_registry_enforcement' in requirements: MUST include 'restrict-image-registries' or 'advanced-restrict-image-registries'
2. If 'img_latest_tag_prevention' in requirements: MUST include 'disallow-latest-tag'
3. If 'img_vulnerability_scanning' in requirements: MUST include 'block-stale-images' or 'require-image-checksum'
4. If 'res_limits_required' or 'res_requests_required' in requirements: MUST include 'require-pod-requests-limits'
5. If 'sec_non_root_required' in requirements: MUST include 'require-non-root-groups' or 'require-run-as-nonroot'
6. If 'sec_privileged_prevention' in requirements: MUST include 'deny-privileged-profile' or 'prevent-cr8escape'
7. If 'sec_capabilities_restriction' in requirements: MUST include 'require-drop-all' or 'restrict-adding-capabilities'
8. If 'sec_readonly_filesystem' in requirements: MUST include 'require-ro-rootfs'
9. If 'net_policies_required' in requirements: MUST include 'require-netpol'
10. If 'comp_labeling_standards' in requirements: MUST include 'require-labels' or 'require-annotations'
11. If 'comp_pod_disruption_budgets' in requirements: MUST include 'require-pdb'

AVAILABLE POLICIES:
{json.dumps(context['available_policies'], indent=2)}

SELECTION CRITERIA:
1. FIRST: Include ALL mandatory policies based on governance requirements above
2. SECOND: Include essential best practices: 'require-probes', 'restrict-automount-sa-token', 'disallow-default-namespace'
3. THIRD: Add policies relevant to detected third-party controllers (Grafana, Prometheus, Jaeger, OpenTelemetry, Ingress-Nginx, OpenSearch)
4. FOURTH: Fill remaining slots with compliance-focused policies for CIS, NIST, ISO27001
5. Focus on policies that enhance security posture and operational reliability
6. Include both standard Kyverno and CEL policies as appropriate

INSTRUCTIONS:
1. Analyze the governance requirements and identify mandatory policies
2. Select exactly {target_count} policies ensuring all mandatory requirements are covered
3. Prioritize policies that directly address the "yes" answers in governance requirements
4. Return ONLY a JSON array of policy names, nothing else

Example response format:
["policy-name-1", "policy-name-2", "policy-name-3", ...]
"""
        return prompt
    
    def _parse_selection_response(self, response: str) -> List[str]:
        """Parse selected policy names from AI response."""
        try:
            response = response.strip()
            
            # Try to extract JSON array
            if response.startswith('[') and response.endswith(']'):
                policy_names = json.loads(response)
            else:
                # Try to find JSON array in response
                import re
                json_match = re.search(r'\[.*?\]', response, re.DOTALL)
                if json_match:
                    policy_names = json.loads(json_match.group())
                else:
                    # Fallback: extract policy names from text
                    lines = response.split('\n')
                    policy_names = []
                    for line in lines:
                        line = line.strip().strip('"').strip("'").strip('-').strip()
                        if line and len(line) > 2 and not line.startswith('[') and not line.startswith(']'):
                            policy_names.append(line)
            
            # Validate and clean policy names
            cleaned_names = []
            for name in policy_names:
                if isinstance(name, str) and len(name.strip()) > 0:
                    cleaned_names.append(name.strip())
            
            return cleaned_names
            
        except Exception as e:
            self.logger.error(f"Error parsing selection response: {e}")
            raise AISelectionError(f"Failed to parse policy selection from AI response: {e}")
    
    def _map_policies_from_index(self, policy_names: List[str], policy_index: PolicyIndex) -> List[PolicyCatalogEntry]:
        """Map policy names to PolicyCatalogEntry objects from index."""
        selected_policies = []
        
        # Create a lookup map for all policies
        policy_lookup = {}
        for category_policies in policy_index.categories.values():
            for policy in category_policies:
                policy_lookup[policy.name] = policy
        
        # Map selected names to policies
        for name in policy_names:
            if name in policy_lookup:
                selected_policies.append(policy_lookup[name])
            else:
                self.logger.warning(f"Policy '{name}' not found in index")
        
        return selected_policies
    
    def _sample_policies_for_ai(self, policy_index: PolicyIndex, max_policies: int = 50) -> List[Dict[str, Any]]:
        """Sample policies from index for AI analysis - include both normal and CEL policies."""
        sampled_policies = []
        
        # Get top policies from each category, including both normal and CEL policies
        policies_per_category = max(1, max_policies // len(policy_index.categories))
        
        for category, policies in policy_index.categories.items():
            # Sort all policies by name for consistent ordering (no CEL filtering)
            sorted_policies = sorted(policies, key=lambda p: p.name.lower())
            category_sample = sorted_policies[:policies_per_category]
            
            for policy in category_sample:
                sampled_policies.append({
                    "name": policy.name,
                    "category": policy.category,
                    "description": policy.description[:300],  # Truncate for token efficiency
                    "tags": policy.tags,
                    "is_cel": '-cel' in policy.category.lower()
                })
        
        return sampled_policies[:max_policies]
    
    def _supplement_with_fallback(self, selected_policies: List[PolicyCatalogEntry], 
                                policy_index: PolicyIndex, target_count: int,
                                cluster_info: ClusterInfo, requirements: GovernanceRequirements) -> List[PolicyCatalogEntry]:
        """Supplement AI selection with fallback policies."""
        current_names = {p.name for p in selected_policies}
        needed_count = target_count - len(selected_policies)
        
        # Get additional policies using rule-based selection
        fallback_policies = self._fallback_policy_selection(
            cluster_info, requirements, policy_index, needed_count
        )
        
        # Add policies that aren't already selected
        for policy in fallback_policies:
            if policy.name not in current_names and len(selected_policies) < target_count:
                selected_policies.append(policy)
                current_names.add(policy.name)
        
        return selected_policies
    
    def _fallback_policy_selection(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                                 policy_index: PolicyIndex, target_count: int) -> List[PolicyCatalogEntry]:
        """Rule-based fallback policy selection based on governance requirements."""
        selected_policies = []
        
        # Create a lookup map for all policies
        policy_lookup = {}
        for category_policies in policy_index.categories.values():
            for policy in category_policies:
                policy_lookup[policy.name] = policy
        
        # Essential policies based on governance requirements
        essential_policies = []
        
        # Image security requirements
        if any(answer.question_id == 'img_registry_enforcement' and answer.answer for answer in requirements.answers):
            essential_policies.extend(['restrict-image-registries', 'advanced-restrict-image-registries'])
        
        if any(answer.question_id == 'img_latest_tag_prevention' and answer.answer for answer in requirements.answers):
            essential_policies.append('disallow-latest-tag')
        
        if any(answer.question_id == 'img_vulnerability_scanning' and answer.answer for answer in requirements.answers):
            essential_policies.extend(['block-stale-images', 'require-image-checksum'])
        
        # Resource management requirements
        if any(answer.question_id == 'res_limits_required' and answer.answer for answer in requirements.answers):
            essential_policies.append('require-pod-requests-limits')
        
        if any(answer.question_id == 'res_requests_required' and answer.answer for answer in requirements.answers):
            essential_policies.append('require-pod-requests-limits')
        
        # Security context requirements
        if any(answer.question_id == 'sec_non_root_required' and answer.answer for answer in requirements.answers):
            essential_policies.extend(['require-non-root-groups', 'require-run-as-nonroot'])
        
        if any(answer.question_id == 'sec_privileged_prevention' and answer.answer for answer in requirements.answers):
            essential_policies.extend(['deny-privileged-profile', 'prevent-cr8escape'])
        
        if any(answer.question_id == 'sec_capabilities_restriction' and answer.answer for answer in requirements.answers):
            essential_policies.extend(['require-drop-all', 'restrict-adding-capabilities'])
        
        if any(answer.question_id == 'sec_readonly_filesystem' and answer.answer for answer in requirements.answers):
            essential_policies.append('require-ro-rootfs')
        
        # Network security requirements
        if any(answer.question_id == 'net_policies_required' and answer.answer for answer in requirements.answers):
            essential_policies.append('require-netpol')
        
        if any(answer.question_id == 'net_ingress_restrictions' and answer.answer for answer in requirements.answers):
            essential_policies.extend(['require-ingress-https', 'restrict-ingress-wildcard'])
        
        # Compliance requirements
        if any(answer.question_id == 'comp_labeling_standards' and answer.answer for answer in requirements.answers):
            essential_policies.extend(['require-labels', 'require-annotations'])
        
        if any(answer.question_id == 'comp_pod_disruption_budgets' and answer.answer for answer in requirements.answers):
            essential_policies.append('require-pdb')
        
        # Add essential policies first
        for policy_name in essential_policies:
            if policy_name in policy_lookup and len(selected_policies) < target_count:
                selected_policies.append(policy_lookup[policy_name])
        
        # Add best practice policies to fill remaining slots
        if len(selected_policies) < target_count:
            best_practice_policies = ['require-probes', 'restrict-automount-sa-token', 'disallow-default-namespace',
                                    'restrict-node-port', 'imagepullpolicy-always', 'require-qos-burstable']
            
            for policy_name in best_practice_policies:
                if policy_name in policy_lookup and len(selected_policies) < target_count:
                    if not any(p.name == policy_name for p in selected_policies):
                        selected_policies.append(policy_lookup[policy_name])
        
        # Fill remaining slots from priority categories
        if len(selected_policies) < target_count:
            priority_categories = ["best-practices", "pod-security", "other"]
            remaining_needed = target_count - len(selected_policies)
            
            for category in priority_categories:
                if category in policy_index.categories and remaining_needed > 0:
                    category_policies = policy_index.categories[category]
                    for policy in category_policies:
                        if not any(p.name == policy.name for p in selected_policies) and remaining_needed > 0:
                            selected_policies.append(policy)
                            remaining_needed -= 1
        
        return selected_policies[:target_count]
    
    def _read_policy_content(self, policy: PolicyCatalogEntry) -> str:
        """Read policy content from file."""
        import os
        policy_path = os.path.join(self.policy_catalog_path, policy.relative_path)
        
        try:
            with open(policy_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Error reading policy file {policy_path}: {e}")
            return f"# Error reading policy {policy.name}\n# {e}"
    
    def _read_test_content(self, policy: PolicyCatalogEntry) -> Optional[str]:
        """Read test content from directory."""
        if not policy.test_directory:
            return None
        
        import os
        test_path = os.path.join(self.policy_catalog_path, policy.test_directory)
        
        try:
            if os.path.isdir(test_path):
                # Find test files in directory, prioritize kyverno-test.yaml
                test_files = [f for f in os.listdir(test_path) if f.endswith(('.yaml', '.yml'))]
                
                # Prioritize specific test file names
                priority_files = ['kyverno-test.yaml', 'test.yaml', 'kyverno-test.yml', 'test.yml']
                selected_file = None
                
                for priority_file in priority_files:
                    if priority_file in test_files:
                        selected_file = priority_file
                        break
                
                if not selected_file and test_files:
                    selected_file = test_files[0]
                
                if selected_file:
                    test_file_path = os.path.join(test_path, selected_file)
                    with open(test_file_path, 'r', encoding='utf-8') as f:
                        return f.read()
            return None
        except Exception as e:
            self.logger.error(f"Error reading test content for {policy.name}: {e}")
            return None
    
    def _prepare_phase_one_context(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                                  lightweight_policies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare context for Phase 1 AI filtering with lightweight metadata."""
        context = {
            "cluster": {
                "version": cluster_info.version,
                "managed_service": cluster_info.managed_service,
                "node_count": cluster_info.node_count,
                "namespace_count": cluster_info.namespace_count,
                "third_party_controllers": [
                    {"name": ctrl.name, "type": ctrl.type.value}
                    for ctrl in cluster_info.third_party_controllers
                ],
                "compliance_frameworks": cluster_info.compliance_frameworks
            },
            "requirements": {
                "compliance_frameworks": requirements.compliance_frameworks,
                "registries": requirements.registries,
                "answered_yes": [
                    answer.question_id for answer in requirements.answers if answer.answer
                ]
            },
            "total_policies": len(lightweight_policies),
            "policies_by_category": self._group_policies_by_category(lightweight_policies)
        }
        
        return context
    
    def _create_phase_one_prompt(self, context: Dict[str, Any]) -> str:
        """Create AI prompt for Phase 1 lightweight filtering."""
        prompt = f"""
You are an expert Kubernetes governance consultant performing Phase 1 policy filtering. Your task is to filter a large set of policies ({context['total_policies']} total) down to approximately 100-150 relevant candidates based on cluster characteristics and governance requirements.

CLUSTER INFORMATION:
- Kubernetes Version: {context['cluster']['version']}
- Managed Service: {context['cluster']['managed_service']}
- Node Count: {context['cluster']['node_count']}
- Third-party Controllers: {[ctrl['name'] + ' (' + ctrl['type'] + ')' for ctrl in context['cluster']['third_party_controllers']]}
- Compliance Frameworks: {context['cluster']['compliance_frameworks']}

GOVERNANCE REQUIREMENTS:
- Compliance Frameworks: {context['requirements']['compliance_frameworks']}
- Allowed Registries: {context['requirements']['registries']}
- Requirements Answered Yes: {context['requirements']['answered_yes']}

AVAILABLE POLICIES BY CATEGORY:
{json.dumps(context['policies_by_category'], indent=2)}

PHASE 1 FILTERING CRITERIA:
1. Focus on policies relevant to the cluster environment (managed service, controllers, etc.)
2. Prioritize policies that address the specific governance requirements
3. Include essential security policies based on answered "yes" requirements
4. Consider compliance framework requirements (CIS, NIST, ISO27001)
5. Include policies for registry enforcement if registries are specified
6. Include policies for resource management, security contexts, and network security
7. Aim for approximately {self.phase_one_candidates} candidate policies
8. Ensure good coverage across different policy categories
9. Include policies for different resource types (pods, services, ingress, etc.)
10. Include both standard Kyverno and CEL policies as appropriate

INSTRUCTIONS:
1. Analyze the cluster characteristics and requirements
2. For each category, select the most relevant policies based on:
   - Cluster environment compatibility
   - Governance requirement alignment
   - Security best practices
   - Compliance framework needs
3. Return ONLY a JSON array of policy names for the filtered candidates
4. Target approximately {self.phase_one_candidates} policy names in your response

Example response format:
["policy-name-1", "policy-name-2", "policy-name-3", ...]
"""
        return prompt
    
    def _group_policies_by_category(self, lightweight_policies: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group lightweight policies by category for efficient processing."""
        grouped = {}
        for policy in lightweight_policies:
            category = policy['category']
            if category not in grouped:
                grouped[category] = []
            grouped[category].append({
                'name': policy['name'],
                'tags': policy['tags'][:3]  # Limit tags for token efficiency
            })
        return grouped
    
    def _parse_phase_one_response(self, response: str) -> List[str]:
        """Parse candidate policy names from Phase 1 AI response."""
        try:
            response = response.strip()
            
            # Try to extract JSON array
            if response.startswith('[') and response.endswith(']'):
                policy_names = json.loads(response)
            else:
                # Try to find JSON array in response - improved regex
                import re
                # Look for JSON array with better pattern matching
                json_match = re.search(r'\[\s*"[^"]+"\s*(?:,\s*"[^"]+"\s*)*\]', response, re.DOTALL)
                if json_match:
                    policy_names = json.loads(json_match.group())
                else:
                    # More aggressive fallback: extract policy names from text
                    self.logger.warning("Could not find valid JSON array, extracting policy names from text")
                    
                    # Try multiple extraction methods
                    policy_names = []
                    
                    # Method 1: Look for quoted strings that look like policy names
                    import re
                    quoted_matches = re.findall(r'"([a-z0-9-]+)"', response)
                    for match in quoted_matches:
                        if '-' in match and 3 < len(match) < 100:
                            policy_names.append(match)
                    
                    # Method 2: If not enough, try line-by-line extraction
                    if len(policy_names) < 20:
                        lines = response.split('\n')
                        for line in lines:
                            line = line.strip().strip('"').strip("'").strip('-').strip().strip(',').strip()
                            # Look for policy-like names (contain hyphens, reasonable length)
                            if (line and 3 < len(line) < 100 and '-' in line and 
                                not line.startswith('[') and not line.startswith(']') and
                                not line.startswith('{') and not line.startswith('}') and
                                not line.lower().startswith('based on') and
                                not line.lower().startswith('here') and
                                not '```' in line and
                                not line.lower().startswith('json') and
                                not line.lower().startswith('the ') and
                                not line.lower().startswith('i ') and
                                not line.lower().startswith('this ')):
                                policy_names.append(line)
            
            # Validate and clean policy names
            cleaned_names = []
            for name in policy_names:
                if isinstance(name, str) and len(name.strip()) > 0:
                    clean_name = name.strip().strip('"').strip("'").strip(',')
                    # Additional validation for policy names
                    if (len(clean_name) > 3 and '-' in clean_name and 
                        not clean_name.startswith('```') and
                        not clean_name.lower().startswith('based on')):
                        cleaned_names.append(clean_name)
            
            self.logger.info(f"Parsed {len(cleaned_names)} policy names from Phase 1 response")
            return cleaned_names[:self.phase_one_candidates]  # Limit to target count
            
        except Exception as e:
            self.logger.error(f"Error parsing Phase 1 response: {e}")
            # Return fallback selection instead of raising error
            self.logger.warning("Using fallback Phase 1 selection due to parsing error")
            return []
    
    def _extract_lightweight_policies_from_index(self, policy_index: PolicyIndex) -> List[Dict[str, Any]]:
        """Extract lightweight policy metadata from policy index."""
        lightweight_policies = []
        
        for category, policies in policy_index.categories.items():
            for policy in policies:
                lightweight_policies.append({
                    'name': policy.name,
                    'category': policy.category,
                    'tags': policy.tags[:5]  # Limit tags for lightweight processing
                })
        
        return lightweight_policies

    def _fallback_phase_one_selection(self, policy_index: PolicyIndex) -> List[str]:
        """Fallback Phase 1 selection using rule-based approach."""
        self.logger.info("Using fallback Phase 1 selection")
        
        candidate_names = []
        target_candidates = self.phase_one_candidates  # Use configured target
        
        # Distribute evenly across categories, including both normal and CEL policies
        policies_per_category = max(1, target_candidates // len(policy_index.categories))
        
        for category, policies in policy_index.categories.items():
            if policies:
                # Sort all policies by name for consistency (no CEL filtering)
                sorted_policies = sorted(policies, key=lambda p: p.name.lower())
                category_candidates = sorted_policies[:policies_per_category]
                candidate_names.extend([p.name for p in category_candidates])
            
            if len(candidate_names) >= target_candidates:
                break
        
        final_candidates = candidate_names[:target_candidates]
        self.logger.info(f"Fallback selection: {len(final_candidates)} total candidates")
        
        return final_candidates

    def _generate_validation_summary(self, policies: List[RecommendedPolicy]) -> Dict[str, int]:
        """Generate validation summary statistics."""
        summary = {
            "total": len(policies),
            "passed": 0,
            "failed": 0,
            "error": 0,
            "pending": 0
        }
        
        for policy in policies:
            if policy.validation_status in summary:
                summary[policy.validation_status] += 1
        
        return summary

    def _prepare_phase_two_context(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                                  detailed_policies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare context for Phase 2 AI selection with detailed metadata."""
        context = {
            "cluster": {
                "version": cluster_info.version,
                "managed_service": cluster_info.managed_service,
                "node_count": cluster_info.node_count,
                "namespace_count": cluster_info.namespace_count,
                "third_party_controllers": [
                    {"name": ctrl.name, "type": ctrl.type.value}
                    for ctrl in cluster_info.third_party_controllers
                ],
                "compliance_frameworks": cluster_info.compliance_frameworks,
                "security_features": cluster_info.security_features
            },
            "requirements": {
                "compliance_frameworks": requirements.compliance_frameworks,
                "registries": requirements.registries,
                "custom_labels": requirements.custom_labels,
                "answered_yes": [
                    answer.question_id for answer in requirements.answers if answer.answer
                ]
            },
            "candidate_policies": detailed_policies,
            "total_candidates": len(detailed_policies)
        }
        
        return context

    def _create_phase_two_prompt(self, context: Dict[str, Any], target_count: int) -> str:
        """Create AI prompt for Phase 2 detailed selection."""
        prompt = f"""
You are an expert Kubernetes governance consultant performing Phase 2 policy selection. Your task is to make the final selection of exactly {target_count} policies from {context['total_candidates']} pre-filtered candidates based on detailed analysis of cluster characteristics and governance requirements.

CLUSTER INFORMATION:
- Kubernetes Version: {context['cluster']['version']}
- Managed Service: {context['cluster']['managed_service']}
- Node Count: {context['cluster']['node_count']}
- Namespace Count: {context['cluster']['namespace_count']}
- Third-party Controllers: {[ctrl['name'] + ' (' + ctrl['type'] + ')' for ctrl in context['cluster']['third_party_controllers']]}
- Compliance Frameworks: {context['cluster']['compliance_frameworks']}
- Security Features: {context['cluster']['security_features']}

GOVERNANCE REQUIREMENTS:
- Compliance Frameworks: {context['requirements']['compliance_frameworks']}
- Allowed Registries: {context['requirements']['registries']}
- Custom Labels: {context['requirements']['custom_labels']}
- Requirements Answered Yes: {context['requirements']['answered_yes']}

CANDIDATE POLICIES (Pre-filtered from Phase 1):
{json.dumps(context['candidate_policies'], indent=2)}

SELECTION CRITERIA FOR PHASE 2:
1. **Compliance Priority**: Prioritize policies that directly address required compliance frameworks
2. **Security Coverage**: Ensure comprehensive security coverage across different resource types
3. **Operational Impact**: Balance security with operational efficiency and developer experience
4. **Environment Fit**: Consider cluster environment (managed service, controllers, scale)
5. **Policy Quality**: Prefer policies with comprehensive descriptions and test coverage
6. **Best Practices**: Include at least 8-10 fundamental best practice policies
7. **Resource Coverage**: Ensure coverage for pods, services, ingress, RBAC, and storage
8. **Registry Enforcement**: Include registry policies if registries are specified
9. **Controller Integration**: Include policies relevant to detected third-party controllers
10. **Avoid Redundancy**: Select complementary policies that don't overlap in functionality

CUSTOMIZATION REQUIREMENTS:
For each selected policy, identify specific customizations needed:
- Registry replacements (if registries specified)
- Label additions/modifications (if custom labels specified)
- Parameter adjustments based on cluster characteristics
- Compliance-specific configurations

INSTRUCTIONS:
1. Analyze each candidate policy's description, category, and tags
2. Consider the cluster environment and specific requirements
3. Select exactly {target_count} policies that provide optimal governance coverage
4. Ensure good distribution across categories (security, best-practices, compliance, etc.)
5. For each selected policy, provide reasoning and any needed customizations

RESPONSE FORMAT:
Return a JSON object with the following structure:
{{
    "selected_policies": [
        {{
            "name": "policy-name",
            "reasoning": "Why this policy was selected and how it fits the requirements",
            "customizations": [
                {{
                    "type": "registry_replacement|label_addition|parameter_adjustment",
                    "description": "What customization is needed",
                    "value": "specific value or configuration"
                }}
            ]
        }}
    ]
}}

Ensure exactly {target_count} policies are selected with clear reasoning for each.
"""
        return prompt

    def _parse_phase_two_response(self, response: str) -> List[str]:
        """Parse final policy selection from Phase 2 AI response."""
        try:
            response = response.strip()
            
            # Try to extract JSON object
            if response.startswith('{') and response.endswith('}'):
                selection_data = json.loads(response)
            else:
                # Try to find JSON object in response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    selection_data = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found in response")
            
            # Extract policy names from the structured response
            selected_policies = selection_data.get('selected_policies', [])
            policy_names = []
            
            for policy_data in selected_policies:
                if isinstance(policy_data, dict) and 'name' in policy_data:
                    policy_names.append(policy_data['name'])
                    # Store customization info for later use
                    if hasattr(self, '_phase_two_customizations'):
                        self._phase_two_customizations[policy_data['name']] = {
                            'reasoning': policy_data.get('reasoning', ''),
                            'customizations': policy_data.get('customizations', [])
                        }
                    else:
                        self._phase_two_customizations = {
                            policy_data['name']: {
                                'reasoning': policy_data.get('reasoning', ''),
                                'customizations': policy_data.get('customizations', [])
                            }
                        }
            
            return policy_names
            
        except Exception as e:
            self.logger.error(f"Error parsing Phase 2 response: {e}")
            # Fallback: try to extract policy names from text
            lines = response.split('\n')
            policy_names = []
            for line in lines:
                line = line.strip().strip('"').strip("'").strip('-').strip()
                if line and len(line) > 2 and not line.startswith('{') and not line.startswith('}'):
                    # Simple heuristic: if line looks like a policy name
                    if '-' in line and len(line.split('-')) >= 2:
                        policy_names.append(line)
            
            return policy_names[:20]  # Limit to reasonable number

    def _map_detailed_policies_to_entries(self, policy_names: List[str], 
                                        detailed_policies: List[Dict[str, Any]]) -> List[PolicyCatalogEntry]:
        """Map selected policy names back to PolicyCatalogEntry objects."""
        selected_entries = []
        
        # Create lookup map
        policy_lookup = {policy['name']: policy for policy in detailed_policies}
        
        for name in policy_names:
            if name in policy_lookup:
                policy_data = policy_lookup[name]
                entry = PolicyCatalogEntry(
                    name=policy_data['name'],
                    category=policy_data['category'],
                    description=policy_data['description'],
                    relative_path=policy_data['relative_path'],
                    test_directory=policy_data.get('test_directory'),
                    source_repo=policy_data['source_repo'],
                    tags=policy_data['tags']
                )
                selected_entries.append(entry)
            else:
                self.logger.warning(f"Policy '{name}' not found in detailed policies")
        
        return selected_entries

    def _apply_comprehensive_customization(self, policies: List[PolicyCatalogEntry], 
                                         requirements: GovernanceRequirements) -> List[PolicyCatalogEntry]:
        """Apply comprehensive policy customization based on cluster requirements."""
        try:
            self.logger.info(f"Applying comprehensive customization to {len(policies)} policies")
            
            customized_policies = []
            
            for policy in policies:
                # Create a copy of the policy for customization
                customized_policy = PolicyCatalogEntry(
                    name=policy.name,
                    category=policy.category,
                    description=policy.description,
                    relative_path=policy.relative_path,
                    test_directory=policy.test_directory,
                    source_repo=policy.source_repo,
                    tags=policy.tags.copy()
                )
                
                # Apply registry customizations
                if requirements.registries:
                    customized_policy = self._apply_registry_customization(customized_policy, requirements.registries)
                
                # Apply label customizations
                if requirements.custom_labels:
                    customized_policy = self._apply_label_customization(customized_policy, requirements.custom_labels)
                
                # Apply compliance-specific customizations
                if requirements.compliance_frameworks:
                    customized_policy = self._apply_compliance_customization(customized_policy, requirements.compliance_frameworks)
                
                # Add AI-suggested customizations if available
                if hasattr(self, '_phase_two_customizations') and policy.name in self._phase_two_customizations:
                    customized_policy = self._apply_ai_suggested_customizations(
                        customized_policy, 
                        self._phase_two_customizations[policy.name]['customizations']
                    )
                
                customized_policies.append(customized_policy)
            
            self.logger.info(f"Successfully applied customizations to {len(customized_policies)} policies")
            return customized_policies
            
        except Exception as e:
            self.logger.error(f"Error applying comprehensive customization: {e}")
            # Return original policies if customization fails
            return policies

    def _apply_registry_customization(self, policy: PolicyCatalogEntry, registries: List[str]) -> PolicyCatalogEntry:
        """Apply registry-specific customizations to policy."""
        # Add registry information to policy tags for later processing
        registry_tags = [f"registry:{registry}" for registry in registries]
        policy.tags.extend(registry_tags)
        
        # Update description to indicate registry customization
        if "registry" in policy.description.lower() or "image" in policy.description.lower():
            policy.description += f" [Customized for registries: {', '.join(registries)}]"
        
        return policy

    def _apply_label_customization(self, policy: PolicyCatalogEntry, custom_labels: Dict[str, str]) -> PolicyCatalogEntry:
        """Apply label-specific customizations to policy."""
        # Add label information to policy tags for later processing
        label_tags = [f"label:{key}={value}" for key, value in custom_labels.items()]
        policy.tags.extend(label_tags)
        
        # Update description to indicate label customization
        if "label" in policy.description.lower():
            policy.description += f" [Customized with labels: {custom_labels}]"
        
        return policy

    def _apply_compliance_customization(self, policy: PolicyCatalogEntry, frameworks: List[str]) -> PolicyCatalogEntry:
        """Apply compliance framework-specific customizations to policy."""
        # Add compliance framework tags
        compliance_tags = [f"compliance:{framework}" for framework in frameworks]
        policy.tags.extend(compliance_tags)
        
        # Update description to indicate compliance customization
        policy.description += f" [Compliance: {', '.join(frameworks)}]"
        
        return policy

    def _apply_ai_suggested_customizations(self, policy: PolicyCatalogEntry, customizations: List[Dict[str, Any]]) -> PolicyCatalogEntry:
        """Apply AI-suggested customizations from Phase 2 selection."""
        for customization in customizations:
            customization_type = customization.get('type', '')
            description = customization.get('description', '')
            value = customization.get('value', '')
            
            # Add customization information to tags
            if customization_type and value:
                policy.tags.append(f"ai_custom:{customization_type}={value}")
            
            # Update policy description with AI reasoning
            if description:
                policy.description += f" [AI Customization: {description}]"
        
        return policy
    
    def _legacy_single_phase_selection(self, cluster_info: ClusterInfo, requirements: GovernanceRequirements,
                                     policy_index: PolicyIndex, target_count: int) -> List[PolicyCatalogEntry]:
        """Legacy single-phase AI policy selection for backward compatibility."""
        try:
            self.logger.info("Using legacy single-phase AI policy selection")
            
            # Prepare context for single-phase selection
            context = self._prepare_selection_context(cluster_info, requirements, policy_index)
            
            # Create selection prompt
            prompt = self._create_selection_prompt(context, target_count)
            
            # Get AI response
            response = self.bedrock_client.send_request(prompt, max_tokens=4000, temperature=0.1)
            
            # Parse selected policy names
            selected_names = self._parse_selection_response(response)
            
            # Map to PolicyCatalogEntry objects
            selected_policies = self._map_policies_from_index(selected_names, policy_index)
            
            self.logger.info(f"Legacy single-phase selection completed: {len(selected_policies)} policies selected")
            return selected_policies[:target_count]
            
        except Exception as e:
            self.logger.error(f"Legacy single-phase selection failed: {e}")
            # Fallback to rule-based selection
            return self._fallback_policy_selection(cluster_info, requirements, policy_index, target_count)

    def _emergency_policy_selection(self, policy_index: PolicyIndex, target_count: int) -> List[PolicyCatalogEntry]:
        """Emergency policy selection as last resort."""
        self.logger.warning("Using emergency policy selection - basic sampling from all categories")
        
        emergency_policies = []
        policies_per_category = max(1, target_count // len(policy_index.categories))
        
        for category, policies in policy_index.categories.items():
            if len(emergency_policies) >= target_count:
                break
            
            # Take first few policies from each category
            category_policies = policies[:policies_per_category]
            emergency_policies.extend(category_policies)
        
        return emergency_policies[:target_count]
    
    def _validate_two_phase_config(self) -> bool:
        """Validate Two-Phase selection configuration."""
        try:
            required_keys = ['phase_one_candidates', 'phase_two_target']
            for key in required_keys:
                if key not in self.two_phase_config:
                    self.logger.warning(f"Missing Two-Phase config key: {key}")
                    return False
            
            # Validate numeric values
            if self.phase_one_candidates <= 0 or self.phase_one_candidates > 1000:
                self.logger.warning(f"Invalid phase_one_candidates: {self.phase_one_candidates}")
                return False
            
            if self.phase_one_max_tokens <= 0 or self.phase_one_max_tokens > 100000:
                self.logger.warning(f"Invalid phase_one_max_tokens: {self.phase_one_max_tokens}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating Two-Phase config: {e}")
            return False
    
    def get_selection_metrics(self) -> Dict[str, Any]:
        """Get metrics about the selection process."""
        return {
            "two_phase_enabled": True,
            "phase_one_candidates_limit": self.phase_one_candidates,
            "phase_one_max_tokens": self.phase_one_max_tokens,
            "phase_two_max_tokens": self.phase_two_max_tokens,
            "bedrock_model": self.bedrock_client.model_id,
            "bedrock_available": self.bedrock_client.is_available(),
            "config_valid": self._validate_two_phase_config()
        }
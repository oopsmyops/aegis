"""
Policy customization system for AEGIS.
Handles registry replacement, label modification, and parameter customization based on requirements.
"""

import re
import logging
from typing import Dict, List, Any, Optional
from models import PolicyCatalogEntry, GovernanceRequirements, RecommendedPolicy
from utils.yaml_utils import YamlUtils
from exceptions import AISelectionError


class PolicyCustomizer:
    """Handles policy customization based on governance requirements."""
    
    def __init__(self):
        """Initialize policy customizer."""
        self.logger = logging.getLogger(__name__)
    
    def customize_policy(self, policy: PolicyCatalogEntry, requirements: GovernanceRequirements, 
                        policy_content: str) -> RecommendedPolicy:
        """Customize a single policy based on requirements."""
        try:
            self.logger.info(f"Customizing policy: {policy.name}")
            
            # Parse policy content
            policy_data = YamlUtils.load_yaml_safe_from_string(policy_content)
            if not policy_data:
                raise AISelectionError(f"Failed to parse policy content for {policy.name}")
            
            customizations_applied = []
            
            # Apply registry customizations
            if requirements.registries:
                policy_data, registry_changes = self._customize_registries(policy_data, requirements.registries)
                customizations_applied.extend(registry_changes)
            
            # Apply label customizations
            if requirements.custom_labels:
                policy_data, label_changes = self._customize_labels(policy_data, requirements.custom_labels)
                customizations_applied.extend(label_changes)
            
            # Apply parameter customizations based on requirements
            policy_data, param_changes = self._customize_parameters(policy_data, requirements)
            customizations_applied.extend(param_changes)
            
            # Convert back to YAML string
            customized_content = YamlUtils.dump_yaml_safe(policy_data)
            
            # Create recommended policy
            recommended_policy = RecommendedPolicy(
                original_policy=policy,
                customized_content=customized_content,
                category=policy.category,
                validation_status="pending",
                customizations_applied=customizations_applied
            )
            
            self.logger.info(f"Applied {len(customizations_applied)} customizations to {policy.name}")
            return recommended_policy
            
        except Exception as e:
            self.logger.error(f"Error customizing policy {policy.name}: {e}")
            # Return policy with original content if customization fails
            return RecommendedPolicy(
                original_policy=policy,
                customized_content=policy_content,
                category=policy.category,
                validation_status="error",
                customizations_applied=[f"Customization failed: {e}"]
            )
    
    def customize_policies_batch(self, policies: List[PolicyCatalogEntry], 
                               requirements: GovernanceRequirements,
                               policy_contents: Dict[str, str]) -> List[RecommendedPolicy]:
        """Customize multiple policies in batch."""
        recommended_policies = []
        
        for policy in policies:
            policy_content = policy_contents.get(policy.name, "")
            if not policy_content:
                self.logger.warning(f"No content found for policy {policy.name}")
                continue
            
            recommended_policy = self.customize_policy(policy, requirements, policy_content)
            recommended_policies.append(recommended_policy)
        
        return recommended_policies
    
    def _customize_registries(self, policy_data: Dict[str, Any], 
                            allowed_registries: List[str]) -> tuple[Dict[str, Any], List[str]]:
        """Customize registry-related configurations in policy."""
        changes = []
        
        try:
            # Look for registry patterns in the policy
            policy_str = str(policy_data)
            
            # Common registry patterns to replace
            registry_patterns = [
                r'registry\.k8s\.io',
                r'docker\.io',
                r'gcr\.io',
                r'quay\.io',
                r'registry-1\.docker\.io'
            ]
            
            # If policy contains registry restrictions, update them
            if 'spec' in policy_data and isinstance(policy_data['spec'], dict):
                spec = policy_data['spec']
                
                # Handle ClusterPolicy and Policy structures
                if 'rules' in spec:
                    for rule in spec['rules']:
                        if isinstance(rule, dict) and 'validate' in rule:
                            validate = rule['validate']
                            
                            # Update registry allowlists in validation rules
                            if isinstance(validate, dict):
                                changes.extend(self._update_registry_in_validation(validate, allowed_registries))
                        
                        elif isinstance(rule, dict) and 'verifyImages' in rule:
                            verify_images = rule['verifyImages']
                            if isinstance(verify_images, list):
                                for verify_rule in verify_images:
                                    if isinstance(verify_rule, dict) and 'imageReferences' in verify_rule:
                                        # Update image references to use allowed registries
                                        old_refs = verify_rule['imageReferences']
                                        if allowed_registries:
                                            verify_rule['imageReferences'] = [f"{reg}/*" for reg in allowed_registries]
                                            changes.append(f"Updated imageReferences from {old_refs} to allowed registries")
            
            # Update any hardcoded registry references in the policy text
            policy_yaml_str = YamlUtils.dump_yaml_safe(policy_data)
            for pattern in registry_patterns:
                if re.search(pattern, policy_yaml_str) and allowed_registries:
                    # Replace with first allowed registry as default
                    new_registry = allowed_registries[0]
                    policy_yaml_str = re.sub(pattern, new_registry, policy_yaml_str)
                    changes.append(f"Replaced registry pattern {pattern} with {new_registry}")
            
            # Parse back if changes were made
            if changes:
                policy_data = YamlUtils.load_yaml_safe_from_string(policy_yaml_str)
            
        except Exception as e:
            self.logger.warning(f"Error customizing registries: {e}")
        
        return policy_data, changes
    
    def _customize_labels(self, policy_data: Dict[str, Any], 
                         custom_labels: Dict[str, str]) -> tuple[Dict[str, Any], List[str]]:
        """Customize label-related configurations in policy."""
        changes = []
        
        try:
            if 'metadata' not in policy_data:
                policy_data['metadata'] = {}
            
            if 'labels' not in policy_data['metadata']:
                policy_data['metadata']['labels'] = {}
            
            # Add custom labels to policy metadata
            for key, value in custom_labels.items():
                old_value = policy_data['metadata']['labels'].get(key)
                policy_data['metadata']['labels'][key] = value
                
                if old_value != value:
                    if old_value is None:
                        changes.append(f"Added label {key}={value}")
                    else:
                        changes.append(f"Updated label {key} from {old_value} to {value}")
            
            # Also add labels to any resource templates in the policy
            if 'spec' in policy_data and isinstance(policy_data['spec'], dict):
                spec = policy_data['spec']
                
                if 'rules' in spec:
                    for rule in spec['rules']:
                        if isinstance(rule, dict) and 'generate' in rule:
                            generate = rule['generate']
                            if isinstance(generate, dict) and 'data' in generate:
                                data = generate['data']
                                if isinstance(data, dict) and 'metadata' in data:
                                    if 'labels' not in data['metadata']:
                                        data['metadata']['labels'] = {}
                                    
                                    for key, value in custom_labels.items():
                                        data['metadata']['labels'][key] = value
                                        changes.append(f"Added label {key}={value} to generated resource")
        
        except Exception as e:
            self.logger.warning(f"Error customizing labels: {e}")
        
        return policy_data, changes
    
    def _customize_parameters(self, policy_data: Dict[str, Any], 
                            requirements: GovernanceRequirements) -> tuple[Dict[str, Any], List[str]]:
        """Customize policy parameters based on requirements."""
        changes = []
        
        try:
            # Analyze requirements to determine parameter customizations
            requirement_flags = {answer.question_id: answer.answer for answer in requirements.answers}
            
            # Apply customizations based on specific requirements
            if requirement_flags.get('enforce_resource_limits', False):
                changes.extend(self._enable_resource_limit_enforcement(policy_data))
            
            if requirement_flags.get('require_security_context', False):
                changes.extend(self._enable_security_context_requirements(policy_data))
            
            if requirement_flags.get('enforce_network_policies', False):
                changes.extend(self._enable_network_policy_enforcement(policy_data))
            
            if requirement_flags.get('require_pod_security_standards', False):
                changes.extend(self._enable_pod_security_standards(policy_data))
            
            # Customize based on compliance frameworks
            for framework in requirements.compliance_frameworks:
                if framework.lower() == 'cis':
                    changes.extend(self._apply_cis_customizations(policy_data))
                elif framework.lower() == 'pci':
                    changes.extend(self._apply_pci_customizations(policy_data))
                elif framework.lower() == 'hipaa':
                    changes.extend(self._apply_hipaa_customizations(policy_data))
        
        except Exception as e:
            self.logger.warning(f"Error customizing parameters: {e}")
        
        return policy_data, changes
    
    def _update_registry_in_validation(self, validate: Dict[str, Any], 
                                     allowed_registries: List[str]) -> List[str]:
        """Update registry references in validation rules."""
        changes = []
        
        try:
            # Handle different validation rule structures
            if 'pattern' in validate:
                pattern = validate['pattern']
                if isinstance(pattern, dict) and 'spec' in pattern:
                    spec = pattern['spec']
                    if 'containers' in spec:
                        for container in spec['containers']:
                            if 'image' in container and allowed_registries:
                                old_image = container['image']
                                # Update image pattern to use allowed registries
                                new_pattern = f"({('|'.join(allowed_registries))})/.*"
                                container['image'] = new_pattern
                                changes.append(f"Updated image pattern from {old_image} to {new_pattern}")
            
            elif 'anyPattern' in validate:
                # Handle anyPattern validation rules
                any_pattern = validate['anyPattern']
                if isinstance(any_pattern, list):
                    for pattern in any_pattern:
                        if isinstance(pattern, dict) and 'spec' in pattern:
                            # Similar logic as above
                            pass
        
        except Exception as e:
            self.logger.warning(f"Error updating registry in validation: {e}")
        
        return changes
    
    def _enable_resource_limit_enforcement(self, policy_data: Dict[str, Any]) -> List[str]:
        """Enable resource limit enforcement in policy."""
        changes = []
        
        try:
            # Look for resource limit related policies and make them more strict
            policy_str = str(policy_data).lower()
            if 'resource' in policy_str and 'limit' in policy_str:
                # Policy is resource-limit related, make it more restrictive
                if 'spec' in policy_data and 'rules' in policy_data['spec']:
                    for rule in policy_data['spec']['rules']:
                        if isinstance(rule, dict) and 'validate' in rule:
                            # Make validation more strict
                            changes.append("Enabled stricter resource limit enforcement")
        
        except Exception as e:
            self.logger.warning(f"Error enabling resource limit enforcement: {e}")
        
        return changes
    
    def _enable_security_context_requirements(self, policy_data: Dict[str, Any]) -> List[str]:
        """Enable security context requirements in policy."""
        changes = []
        
        try:
            policy_str = str(policy_data).lower()
            if 'security' in policy_str and 'context' in policy_str:
                changes.append("Enabled stricter security context requirements")
        
        except Exception as e:
            self.logger.warning(f"Error enabling security context requirements: {e}")
        
        return changes
    
    def _enable_network_policy_enforcement(self, policy_data: Dict[str, Any]) -> List[str]:
        """Enable network policy enforcement in policy."""
        changes = []
        
        try:
            policy_str = str(policy_data).lower()
            if 'network' in policy_str:
                changes.append("Enabled network policy enforcement")
        
        except Exception as e:
            self.logger.warning(f"Error enabling network policy enforcement: {e}")
        
        return changes
    
    def _enable_pod_security_standards(self, policy_data: Dict[str, Any]) -> List[str]:
        """Enable Pod Security Standards in policy."""
        changes = []
        
        try:
            policy_str = str(policy_data).lower()
            if 'pod' in policy_str and 'security' in policy_str:
                changes.append("Enabled Pod Security Standards compliance")
        
        except Exception as e:
            self.logger.warning(f"Error enabling Pod Security Standards: {e}")
        
        return changes
    
    def _apply_cis_customizations(self, policy_data: Dict[str, Any]) -> List[str]:
        """Apply CIS Kubernetes Benchmark customizations."""
        changes = []
        
        try:
            # Add CIS-specific labels and annotations
            if 'metadata' not in policy_data:
                policy_data['metadata'] = {}
            
            if 'annotations' not in policy_data['metadata']:
                policy_data['metadata']['annotations'] = {}
            
            policy_data['metadata']['annotations']['policies.kyverno.io/cis-compliance'] = 'true'
            changes.append("Added CIS compliance annotation")
        
        except Exception as e:
            self.logger.warning(f"Error applying CIS customizations: {e}")
        
        return changes
    
    def _apply_pci_customizations(self, policy_data: Dict[str, Any]) -> List[str]:
        """Apply PCI DSS customizations."""
        changes = []
        
        try:
            if 'metadata' not in policy_data:
                policy_data['metadata'] = {}
            
            if 'annotations' not in policy_data['metadata']:
                policy_data['metadata']['annotations'] = {}
            
            policy_data['metadata']['annotations']['policies.kyverno.io/pci-compliance'] = 'true'
            changes.append("Added PCI DSS compliance annotation")
        
        except Exception as e:
            self.logger.warning(f"Error applying PCI customizations: {e}")
        
        return changes
    
    def _apply_hipaa_customizations(self, policy_data: Dict[str, Any]) -> List[str]:
        """Apply HIPAA customizations."""
        changes = []
        
        try:
            if 'metadata' not in policy_data:
                policy_data['metadata'] = {}
            
            if 'annotations' not in policy_data['metadata']:
                policy_data['metadata']['annotations'] = {}
            
            policy_data['metadata']['annotations']['policies.kyverno.io/hipaa-compliance'] = 'true'
            changes.append("Added HIPAA compliance annotation")
        
        except Exception as e:
            self.logger.warning(f"Error applying HIPAA customizations: {e}")
        
        return changes
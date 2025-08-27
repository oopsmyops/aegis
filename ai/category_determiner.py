"""
AI-powered dynamic category determination for policy organization.
Uses AWS Bedrock to intelligently organize policies into meaningful categories.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from models import ClusterInfo, PolicyCatalogEntry, GovernanceRequirements
from ai.bedrock_client import BedrockClient
from exceptions import AISelectionError


class CategoryDeterminer:
    """Determines dynamic categories for policy organization using AI."""
    
    def __init__(self, bedrock_client: BedrockClient):
        """Initialize category determiner with Bedrock client."""
        self.bedrock_client = bedrock_client
        self.logger = logging.getLogger(__name__)
    
    def determine_categories(self, cluster_info: ClusterInfo, selected_policies: List[PolicyCatalogEntry],
                           requirements: GovernanceRequirements) -> List[str]:
        """Dynamically determine output categories using AI."""
        try:
            # Prepare context for AI
            context = self._prepare_context(cluster_info, selected_policies, requirements)
            
            # Create prompt for category determination
            prompt = self._create_category_prompt(context)
            
            # Get AI response
            response = self.bedrock_client.send_request(prompt, max_tokens=1000, temperature=0.1)
            
            # Parse categories from response
            categories = self._parse_categories_response(response)
            
            # Validate and filter categories
            validated_categories = self._validate_categories(categories, selected_policies)
            
            self.logger.info(f"Determined {len(validated_categories)} categories: {validated_categories}")
            return validated_categories
            
        except Exception as e:
            self.logger.error(f"Error determining categories: {e}")
            # Fallback to default categories
            return self._get_fallback_categories(selected_policies)
    
    def _prepare_context(self, cluster_info: ClusterInfo, selected_policies: List[PolicyCatalogEntry],
                        requirements: GovernanceRequirements) -> Dict[str, Any]:
        """Prepare context information for AI analysis."""
        # Extract cluster characteristics
        cluster_context = {
            "kubernetes_version": cluster_info.version,
            "managed_service": cluster_info.managed_service,
            "node_count": cluster_info.node_count,
            "namespace_count": cluster_info.namespace_count,
            "third_party_controllers": [
                {
                    "name": controller.name,
                    "type": controller.type.value,
                    "namespace": controller.namespace
                }
                for controller in cluster_info.third_party_controllers
            ],
            "compliance_frameworks": cluster_info.compliance_frameworks
        }
        
        # Extract policy information
        policy_context = []
        for policy in selected_policies:
            policy_context.append({
                "name": policy.name,
                "category": policy.category,
                "description": policy.description[:200],  # Truncate for context
                "tags": policy.tags
            })
        
        # Extract requirements context
        requirements_context = {
            "compliance_frameworks": requirements.compliance_frameworks,
            "registries": requirements.registries,
            "custom_labels": requirements.custom_labels,
            "answered_yes": [
                answer.question_id for answer in requirements.answers if answer.answer
            ]
        }
        
        return {
            "cluster": cluster_context,
            "policies": policy_context,
            "requirements": requirements_context
        }
    
    def _create_category_prompt(self, context: Dict[str, Any]) -> str:
        """Create AI prompt for category determination."""
        prompt = f"""
You are an expert Kubernetes governance consultant. Based on the cluster information, selected policies, and governance requirements provided, determine the most logical and meaningful categories to organize these policies.

CLUSTER INFORMATION:
- Kubernetes Version: {context['cluster']['kubernetes_version']}
- Managed Service: {context['cluster']['managed_service']}
- Node Count: {context['cluster']['node_count']}
- Third-party Controllers: {[ctrl['name'] + ' (' + ctrl['type'] + ')' for ctrl in context['cluster']['third_party_controllers']]}
- Compliance Frameworks: {context['cluster']['compliance_frameworks']}

GOVERNANCE REQUIREMENTS:
- Compliance Frameworks: {context['requirements']['compliance_frameworks']}
- Allowed Registries: {context['requirements']['registries']}
- Requirements Answered Yes: {context['requirements']['answered_yes']}

SELECTED POLICIES ({len(context['policies'])} total):
{json.dumps(context['policies'], indent=2)}

INSTRUCTIONS:
1. Analyze the cluster characteristics, governance requirements, and selected policies
2. Create 3-6 meaningful categories that logically group these policies
3. Categories should be:
   - Descriptive and clear
   - Relevant to the cluster environment
   - Aligned with governance requirements
   - Practical for operations teams

4. Consider these category types:
   - Security & Compliance (for security-focused policies)
   - Best Practices (for general operational policies)
   - Resource Management (for resource limits, quotas)
   - Network Security (for network policies, ingress rules)
   - Workload Security (for pod security, containers)
   - Platform Specific (for cloud provider specific policies)
   - Compliance Framework specific (PCI, HIPAA, CIS, etc.)

5. Return ONLY a JSON array of category names, nothing else.

Example response format:
["Security & Compliance", "Best Practices", "Resource Management", "Network Security"]
"""
        return prompt
    
    def _parse_categories_response(self, response: str) -> List[str]:
        """Parse categories from AI response."""
        try:
            # Clean the response
            response = response.strip()
            
            # Try to extract JSON array from response
            if response.startswith('[') and response.endswith(']'):
                categories = json.loads(response)
            else:
                # Try to find JSON array in the response
                import re
                json_match = re.search(r'\[.*?\]', response, re.DOTALL)
                if json_match:
                    categories = json.loads(json_match.group())
                else:
                    # Fallback: split by lines and clean
                    lines = response.split('\n')
                    categories = []
                    for line in lines:
                        line = line.strip().strip('"').strip("'").strip('-').strip()
                        if line and len(line) > 2:
                            categories.append(line)
            
            # Validate that we have a list of strings
            if not isinstance(categories, list):
                raise ValueError("Response is not a list")
            
            # Clean and validate each category
            cleaned_categories = []
            for cat in categories:
                if isinstance(cat, str) and len(cat.strip()) > 0:
                    cleaned_categories.append(cat.strip())
            
            return cleaned_categories[:6]  # Limit to 6 categories max
            
        except Exception as e:
            self.logger.error(f"Error parsing categories response: {e}")
            self.logger.debug(f"Raw response: {response}")
            raise AISelectionError(f"Failed to parse categories from AI response: {e}")
    
    def _validate_categories(self, categories: List[str], policies: List[PolicyCatalogEntry]) -> List[str]:
        """Validate and filter categories."""
        if not categories:
            return self._get_fallback_categories(policies)
        
        # Ensure we have at least 2 categories and at most 6
        if len(categories) < 2:
            categories.extend(self._get_fallback_categories(policies))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_categories = []
        for cat in categories:
            if cat not in seen:
                seen.add(cat)
                unique_categories.append(cat)
        
        return unique_categories[:6]  # Limit to 6 categories
    
    def _get_fallback_categories(self, policies: List[PolicyCatalogEntry]) -> List[str]:
        """Get fallback categories based on policy analysis."""
        # Analyze existing policy categories and tags
        category_counts = {}
        tag_counts = {}
        
        for policy in policies:
            # Count original categories
            if policy.category:
                category_counts[policy.category] = category_counts.get(policy.category, 0) + 1
            
            # Count tags
            for tag in policy.tags:
                tag_counts[tag.lower()] = tag_counts.get(tag.lower(), 0) + 1
        
        # Determine fallback categories based on analysis
        fallback_categories = ["Best Practices", "Security & Compliance"]
        
        # Add categories based on most common original categories
        sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        for cat, count in sorted_categories[:2]:
            if cat not in fallback_categories and cat != "other":
                fallback_categories.append(cat.title())
        
        # Add categories based on common tags
        if any("network" in tag for tag in tag_counts):
            fallback_categories.append("Network Security")
        if any("resource" in tag for tag in tag_counts):
            fallback_categories.append("Resource Management")
        if any(tag in ["aws", "gcp", "azure", "eks", "aks", "gke"] for tag in tag_counts):
            fallback_categories.append("Platform Specific")
        
        return fallback_categories[:6]
    
    def assign_policies_to_categories(self, policies: List[PolicyCatalogEntry], 
                                    categories: List[str]) -> Dict[str, List[PolicyCatalogEntry]]:
        """Assign policies to determined categories using AI."""
        try:
            # Prepare assignment context
            assignment_context = {
                "categories": categories,
                "policies": [
                    {
                        "name": policy.name,
                        "description": policy.description[:200],
                        "tags": policy.tags,
                        "original_category": policy.category
                    }
                    for policy in policies
                ]
            }
            
            # Create assignment prompt
            prompt = self._create_assignment_prompt(assignment_context)
            
            # Get AI response
            response = self.bedrock_client.send_request(prompt, max_tokens=2000, temperature=0.1)
            
            # Parse assignment response
            assignments = self._parse_assignment_response(response, policies, categories)
            
            return assignments
            
        except Exception as e:
            self.logger.error(f"Error assigning policies to categories: {e}")
            # Fallback to simple assignment
            return self._fallback_policy_assignment(policies, categories)
    
    def _create_assignment_prompt(self, context: Dict[str, Any]) -> str:
        """Create prompt for policy-to-category assignment."""
        prompt = f"""
You are assigning Kubernetes policies to categories. Based on each policy's name, description, and tags, assign each policy to the most appropriate category.

AVAILABLE CATEGORIES:
{json.dumps(context['categories'], indent=2)}

POLICIES TO ASSIGN:
{json.dumps(context['policies'], indent=2)}

INSTRUCTIONS:
1. Assign each policy to exactly one category
2. Base assignments on policy name, description, and tags
3. Consider the policy's purpose and scope
4. Distribute policies reasonably across categories
5. Return a JSON object mapping policy names to category names

Example response format:
{{
  "policy-name-1": "Security & Compliance",
  "policy-name-2": "Best Practices",
  "policy-name-3": "Network Security"
}}
"""
        return prompt
    
    def _parse_assignment_response(self, response: str, policies: List[PolicyCatalogEntry], 
                                 categories: List[str]) -> Dict[str, List[PolicyCatalogEntry]]:
        """Parse policy assignment response."""
        try:
            # Clean and parse JSON response
            response = response.strip()
            if not response.startswith('{'):
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    response = json_match.group()
                else:
                    raise ValueError("No JSON found in response")
            
            assignments = json.loads(response)
            
            # Create category mapping
            category_mapping = {cat: [] for cat in categories}
            
            # Create policy lookup
            policy_lookup = {policy.name: policy for policy in policies}
            
            # Assign policies to categories
            for policy_name, category in assignments.items():
                if policy_name in policy_lookup and category in category_mapping:
                    category_mapping[category].append(policy_lookup[policy_name])
            
            # Handle unassigned policies
            assigned_policies = set()
            for policy_list in category_mapping.values():
                assigned_policies.update(policy.name for policy in policy_list)
            
            unassigned_policies = [p for p in policies if p.name not in assigned_policies]
            if unassigned_policies:
                # Distribute unassigned policies to categories with fewer policies
                sorted_categories = sorted(categories, key=lambda c: len(category_mapping[c]))
                for i, policy in enumerate(unassigned_policies):
                    category = sorted_categories[i % len(sorted_categories)]
                    category_mapping[category].append(policy)
            
            return category_mapping
            
        except Exception as e:
            self.logger.error(f"Error parsing assignment response: {e}")
            return self._fallback_policy_assignment(policies, categories)
    
    def _fallback_policy_assignment(self, policies: List[PolicyCatalogEntry], 
                                  categories: List[str]) -> Dict[str, List[PolicyCatalogEntry]]:
        """Fallback policy assignment based on simple rules."""
        category_mapping = {cat: [] for cat in categories}
        
        # Simple rule-based assignment
        for policy in policies:
            assigned = False
            
            # Check tags and description for keywords
            policy_text = (policy.name + " " + policy.description + " " + " ".join(policy.tags)).lower()
            
            for category in categories:
                category_lower = category.lower()
                
                if not assigned:
                    if "security" in category_lower and any(word in policy_text for word in ["security", "rbac", "psp", "privileged"]):
                        category_mapping[category].append(policy)
                        assigned = True
                    elif "network" in category_lower and any(word in policy_text for word in ["network", "ingress", "egress", "service"]):
                        category_mapping[category].append(policy)
                        assigned = True
                    elif "resource" in category_lower and any(word in policy_text for word in ["resource", "limit", "quota", "memory", "cpu"]):
                        category_mapping[category].append(policy)
                        assigned = True
                    elif "platform" in category_lower and any(word in policy_text for word in ["aws", "gcp", "azure", "eks", "aks", "gke"]):
                        category_mapping[category].append(policy)
                        assigned = True
            
            # If not assigned, put in first available category
            if not assigned:
                category_mapping[categories[0]].append(policy)
        
        return category_mapping
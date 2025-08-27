"""
Output management system for AEGIS policy recommendations.
Organizes policies in dynamic categories with test cases and validation reports.
"""

import os
import yaml
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import asdict
from models import PolicyRecommendation, RecommendedPolicy
from ai.kyverno_validator import ValidationResult
from exceptions import FileSystemError


class OutputManager:
    """Manages policy output organization and validation reporting."""
    
    def __init__(self, output_directory: str = "./recommended-policies"):
        """Initialize output manager."""
        self.output_directory = output_directory
        self.logger = logging.getLogger(__name__)
    
    def organize_policies_by_categories(self, recommendation: PolicyRecommendation, 
                                      validation_results: List[ValidationResult]) -> Dict[str, str]:
        """Organize policies into dynamic category-based folder structure."""
        try:
            # Create output directory
            os.makedirs(self.output_directory, exist_ok=True)
            
            # Group policies by category
            category_policies = self._group_policies_by_category(
                recommendation.recommended_policies, 
                recommendation.categories
            )
            
            # Create validation results lookup
            validation_lookup = {result.policy_name: result for result in validation_results}
            
            created_files = {}
            
            # Process each category
            for category, policies in category_policies.items():
                category_dir = os.path.join(self.output_directory, self._sanitize_category_name(category))
                os.makedirs(category_dir, exist_ok=True)
                
                category_files = []
                
                # Process each policy in the category
                for policy in policies:
                    policy_files = self._create_policy_files(
                        policy, 
                        category_dir, 
                        validation_lookup.get(policy.original_policy.name)
                    )
                    category_files.extend(policy_files)
                
                created_files[category] = category_files
            
            # Create summary files
            self._create_recommendation_summary(recommendation, validation_results)
            self._create_validation_report(validation_results)
            self._create_category_index(category_policies, validation_results)
            
            self.logger.info(f"Successfully organized {len(recommendation.recommended_policies)} policies into {len(category_policies)} categories")
            return created_files
            
        except Exception as e:
            self.logger.error(f"Error organizing policies: {e}")
            raise FileSystemError(f"Failed to organize policies: {e}")
    
    def create_policy_directory_structure(self, policy: RecommendedPolicy, base_dir: str, 
                                        validation_result: Optional[ValidationResult] = None) -> List[str]:
        """Create directory structure for a single policy with all files."""
        try:
            policy_name = self._sanitize_policy_name(policy.original_policy.name)
            policy_dir = os.path.join(base_dir, policy_name)
            os.makedirs(policy_dir, exist_ok=True)
            
            created_files = []
            
            # Get the original policy file name from the relative path
            original_policy_filename = os.path.basename(policy.original_policy.relative_path)
            
            # Create main policy file with correct original name
            policy_file = os.path.join(policy_dir, original_policy_filename)
            # NEVER use fixed_content as it might modify policy - always use original
            policy_content = policy.customized_content
            
            with open(policy_file, 'w', encoding='utf-8') as f:
                f.write(policy_content)
            created_files.append(policy_file)
            
            # Handle test files - preserve existing, only generate if missing
            test_file = os.path.join(policy_dir, "kyverno-test.yaml")
            
            # Check if original test directory exists and copy existing test files
            if policy.original_policy.test_directory:
                original_test_dir = os.path.join("./policy-catalog", policy.original_policy.test_directory)
                if os.path.exists(original_test_dir):
                    # Copy existing test files
                    original_test_file = os.path.join(original_test_dir, "kyverno-test.yaml")
                    if os.path.exists(original_test_file):
                        import shutil
                        shutil.copy2(original_test_file, test_file)
                        created_files.append(test_file)
                        self.logger.info(f"Copied existing test case for {policy.original_policy.name}")
                    
                    # Copy resource files if they exist (check multiple possible names)
                    resource_files_to_check = ["resource.yaml", "resources.yaml", "resource.yml", "resources.yml"]
                    resource_copied = False
                    
                    for resource_filename in resource_files_to_check:
                        original_resource_file = os.path.join(original_test_dir, resource_filename)
                        if os.path.exists(original_resource_file):
                            # Use the same filename as in the original
                            resource_file = os.path.join(policy_dir, resource_filename)
                            shutil.copy2(original_resource_file, resource_file)
                            created_files.append(resource_file)
                            resource_copied = True
                            break
                    
                    if not resource_copied:
                        # Generate sample resource if original doesn't exist
                        resource_file = os.path.join(policy_dir, "resource.yaml")
                        resource_content = self._generate_sample_resource(policy)
                        with open(resource_file, 'w', encoding='utf-8') as f:
                            f.write(resource_content)
                        created_files.append(resource_file)
                else:
                    # Original test directory doesn't exist, generate if we have test content
                    if policy.test_content:
                        with open(test_file, 'w', encoding='utf-8') as f:
                            f.write(policy.test_content)
                        created_files.append(test_file)
                        self.logger.info(f"Generated new test case for {policy.original_policy.name}")
                    
                    # Generate sample resource
                    resource_file = os.path.join(policy_dir, "resource.yaml")
                    resource_content = self._generate_sample_resource(policy)
                    with open(resource_file, 'w', encoding='utf-8') as f:
                        f.write(resource_content)
                    created_files.append(resource_file)
            else:
                # No test directory specified, generate if we have test content
                if policy.test_content:
                    with open(test_file, 'w', encoding='utf-8') as f:
                        f.write(policy.test_content)
                    created_files.append(test_file)
                    self.logger.info(f"Generated new test case for {policy.original_policy.name}")
                
                # Generate sample resource
                resource_file = os.path.join(policy_dir, "resource.yaml")
                resource_content = self._generate_sample_resource(policy)
                with open(resource_file, 'w', encoding='utf-8') as f:
                    f.write(resource_content)
                created_files.append(resource_file)
            
            # Create policy metadata file
            metadata_file = os.path.join(policy_dir, "policy-info.yaml")
            metadata_content = self._create_policy_metadata(policy, validation_result)
            with open(metadata_file, 'w', encoding='utf-8') as f:
                f.write(yaml.dump(metadata_content, default_flow_style=False))
            created_files.append(metadata_file)
            
            return created_files
            
        except Exception as e:
            self.logger.error(f"Error creating policy directory for {policy.original_policy.name}: {e}")
            raise FileSystemError(f"Failed to create policy directory: {e}")
    
    def generate_validation_report(self, validation_results: List[ValidationResult], 
                                 output_file: Optional[str] = None) -> str:
        """Generate comprehensive validation report."""
        try:
            if not output_file:
                output_file = os.path.join(self.output_directory, "validation-report.yaml")
            
            # Calculate statistics
            total_policies = len(validation_results)
            passed_policies = sum(1 for r in validation_results if r.passed)
            failed_policies = total_policies - passed_policies
            fixed_policies = sum(1 for r in validation_results if r.fixed_content)
            
            # Group results by status
            passed_results = [r for r in validation_results if r.passed]
            failed_results = [r for r in validation_results if not r.passed]
            
            report = {
                "validation_summary": {
                    "total_policies": total_policies,
                    "passed": passed_policies,
                    "failed": failed_policies,
                    "success_rate": f"{(passed_policies/total_policies*100):.1f}%" if total_policies > 0 else "0%",
                    "automatically_fixed": fixed_policies,
                    "generated_at": datetime.now().isoformat()
                },
                "passed_policies": [
                    {
                        "name": r.policy_name,
                        "warnings": r.warnings
                    } for r in passed_results
                ],
                "failed_policies": [
                    {
                        "name": r.policy_name,
                        "errors": r.errors,
                        "automatically_fixed": bool(r.fixed_content)
                    } for r in failed_results
                ],
                "recommendations": self._generate_validation_recommendations(validation_results)
            }
            
            # Write report
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(yaml.dump(report, default_flow_style=False))
            
            self.logger.info(f"Validation report created: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"Error generating validation report: {e}")
            raise FileSystemError(f"Failed to generate validation report: {e}")
    
    def create_deployment_guide(self, recommendation: PolicyRecommendation, 
                              validation_results: List[ValidationResult]) -> str:
        """Create deployment guide for recommended policies."""
        try:
            guide_file = os.path.join(self.output_directory, "DEPLOYMENT_GUIDE.md")
            
            # Calculate statistics
            total_policies = len(recommendation.recommended_policies)
            passed_validation = sum(1 for r in validation_results if r.passed)
            
            guide_content = f"""# AEGIS Policy Deployment Guide

## Overview
This directory contains {total_policies} Kyverno policies recommended for your Kubernetes cluster.
{passed_validation} policies passed validation and are ready for deployment.

## Cluster Information
- **Kubernetes Version**: {recommendation.cluster_info.version}
- **Managed Service**: {recommendation.cluster_info.managed_service or 'Self-managed'}
- **Node Count**: {recommendation.cluster_info.node_count}
- **Namespace Count**: {recommendation.cluster_info.namespace_count}

## Policy Categories
"""
            
            # Add category information
            category_policies = self._group_policies_by_category(
                recommendation.recommended_policies, 
                recommendation.categories
            )
            
            for category, policies in category_policies.items():
                guide_content += f"\n### {category.replace('-', ' ').title()}\n"
                guide_content += f"- **Policy Count**: {len(policies)}\n"
                guide_content += f"- **Directory**: `./{self._sanitize_category_name(category)}/`\n"
                
                # List policies in category
                for policy in policies:
                    validation_status = "✅" if any(r.policy_name == policy.original_policy.name and r.passed for r in validation_results) else "❌"
                    guide_content += f"  - {validation_status} {policy.original_policy.name}\n"
            
            guide_content += f"""
## Deployment Instructions

### Prerequisites
1. Kyverno must be installed in your cluster
2. You should have cluster-admin permissions
3. Review each policy before applying

### Deployment Steps

#### 1. Review Policies
```bash
# Review the validation report
cat validation-report.yaml

# Check individual policy files
find . -name "*.yaml" -path "*/policy-info.yaml" -prune -o -name "*.yaml" -print
```

#### 2. Test Policies (Recommended)
```bash
# Test policies using Kyverno CLI
kyverno test .

# Test specific category
kyverno test ./best-practices/
```

#### 3. Deploy in Audit Mode (Recommended)
```bash
# Apply all policies in audit mode first
find . -name "*.yaml" -not -path "*/kyverno-test.yaml" -not -path "*/resource.yaml" -not -path "*/policy-info.yaml" | xargs kubectl apply -f

# Monitor audit results
kubectl get cpol -o wide
kubectl get events --field-selector reason=PolicyViolation
```

#### 4. Switch to Enforce Mode
After reviewing audit results, you can switch policies to enforce mode by updating the `validationFailureAction` field.

### Policy Management

#### Customization Applied
The following customizations were applied based on your requirements:
"""
            
            # Add customization information
            all_customizations = set()
            for policy in recommendation.recommended_policies:
                all_customizations.update(policy.customizations_applied)
            
            for customization in sorted(all_customizations):
                guide_content += f"- {customization}\n"
            
            guide_content += f"""
#### Compliance Frameworks
{', '.join(recommendation.requirements.compliance_frameworks) if recommendation.requirements.compliance_frameworks else 'None specified'}

#### Registry Restrictions
{', '.join(recommendation.requirements.registries) if recommendation.requirements.registries else 'None specified'}

## Troubleshooting

### Common Issues
1. **Policy Validation Failures**: Check the validation-report.yaml for specific errors
2. **Resource Conflicts**: Some policies may conflict with existing resources
3. **Permission Issues**: Ensure you have sufficient RBAC permissions

### Support
- Review individual policy documentation in each policy directory
- Check Kyverno documentation: https://kyverno.io/docs/
- Validate policies using: `kyverno test <directory>`

## Generated Information
- **Generated At**: {recommendation.generation_timestamp.isoformat()}
- **AI Model Used**: {recommendation.ai_model_used}
- **Total Policies**: {total_policies}
- **Validation Success Rate**: {(passed_validation/total_policies*100):.1f}%
"""
            
            with open(guide_file, 'w', encoding='utf-8') as f:
                f.write(guide_content)
            
            self.logger.info(f"Deployment guide created: {guide_file}")
            return guide_file
            
        except Exception as e:
            self.logger.error(f"Error creating deployment guide: {e}")
            raise FileSystemError(f"Failed to create deployment guide: {e}")
    
    def _group_policies_by_category(self, policies: List[RecommendedPolicy], 
                                  categories: List[str]) -> Dict[str, List[RecommendedPolicy]]:
        """Group policies by their assigned categories."""
        category_policies = {}
        
        # Initialize categories
        for category in categories:
            category_policies[category] = []
        
        # Group policies
        for policy in policies:
            category = policy.category if policy.category else policy.original_policy.category
            
            # Ensure category exists
            if category not in category_policies:
                category_policies[category] = []
            
            category_policies[category].append(policy)
        
        # Remove empty categories
        return {k: v for k, v in category_policies.items() if v}
    
    def _create_policy_files(self, policy: RecommendedPolicy, category_dir: str, 
                           validation_result: Optional[ValidationResult]) -> List[str]:
        """Create all files for a single policy."""
        return self.create_policy_directory_structure(policy, category_dir, validation_result)
    
    def _create_recommendation_summary(self, recommendation: PolicyRecommendation, 
                                     validation_results: List[ValidationResult]) -> str:
        """Create high-level recommendation summary."""
        try:
            summary_file = os.path.join(self.output_directory, "recommendation-summary.yaml")
            
            # Calculate validation statistics
            validation_stats = {
                "total": len(validation_results),
                "passed": sum(1 for r in validation_results if r.passed),
                "failed": sum(1 for r in validation_results if not r.passed),
                "fixed": sum(1 for r in validation_results if r.fixed_content)
            }
            
            summary = {
                "recommendation_metadata": {
                    "generated_at": recommendation.generation_timestamp.isoformat(),
                    "ai_model_used": recommendation.ai_model_used,
                    "total_policies": len(recommendation.recommended_policies),
                    "categories": recommendation.categories
                },
                "cluster_information": {
                    "kubernetes_version": recommendation.cluster_info.version,
                    "managed_service": recommendation.cluster_info.managed_service,
                    "node_count": recommendation.cluster_info.node_count,
                    "namespace_count": recommendation.cluster_info.namespace_count,
                    "third_party_controllers": [
                        {"name": ctrl.name, "type": ctrl.type.value}
                        for ctrl in recommendation.cluster_info.third_party_controllers
                    ]
                },
                "governance_requirements": {
                    "compliance_frameworks": recommendation.requirements.compliance_frameworks,
                    "allowed_registries": recommendation.requirements.registries,
                    "requirements_count": len(recommendation.requirements.answers)
                },
                "validation_summary": validation_stats,
                "policy_categories": {}
            }
            
            # Add category breakdown
            category_policies = self._group_policies_by_category(
                recommendation.recommended_policies, 
                recommendation.categories
            )
            
            for category, policies in category_policies.items():
                category_validation = [
                    r for r in validation_results 
                    if any(p.original_policy.name == r.policy_name for p in policies)
                ]
                
                summary["policy_categories"][category] = {
                    "policy_count": len(policies),
                    "validation_passed": sum(1 for r in category_validation if r.passed),
                    "policies": [p.original_policy.name for p in policies]
                }
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(yaml.dump(summary, default_flow_style=False))
            
            return summary_file
            
        except Exception as e:
            self.logger.error(f"Error creating recommendation summary: {e}")
            raise FileSystemError(f"Failed to create recommendation summary: {e}")
    
    def _create_validation_report(self, validation_results: List[ValidationResult]) -> str:
        """Create detailed validation report."""
        return self.generate_validation_report(validation_results)
    
    def _create_category_index(self, category_policies: Dict[str, List[RecommendedPolicy]], 
                             validation_results: List[ValidationResult]) -> str:
        """Create index file for all categories."""
        try:
            index_file = os.path.join(self.output_directory, "category-index.yaml")
            
            index = {
                "categories": {},
                "generated_at": datetime.now().isoformat()
            }
            
            for category, policies in category_policies.items():
                category_validation = [
                    r for r in validation_results 
                    if any(p.original_policy.name == r.policy_name for p in policies)
                ]
                
                index["categories"][category] = {
                    "directory": self._sanitize_category_name(category),
                    "policy_count": len(policies),
                    "validation_passed": sum(1 for r in category_validation if r.passed),
                    "description": self._get_category_description(category),
                    "policies": [
                        {
                            "name": p.original_policy.name,
                            "description": p.original_policy.description[:100] + "..." if len(p.original_policy.description) > 100 else p.original_policy.description,
                            "validation_passed": any(r.policy_name == p.original_policy.name and r.passed for r in validation_results)
                        }
                        for p in policies
                    ]
                }
            
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(yaml.dump(index, default_flow_style=False))
            
            return index_file
            
        except Exception as e:
            self.logger.error(f"Error creating category index: {e}")
            raise FileSystemError(f"Failed to create category index: {e}")
    
    def _sanitize_category_name(self, category: str) -> str:
        """Sanitize category name for directory creation."""
        return category.lower().replace(' ', '-').replace('_', '-')
    
    def _sanitize_policy_name(self, policy_name: str) -> str:
        """Sanitize policy name for directory creation."""
        return policy_name.lower().replace(' ', '-').replace('_', '-')
    
    def _generate_sample_resource(self, policy: RecommendedPolicy) -> str:
        """Generate sample resource for testing the policy."""
        try:
            # Parse policy to understand what resources it targets
            policy_data = yaml.safe_load(policy.customized_content)
            policy_name = policy.original_policy.name
            
            # Special handling for specific policies
            if "service-mesh-require-run-as-nonroot" in policy_name:
                return self._generate_service_mesh_test_resources()
            elif "disallow-default-namespace" in policy_name:
                return self._generate_namespace_test_resources()
            
            # Extract resource kinds from policy rules
            resource_kinds = set()
            rules = policy_data.get("spec", {}).get("rules", [])
            
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
            
            # Generate sample resource for the first kind found
            if resource_kinds:
                kind = list(resource_kinds)[0]
                return self._generate_resource_template(kind)
            else:
                return self._generate_resource_template("Pod")
                
        except Exception as e:
            self.logger.error(f"Error generating sample resource: {e}")
            return self._generate_resource_template("Pod")
    
    def _generate_service_mesh_test_resources(self) -> str:
        """Generate test resources for service mesh policies."""
        return """apiVersion: v1
kind: Pod
metadata:
  name: good-pod
  namespace: default
  labels:
    app: test-app
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
  containers:
  - name: app-container
    image: nginx:latest
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
---
apiVersion: v1
kind: Pod
metadata:
  name: bad-pod
  namespace: default
  labels:
    app: test-app
spec:
  containers:
  - name: app-container
    image: nginx:latest
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
"""
    
    def _generate_namespace_test_resources(self) -> str:
        """Generate test resources for namespace policies."""
        return """apiVersion: v1
kind: Pod
metadata:
  name: badpod01
  namespace: default
  labels:
    app: myapp
spec:
  containers:
  - name: nginx
    image: nginx
---
apiVersion: v1
kind: Pod
metadata:
  name: goodpod01
  namespace: foo
  labels:
    app: myapp
spec:
  containers:
  - name: nginx
    image: nginx
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: baddeployment01
  labels:
    app: busybox
spec:
  replicas: 1
  selector:
    matchLabels:
      app: busybox
  template:
    metadata:
      labels:
        app: busybox
    spec:
      containers:
      - image: busybox:1.28
        name: busybox
        command: ["sleep", "9999"]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gooddeployment01
  labels:
    app: busybox
  namespace: foo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: busybox
  template:
    metadata:
      labels:
        app: busybox
    spec:
      containers:
      - image: busybox:1.28
        name: busybox
        command: ["sleep", "9999"]
"""
    
    def _generate_resource_template(self, kind: str) -> str:
        """Generate resource template for specific kind."""
        templates = {
            "Pod": """apiVersion: v1
kind: Pod
metadata:
  name: test-pod
  namespace: default
  labels:
    app: test-app
spec:
  containers:
  - name: test-container
    image: nginx:latest
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
""",
            "Deployment": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-deployment
  namespace: default
  labels:
    app: test-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-app
  template:
    metadata:
      labels:
        app: test-app
    spec:
      containers:
      - name: test-container
        image: nginx:latest
        resources:
          requests:
            memory: "64Mi"
            cpu: "250m"
          limits:
            memory: "128Mi"
            cpu: "500m"
""",
            "Service": """apiVersion: v1
kind: Service
metadata:
  name: test-service
  namespace: default
spec:
  selector:
    app: test-app
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
""",
            "Ingress": """apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: test-ingress
  namespace: default
spec:
  rules:
  - host: example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: test-service
            port:
              number: 80
"""
        }
        
        return templates.get(kind, templates["Pod"])
    
    def _create_policy_metadata(self, policy: RecommendedPolicy, 
                              validation_result: Optional[ValidationResult]) -> Dict[str, Any]:
        """Create metadata for a policy."""
        metadata = {
            "policy_name": policy.original_policy.name,
            "category": policy.category or policy.original_policy.category,
            "description": policy.original_policy.description,
            "source_repository": policy.original_policy.source_repo,
            "tags": policy.original_policy.tags,
            "customizations_applied": policy.customizations_applied,
            "validation": {
                "status": validation_result.passed if validation_result else "unknown",
                "errors": validation_result.errors if validation_result else [],
                "warnings": validation_result.warnings if validation_result else [],
                "automatically_fixed": bool(validation_result.fixed_content) if validation_result else False
            },
            "files": {
                "policy": os.path.basename(policy.original_policy.relative_path),
                "test": "kyverno-test.yaml" if (policy.test_content or policy.original_policy.test_directory) else None,
                "sample_resource": "resource.yaml"
            }
        }
        
        return metadata
    
    def _get_category_description(self, category: str) -> str:
        """Get description for a category."""
        descriptions = {
            "best-practices": "General Kubernetes best practices and operational excellence policies",
            "security": "Security-focused policies for workload and cluster protection",
            "compliance": "Compliance framework policies for regulatory requirements",
            "network-security": "Network security and ingress/egress control policies",
            "resource-management": "Resource allocation and management policies",
            "workload-security": "Workload-specific security and runtime policies",
            "storage-management": "Storage and persistent volume management policies",
            "security-and-compliance": "Combined security and compliance policies"
        }
        
        return descriptions.get(category, f"Policies related to {category.replace('-', ' ')}")
    
    def _generate_validation_recommendations(self, validation_results: List[ValidationResult]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        failed_count = sum(1 for r in validation_results if not r.passed)
        fixed_count = sum(1 for r in validation_results if r.fixed_content)
        
        if failed_count > 0:
            recommendations.append(f"{failed_count} policies failed validation - review errors before deployment")
        
        if fixed_count > 0:
            recommendations.append(f"{fixed_count} policies were automatically fixed - review changes before deployment")
        
        if failed_count == 0:
            recommendations.append("All policies passed validation - ready for deployment")
        
        recommendations.append("Test policies in audit mode before enforcing")
        recommendations.append("Review policy customizations to ensure they match your requirements")
        
        return recommendations
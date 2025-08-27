"""
Policy Retriever for AEGIS.
Handles copying selected policies and test cases using relative paths.
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any

from models import PolicyCatalogEntry, RecommendedPolicy
from exceptions import CatalogError
from utils.file_utils import FileUtils
from utils.yaml_utils import YamlUtils
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class PolicyRetriever:
    """Retrieves and copies selected policies with their test cases."""
    
    def __init__(self, catalog_path: str, output_path: str):
        """Initialize policy retriever."""
        self.catalog_path = catalog_path
        self.output_path = output_path
        
        # Ensure output directory exists
        FileUtils.ensure_directory(self.output_path)
    
    def retrieve_policies(self, selected_policies: List[PolicyCatalogEntry], 
                         categories: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """Retrieve selected policies and organize them by category."""
        try:
            logger.info(f"Retrieving {len(selected_policies)} policies")
            
            retrieved_files = {}
            
            for policy in selected_policies:
                try:
                    # Determine output category
                    output_category = self._determine_output_category(policy, categories)
                    
                    # Copy policy file
                    policy_dest = self._copy_policy_file(policy, output_category)
                    
                    # Copy test files if they exist
                    test_files = self._copy_test_files(policy, output_category)
                    
                    # Track retrieved files
                    if output_category not in retrieved_files:
                        retrieved_files[output_category] = []
                    
                    retrieved_files[output_category].append(policy_dest)
                    retrieved_files[output_category].extend(test_files)
                    
                    logger.debug(f"Retrieved policy: {policy.name} -> {output_category}")
                    
                except Exception as e:
                    logger.error(f"Failed to retrieve policy {policy.name}: {str(e)}")
                    continue
            
            logger.info(f"Successfully retrieved policies into {len(retrieved_files)} categories")
            return retrieved_files
            
        except Exception as e:
            logger.error(f"Failed to retrieve policies: {str(e)}")
            raise CatalogError("Failed to retrieve policies", str(e))
    
    def retrieve_recommended_policies(self, recommended_policies: List[RecommendedPolicy]) -> Dict[str, List[str]]:
        """Retrieve recommended policies with customizations applied."""
        try:
            logger.info(f"Retrieving {len(recommended_policies)} recommended policies")
            
            retrieved_files = {}
            
            for rec_policy in recommended_policies:
                try:
                    # Use the category from the recommendation
                    category = rec_policy.category or rec_policy.original_policy.category
                    
                    # Create customized policy file
                    policy_dest = self._create_customized_policy_file(rec_policy, category)
                    
                    # Create test file if available
                    test_files = self._create_test_files(rec_policy, category)
                    
                    # Track retrieved files
                    if category not in retrieved_files:
                        retrieved_files[category] = []
                    
                    retrieved_files[category].append(policy_dest)
                    retrieved_files[category].extend(test_files)
                    
                    logger.debug(f"Retrieved recommended policy: {rec_policy.original_policy.name} -> {category}")
                    
                except Exception as e:
                    logger.error(f"Failed to retrieve recommended policy {rec_policy.original_policy.name}: {str(e)}")
                    continue
            
            logger.info(f"Successfully retrieved recommended policies into {len(retrieved_files)} categories")
            return retrieved_files
            
        except Exception as e:
            logger.error(f"Failed to retrieve recommended policies: {str(e)}")
            raise CatalogError("Failed to retrieve recommended policies", str(e))
    
    def copy_policy_subset(self, policies: List[PolicyCatalogEntry], 
                          destination: str, preserve_structure: bool = True) -> List[str]:
        """Copy a subset of policies to a specific destination."""
        try:
            logger.info(f"Copying {len(policies)} policies to {destination}")
            
            FileUtils.ensure_directory(destination)
            copied_files = []
            
            for policy in policies:
                try:
                    source_path = os.path.join(self.catalog_path, policy.relative_path)
                    
                    if preserve_structure:
                        # Preserve directory structure
                        dest_path = os.path.join(destination, policy.relative_path)
                    else:
                        # Flat structure
                        filename = os.path.basename(policy.relative_path)
                        dest_path = os.path.join(destination, filename)
                    
                    # Copy policy file
                    FileUtils.copy_file(source_path, dest_path, create_dirs=True)
                    copied_files.append(dest_path)
                    
                    # Copy test files if they exist
                    if policy.test_directory:
                        test_source_dir = os.path.join(self.catalog_path, policy.test_directory)
                        if os.path.exists(test_source_dir):
                            # Copy all test files from the test directory
                            test_files = ['kyverno-test.yaml', 'resource.yaml', 'resources.yaml', 'values.yaml']
                            for test_file in test_files:
                                test_file_path = os.path.join(test_source_dir, test_file)
                                if os.path.exists(test_file_path):
                                    if preserve_structure:
                                        test_dest = os.path.join(destination, policy.test_directory, test_file)
                                    else:
                                        test_dest = os.path.join(destination, test_file)
                                    
                                    FileUtils.copy_file(test_file_path, test_dest, create_dirs=True)
                                    copied_files.append(test_dest)

                    
                    logger.debug(f"Copied policy: {policy.name}")
                    
                except Exception as e:
                    logger.error(f"Failed to copy policy {policy.name}: {str(e)}")
                    continue
            
            logger.info(f"Successfully copied {len(copied_files)} files")
            return copied_files
            
        except Exception as e:
            logger.error(f"Failed to copy policy subset: {str(e)}")
            raise CatalogError("Failed to copy policy subset", str(e))
    
    def create_category_structure(self, categories: List[str]) -> Dict[str, str]:
        """Create directory structure for categories."""
        try:
            category_paths = {}
            
            for category in categories:
                category_path = os.path.join(self.output_path, category)
                FileUtils.ensure_directory(category_path)
                category_paths[category] = category_path
                logger.debug(f"Created category directory: {category}")
            
            return category_paths
            
        except Exception as e:
            logger.error(f"Failed to create category structure: {str(e)}")
            raise CatalogError("Failed to create category structure", str(e))
    
    def _determine_output_category(self, policy: PolicyCatalogEntry, 
                                  categories: Optional[List[str]]) -> str:
        """Determine output category for policy."""
        if categories and policy.category in categories:
            return policy.category
        elif categories:
            # Map to closest category
            category_mapping = {
                'best-practices': ['best-practices', 'bestpractices', 'best_practices'],
                'security': ['security', 'sec', 'pod-security', 'pss'],
                'compliance': ['compliance', 'cis', 'nist', 'pci', 'hipaa'],
                'networking': ['networking', 'network', 'ingress'],
                'storage': ['storage', 'volume', 'pv', 'pvc'],
                'rbac': ['rbac', 'role', 'auth'],
                'workload': ['workload', 'pod', 'deployment'],
                'other': []
            }
            
            policy_category_lower = policy.category.lower()
            for target_category, keywords in category_mapping.items():
                if target_category in categories and any(keyword in policy_category_lower for keyword in keywords):
                    return target_category
            
            # Default to first category if no match
            return categories[0] if categories else policy.category
        
        return policy.category
    
    def _copy_policy_file(self, policy: PolicyCatalogEntry, output_category: str) -> str:
        """Copy policy file to output directory."""
        source_path = os.path.join(self.catalog_path, policy.relative_path)
        
        # Create filename for output
        filename = f"{policy.name}.yaml"
        dest_path = os.path.join(self.output_path, output_category, filename)
        
        # Copy file
        FileUtils.copy_file(source_path, dest_path, create_dirs=True)
        
        return dest_path
    
    def _copy_test_files(self, policy: PolicyCatalogEntry, output_category: str) -> List[str]:
        """Copy test files associated with policy from test directory."""
        test_files = []
        
        if not policy.test_directory:
            return test_files
        
        try:
            test_source_dir = os.path.join(self.catalog_path, policy.test_directory)
            if os.path.exists(test_source_dir):
                # Copy all test files from the test directory
                test_file_names = ['kyverno-test.yaml', 'resource.yaml', 'resources.yaml', 'values.yaml']
                for test_file_name in test_file_names:
                    test_file_path = os.path.join(test_source_dir, test_file_name)
                    if os.path.exists(test_file_path):
                        test_dest = os.path.join(self.output_path, output_category, f"{policy.name}-{test_file_name}")
                        FileUtils.copy_file(test_file_path, test_dest, create_dirs=True)
                        test_files.append(test_dest)
            
        except Exception as e:
            logger.warning(f"Failed to copy test files for {policy.name}: {str(e)}")
        
        return test_files
    
    def _find_test_resource_files(self, test_file: str, test_dir: str) -> List[str]:
        """Find resource files referenced in test file."""
        resource_files = []
        
        try:
            test_content = YamlUtils.load_yaml_safe(test_file)
            
            # Get resources and variables from test file
            resources = test_content.get('resources', [])
            variables = test_content.get('variables', [])
            
            all_refs = resources + variables
            
            for ref in all_refs:
                if isinstance(ref, str):
                    # Handle relative paths
                    if ref.startswith('./') or not ref.startswith('/'):
                        resource_path = os.path.join(test_dir, ref)
                        if os.path.exists(resource_path):
                            resource_files.append(resource_path)
            
        except Exception as e:
            logger.warning(f"Failed to parse test file {test_file}: {str(e)}")
        
        return resource_files
    
    def _create_customized_policy_file(self, rec_policy: RecommendedPolicy, category: str) -> str:
        """Create customized policy file from recommended policy."""
        filename = f"{rec_policy.original_policy.name}.yaml"
        dest_path = os.path.join(self.output_path, category, filename)
        
        # Write customized content
        FileUtils.write_file(dest_path, rec_policy.customized_content, create_dirs=True)
        
        return dest_path
    
    def _create_test_files(self, rec_policy: RecommendedPolicy, category: str) -> List[str]:
        """Create test files for recommended policy."""
        test_files = []
        
        if rec_policy.test_content:
            test_filename = f"{rec_policy.original_policy.name}-test.yaml"
            test_dest = os.path.join(self.output_path, category, test_filename)
            
            FileUtils.write_file(test_dest, rec_policy.test_content, create_dirs=True)
            test_files.append(test_dest)
        
        return test_files
    
    def cleanup_output_directory(self) -> None:
        """Clean up output directory."""
        try:
            if os.path.exists(self.output_path):
                FileUtils.remove_directory(self.output_path)
                logger.info(f"Cleaned up output directory: {self.output_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup output directory: {str(e)}")
    
    def get_retrieval_summary(self, retrieved_files: Dict[str, List[str]]) -> Dict[str, Any]:
        """Get summary of retrieved files."""
        summary = {
            'total_files': sum(len(files) for files in retrieved_files.values()),
            'categories': len(retrieved_files),
            'category_breakdown': {
                category: len(files) for category, files in retrieved_files.items()
            }
        }
        
        return summary
    
    def validate_retrieved_policies(self, retrieved_files: Dict[str, List[str]]) -> Dict[str, Any]:
        """Validate that retrieved policy files are valid YAML."""
        validation_results = {
            'valid_files': 0,
            'invalid_files': 0,
            'errors': []
        }
        
        for category, files in retrieved_files.items():
            for file_path in files:
                try:
                    if file_path.endswith('.yaml'):
                        YamlUtils.load_yaml_safe(file_path)
                        validation_results['valid_files'] += 1
                except Exception as e:
                    validation_results['invalid_files'] += 1
                    validation_results['errors'].append({
                        'file': file_path,
                        'error': str(e)
                    })
        
        return validation_results
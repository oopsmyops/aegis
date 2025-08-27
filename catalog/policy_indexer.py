"""
Policy Indexer for AEGIS.
Creates lightweight metadata index for efficient policy selection and AI consumption.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from models import PolicyIndex, PolicyCatalogEntry
from exceptions import CatalogError
from utils.file_utils import FileUtils
from utils.yaml_utils import YamlUtils
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class PolicyIndexer:
    """Creates and manages lightweight policy metadata index."""
    
    def __init__(self, catalog_path: str, index_file: str):
        """Initialize policy indexer."""
        self.catalog_path = catalog_path
        self.index_file = index_file
    
    def create_index(self) -> PolicyIndex:
        """Create comprehensive policy index from catalog."""
        try:
            logger.info("Creating policy index from catalog")
            
            if not os.path.exists(self.catalog_path):
                raise CatalogError(f"Policy catalog not found: {self.catalog_path}")
            
            policy_index = PolicyIndex()
            
            # Scan all policy files
            policy_files = self._find_all_policy_files()
            
            for policy_file in policy_files:
                try:
                    policy_entry = self._analyze_policy_file(policy_file)
                    if policy_entry:
                        category = policy_entry.category
                        if category not in policy_index.categories:
                            policy_index.categories[category] = []
                        
                        policy_index.categories[category].append(policy_entry)
                        policy_index.total_policies += 1
                        
                        logger.debug(f"Indexed policy: {policy_entry.name} ({category})")
                
                except Exception as e:
                    logger.warning(f"Failed to index policy {policy_file}: {str(e)}")
                    continue
            
            # Sort policies within categories
            self._sort_policies_by_relevance(policy_index)
            
            # Save index
            self._save_index(policy_index)
            
            logger.info(f"Created index with {policy_index.total_policies} policies across {len(policy_index.categories)} categories")
            return policy_index
            
        except Exception as e:
            logger.error(f"Failed to create policy index: {str(e)}")
            raise CatalogError("Failed to create policy index", str(e))
    
    def load_index(self) -> Optional[PolicyIndex]:
        """Load existing policy index."""
        try:
            if not os.path.exists(self.index_file):
                logger.warning(f"Index file not found: {self.index_file}")
                return None
            
            with open(self.index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            return self._deserialize_index(index_data)
            
        except Exception as e:
            logger.error(f"Failed to load policy index: {str(e)}")
            return None
    
    def update_index(self) -> PolicyIndex:
        """Update existing index or create new one."""
        try:
            existing_index = self.load_index()
            
            # Check if catalog is newer than index
            if existing_index and self._is_index_current(existing_index):
                logger.info("Policy index is current, no update needed")
                return existing_index
            
            logger.info("Policy index is outdated, rebuilding")
            return self.create_index()
            
        except Exception as e:
            logger.error(f"Failed to update policy index: {str(e)}")
            raise CatalogError("Failed to update policy index", str(e))
    
    def get_category_summary(self) -> Dict[str, int]:
        """Get summary of policies per category."""
        try:
            index = self.load_index()
            if not index:
                return {}
            
            return {category: len(policies) for category, policies in index.categories.items()}
            
        except Exception as e:
            logger.error(f"Failed to get category summary: {str(e)}")
            return {}
    
    def get_all_policies_lightweight(self) -> List[Dict[str, Any]]:
        """Get all policies with minimal metadata for Phase 1 AI filtering."""
        try:
            index = self.load_index()
            if not index:
                return []
            
            lightweight_policies = []
            
            for category, policies in index.categories.items():
                for policy in policies:
                    lightweight_policies.append({
                        'name': policy.name,
                        'category': policy.category,
                        'tags': policy.tags[:5]  # Limit tags for lightweight processing
                    })
            
            logger.info(f"Retrieved {len(lightweight_policies)} policies with lightweight metadata")
            return lightweight_policies
            
        except Exception as e:
            logger.error(f"Failed to get lightweight policies: {str(e)}")
            return []
    
    def get_policies_detailed(self, policy_names: List[str]) -> List[Dict[str, Any]]:
        """Get detailed policy information for Phase 2 AI selection."""
        try:
            index = self.load_index()
            if not index:
                return []
            
            detailed_policies = []
            
            # Create a lookup map for faster searching
            policy_lookup = {}
            for category, policies in index.categories.items():
                for policy in policies:
                    policy_lookup[policy.name] = policy
            
            for policy_name in policy_names:
                if policy_name in policy_lookup:
                    policy = policy_lookup[policy_name]
                    detailed_policies.append({
                        'name': policy.name,
                        'category': policy.category,
                        'description': policy.description,
                        'relative_path': policy.relative_path,
                        'test_directory': policy.test_directory,
                        'source_repo': policy.source_repo,
                        'tags': policy.tags,
                        'has_tests': policy.test_directory is not None
                    })
            
            logger.info(f"Retrieved detailed information for {len(detailed_policies)} policies")
            return detailed_policies
            
        except Exception as e:
            logger.error(f"Failed to get detailed policies: {str(e)}")
            return []
    
    def search_policies(self, query: str, categories: Optional[List[str]] = None) -> List[PolicyCatalogEntry]:
        """Search policies by name, description, or tags."""
        try:
            index = self.load_index()
            if not index:
                return []
            
            query_lower = query.lower()
            results = []
            
            categories_to_search = categories or list(index.categories.keys())
            
            for category in categories_to_search:
                if category not in index.categories:
                    continue
                
                for policy in index.categories[category]:
                    # Search in name, description, and tags
                    if (query_lower in policy.name.lower() or
                        query_lower in policy.description.lower() or
                        any(query_lower in tag.lower() for tag in policy.tags)):
                        results.append(policy)
            
            # Sort by name for consistent ordering
            results.sort(key=lambda p: p.name.lower())
            return results
            
        except Exception as e:
            logger.error(f"Failed to search policies: {str(e)}")
            return []
    
    def _find_all_policy_files(self) -> List[str]:
        """Find all policy YAML files in catalog."""
        policy_files = []
        
        for root, dirs, files in os.walk(self.catalog_path):
            for file in files:
                if file.endswith('.yaml') and not self._is_test_file(file):
                    policy_files.append(os.path.join(root, file))
        return policy_files
    
    def _is_test_file(self, filename: str) -> bool:
        """Check if file is a test file."""
        # Exact matches for test files
        if filename in ['kyverno-test.yaml', 'resource.yaml', 'resources.yaml', 'values.yaml']:
            return True
        
        # Pattern matches for test files
        if filename.startswith('test-') or filename.endswith('-test.yaml'):
            return True
        
        # Check for chainsaw test directories
        if '.chainsaw-test' in filename:
            return True
            
        return False
    
    def _analyze_policy_file(self, policy_file: str) -> Optional[PolicyCatalogEntry]:
        """Analyze a policy file and create catalog entry."""
        try:
            # Load and validate policy content using safe loader for multi-document files
            policy_content = YamlUtils.load_yaml_safe(policy_file)
            
            if not self._is_valid_kyverno_policy(policy_content):
                return None
            
            # Extract basic information
            metadata = policy_content.get('metadata', {})
            name = metadata.get('name', os.path.basename(policy_file).replace('.yaml', ''))
            
            # Calculate relative path
            rel_path = os.path.relpath(policy_file, self.catalog_path)
            
            # Determine category
            category = self._categorize_policy(rel_path, policy_content)
            
            # Extract description
            description = self._extract_description(metadata)
            
            # Find test directory
            test_directory = self._find_test_directory(policy_file)
            
            # Extract tags
            tags = self._extract_tags(metadata, rel_path)
            
            # Determine source repository
            source_repo = self._determine_source_repo(rel_path)
            
            return PolicyCatalogEntry(
                name=name,
                category=category,
                description=description,
                relative_path=rel_path,
                test_directory=test_directory,
                source_repo=source_repo,
                tags=tags
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze policy file {policy_file}: {str(e)}")
            return None
    
    def _is_valid_kyverno_policy(self, content: Dict[str, Any]) -> bool:
        """Check if content is a valid Kyverno policy."""
        return (
            content.get('kind') in ['ClusterPolicy', 'Policy'] and
            content.get('apiVersion', '').startswith('kyverno.io/') and
            'spec' in content and
            'rules' in content.get('spec', {})
        )
    
    def _categorize_policy(self, rel_path: str, content: Dict[str, Any]) -> str:
        """Categorize policy based on path and content."""
        path_lower = rel_path.lower()
        
        # Path-based categorization
        path_categories = {
            'best-practices': ['best-practices', 'best_practices', 'bestpractices'],
            'security': ['security', 'sec', 'pss', 'pod-security'],
            'compliance': ['compliance', 'cis', 'nist', 'pci', 'hipaa', 'soc'],
            'networking': ['networking', 'network', 'ingress', 'service', 'networkpolicy'],
            'storage': ['storage', 'pv', 'pvc', 'volume', 'persistentvolume'],
            'rbac': ['rbac', 'role', 'rolebinding', 'serviceaccount', 'clusterrole'],
            'workload': ['workload', 'deployment', 'pod', 'job', 'cronjob', 'daemonset'],
            'resource-management': ['resources', 'limits', 'requests', 'quota', 'limitrange'],
            'configuration': ['config', 'configmap', 'secret', 'environment']
        }
        
        for category, keywords in path_categories.items():
            if any(keyword in path_lower for keyword in keywords):
                return category
        
        # Content-based categorization
        try:
            spec = content.get('spec', {})
            rules = spec.get('rules', [])
            
            for rule in rules:
                match_resources = []
                if 'match' in rule:
                    match_any = rule['match'].get('any', [])
                    match_all = rule['match'].get('all', [])
                    for match in match_any + match_all:
                        if 'resources' in match:
                            match_resources.extend(match['resources'].get('kinds', []))
                
                # Categorize based on resource types
                resource_categories = {
                    'networking': ['Service', 'Ingress', 'NetworkPolicy'],
                    'storage': ['PersistentVolume', 'PersistentVolumeClaim', 'StorageClass'],
                    'rbac': ['Role', 'RoleBinding', 'ClusterRole', 'ClusterRoleBinding', 'ServiceAccount'],
                    'workload': ['Pod', 'Deployment', 'StatefulSet', 'DaemonSet', 'Job', 'CronJob'],
                    'configuration': ['ConfigMap', 'Secret']
                }
                
                for category, resource_types in resource_categories.items():
                    if any(rt in match_resources for rt in resource_types):
                        return category
        
        except Exception:
            pass
        
        return 'other'
    
    def _extract_description(self, metadata: Dict[str, Any]) -> str:
        """Extract policy description from metadata."""
        annotations = metadata.get('annotations', {})
        
        # Try different annotation keys
        description_keys = [
            'policies.kyverno.io/description',
            'description',
            'policies.kyverno.io/title',
            'title'
        ]
        
        for key in description_keys:
            if key in annotations and annotations[key]:
                return annotations[key]
        
        # Fallback to policy name
        name = metadata.get('name', 'Unknown Policy')
        return f"Kyverno policy: {name}"
    
    def _find_test_directory(self, policy_file: str) -> Optional[str]:
        """Find directory containing test files for policy."""
        policy_dir = os.path.dirname(policy_file)
        
        # Check if there are any test files in the policy directory
        test_files = ['kyverno-test.yaml', 'resource.yaml', 'resources.yaml', 'values.yaml']
        has_test_files = any(os.path.exists(os.path.join(policy_dir, test_file)) for test_file in test_files)
        
        if has_test_files:
            return os.path.relpath(policy_dir, self.catalog_path)
        
        return None
    

    
    def _extract_tags(self, metadata: Dict[str, Any], rel_path: str) -> List[str]:
        """Extract tags from metadata and path."""
        tags = set()
        
        # Extract from annotations
        annotations = metadata.get('annotations', {})
        
        tag_sources = [
            'policies.kyverno.io/category',
            'policies.kyverno.io/subject',
            'policies.kyverno.io/title',
            'policies.kyverno.io/severity'
        ]
        
        for key in tag_sources:
            if key in annotations:
                value = annotations[key]
                if isinstance(value, str):
                    # Split by common delimiters
                    for delimiter in [',', ';', '|']:
                        if delimiter in value:
                            tags.update(tag.strip() for tag in value.split(delimiter))
                            break
                    else:
                        tags.add(value.strip())
        
        # Extract from path
        path_parts = rel_path.split(os.sep)[:-1]  # Exclude filename
        for part in path_parts:
            # Clean up path part
            clean_part = part.replace('-', ' ').replace('_', ' ')
            if clean_part and len(clean_part) > 2:
                tags.add(clean_part)
        
        # Clean and limit tags
        cleaned_tags = []
        for tag in tags:
            if tag and len(tag.strip()) > 1:
                cleaned_tags.append(tag.strip())
        
        return sorted(list(set(cleaned_tags)))[:10]  # Limit to 10 unique tags
    
    def _determine_source_repo(self, rel_path: str) -> str:
        """Determine source repository from path."""
        # Try to determine from common repository patterns
        path_lower = rel_path.lower()
        
        # Check for specific repository indicators in the path structure
        if any(indicator in path_lower for indicator in ['kyverno', 'best-practices', 'pod-security', 'pss']):
            return 'kyverno/policies'
        elif 'nirmata' in path_lower:
            return 'nirmata/kyverno-policies'
        else:
            # For now, assume kyverno/policies as it's the most common
            return 'kyverno/policies'
    
    def _sort_policies_by_relevance(self, policy_index: PolicyIndex) -> None:
        """Sort policies within each category by name for consistent ordering."""
        for category in policy_index.categories:
            policy_index.categories[category].sort(key=lambda p: p.name.lower())
    
    def _save_index(self, policy_index: PolicyIndex) -> None:
        """Save policy index to file."""
        try:
            index_data = self._serialize_index(policy_index)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
            
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Policy index saved to {self.index_file}")
            
        except Exception as e:
            logger.error(f"Failed to save policy index: {str(e)}")
            raise CatalogError("Failed to save policy index", str(e))
    
    def _serialize_index(self, policy_index: PolicyIndex) -> Dict[str, Any]:
        """Serialize policy index to dictionary."""
        return {
            'metadata': {
                'total_policies': policy_index.total_policies,
                'last_updated': policy_index.last_updated.isoformat(),
                'categories_count': len(policy_index.categories)
            },
            'categories': {
                category: [
                    {
                        'name': policy.name,
                        'category': policy.category,
                        'description': policy.description,
                        'relative_path': policy.relative_path,
                        'test_directory': policy.test_directory,
                        'source_repo': policy.source_repo,
                        'tags': policy.tags
                    }
                    for policy in policies
                ]
                for category, policies in policy_index.categories.items()
            }
        }
    
    def _deserialize_index(self, index_data: Dict[str, Any]) -> PolicyIndex:
        """Deserialize policy index from dictionary."""
        policy_index = PolicyIndex()
        
        metadata = index_data.get('metadata', {})
        policy_index.total_policies = metadata.get('total_policies', 0)
        policy_index.last_updated = datetime.fromisoformat(
            metadata.get('last_updated', datetime.now().isoformat())
        )
        
        categories_data = index_data.get('categories', {})
        for category, policies_data in categories_data.items():
            policies = []
            for policy_data in policies_data:
                policy = PolicyCatalogEntry(
                    name=policy_data['name'],
                    category=policy_data['category'],
                    description=policy_data['description'],
                    relative_path=policy_data['relative_path'],
                    test_directory=policy_data.get('test_directory') or policy_data.get('test_path'),
                    source_repo=policy_data.get('source_repo', ''),
                    tags=policy_data.get('tags', [])
                )
                policies.append(policy)
            policy_index.categories[category] = policies
        
        return policy_index
    
    def _is_index_current(self, policy_index: PolicyIndex) -> bool:
        """Check if index is current compared to catalog."""
        try:
            # Get catalog modification time
            catalog_mtime = os.path.getmtime(self.catalog_path)
            catalog_datetime = datetime.fromtimestamp(catalog_mtime)
            
            # Compare with index timestamp
            return policy_index.last_updated >= catalog_datetime
            
        except Exception:
            # If we can't determine, assume index is outdated
            return False
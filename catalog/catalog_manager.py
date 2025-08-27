"""
Policy Catalog Manager for AEGIS.
Manages policy catalog creation from GitHub repositories and provides indexing functionality.
"""

import os
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from models import PolicyIndex, PolicyCatalogEntry
from interfaces import PolicyCatalogInterface
from exceptions import CatalogError
from utils.file_utils import FileUtils
from utils.yaml_utils import YamlUtils
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class PolicyCatalogManager(PolicyCatalogInterface):
    """Main policy catalog management class."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize catalog manager with configuration."""
        self.config = config
        self.catalog_config = config.get('catalog', {})
        self.local_storage = self.catalog_config.get('local_storage', './policy-catalog')
        # Default index file inside the catalog directory
        default_index_file = os.path.join(self.local_storage, 'policy-index.json')
        self.index_file = self.catalog_config.get('index_file', default_index_file)
        self.repositories = self.catalog_config.get('repositories', [])
        
        # Ensure directories exist
        FileUtils.ensure_directory(self.local_storage)
        FileUtils.ensure_directory(os.path.dirname(self.index_file))
    
    def create_catalog_from_repos(self, repo_urls: Optional[List[str]] = None) -> None:
        """Create policy catalog from GitHub repositories using adapted bash script logic."""
        try:
            logger.info("Starting policy catalog creation from repositories")
            
            # Use provided URLs or fall back to config
            repos_to_process = repo_urls or self.repositories
            if not repos_to_process:
                raise CatalogError("No repositories specified for catalog creation")
            
            # Update index file path to be inside the catalog directory
            self.index_file = os.path.join(self.local_storage, 'policy-index.json')
            
            # Clean up existing catalog
            self._cleanup_existing_catalog()
            
            # Process each repository
            source_dirs = []
            for repo_config in repos_to_process:
                if isinstance(repo_config, str):
                    # Simple URL string
                    repo_dir = self._clone_repository(repo_config, "main")
                else:
                    # Dictionary with url and branch
                    url = repo_config.get('url')
                    branch = repo_config.get('branch', 'main')
                    repo_dir = self._clone_repository(url, branch)
                
                if repo_dir:
                    source_dirs.append(repo_dir)
            
            # Process policies from cloned repositories with repo info
            repo_info = {}
            for i, repo_config in enumerate(repos_to_process):
                if isinstance(repo_config, str):
                    repo_url = repo_config
                else:
                    repo_url = repo_config.get('url')
                
                if i < len(source_dirs):
                    repo_info[source_dirs[i]] = repo_url  # Store full HTTPS URL for GitLab/GitHub/etc support
            
            self._process_policy_repositories(source_dirs, repo_info)
            
            # Clean up cloned repositories
            self._cleanup_cloned_repos(source_dirs)
            
            logger.info(f"Policy catalog created successfully at {self.local_storage}")
            
        except Exception as e:
            logger.error(f"Failed to create policy catalog: {str(e)}")
            raise CatalogError("Failed to create policy catalog", str(e))
    
    def build_policy_index(self) -> PolicyIndex:
        """Build lightweight metadata index with policy paths and summaries."""
        try:
            logger.info("Building policy index")
            
            if not os.path.exists(self.local_storage):
                raise CatalogError(f"Policy catalog directory not found: {self.local_storage}")
            
            policy_index = PolicyIndex()
            
            # Find all policy files in the catalog
            policy_files = FileUtils.list_files(
                self.local_storage, 
                "*.yaml", 
                recursive=True
            )
            
            for policy_file in policy_files:
                try:
                    # Skip test files and resource files
                    filename = os.path.basename(policy_file)
                    if (filename in ['kyverno-test.yaml', 'resource.yaml', 'resources.yaml'] or
                        filename.startswith('test-') or filename.endswith('-test.yaml') or
                        '.chainsaw-test' in policy_file or filename.endswith('-bad.yaml') or
                        filename.endswith('-good.yaml')):
                        continue
                    
                    policy_entry = self._create_policy_entry(policy_file)
                    if policy_entry:
                        category = policy_entry.category
                        if category not in policy_index.categories:
                            policy_index.categories[category] = []
                        policy_index.categories[category].append(policy_entry)
                        policy_index.total_policies += 1
                
                except Exception as e:
                    logger.warning(f"Failed to process policy file {policy_file}: {str(e)}")
                    continue
            
            # Sort policies within each category by name for consistent ordering
            for category in policy_index.categories:
                policy_index.categories[category].sort(key=lambda p: p.name.lower())
            
            # Save index to file
            self._save_policy_index(policy_index)
            
            logger.info(f"Policy index built with {policy_index.total_policies} policies across {len(policy_index.categories)} categories")
            return policy_index
            
        except Exception as e:
            logger.error(f"Failed to build policy index: {str(e)}")
            raise CatalogError("Failed to build policy index", str(e))
    
    def get_all_policies_lightweight(self) -> List[Dict[str, Any]]:
        """Get all policies with minimal metadata for Phase 1 AI filtering."""
        try:
            logger.info("Getting all policies with lightweight metadata for Phase 1 filtering")
            
            # Load existing index
            policy_index = self._load_policy_index()
            if not policy_index:
                raise CatalogError("Policy index not found. Please build the catalog first.")
            
            lightweight_policies = []
            
            for category, policies in policy_index.categories.items():
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
            raise CatalogError("Failed to get lightweight policies", str(e))
    
    def get_policies_detailed(self, policy_names: List[str]) -> List[Dict[str, Any]]:
        """Get detailed policy information for Phase 2 AI selection."""
        try:
            logger.info(f"Getting detailed information for {len(policy_names)} policies for Phase 2 selection")
            
            # Load existing index
            policy_index = self._load_policy_index()
            if not policy_index:
                raise CatalogError("Policy index not found. Please build the catalog first.")
            
            detailed_policies = []
            
            # Create a lookup map for faster searching
            policy_lookup = {}
            for category, policies in policy_index.categories.items():
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
                else:
                    logger.warning(f"Policy not found in index: {policy_name}")
            
            logger.info(f"Retrieved detailed information for {len(detailed_policies)} policies")
            return detailed_policies
            
        except Exception as e:
            logger.error(f"Failed to get detailed policies: {str(e)}")
            raise CatalogError("Failed to get detailed policies", str(e))
    
    def _cleanup_existing_catalog(self) -> None:
        """Remove existing policy catalog directory."""
        if os.path.exists(self.local_storage):
            logger.info(f"Removing existing policy catalog: {self.local_storage}")
            FileUtils.remove_directory(self.local_storage)
        
        # Recreate directory
        FileUtils.ensure_directory(self.local_storage)
    
    def _clone_repository(self, url: str, branch: str) -> Optional[str]:
        """Clone a Git repository to temporary directory (GitHub, GitLab, etc.)."""
        try:
            # Generate repository directory name
            repo_name = self._get_repo_name_from_url(url)
            temp_dir = os.path.join(tempfile.gettempdir(), f"aegis_repo_{repo_name}")
            
            # Remove if exists
            if os.path.exists(temp_dir):
                FileUtils.remove_directory(temp_dir)
            
            # Clone repository
            cmd = [
                'git', 'clone', 
                '--depth', '1', 
                '--branch', branch, 
                url, temp_dir
            ]
            
            logger.info(f"Cloning repository {url} (branch: {branch})")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                logger.error(f"Failed to clone repository {url}: {result.stderr}")
                return None
            
            logger.info(f"Successfully cloned {url} to {temp_dir}")
            return temp_dir
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout cloning repository {url}")
            return None
        except Exception as e:
            logger.error(f"Error cloning repository {url}: {str(e)}")
            return None
    
    def _get_repo_name_from_url(self, url: str) -> str:
        """Extract repository name from Git URL (GitHub, GitLab, etc.)."""
        # Handle both https and git URLs
        if url.endswith('.git'):
            url = url[:-4]
        
        parts = url.rstrip('/').split('/')
        if len(parts) >= 2:
            owner = parts[-2]
            repo = parts[-1]
            return f"{owner}-{repo}"
        
        return "unknown-repo"
    
    def _process_policy_repositories(self, source_dirs: List[str], repo_info: Dict[str, str]) -> None:
        """Process cloned repositories to extract policies and tests."""
        # Store repo info for later use during indexing
        self._repo_info = repo_info
        
        for source_dir in source_dirs:
            repo_name = repo_info.get(source_dir, 'unknown')
            logger.info(f"Processing repository: {source_dir} ({repo_name})")
            
            try:
                # Find policy files using grep (adapted from bash script)
                policy_files = self._find_policy_files(source_dir)
                
                # Copy policy files preserving directory structure
                self._copy_policy_files(source_dir, policy_files)
                
                # Copy associated test files
                self._copy_test_files(source_dir, policy_files)
                
                logger.info(f"Successfully processed repository: {source_dir}")
                
            except Exception as e:
                logger.error(f"Failed to process repository {source_dir}: {str(e)}")
                continue
    
    def _find_policy_files(self, source_dir: str) -> List[str]:
        """Find Kyverno policy files in the repository."""
        try:
            # Use grep to find files with ClusterPolicy kind and validationFailureAction
            cmd1 = [
                'grep', '-r', '--exclude-dir=.*', '--include=*.yaml',
                '-l', '-e', 'kind: ClusterPolicy$', source_dir
            ]
            
            result1 = subprocess.run(cmd1, capture_output=True, text=True)
            if result1.returncode != 0:
                return []
            
            candidate_files = result1.stdout.strip().split('\n')
            if not candidate_files or candidate_files == ['']:
                return []
            
            # Filter files that also contain validationFailureAction
            cmd2 = ['grep', '-l', '-e', 'validationFailureAction'] + candidate_files
            result2 = subprocess.run(cmd2, capture_output=True, text=True)
            
            if result2.returncode != 0:
                return []
            
            policy_files = result2.stdout.strip().split('\n')
            return [f for f in policy_files if f]
            
        except Exception as e:
            logger.error(f"Error finding policy files in {source_dir}: {str(e)}")
            return []
    
    def _copy_policy_files(self, source_dir: str, policy_files: List[str]) -> None:
        """Copy policy files to catalog preserving directory structure."""
        for policy_file in policy_files:
            try:
                # Calculate relative path from source directory
                rel_path = os.path.relpath(policy_file, source_dir)
                dest_path = os.path.join(self.local_storage, rel_path)
                
                # Copy file
                FileUtils.copy_file(policy_file, dest_path, create_dirs=True)
                logger.debug(f"Copied policy file: {rel_path}")
                
            except Exception as e:
                logger.error(f"Failed to copy policy file {policy_file}: {str(e)}")
                continue
    
    def _copy_test_files(self, source_dir: str, policy_files: List[str]) -> None:
        """Copy test files associated with policies."""
        # Get unique policy directories to avoid processing the same directory multiple times
        policy_dirs = set()
        for policy_file in policy_files:
            policy_dir = os.path.dirname(policy_file)
            rel_policy_dir = os.path.relpath(policy_dir, source_dir)
            policy_dirs.add((policy_dir, rel_policy_dir))
        
        for policy_dir, rel_policy_dir in policy_dirs:
            try:
                dest_policy_dir = os.path.join(self.local_storage, rel_policy_dir)
                
                # Check for .kyverno-test/kyverno-test.yaml (priority case)
                kyverno_test_dir = os.path.join(policy_dir, '.kyverno-test')
                kyverno_test_file = os.path.join(kyverno_test_dir, 'kyverno-test.yaml')
                
                if os.path.exists(kyverno_test_file):
                    self._copy_kyverno_test_files(source_dir, policy_dir, kyverno_test_dir, dest_policy_dir)
                
                # Check for direct kyverno-test.yaml and resource.yaml (fallback case)
                elif os.path.exists(os.path.join(policy_dir, 'kyverno-test.yaml')):
                    self._copy_direct_test_files(policy_dir, dest_policy_dir, rel_policy_dir)
                
            except Exception as e:
                logger.error(f"Failed to copy test files for directory {rel_policy_dir}: {str(e)}")
                continue
    
    def _copy_kyverno_test_files(self, source_dir: str, policy_dir: str, kyverno_test_dir: str, dest_policy_dir: str) -> None:
        """Copy .kyverno-test directory contents with path adjustments."""
        try:
            kyverno_test_file = os.path.join(kyverno_test_dir, 'kyverno-test.yaml')
            dest_test_file = os.path.join(dest_policy_dir, 'kyverno-test.yaml')
            
            # Copy and modify the test file (remove ../ references as per bash script)
            test_content = FileUtils.read_file(kyverno_test_file)
            modified_content = test_content.replace('../', '')
            FileUtils.write_file(dest_test_file, modified_content)
            logger.debug(f"Copied and modified test file: kyverno-test.yaml")
            
            # Parse test file to find resource and variable files
            try:
                test_data = YamlUtils.load_yaml_safe(kyverno_test_file)
                resources = test_data.get('resources', [])
                variables = test_data.get('variables', [])
                
                # Ensure both are lists before concatenating
                if not isinstance(resources, list):
                    resources = [resources] if resources else []
                if not isinstance(variables, list):
                    variables = [variables] if variables else []
                
                # Process resources first, then variables (matching bash script logic)
                all_resource_refs = resources + variables
                
                for resource_ref in all_resource_refs:
                    if isinstance(resource_ref, str) and resource_ref.strip():
                        # Handle relative paths from .kyverno-test directory
                        resource_source_path = os.path.join(kyverno_test_dir, resource_ref)
                        
                        if os.path.exists(resource_source_path):
                            # Clean the destination path (remove ../ references)
                            clean_resource_path = resource_ref.replace('../', '')
                            
                            # Create destination directory structure
                            dest_resource_path = os.path.join(dest_policy_dir, clean_resource_path)
                            dest_resource_dir = os.path.dirname(dest_resource_path)
                            
                            # Copy the resource file
                            FileUtils.copy_file(resource_source_path, dest_resource_path, create_dirs=True)
                            logger.debug(f"Copied test resource: {clean_resource_path}")
                        else:
                            logger.debug(f"Resource file not found: {resource_source_path}")
                
            except Exception as e:
                logger.warning(f"Failed to parse test file resources: {str(e)}")
            
        except Exception as e:
            logger.error(f"Failed to copy kyverno test files: {str(e)}")
    
    def _copy_direct_test_files(self, policy_dir: str, dest_policy_dir: str, rel_policy_dir: str) -> None:
        """Copy direct test files (kyverno-test.yaml and resource.yaml in same directory)."""
        try:
            # Copy kyverno-test.yaml
            direct_test_file = os.path.join(policy_dir, 'kyverno-test.yaml')
            if os.path.exists(direct_test_file):
                FileUtils.copy_file(direct_test_file, os.path.join(dest_policy_dir, 'kyverno-test.yaml'))
                logger.debug(f"Copied direct test file: {os.path.join(rel_policy_dir, 'kyverno-test.yaml')}")
            
            # Copy resource.yaml if it exists
            resource_file = os.path.join(policy_dir, 'resource.yaml')
            if os.path.exists(resource_file):
                FileUtils.copy_file(resource_file, os.path.join(dest_policy_dir, 'resource.yaml'))
                logger.debug(f"Copied resource file: {os.path.join(rel_policy_dir, 'resource.yaml')}")
            
            # Copy values.yaml if it exists (some policies use this)
            values_file = os.path.join(policy_dir, 'values.yaml')
            if os.path.exists(values_file):
                FileUtils.copy_file(values_file, os.path.join(dest_policy_dir, 'values.yaml'))
                logger.debug(f"Copied values file: {os.path.join(rel_policy_dir, 'values.yaml')}")
                
        except Exception as e:
            logger.error(f"Failed to copy direct test files for {rel_policy_dir}: {str(e)}")
    
    def _cleanup_cloned_repos(self, source_dirs: List[str]) -> None:
        """Clean up cloned repository directories."""
        for source_dir in source_dirs:
            try:
                if os.path.exists(source_dir):
                    FileUtils.remove_directory(source_dir)
                    logger.debug(f"Cleaned up repository: {source_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup repository {source_dir}: {str(e)}")
    
    def _create_policy_entry(self, policy_file: str) -> Optional[PolicyCatalogEntry]:
        """Create a PolicyCatalogEntry from a policy file."""
        try:
            # Load policy content using safe loader for multi-document files
            policy_content = YamlUtils.load_yaml_safe(policy_file)
            
            # Check if this is a valid Kyverno policy
            if not self._is_valid_kyverno_policy(policy_content):
                return None
            
            # Extract metadata
            metadata = policy_content.get('metadata', {})
            name = metadata.get('name', os.path.basename(policy_file).replace('.yaml', ''))
            
            # Determine category from file path
            rel_path = os.path.relpath(policy_file, self.local_storage)
            category = self._determine_category_from_path(rel_path)
            
            # Extract description
            description = metadata.get('annotations', {}).get('policies.kyverno.io/description', '')
            if not description:
                description = metadata.get('annotations', {}).get('description', '')
            if not description:
                description = f"Kyverno policy: {name}"
            
            # Find associated test directory
            test_directory = self._find_test_directory(policy_file)
            
            # Extract tags
            tags = self._extract_tags(policy_content, rel_path)
            
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
            logger.error(f"Failed to create policy entry for {policy_file}: {str(e)}")
            return None
    
    def _is_valid_kyverno_policy(self, content: Dict[str, Any]) -> bool:
        """Check if content is a valid Kyverno policy."""
        return (
            isinstance(content, dict) and
            content.get('kind') in ['ClusterPolicy', 'Policy'] and
            content.get('apiVersion', '').startswith('kyverno.io/') and
            'spec' in content and
            'rules' in content.get('spec', {})
        )
    
    def _determine_category_from_path(self, rel_path: str) -> str:
        """Determine policy category from file path."""
        path_parts = rel_path.lower().split(os.sep)
        
        # Common category mappings
        category_keywords = {
            'best-practices': ['best-practices', 'best_practices', 'bestpractices'],
            'security': ['security', 'sec'],
            'compliance': ['compliance', 'cis', 'nist', 'pci', 'hipaa'],
            'networking': ['networking', 'network', 'ingress', 'service'],
            'storage': ['storage', 'pv', 'pvc', 'volume'],
            'rbac': ['rbac', 'role', 'rolebinding', 'serviceaccount'],
            'pod-security': ['pod-security', 'podsecurity', 'pss'],
            'resource-management': ['resources', 'limits', 'requests', 'quota'],
            'workload': ['workload', 'deployment', 'pod', 'job'],
            'other': []
        }
        
        for part in path_parts:
            for category, keywords in category_keywords.items():
                if any(keyword in part for keyword in keywords):
                    return category
        
        return 'other'
    
    def _find_test_directory(self, policy_file: str) -> Optional[str]:
        """Find directory containing test files for a policy."""
        policy_dir = os.path.dirname(policy_file)
        
        # Check if there are any test files in the policy directory
        test_files = ['kyverno-test.yaml', 'resource.yaml', 'resources.yaml', 'values.yaml']
        has_test_files = any(os.path.exists(os.path.join(policy_dir, test_file)) for test_file in test_files)
        
        if has_test_files:
            return os.path.relpath(policy_dir, self.local_storage)
        
        return None
    

    
    def _extract_tags(self, policy_content: Dict[str, Any], rel_path: str) -> List[str]:
        """Extract tags from policy content and path."""
        tags = []
        
        # Extract from annotations
        annotations = policy_content.get('metadata', {}).get('annotations', {})
        
        # Common annotation keys for tags
        tag_keys = [
            'policies.kyverno.io/category',
            'policies.kyverno.io/subject',
            'policies.kyverno.io/title'
        ]
        
        for key in tag_keys:
            if key in annotations:
                value = annotations[key]
                if isinstance(value, str):
                    tags.extend([tag.strip() for tag in value.split(',')])
        
        # Extract from path
        path_parts = rel_path.split(os.sep)
        tags.extend([part.replace('-', ' ').replace('_', ' ') for part in path_parts[:-1]])
        
        # Clean and deduplicate tags
        cleaned_tags = []
        for tag in tags:
            if tag and tag.lower() not in [t.lower() for t in cleaned_tags]:
                cleaned_tags.append(tag.strip())
        
        return cleaned_tags[:10]  # Limit to 10 tags
    
    def _determine_source_repo(self, rel_path: str) -> str:
        """Determine source repository URL from path."""
        # Use stored repo info if available
        if hasattr(self, '_repo_info'):
            # For single repository catalogs, return the full HTTPS URL
            if len(self._repo_info) == 1:
                return list(self._repo_info.values())[0]
            
            # For multiple repositories, try to match based on path patterns
            # This is a simple heuristic - in practice, we might need more sophisticated mapping
            for source_dir, repo_url in self._repo_info.items():
                repo_name = self._extract_repo_name_from_url(repo_url)
                if repo_name.lower() in rel_path.lower():
                    return repo_url
            
            # If no match found, return the first repository URL (full HTTPS URL)
            return list(self._repo_info.values())[0]
        
        # Fallback - return unknown since we don't have the original URL
        return 'unknown'
    
    def _extract_repo_name_from_url(self, url: str) -> str:
        """Extract owner/repo from Git URL (GitHub, GitLab, etc.)."""
        try:
            # Handle both https and git URLs
            if url.endswith('.git'):
                url = url[:-4]
            
            # Extract from URL like https://github.com/kyverno/policies or https://gitlab.com/owner/repo
            parts = url.rstrip('/').split('/')
            if len(parts) >= 2:
                owner = parts[-2]
                repo = parts[-1]
                return f"{owner}/{repo}"
            
            return 'unknown'
        except Exception:
            return 'unknown'
    
    def _save_policy_index(self, policy_index: PolicyIndex) -> None:
        """Save policy index to JSON file."""
        try:
            # Convert to serializable format
            index_data = {
                'categories': {},
                'total_policies': policy_index.total_policies,
                'last_updated': policy_index.last_updated.isoformat()
            }
            
            for category, policies in policy_index.categories.items():
                index_data['categories'][category] = [
                    {
                        'name': p.name,
                        'category': p.category,
                        'description': p.description,
                        'relative_path': p.relative_path,
                        'test_directory': p.test_directory,
                        'source_repo': p.source_repo,
                        'tags': p.tags
                    }
                    for p in policies
                ]
            
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Policy index saved to {self.index_file}")
            
        except Exception as e:
            logger.error(f"Failed to save policy index: {str(e)}")
            raise CatalogError("Failed to save policy index", str(e))
    
    def _load_policy_index(self) -> Optional[PolicyIndex]:
        """Load policy index from JSON file."""
        try:
            if not os.path.exists(self.index_file):
                return None
            
            with open(self.index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            policy_index = PolicyIndex()
            policy_index.total_policies = index_data.get('total_policies', 0)
            policy_index.last_updated = datetime.fromisoformat(index_data.get('last_updated', datetime.now().isoformat()))
            
            for category, policies_data in index_data.get('categories', {}).items():
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
            
        except Exception as e:
            logger.error(f"Failed to load policy index: {str(e)}")
            return None
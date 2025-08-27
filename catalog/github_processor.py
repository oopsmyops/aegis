"""
Git Repository Processor for AEGIS.
Handles Git repository operations for policy catalog creation (GitHub, GitLab, etc.).
"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from urllib.parse import urlparse

from exceptions import CatalogError, NetworkError
from utils.file_utils import FileUtils
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class GitHubProcessor:
    """Handles Git repository operations for policy catalog creation (GitHub, GitLab, etc.)."""
    
    def __init__(self, temp_dir: Optional[str] = None):
        """Initialize GitHub processor."""
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.cloned_repos = []
    
    def clone_repository(self, url: str, branch: str = "main", depth: int = 1) -> Optional[str]:
        """Clone a Git repository to temporary directory (GitHub, GitLab, etc.)."""
        try:
            # Generate unique directory name
            repo_name = self._extract_repo_name(url)
            clone_dir = os.path.join(self.temp_dir, f"aegis_clone_{repo_name}")
            
            # Remove existing directory if it exists
            if os.path.exists(clone_dir):
                shutil.rmtree(clone_dir)
            
            # Build git clone command
            cmd = ['git', 'clone']
            if depth > 0:
                cmd.extend(['--depth', str(depth)])
            cmd.extend(['--branch', branch, url, clone_dir])
            
            logger.info(f"Cloning repository {url} (branch: {branch})")
            
            # Execute clone command
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300,
                cwd=self.temp_dir
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to clone repository {url}: {result.stderr}")
                return None
            
            # Track cloned repository
            self.cloned_repos.append(clone_dir)
            logger.info(f"Successfully cloned {url} to {clone_dir}")
            
            return clone_dir
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout cloning repository {url}")
            return None
        except Exception as e:
            logger.error(f"Error cloning repository {url}: {str(e)}")
            return None
    
    def find_policy_files(self, repo_dir: str) -> List[str]:
        """Find Kyverno policy files in repository using grep."""
        try:
            logger.info(f"Finding policy files in {repo_dir}")
            
            # First, find files with ClusterPolicy kind
            cmd1 = [
                'grep', '-r', '--exclude-dir=.*', '--include=*.yaml',
                '-l', '-e', 'kind: ClusterPolicy', repo_dir
            ]
            
            result1 = subprocess.run(cmd1, capture_output=True, text=True)
            if result1.returncode != 0:
                logger.warning(f"No ClusterPolicy files found in {repo_dir}")
                return []
            
            candidate_files = [f.strip() for f in result1.stdout.strip().split('\n') if f.strip()]
            if not candidate_files:
                return []
            
            # Filter files that also contain validationFailureAction
            cmd2 = ['grep', '-l', '-e', 'validationFailureAction'] + candidate_files
            result2 = subprocess.run(cmd2, capture_output=True, text=True)
            
            if result2.returncode != 0:
                logger.warning(f"No policy files with validationFailureAction found in {repo_dir}")
                return []
            
            policy_files = [f.strip() for f in result2.stdout.strip().split('\n') if f.strip()]
            logger.info(f"Found {len(policy_files)} policy files in {repo_dir}")
            
            return policy_files
            
        except Exception as e:
            logger.error(f"Error finding policy files in {repo_dir}: {str(e)}")
            return []
    
    def extract_policies_with_tests(self, repo_dir: str, policy_files: List[str]) -> Dict[str, Dict[str, Any]]:
        """Extract policies with their associated test files."""
        try:
            logger.info(f"Extracting policies and tests from {repo_dir}")
            
            extracted_policies = {}
            
            for policy_file in policy_files:
                try:
                    # Get relative path from repo root
                    rel_path = os.path.relpath(policy_file, repo_dir)
                    policy_dir = os.path.dirname(policy_file)
                    
                    # Find associated test files
                    test_files = self._find_test_files(policy_dir)
                    
                    # Store policy information
                    extracted_policies[rel_path] = {
                        'policy_file': policy_file,
                        'relative_path': rel_path,
                        'test_files': test_files,
                        'policy_dir': policy_dir
                    }
                    
                    logger.debug(f"Extracted policy: {rel_path} with {len(test_files)} test files")
                    
                except Exception as e:
                    logger.warning(f"Failed to extract policy {policy_file}: {str(e)}")
                    continue
            
            logger.info(f"Extracted {len(extracted_policies)} policies from {repo_dir}")
            return extracted_policies
            
        except Exception as e:
            logger.error(f"Error extracting policies from {repo_dir}: {str(e)}")
            return {}
    
    def copy_policies_to_catalog(self, repo_dir: str, extracted_policies: Dict[str, Dict[str, Any]], 
                                catalog_dir: str) -> List[str]:
        """Copy extracted policies and tests to catalog directory."""
        try:
            logger.info(f"Copying policies from {repo_dir} to catalog {catalog_dir}")
            
            copied_files = []
            
            for rel_path, policy_info in extracted_policies.items():
                try:
                    # Copy policy file
                    policy_dest = os.path.join(catalog_dir, rel_path)
                    FileUtils.copy_file(policy_info['policy_file'], policy_dest, create_dirs=True)
                    copied_files.append(policy_dest)
                    
                    # Copy test files
                    for test_file_info in policy_info['test_files']:
                        test_source = test_file_info['file_path']
                        test_rel_path = test_file_info['relative_path']
                        test_dest = os.path.join(catalog_dir, os.path.dirname(rel_path), test_rel_path)
                        
                        if test_file_info['needs_modification']:
                            # Modify test file content (remove ../ references)
                            self._copy_and_modify_test_file(test_source, test_dest)
                        else:
                            FileUtils.copy_file(test_source, test_dest, create_dirs=True)
                        
                        copied_files.append(test_dest)
                    
                    logger.debug(f"Copied policy and tests: {rel_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to copy policy {rel_path}: {str(e)}")
                    continue
            
            logger.info(f"Copied {len(copied_files)} files to catalog")
            return copied_files
            
        except Exception as e:
            logger.error(f"Error copying policies to catalog: {str(e)}")
            return []
    
    def cleanup_cloned_repositories(self) -> None:
        """Clean up all cloned repositories."""
        for repo_dir in self.cloned_repos:
            try:
                if os.path.exists(repo_dir):
                    shutil.rmtree(repo_dir)
                    logger.debug(f"Cleaned up repository: {repo_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup repository {repo_dir}: {str(e)}")
        
        self.cloned_repos.clear()
    
    def validate_repository_url(self, url: str) -> bool:
        """Validate GitHub repository URL."""
        try:
            parsed = urlparse(url)
            
            # Check if it's a valid HTTPS URL
            if parsed.scheme not in ['https', 'http']:
                return False
            
            # Check if it's a GitHub URL
            if parsed.netloc.lower() != 'github.com':
                return False
            
            # Check if path has at least owner/repo structure
            path_parts = parsed.path.strip('/').split('/')
            if len(path_parts) < 2:
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_repository_info(self, repo_dir: str) -> Dict[str, Any]:
        """Get repository information from cloned directory."""
        try:
            # Get remote URL
            cmd = ['git', 'remote', 'get-url', 'origin']
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_dir)
            remote_url = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get current branch
            cmd = ['git', 'branch', '--show-current']
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_dir)
            current_branch = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get last commit info
            cmd = ['git', 'log', '-1', '--format=%H|%s|%ad', '--date=iso']
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_dir)
            
            commit_info = {'hash': 'unknown', 'message': 'unknown', 'date': 'unknown'}
            if result.returncode == 0:
                parts = result.stdout.strip().split('|', 2)
                if len(parts) == 3:
                    commit_info = {
                        'hash': parts[0][:8],  # Short hash
                        'message': parts[1],
                        'date': parts[2]
                    }
            
            return {
                'remote_url': remote_url,
                'branch': current_branch,
                'last_commit': commit_info,
                'local_path': repo_dir
            }
            
        except Exception as e:
            logger.error(f"Failed to get repository info for {repo_dir}: {str(e)}")
            return {
                'remote_url': 'unknown',
                'branch': 'unknown',
                'last_commit': {'hash': 'unknown', 'message': 'unknown', 'date': 'unknown'},
                'local_path': repo_dir
            }
    
    def _extract_repo_name(self, url: str) -> str:
        """Extract repository name from URL."""
        try:
            # Remove .git suffix if present
            if url.endswith('.git'):
                url = url[:-4]
            
            # Extract owner/repo from URL
            parts = url.rstrip('/').split('/')
            if len(parts) >= 2:
                owner = parts[-2]
                repo = parts[-1]
                return f"{owner}_{repo}"
            
            return "unknown_repo"
            
        except Exception:
            return "unknown_repo"
    
    def _find_test_files(self, policy_dir: str) -> List[Dict[str, Any]]:
        """Find test files associated with a policy directory."""
        test_files = []
        
        try:
            # Check for .kyverno-test directory
            kyverno_test_dir = os.path.join(policy_dir, '.kyverno-test')
            if os.path.exists(kyverno_test_dir):
                test_files.extend(self._process_kyverno_test_dir(kyverno_test_dir, policy_dir))
            
            # Check for direct test files
            direct_test_files = ['kyverno-test.yaml', 'resource.yaml']
            for test_file in direct_test_files:
                test_path = os.path.join(policy_dir, test_file)
                if os.path.exists(test_path):
                    test_files.append({
                        'file_path': test_path,
                        'relative_path': test_file,
                        'needs_modification': False
                    })
            
        except Exception as e:
            logger.warning(f"Error finding test files in {policy_dir}: {str(e)}")
        
        return test_files
    
    def _process_kyverno_test_dir(self, kyverno_test_dir: str, policy_dir: str) -> List[Dict[str, Any]]:
        """Process .kyverno-test directory and find all test files."""
        test_files = []
        
        try:
            # Main test file
            main_test_file = os.path.join(kyverno_test_dir, 'kyverno-test.yaml')
            if os.path.exists(main_test_file):
                test_files.append({
                    'file_path': main_test_file,
                    'relative_path': 'kyverno-test.yaml',
                    'needs_modification': True  # Need to remove ../ references
                })
                
                # Find resource files referenced in test
                resource_files = self._find_referenced_resources(main_test_file, kyverno_test_dir)
                test_files.extend(resource_files)
            
        except Exception as e:
            logger.warning(f"Error processing kyverno test directory {kyverno_test_dir}: {str(e)}")
        
        return test_files
    
    def _find_referenced_resources(self, test_file: str, test_dir: str) -> List[Dict[str, Any]]:
        """Find resource files referenced in kyverno test file."""
        resource_files = []
        
        try:
            from utils.yaml_utils import YamlUtils
            
            test_content = YamlUtils.load_yaml_safe(test_file)
            
            # Get resources and variables
            resources = test_content.get('resources', [])
            variables = test_content.get('variables', [])
            
            all_refs = resources + variables
            
            for ref in all_refs:
                if isinstance(ref, str):
                    # Handle relative paths
                    resource_path = os.path.join(test_dir, ref)
                    if os.path.exists(resource_path):
                        # Clean up the relative path (remove ../)
                        clean_ref = ref.replace('../', '')
                        resource_files.append({
                            'file_path': resource_path,
                            'relative_path': clean_ref,
                            'needs_modification': False
                        })
            
        except Exception as e:
            logger.warning(f"Error finding referenced resources in {test_file}: {str(e)}")
        
        return resource_files
    
    def _copy_and_modify_test_file(self, source_path: str, dest_path: str) -> None:
        """Copy test file and modify content to remove ../ references."""
        try:
            # Read source content
            content = FileUtils.read_file(source_path)
            
            # Remove ../ references
            modified_content = content.replace('../', '')
            
            # Write to destination
            FileUtils.write_file(dest_path, modified_content, create_dirs=True)
            
        except Exception as e:
            logger.error(f"Failed to copy and modify test file {source_path}: {str(e)}")
            # Fallback to regular copy
            FileUtils.copy_file(source_path, dest_path, create_dirs=True)
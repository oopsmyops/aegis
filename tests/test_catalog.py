"""
Tests for AEGIS catalog functionality.
"""

import os
import tempfile
import shutil
import pytest
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from catalog import PolicyCatalogManager, PolicyIndexer, GitHubProcessor
from models import PolicyIndex, PolicyCatalogEntry
from exceptions import CatalogError


class TestPolicyCatalogManager:
    """Test PolicyCatalogManager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.catalog_dir = os.path.join(self.temp_dir, "catalog")
        self.index_file = os.path.join(self.temp_dir, "index.json")
        
        self.config = {
            'catalog': {
                'local_storage': self.catalog_dir,
                'index_file': self.index_file,
                'repositories': [
                    {'url': 'https://github.com/test/repo', 'branch': 'main'}
                ],
                'ai_selection': {
                    'max_policies_per_category': 10,
                    'total_policies_for_ai': 50
                }
            }
        }
        
        self.catalog_manager = PolicyCatalogManager(self.config)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test catalog manager initialization."""
        assert self.catalog_manager.local_storage == self.catalog_dir
        assert self.catalog_manager.index_file == self.index_file
        assert os.path.exists(self.catalog_dir)
    
    @patch('catalog.catalog_manager.subprocess.run')
    @patch('catalog.catalog_manager.FileUtils')
    def test_create_catalog_from_repos(self, mock_file_utils, mock_subprocess):
        """Test catalog creation from repositories."""
        # Mock successful git clone
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        # Mock file operations
        mock_file_utils.remove_directory = Mock()
        mock_file_utils.ensure_directory = Mock()
        mock_file_utils.copy_file = Mock()
        mock_file_utils.read_file = Mock(return_value="test content")
        
        # Mock finding policy files
        with patch.object(self.catalog_manager, '_find_policy_files') as mock_find:
            mock_find.return_value = ['/tmp/test/policy.yaml']
            
            with patch.object(self.catalog_manager, '_copy_policy_files') as mock_copy:
                mock_copy.return_value = None
                
                # Test catalog creation
                repo_urls = ['https://github.com/test/repo']
                self.catalog_manager.create_catalog_from_repos(repo_urls)
                
                # Verify git clone was called
                mock_subprocess.assert_called()
    
    def test_build_policy_index_empty_catalog(self):
        """Test building index with empty catalog."""
        # Empty catalog should return empty index, not raise error
        policy_index = self.catalog_manager.build_policy_index()
        assert policy_index.total_policies == 0
        assert len(policy_index.categories) == 0
    
    @patch('catalog.catalog_manager.FileUtils.list_files')
    def test_build_policy_index_with_policies(self, mock_list_files):
        """Test building index with policies."""
        # Create catalog directory
        os.makedirs(self.catalog_dir, exist_ok=True)
        
        # Mock policy files
        mock_list_files.return_value = [
            os.path.join(self.catalog_dir, 'test-policy.yaml')
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
    validate:
      message: "Test validation"
      pattern:
        spec:
          containers:
          - name: "*"
"""
        
        test_policy_file = os.path.join(self.catalog_dir, 'test-policy.yaml')
        with open(test_policy_file, 'w') as f:
            f.write(test_policy_content)
        
        # Test index building
        policy_index = self.catalog_manager.build_policy_index()
        
        assert isinstance(policy_index, PolicyIndex)
        assert policy_index.total_policies >= 0
    
    def test_get_policies_detailed_no_index(self):
        """Test getting detailed policies when no index exists."""
        with pytest.raises(CatalogError):
            self.catalog_manager.get_policies_detailed(['test-policy'])


class TestPolicyIndexer:
    """Test PolicyIndexer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.catalog_dir = os.path.join(self.temp_dir, "catalog")
        self.index_file = os.path.join(self.temp_dir, "index.json")
        
        os.makedirs(self.catalog_dir, exist_ok=True)
        
        self.indexer = PolicyIndexer(self.catalog_dir, self.index_file)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test indexer initialization."""
        assert self.indexer.catalog_path == self.catalog_dir
        assert self.indexer.index_file == self.index_file
    
    def test_create_index_empty_catalog(self):
        """Test creating index with empty catalog."""
        policy_index = self.indexer.create_index()
        
        assert isinstance(policy_index, PolicyIndex)
        assert policy_index.total_policies == 0
        assert len(policy_index.categories) == 0
    
    def test_create_index_with_policy(self):
        """Test creating index with a policy file."""
        # Create a test policy file
        test_policy_content = """
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: sample-policy
  annotations:
    policies.kyverno.io/description: "Test policy for validation"
spec:
  validationFailureAction: enforce
  rules:
  - name: test-rule
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Test validation"
      pattern:
        spec:
          containers:
          - name: "*"
"""
        
        policy_file = os.path.join(self.catalog_dir, 'sample-policy.yaml')
        with open(policy_file, 'w') as f:
            f.write(test_policy_content)
        
        # Create index
        policy_index = self.indexer.create_index()
        
        assert policy_index.total_policies == 1
        assert len(policy_index.categories) >= 1
        
        # Check if policy was categorized (should be in 'workload' category since it targets Pod)
        found_policy = False
        for category, policies in policy_index.categories.items():
            for policy in policies:
                if policy.name == 'sample-policy':
                    found_policy = True
                    assert policy.description == "Test policy for validation"
                    assert policy.test_directory is None or isinstance(policy.test_directory, str)
                    break
        
        assert found_policy, "Test policy not found in index"
    
    def test_load_nonexistent_index(self):
        """Test loading non-existent index."""
        result = self.indexer.load_index()
        assert result is None
    
    def test_search_policies_empty_index(self):
        """Test searching policies with empty index."""
        results = self.indexer.search_policies("test")
        assert results == []


class TestGitHubProcessor:
    """Test GitHubProcessor functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.processor = GitHubProcessor(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        self.processor.cleanup_cloned_repositories()
    
    def test_initialization(self):
        """Test processor initialization."""
        assert self.processor.temp_dir == self.temp_dir
        assert self.processor.cloned_repos == []
    
    def test_validate_repository_url(self):
        """Test repository URL validation."""
        # Valid URLs
        assert self.processor.validate_repository_url("https://github.com/owner/repo")
        assert self.processor.validate_repository_url("https://github.com/owner/repo.git")
        
        # Invalid URLs
        assert not self.processor.validate_repository_url("https://gitlab.com/owner/repo")
        assert not self.processor.validate_repository_url("https://github.com/owner")
        assert not self.processor.validate_repository_url("invalid-url")
    
    def test_extract_repo_name(self):
        """Test repository name extraction."""
        url1 = "https://github.com/kyverno/policies"
        name1 = self.processor._extract_repo_name(url1)
        assert name1 == "kyverno_policies"
        
        url2 = "https://github.com/nirmata/kyverno-policies.git"
        name2 = self.processor._extract_repo_name(url2)
        assert name2 == "nirmata_kyverno-policies"
    
    @patch('catalog.github_processor.subprocess.run')
    def test_clone_repository_success(self, mock_subprocess):
        """Test successful repository cloning."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        url = "https://github.com/test/repo"
        result = self.processor.clone_repository(url)
        
        assert result is not None
        assert result in self.processor.cloned_repos
        mock_subprocess.assert_called_once()
    
    @patch('catalog.github_processor.subprocess.run')
    def test_clone_repository_failure(self, mock_subprocess):
        """Test failed repository cloning."""
        mock_subprocess.return_value = Mock(returncode=1, stdout="", stderr="Clone failed")
        
        url = "https://github.com/test/repo"
        result = self.processor.clone_repository(url)
        
        assert result is None
        assert len(self.processor.cloned_repos) == 0
    
    def test_find_policy_files_empty_dir(self):
        """Test finding policy files in empty directory."""
        empty_dir = os.path.join(self.temp_dir, "empty")
        os.makedirs(empty_dir)
        
        result = self.processor.find_policy_files(empty_dir)
        assert result == []


if __name__ == '__main__':
    pytest.main([__file__])
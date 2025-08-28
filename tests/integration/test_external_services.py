"""
Integration tests for external service interactions.
Tests real interactions with AWS Bedrock, GitHub, and Kubernetes APIs.
These tests require proper credentials and network access.
"""

import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, Mock
import pytest

# Skip these tests if running in CI or without credentials
SKIP_EXTERNAL_TESTS = os.getenv('SKIP_EXTERNAL_TESTS', 'true').lower() == 'true'

@pytest.mark.skipif(SKIP_EXTERNAL_TESTS, reason="External service tests disabled")
class TestExternalServiceIntegration(unittest.TestCase):
    """Test integration with external services."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Configuration for external services
        self.config = {
            'ai': {
                'provider': 'aws-bedrock',
                'model': 'anthropic.claude-3-haiku-20240307-v1:0',  # Use cheaper model for tests
                'region': os.getenv('AWS_REGION', 'us-east-1'),
                'max_tokens': 1000,  # Smaller for tests
                'temperature': 0.1
            },
            'catalog': {
                'local_storage': os.path.join(self.temp_dir, 'catalog'),
                'repositories': [
                    {
                        'url': 'https://github.com/kyverno/policies',
                        'branch': 'main'
                    }
                ]
            }
        }
        
        # Create directories
        os.makedirs(self.config['catalog']['local_storage'], exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.integration
    def test_aws_bedrock_connection(self):
        """Test connection to AWS Bedrock service."""
        try:
            from ai.bedrock_client import BedrockClient
            
            # Create Bedrock client
            bedrock_client = BedrockClient(self.config)
            
            # Test simple request
            prompt = "Respond with exactly: 'Connection successful'"
            response = bedrock_client.send_request(prompt, max_tokens=50)
            
            # Verify response
            self.assertIsInstance(response, str)
            self.assertGreater(len(response), 0)
            
            print(f"✅ Bedrock connection successful. Response: {response[:100]}...")
            
        except Exception as e:
            self.skipTest(f"AWS Bedrock not available: {e}")
    
    @pytest.mark.integration
    def test_github_repository_access(self):
        """Test accessing GitHub repositories."""
        try:
            from catalog.github_processor import GitHubProcessor
            
            # Create GitHub processor
            processor = GitHubProcessor(self.temp_dir)
            
            # Test repository validation
            valid_url = "https://github.com/kyverno/policies"
            self.assertTrue(processor.validate_repository_url(valid_url))
            
            # Test cloning (small repository or specific branch)
            # Note: This is a real network operation
            cloned_path = processor.clone_repository(valid_url, depth=1)  # Shallow clone
            
            if cloned_path:
                self.assertTrue(os.path.exists(cloned_path))
                
                # Test finding policy files
                policy_files = processor.find_policy_files(cloned_path)
                self.assertIsInstance(policy_files, list)
                
                print(f"✅ GitHub access successful. Found {len(policy_files)} policy files")
            else:
                self.skipTest("GitHub repository cloning failed")
                
        except Exception as e:
            self.skipTest(f"GitHub access not available: {e}")
    
    @pytest.mark.integration
    def test_kubernetes_cluster_access(self):
        """Test accessing Kubernetes cluster."""
        try:
            from discovery.discovery import ClusterDiscovery
            
            # Create discovery instance
            discovery = ClusterDiscovery()
            
            # Test cluster connection
            discovery._initialize_kubernetes_client()
            
            # Test basic cluster info (non-destructive)
            cluster_info = discovery._discover_basic_info()
            
            self.assertIsInstance(cluster_info, dict)
            self.assertIn('kubernetes_version', cluster_info)
            
            print(f"✅ Kubernetes access successful. Version: {cluster_info.get('kubernetes_version')}")
            
        except Exception as e:
            self.skipTest(f"Kubernetes cluster not available: {e}")
    
    @pytest.mark.integration
    def test_kyverno_cli_availability(self):
        """Test Kyverno CLI availability."""
        try:
            from ai.kyverno_validator import KyvernoValidator
            
            # Create validator
            validator = KyvernoValidator()
            
            # Test Kyverno CLI availability
            available = validator.check_kyverno_available()
            
            if available:
                print("✅ Kyverno CLI is available")
            else:
                self.skipTest("Kyverno CLI not available")
                
        except Exception as e:
            self.skipTest(f"Kyverno CLI test failed: {e}")


@pytest.mark.skipif(not SKIP_EXTERNAL_TESTS, reason="Mock tests only when external tests are disabled")
class TestMockedExternalServices(unittest.TestCase):
    """Test external service interactions with mocks (for CI/CD)."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('ai.bedrock_client.boto3.client')
    def test_bedrock_client_with_mock(self, mock_boto3):
        """Test Bedrock client with mocked AWS service."""
        from ai.bedrock_client import BedrockClient
        
        # Mock Bedrock response
        mock_client = Mock()
        mock_boto3.return_value = mock_client
        
        mock_response = {
            'body': Mock()
        }
        
        import json
        response_data = {
            'content': [{'text': 'Mocked response'}],
            'usage': {'input_tokens': 10, 'output_tokens': 5}
        }
        
        mock_response['body'].read.return_value = json.dumps(response_data).encode()
        mock_client.invoke_model.return_value = mock_response
        
        # Test client
        config = {
            'ai': {
                'region': 'us-east-1',
                'model': 'anthropic.claude-3-sonnet-20240229-v1:0',
                'max_tokens': 1000,
                'temperature': 0.1
            }
        }
        
        bedrock_client = BedrockClient(config)
        response = bedrock_client.send_request("Test prompt")
        
        self.assertEqual(response, 'Mocked response')
        mock_client.invoke_model.assert_called_once()
    
    @patch('catalog.github_processor.subprocess.run')
    def test_github_processor_with_mock(self, mock_subprocess):
        """Test GitHub processor with mocked git operations."""
        from catalog.github_processor import GitHubProcessor
        
        # Mock successful git clone
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        processor = GitHubProcessor(self.temp_dir)
        
        # Test repository cloning
        result = processor.clone_repository("https://github.com/test/repo")
        
        self.assertIsNotNone(result)
        mock_subprocess.assert_called_once()
    
    @patch('discovery.discovery.config.load_kube_config')
    @patch('discovery.discovery.client.ApiClient')
    def test_kubernetes_discovery_with_mock(self, mock_api_client, mock_load_config):
        """Test Kubernetes discovery with mocked API."""
        from discovery.discovery import ClusterDiscovery
        
        # Mock Kubernetes client
        mock_client = Mock()
        mock_api_client.return_value = mock_client
        
        discovery = ClusterDiscovery()
        
        # Mock discovery methods
        with patch.object(discovery, '_discover_basic_info') as mock_basic:
            mock_basic.return_value = {
                'kubernetes_version': '1.28.0',
                'node_count': 3,
                'namespace_count': 10
            }
            
            cluster_info = discovery._discover_basic_info()
            
            self.assertEqual(cluster_info['kubernetes_version'], '1.28.0')
            self.assertEqual(cluster_info['node_count'], 3)
    
    @patch('ai.kyverno_validator.subprocess.run')
    def test_kyverno_validator_with_mock(self, mock_subprocess):
        """Test Kyverno validator with mocked CLI."""
        from ai.kyverno_validator import KyvernoValidator
        
        # Mock Kyverno CLI availability
        mock_subprocess.return_value = Mock(returncode=0, stdout="kyverno version v1.10.0")
        
        validator = KyvernoValidator()
        available = validator.check_kyverno_available()
        
        self.assertTrue(available)
        mock_subprocess.assert_called_once()


class TestServiceErrorHandling(unittest.TestCase):
    """Test error handling for external service failures."""
    
    def test_bedrock_connection_failure(self):
        """Test handling of Bedrock connection failures."""
        from ai.bedrock_client import BedrockClient
        from exceptions import AISelectionError
        
        config = {
            'ai': {
                'region': 'invalid-region',
                'model': 'invalid-model',
                'max_tokens': 1000,
                'temperature': 0.1,
                'error_handling': {
                    'enable_fallbacks': False,
                    'max_retry_attempts': 1
                }
            }
        }
        
        with patch('ai.bedrock_client.boto3.client') as mock_boto3:
            mock_client = Mock()
            mock_boto3.return_value = mock_client
            mock_client.invoke_model.side_effect = Exception("Connection failed")
            
            bedrock_client = BedrockClient(config)
            
            with self.assertRaises(AISelectionError):
                bedrock_client.send_request("Test prompt")
    
    def test_github_access_failure(self):
        """Test handling of GitHub access failures."""
        from catalog.github_processor import GitHubProcessor
        
        processor = GitHubProcessor("/tmp")
        
        with patch('catalog.github_processor.subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=1, stderr="Repository not found")
            
            result = processor.clone_repository("https://github.com/nonexistent/repo")
            
            self.assertIsNone(result)
    
    def test_kubernetes_access_failure(self):
        """Test handling of Kubernetes access failures."""
        from discovery.discovery import ClusterDiscovery
        from exceptions import ClusterDiscoveryError
        
        discovery = ClusterDiscovery()
        
        with patch('discovery.discovery.config.load_kube_config') as mock_load_config:
            mock_load_config.side_effect = Exception("No cluster access")
            
            with self.assertRaises(ClusterDiscoveryError):
                discovery._initialize_kubernetes_client()


if __name__ == '__main__':
    # Run tests with pytest for better integration test support
    import pytest
    pytest.main([__file__, '-v', '-m', 'not integration'])
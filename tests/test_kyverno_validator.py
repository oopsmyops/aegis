"""
Tests for Kyverno validator functionality.
"""

import unittest
import tempfile
import os
import yaml
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from ai.kyverno_validator import KyvernoValidator
from exceptions import ValidationError


class TestKyvernoValidator(unittest.TestCase):
    """Test cases for KyvernoValidator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.validator = KyvernoValidator()
        
        # Create sample policy and test files
        self.policy_content = """
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
            resources:
              requests:
                memory: "?*"
"""
        
        self.test_content = """
apiVersion: kyverno.io/v1
kind: Test
metadata:
  name: test-policy-test
spec:
  policies:
  - test-policy.yaml
  resources:
  - resource.yaml
  results:
  - policy: test-policy
    rule: test-rule
    resource: test-pod
    result: pass
"""
        
        self.resource_content = """
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: test-container
    image: nginx
    resources:
      requests:
        memory: "128Mi"
"""
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test KyvernoValidator initialization."""
        self.assertIsNotNone(self.validator)
        self.assertEqual(self.validator.kyverno_command, 'kyverno')
    
    def test_check_kyverno_available_success(self):
        """Test successful Kyverno CLI detection."""
        with patch('ai.kyverno_validator.subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="kyverno version v1.10.0")
            
            # Create a new validator instance to test the initialization
            validator = KyvernoValidator()
            result = validator.check_kyverno_available()
            
            self.assertTrue(result)
            mock_run.assert_called_once()
    
    def test_check_kyverno_available_failure(self):
        """Test Kyverno CLI not available."""
        with patch('ai.kyverno_validator.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("kyverno not found")
            
            # Create a new validator instance to test the initialization
            validator = KyvernoValidator()
            result = validator.check_kyverno_available()
            
            self.assertFalse(result)
    
    def test_validate_policies_success(self):
        """Test successful policy validation."""
        # Create test policy directory
        policy_dir = os.path.join(self.temp_dir, "policies")
        os.makedirs(policy_dir)
        
        # Write policy file
        policy_file = os.path.join(policy_dir, "test-policy.yaml")
        with open(policy_file, 'w') as f:
            f.write(self.policy_content)
        
        # Write test file
        test_file = os.path.join(policy_dir, "kyverno-test.yaml")
        with open(test_file, 'w') as f:
            f.write(self.test_content)
        
        # Write resource file
        resource_file = os.path.join(policy_dir, "resource.yaml")
        with open(resource_file, 'w') as f:
            f.write(self.resource_content)
        
        # Mock successful Kyverno test
        mock_output = """
Loading policies...
Loading resources...
Applying 1 policy rule(s) to 1 resource(s)...

PASS: test-policy/test-rule/test-pod
"""
        
        with patch('ai.kyverno_validator.subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )
            
            report = self.validator.validate_policies(policy_dir)
            
            self.assertIsNotNone(report)
            self.assertEqual(report['total_tests'], 1)
            self.assertEqual(report['failed_tests'], 0)
            self.assertEqual(report['success_rate'], 100.0)
            self.assertEqual(len(report['failure']), 0)
    
    def test_validate_policies_with_failures(self):
        """Test policy validation with failures."""
        # Create test policy directory
        policy_dir = os.path.join(self.temp_dir, "policies")
        os.makedirs(policy_dir)
        
        # Write policy file
        policy_file = os.path.join(policy_dir, "test-policy.yaml")
        with open(policy_file, 'w') as f:
            f.write(self.policy_content)
        
        # Mock Kyverno test with failures
        mock_output = """
Loading policies...
Loading resources...
Applying 1 policy rule(s) to 1 resource(s)...

FAIL: test-policy/test-rule/test-pod -> validation error: memory request is required
"""
        
        with patch('ai.kyverno_validator.subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout=mock_output,
                stderr=""
            )
            
            report = self.validator.validate_policies(policy_dir)
            
            self.assertIsNotNone(report)
            self.assertEqual(report['total_tests'], 1)
            self.assertEqual(report['failed_tests'], 1)
            self.assertEqual(report['success_rate'], 0.0)
            self.assertEqual(len(report['failure']), 1)
            
            failure = report['failure'][0]
            self.assertEqual(failure['policy'], 'test-policy')
            self.assertEqual(failure['rule'], 'test-rule')
            self.assertEqual(failure['resource'], 'test-pod')
    
    def test_validate_policies_with_test_file_errors(self):
        """Test policy validation with test file errors."""
        # Create test policy directory
        policy_dir = os.path.join(self.temp_dir, "policies")
        os.makedirs(policy_dir)
        
        # Mock Kyverno test with test file error
        mock_output = ""
        mock_stderr = """
Error: failed to load test file: duplicate key 'rule' in test.yaml
"""
        
        with patch('ai.kyverno_validator.subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout=mock_output,
                stderr=mock_stderr
            )
            
            report = self.validator.validate_policies(policy_dir)
            
            self.assertIsNotNone(report)
            self.assertIn('test_file_errors', report)
            self.assertEqual(len(report['test_file_errors']), 1)
            
            error = report['test_file_errors'][0]
            self.assertIn('path', error)
            self.assertIn('error', error)
    
    def test_parse_kyverno_output_pass(self):
        """Test parsing Kyverno output with passing tests."""
        output = """
Loading policies...
Loading resources...
Applying 2 policy rule(s) to 2 resource(s)...

PASS: policy1/rule1/resource1
PASS: policy2/rule2/resource2
"""
        
        report = self.validator._parse_kyverno_output(output, "")
        
        self.assertEqual(report['total_tests'], 2)
        self.assertEqual(report['failed_tests'], 0)
        self.assertEqual(report['success_rate'], 100.0)
        self.assertEqual(len(report['failure']), 0)
    
    def test_parse_kyverno_output_mixed(self):
        """Test parsing Kyverno output with mixed results."""
        output = """
Loading policies...
Loading resources...
Applying 3 policy rule(s) to 3 resource(s)...

PASS: policy1/rule1/resource1
FAIL: policy2/rule2/resource2 -> validation error: missing label
PASS: policy3/rule3/resource3
"""
        
        report = self.validator._parse_kyverno_output(output, "")
        
        self.assertEqual(report['total_tests'], 3)
        self.assertEqual(report['failed_tests'], 1)
        self.assertEqual(report['success_rate'], 66.7)
        self.assertEqual(len(report['failure']), 1)
        
        failure = report['failure'][0]
        self.assertEqual(failure['policy'], 'policy2')
        self.assertEqual(failure['rule'], 'rule2')
        self.assertEqual(failure['resource'], 'resource2')
        self.assertEqual(failure['reason'], 'validation error: missing label')
    
    def test_parse_test_file_errors(self):
        """Test parsing test file errors from stderr."""
        stderr = """
Error: failed to load test file /path/to/test.yaml: duplicate key 'rule'
Warning: some other warning
Error: failed to parse resource file /path/to/resource.yaml: invalid YAML
"""
        
        errors = self.validator._parse_test_file_errors(stderr)
        
        self.assertEqual(len(errors), 2)
        
        self.assertEqual(errors[0]['path'], '/path/to/test.yaml')
        self.assertIn('duplicate key', errors[0]['error'])
        
        self.assertEqual(errors[1]['path'], '/path/to/resource.yaml')
        self.assertIn('invalid YAML', errors[1]['error'])
    
    def test_save_validation_report(self):
        """Test saving validation report to file."""
        report = {
            'total_tests': 2,
            'failed_tests': 1,
            'success_rate': 50.0,
            'failure': [
                {
                    'policy': 'test-policy',
                    'rule': 'test-rule',
                    'resource': 'test-resource',
                    'reason': 'validation failed'
                }
            ]
        }
        
        report_file = os.path.join(self.temp_dir, "validation-report.yaml")
        
        self.validator.save_validation_report(report, report_file)
        
        # Verify file was created and contains correct data
        self.assertTrue(os.path.exists(report_file))
        
        with open(report_file, 'r') as f:
            loaded_report = yaml.safe_load(f)
        
        self.assertEqual(loaded_report['validation_report']['total_tests'], 2)
        self.assertEqual(loaded_report['validation_report']['failed_tests'], 1)
        self.assertEqual(loaded_report['validation_report']['success_rate'], 50.0)
    
    def test_find_test_files(self):
        """Test finding test files in directory."""
        # Create test directory structure
        test_dir = os.path.join(self.temp_dir, "test_policies")
        os.makedirs(test_dir)
        
        # Create various files
        files_to_create = [
            "kyverno-test.yaml",
            "test.yaml", 
            "policy.yaml",
            "resource.yaml",
            "other-test.yaml"
        ]
        
        for filename in files_to_create:
            filepath = os.path.join(test_dir, filename)
            with open(filepath, 'w') as f:
                f.write("# Test file")
        
        test_files = self.validator._find_test_files(test_dir)
        
        # Should find test files (kyverno-test.yaml, test.yaml, other-test.yaml)
        self.assertGreaterEqual(len(test_files), 2)
        
        # Check that test files are found
        test_filenames = [os.path.basename(f) for f in test_files]
        self.assertIn("kyverno-test.yaml", test_filenames)
    
    def test_validate_no_kyverno_cli(self):
        """Test validation when Kyverno CLI is not available."""
        with patch.object(self.validator, 'check_kyverno_available', return_value=False):
            with self.assertRaises(ValidationError):
                self.validator.validate_policies(self.temp_dir)


if __name__ == '__main__':
    unittest.main()
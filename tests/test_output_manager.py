"""
Tests for output manager functionality.
"""

import unittest
import tempfile
import os
import yaml
from unittest.mock import Mock, patch
from pathlib import Path

from ai.output_manager import OutputManager
from models import PolicyCatalogEntry, RecommendedPolicy


class TestOutputManager(unittest.TestCase):
    """Test cases for OutputManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_manager = OutputManager(self.temp_dir)

        # Create sample policies
        self.sample_policies = [
            RecommendedPolicy(
                original_policy=PolicyCatalogEntry(
                    name="require-pod-resources",
                    category="best-practices",
                    description="Require pod resource limits",
                    relative_path="best-practices/require-pod-resources.yaml",
                    tags=["resources", "limits"],
                ),
                customized_content="# Policy content here",
                test_content="# Test content here",
                category="resource-management",
                validation_status="passed",
                customizations_applied=["registry_replacement"],
            ),
            RecommendedPolicy(
                original_policy=PolicyCatalogEntry(
                    name="restrict-image-registries",
                    category="security",
                    description="Restrict allowed image registries",
                    relative_path="security/restrict-image-registries.yaml",
                    tags=["registry", "images"],
                ),
                customized_content="# Security policy content",
                test_content="# Security test content",
                category="security-and-compliance",
                validation_status="passed",
                customizations_applied=["registry_replacement", "label_addition"],
            ),
        ]

        self.categories = ["resource-management", "security-and-compliance"]

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test OutputManager initialization."""
        self.assertEqual(self.output_manager.output_directory, self.temp_dir)
        self.assertTrue(os.path.exists(self.temp_dir))

    def test_create_category_structure(self):
        """Test creating category directory structure."""
        self.output_manager.create_category_structure(self.categories)

        # Check that category directories were created
        for category in self.categories:
            category_dir = os.path.join(self.temp_dir, category)
            self.assertTrue(os.path.exists(category_dir))
            self.assertTrue(os.path.isdir(category_dir))

    def test_organize_policies_by_category(self):
        """Test organizing policies by category."""
        organized = self.output_manager.organize_policies_by_category(
            self.sample_policies
        )

        self.assertIn("resource-management", organized)
        self.assertIn("security-and-compliance", organized)

        self.assertEqual(len(organized["resource-management"]), 1)
        self.assertEqual(len(organized["security-and-compliance"]), 1)

        # Check policy assignment
        resource_policy = organized["resource-management"][0]
        self.assertEqual(resource_policy.original_policy.name, "require-pod-resources")

        security_policy = organized["security-and-compliance"][0]
        self.assertEqual(
            security_policy.original_policy.name, "restrict-image-registries"
        )

    def test_write_policy_files(self):
        """Test writing policy files to disk."""
        # Create category structure
        self.output_manager.create_category_structure(self.categories)

        # Organize policies
        organized_policies = self.output_manager.organize_policies_by_category(
            self.sample_policies
        )

        # Write policy files
        written_files = self.output_manager.write_policy_files(organized_policies)

        # Check that files were written
        self.assertEqual(len(written_files), 2)

        # Check resource management policy
        resource_dir = os.path.join(
            self.temp_dir, "resource-management", "require-pod-resources"
        )
        self.assertTrue(os.path.exists(resource_dir))

        policy_file = os.path.join(resource_dir, "require-pod-resources.yaml")
        test_file = os.path.join(resource_dir, "kyverno-test.yaml")

        self.assertTrue(os.path.exists(policy_file))
        self.assertTrue(os.path.exists(test_file))

        # Check file contents
        with open(policy_file, "r") as f:
            policy_content = f.read()
        self.assertEqual(policy_content, "# Policy content here")

        with open(test_file, "r") as f:
            test_content = f.read()
        self.assertEqual(test_content, "# Test content here")

    def test_write_policy_files_no_test_content(self):
        """Test writing policy files when test content is missing."""
        # Create policy without test content
        policy_without_test = RecommendedPolicy(
            original_policy=PolicyCatalogEntry(
                name="test-policy",
                category="test",
                description="Test policy",
                relative_path="test/test-policy.yaml",
                tags=["test"],
            ),
            customized_content="# Policy content",
            test_content=None,  # No test content
            category="test-category",
            validation_status="passed",
            customizations_applied=[],
        )

        # Create category structure
        os.makedirs(os.path.join(self.temp_dir, "test-category"))

        # Organize and write
        organized = {"test-category": [policy_without_test]}
        written_files = self.output_manager.write_policy_files(organized)

        # Check that only policy file was written
        policy_dir = os.path.join(self.temp_dir, "test-category", "test-policy")
        policy_file = os.path.join(policy_dir, "test-policy.yaml")
        test_file = os.path.join(policy_dir, "kyverno-test.yaml")

        self.assertTrue(os.path.exists(policy_file))
        self.assertFalse(os.path.exists(test_file))

    def test_generate_deployment_guide(self):
        """Test generating deployment guide."""
        deployment_guide = self.output_manager.generate_deployment_guide(
            self.sample_policies, self.categories
        )

        # Check guide structure
        self.assertIn("# AEGIS Policy Deployment Guide", deployment_guide)
        self.assertIn("## Overview", deployment_guide)
        self.assertIn("## Categories", deployment_guide)
        self.assertIn("## Policies", deployment_guide)
        self.assertIn("## Deployment Instructions", deployment_guide)

        # Check that categories are mentioned
        for category in self.categories:
            self.assertIn(category, deployment_guide)

        # Check that policies are mentioned
        for policy in self.sample_policies:
            self.assertIn(policy.original_policy.name, deployment_guide)

    def test_write_deployment_guide(self):
        """Test writing deployment guide to file."""
        guide_content = self.output_manager.generate_deployment_guide(
            self.sample_policies, self.categories
        )

        guide_file = self.output_manager.write_deployment_guide(
            self.sample_policies, self.categories
        )

        # Check that file was created
        expected_path = os.path.join(self.temp_dir, "DEPLOYMENT_GUIDE.md")
        self.assertEqual(guide_file, expected_path)
        self.assertTrue(os.path.exists(guide_file))

        # Check file contents
        with open(guide_file, "r") as f:
            written_content = f.read()

        self.assertEqual(written_content, guide_content)

    def test_generate_summary_report(self):
        """Test generating summary report."""
        summary = self.output_manager.generate_summary_report(
            self.sample_policies, self.categories
        )

        # Check summary structure
        self.assertIn("total_policies", summary)
        self.assertIn("categories", summary)
        self.assertIn("validation_summary", summary)
        self.assertIn("customizations_summary", summary)
        self.assertIn("policies_by_category", summary)

        # Check values
        self.assertEqual(summary["total_policies"], 2)
        self.assertEqual(len(summary["categories"]), 2)
        self.assertEqual(summary["validation_summary"]["passed"], 2)
        self.assertEqual(summary["validation_summary"]["failed"], 0)

    def test_write_summary_report(self):
        """Test writing summary report to file."""
        summary_file = self.output_manager.write_summary_report(
            self.sample_policies, self.categories
        )

        # Check that file was created
        expected_path = os.path.join(self.temp_dir, "SUMMARY.yaml")
        self.assertEqual(summary_file, expected_path)
        self.assertTrue(os.path.exists(summary_file))

        # Check file contents
        with open(summary_file, "r") as f:
            loaded_summary = yaml.safe_load(f)

        self.assertIn("total_policies", loaded_summary)
        self.assertEqual(loaded_summary["total_policies"], 2)

    def test_create_complete_output(self):
        """Test creating complete organized output."""
        result = self.output_manager.create_complete_output(
            self.sample_policies, self.categories
        )

        # Check result structure
        self.assertIn("output_directory", result)
        self.assertIn("categories_created", result)
        self.assertIn("policies_written", result)
        self.assertIn("deployment_guide", result)
        self.assertIn("summary_report", result)

        # Check that all files were created
        self.assertEqual(result["output_directory"], self.temp_dir)
        self.assertEqual(len(result["categories_created"]), 2)
        self.assertEqual(len(result["policies_written"]), 2)

        # Check that guide and summary files exist
        self.assertTrue(os.path.exists(result["deployment_guide"]))
        self.assertTrue(os.path.exists(result["summary_report"]))

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # Test normal filename
        self.assertEqual(
            self.output_manager._sanitize_filename("normal-filename"), "normal-filename"
        )

        # Test filename with special characters
        self.assertEqual(
            self.output_manager._sanitize_filename("file/with\\special:chars"),
            "file-with-special-chars",
        )

        # Test filename with spaces
        self.assertEqual(
            self.output_manager._sanitize_filename("file with spaces"),
            "file-with-spaces",
        )

    def test_ensure_directory_exists(self):
        """Test directory creation."""
        test_dir = os.path.join(self.temp_dir, "nested", "directory", "structure")

        self.output_manager._ensure_directory_exists(test_dir)

        self.assertTrue(os.path.exists(test_dir))
        self.assertTrue(os.path.isdir(test_dir))


if __name__ == "__main__":
    unittest.main()

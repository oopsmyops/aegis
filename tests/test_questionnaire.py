"""
Unit tests for the AEGIS questionnaire system.
Tests the QuestionBank, QuestionnaireRunner, and YamlUpdater components.
"""

import unittest
import tempfile
import os
import yaml
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from questionnaire import QuestionBank, QuestionnaireRunner, YamlUpdater
from models import RequirementAnswer, GovernanceRequirements


class TestQuestionBank(unittest.TestCase):
    """Test cases for QuestionBank class."""

    def setUp(self):
        self.bank = QuestionBank()

    def test_question_count(self):
        """Test that exactly 19 questions are defined."""
        questions = self.bank.get_all_questions()
        self.assertEqual(len(questions), 19, "Should have exactly 19 questions")
        self.assertTrue(self.bank.validate_question_count())

    def test_question_structure(self):
        """Test that all questions have required fields."""
        questions = self.bank.get_all_questions()

        for question in questions:
            self.assertIsNotNone(question.id, "Question ID is required")
            self.assertIsNotNone(question.text, "Question text is required")
            self.assertIsNotNone(question.category, "Question category is required")
            self.assertTrue(
                len(question.text) > 10, "Question text should be descriptive"
            )

    def test_categories_present(self):
        """Test that all expected categories are present."""
        questions = self.bank.get_all_questions()
        categories = set(q.category for q in questions)

        expected_categories = {
            "image_security",
            "resource_management",
            "security_context",
            "network_security",
            "compliance",
        }

        for category in expected_categories:
            self.assertIn(category, categories, f"Missing category: {category}")

    def test_compliance_frameworks(self):
        """Test compliance frameworks are available."""
        frameworks = self.bank.get_compliance_frameworks()
        self.assertGreaterEqual(
            len(frameworks), 5, "Should have at least 5 compliance frameworks"
        )

        for framework in frameworks:
            self.assertIn("id", framework, "Framework should have ID")
            self.assertIn("name", framework, "Framework should have name")

    def test_follow_up_questions(self):
        """Test that follow-up questions are properly configured."""
        questions = self.bank.get_all_questions()
        follow_up_questions = [q for q in questions if q.follow_up_type.value != "none"]

        self.assertGreaterEqual(
            len(follow_up_questions), 3, "Should have at least 3 follow-up questions"
        )

        # Test specific follow-up questions
        registry_question = self.bank.get_question_by_id("img_registry_enforcement")
        self.assertIsNotNone(registry_question)
        self.assertEqual(registry_question.follow_up_type.value, "registry_list")


class TestQuestionnaireRunner(unittest.TestCase):
    """Test cases for QuestionnaireRunner class."""

    def setUp(self):
        self.bank = QuestionBank()
        self.runner = QuestionnaireRunner(self.bank)

    def test_registry_validation(self):
        """Test registry format validation."""
        # Valid registries
        self.assertTrue(self.runner._validate_registry_format("docker.io"))
        self.assertTrue(self.runner._validate_registry_format("gcr.io"))
        self.assertTrue(self.runner._validate_registry_format("localhost:5000"))
        self.assertTrue(self.runner._validate_registry_format("my-registry.com"))

        # Invalid registries
        self.assertFalse(self.runner._validate_registry_format(""))
        self.assertFalse(self.runner._validate_registry_format("invalid"))

    def test_build_governance_requirements(self):
        """Test building governance requirements object."""
        # Add some mock answers
        self.runner.answers = [
            RequirementAnswer("test_q1", True, category="test_category"),
            RequirementAnswer("test_q2", False, category="test_category"),
        ]
        self.runner.registries = ["docker.io"]
        self.runner.compliance_frameworks = ["cis"]
        self.runner.custom_labels = {"env": "prod"}

        requirements = self.runner._build_governance_requirements()

        self.assertEqual(len(requirements.answers), 2)
        self.assertEqual(requirements.registries, ["docker.io"])
        self.assertEqual(requirements.compliance_frameworks, ["cis"])
        self.assertEqual(requirements.custom_labels, {"env": "prod"})

    def test_summary_generation(self):
        """Test summary generation."""
        # Add some mock answers
        self.runner.answers = [
            RequirementAnswer("test_q1", True, category="category1"),
            RequirementAnswer("test_q2", False, category="category1"),
            RequirementAnswer("test_q3", True, category="category2"),
        ]

        summary = self.runner.get_summary()

        self.assertEqual(summary["total_questions"], 3)
        self.assertEqual(summary["yes_answers"], 2)
        self.assertEqual(summary["no_answers"], 1)
        self.assertIn("category1", summary["categories"])
        self.assertIn("category2", summary["categories"])


class TestYamlUpdater(unittest.TestCase):
    """Test cases for YamlUpdater class."""

    def setUp(self):
        self.updater = YamlUpdater()

    def test_yaml_update_functionality(self):
        """Test updating YAML file with governance requirements."""
        # Create temporary YAML file
        test_data = {
            "cluster_info": {"kubernetes_version": "1.32"},
            "discovery_metadata": {"tool": "AEGIS"},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as temp_file:
            yaml.dump(test_data, temp_file)
            temp_path = temp_file.name

        try:
            # Create mock requirements
            mock_answers = [
                RequirementAnswer("test_q1", True, category="test_category")
            ]

            requirements = GovernanceRequirements(
                answers=mock_answers,
                registries=["docker.io"],
                compliance_frameworks=["cis"],
                custom_labels={"env": "prod"},
            )

            # Update YAML
            self.updater.append_to_cluster_yaml(requirements, temp_path)

            # Verify update
            with open(temp_path, "r") as f:
                updated_data = yaml.safe_load(f)

            self.assertIn("governance_requirements", updated_data)

            gov_req = updated_data["governance_requirements"]
            self.assertIn("collection_timestamp", gov_req)
            self.assertIn("total_questions", gov_req)
            self.assertIn("summary", gov_req)
            self.assertIn("answers", gov_req)
            self.assertIn("configurations", gov_req)

            # Check configurations
            configs = gov_req["configurations"]
            self.assertEqual(configs["allowed_registries"], ["docker.io"])
            self.assertEqual(configs["compliance_frameworks"], ["cis"])
            self.assertEqual(configs["custom_labels"]["env"], "prod")

        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_yaml_validation(self):
        """Test YAML structure validation."""
        # Create valid YAML
        valid_data = {
            "cluster_info": {"version": "1.32"},
            "discovery_metadata": {"tool": "AEGIS"},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as temp_file:
            yaml.dump(valid_data, temp_file)
            temp_path = temp_file.name

        try:
            self.assertTrue(self.updater.validate_yaml_structure(temp_path))
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()

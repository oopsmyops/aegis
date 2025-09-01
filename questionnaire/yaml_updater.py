"""
YAML updater for appending questionnaire answers to cluster-discovery.yaml.
Handles merging governance requirements with existing cluster data.
"""

import yaml
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from models import GovernanceRequirements, RequirementAnswer
from exceptions import QuestionnaireError, FileSystemError


class YamlUpdater:
    """Handles updating cluster-discovery.yaml with questionnaire answers."""

    def __init__(self):
        self.default_yaml_path = "cluster-discovery.yaml"

    def append_to_cluster_yaml(
        self, requirements: GovernanceRequirements, yaml_path: Optional[str] = None
    ) -> None:
        """Append questionnaire answers to existing cluster discovery YAML."""
        file_path = yaml_path or self.default_yaml_path

        try:
            # Load existing cluster data
            cluster_data = self._load_existing_yaml(file_path)

            # Add governance requirements section
            governance_section = self._build_governance_section(requirements)
            cluster_data["governance_requirements"] = governance_section

            # Update metadata
            if "discovery_metadata" not in cluster_data:
                cluster_data["discovery_metadata"] = {}

            cluster_data["discovery_metadata"]["questionnaire_completed"] = True
            cluster_data["discovery_metadata"][
                "questionnaire_timestamp"
            ] = datetime.now().isoformat()
            cluster_data["discovery_metadata"]["requirements_version"] = "1.0.0"

            # Write updated data back to file
            self._write_yaml_file(cluster_data, file_path)

            print(f"Successfully updated {file_path} with governance requirements.")

        except Exception as e:
            raise QuestionnaireError(f"Failed to update YAML file", str(e))

    def _load_existing_yaml(self, file_path: str) -> Dict[str, Any]:
        """Load existing cluster discovery YAML file."""
        if not os.path.exists(file_path):
            raise FileSystemError(f"Cluster discovery file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file)

            if not isinstance(data, dict):
                raise QuestionnaireError(
                    "Invalid YAML structure", "Expected dictionary at root level"
                )

            return data

        except yaml.YAMLError as e:
            raise QuestionnaireError(f"Failed to parse YAML file: {file_path}", str(e))
        except IOError as e:
            raise FileSystemError(f"Failed to read file: {file_path}", str(e))

    def _build_governance_section(
        self, requirements: GovernanceRequirements
    ) -> Dict[str, Any]:
        """Build the governance requirements section for YAML."""
        governance_data = {
            "collection_timestamp": requirements.collection_timestamp.isoformat(),
            "total_questions": len(requirements.answers),
            "summary": self._build_summary(requirements),
            "answers": self._build_answers_section(requirements.answers),
            "configurations": self._build_configurations_section(requirements),
        }

        return governance_data

    def _build_summary(self, requirements: GovernanceRequirements) -> Dict[str, Any]:
        """Build summary statistics for the governance requirements."""
        yes_count = sum(1 for answer in requirements.answers if answer.answer)
        no_count = len(requirements.answers) - yes_count

        # Group by category
        categories = {}
        for answer in requirements.answers:
            if answer.category not in categories:
                categories[answer.category] = {"yes": 0, "no": 0, "total": 0}

            categories[answer.category]["total"] += 1
            if answer.answer:
                categories[answer.category]["yes"] += 1
            else:
                categories[answer.category]["no"] += 1

        return {
            "total_yes": yes_count,
            "total_no": no_count,
            "categories": categories,
            "has_registries": len(requirements.registries) > 0,
            "has_compliance_frameworks": len(requirements.compliance_frameworks) > 0,
            "has_custom_labels": len(requirements.custom_labels) > 0,
        }

    def _build_answers_section(
        self, answers: List[RequirementAnswer]
    ) -> Dict[str, Any]:
        """Build the detailed answers section."""
        answers_by_category = {}

        for answer in answers:
            if answer.category not in answers_by_category:
                answers_by_category[answer.category] = []

            answer_data = {
                "question_id": answer.question_id,
                "answer": answer.answer,
            }

            # Add follow-up data if present
            if answer.follow_up_data:
                answer_data["follow_up_data"] = answer.follow_up_data

            answers_by_category[answer.category].append(answer_data)

        return answers_by_category

    def _build_configurations_section(
        self, requirements: GovernanceRequirements
    ) -> Dict[str, Any]:
        """Build the configurations section with collected data."""
        configurations = {}

        # Add registries if any
        if requirements.registries:
            configurations["allowed_registries"] = requirements.registries

        # Add compliance frameworks if any
        if requirements.compliance_frameworks:
            configurations["compliance_frameworks"] = requirements.compliance_frameworks

        # Add custom labels if any
        if requirements.custom_labels:
            configurations["custom_labels"] = requirements.custom_labels

        return configurations

    def _write_yaml_file(self, data: Dict[str, Any], file_path: str) -> None:
        """Write data to YAML file with proper formatting."""
        try:
            # Create backup of original file
            backup_path = f"{file_path}.backup"
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as original:
                    with open(backup_path, "w", encoding="utf-8") as backup:
                        backup.write(original.read())

            # Write updated data
            with open(file_path, "w", encoding="utf-8") as file:
                yaml.dump(
                    data,
                    file,
                    default_flow_style=False,
                    sort_keys=False,
                    indent=2,
                    allow_unicode=True,
                )

            # Remove backup if write was successful
            if os.path.exists(backup_path):
                os.remove(backup_path)

        except IOError as e:
            # Restore from backup if write failed
            backup_path = f"{file_path}.backup"
            if os.path.exists(backup_path):
                os.rename(backup_path, file_path)
            raise FileSystemError(f"Failed to write YAML file: {file_path}", str(e))

    def validate_yaml_structure(self, file_path: str) -> bool:
        """Validate that the YAML file has the expected structure."""
        try:
            data = self._load_existing_yaml(file_path)

            # Check for required sections
            required_sections = ["cluster_info", "discovery_metadata"]
            for section in required_sections:
                if section not in data:
                    return False

            return True

        except Exception:
            return False

    def get_existing_requirements(
        self, file_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get existing governance requirements from YAML file if present."""
        yaml_path = file_path or self.default_yaml_path

        try:
            data = self._load_existing_yaml(yaml_path)
            return data.get("governance_requirements")

        except Exception:
            return None

    def remove_governance_section(self, file_path: Optional[str] = None) -> None:
        """Remove governance requirements section from YAML file."""
        yaml_path = file_path or self.default_yaml_path

        try:
            data = self._load_existing_yaml(yaml_path)

            if "governance_requirements" in data:
                del data["governance_requirements"]

                # Update metadata
                if "discovery_metadata" in data:
                    data["discovery_metadata"]["questionnaire_completed"] = False
                    if "questionnaire_timestamp" in data["discovery_metadata"]:
                        del data["discovery_metadata"]["questionnaire_timestamp"]

                self._write_yaml_file(data, yaml_path)
                print(f"Removed governance requirements from {yaml_path}")
            else:
                print(f"No governance requirements found in {yaml_path}")

        except Exception as e:
            raise QuestionnaireError(f"Failed to remove governance section", str(e))

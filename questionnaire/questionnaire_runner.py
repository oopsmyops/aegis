"""
Interactive questionnaire runner for AEGIS governance requirements.
Handles the execution of questions and follow-up logic.
"""

import sys
from typing import Dict, List, Optional, Any
from models import RequirementAnswer, GovernanceRequirements
from exceptions import QuestionnaireError
from .question_bank import QuestionBank, Question, FollowUpType


class QuestionnaireRunner:
    """Main questionnaire orchestrator for gathering governance requirements."""

    def __init__(self, question_bank: Optional[QuestionBank] = None):
        self.question_bank = question_bank or QuestionBank()
        self.answers: List[RequirementAnswer] = []
        self.registries: List[str] = []
        self.compliance_frameworks: List[str] = []
        self.custom_labels: List[str] = []

    def run_questionnaire(self) -> GovernanceRequirements:
        """Execute interactive questionnaire with fixed set of questions."""
        try:
            print("\n" + "=" * 60)
            print("AEGIS Governance Requirements Questionnaire")
            print("=" * 60)
            print("Please answer the following questions to help determine")
            print("appropriate governance policies for your cluster.")
            print("Answer with 'y' for yes, 'n' for no, or 'q' to quit.\n")

            # Validate question count
            if not self.question_bank.validate_question_count():
                raise QuestionnaireError(
                    "Invalid question count",
                    f"Expected 19 questions, found {len(self.question_bank.get_all_questions())}",
                )

            questions = self.question_bank.get_all_questions()

            for i, question in enumerate(questions, 1):
                print(f"Question {i}/19:")
                answer = self._ask_question(question)

                if answer is None:  # User quit
                    print("\nQuestionnaire cancelled by user.")
                    return GovernanceRequirements()

                # Store the answer
                requirement_answer = RequirementAnswer(
                    question_id=question.id, answer=answer, category=question.category
                )

                # Handle follow-up questions if answer is yes
                if answer and question.follow_up_type != FollowUpType.NONE:
                    follow_up_data = self._ask_follow_up_questions(question)
                    requirement_answer.follow_up_data = follow_up_data

                self.answers.append(requirement_answer)
                print()  # Add spacing between questions

            print("=" * 60)
            print("Questionnaire completed successfully!")
            print(f"Collected {len(self.answers)} responses.")
            print("=" * 60)

            return self._build_governance_requirements()

        except KeyboardInterrupt:
            print("\n\nQuestionnaire interrupted by user.")
            return GovernanceRequirements()
        except Exception as e:
            raise QuestionnaireError("Failed to run questionnaire", str(e))

    def _ask_question(self, question: Question) -> Optional[bool]:
        """Ask a single question and get yes/no response."""
        while True:
            try:
                response = input(f"{question.text} (y/n/q): ").strip().lower()

                if response == "q":
                    return None
                elif response in ["y", "yes"]:
                    return True
                elif response in ["n", "no"]:
                    return False
                else:
                    print("Please answer with 'y' for yes, 'n' for no, or 'q' to quit.")

            except EOFError:
                return None

    def _ask_follow_up_questions(self, question: Question) -> Dict[str, Any]:
        """Handle follow-up questions for yes responses."""
        follow_up_data = {}

        try:
            if question.follow_up_type == FollowUpType.REGISTRY_LIST:
                follow_up_data = self._ask_registry_list(question)

            elif question.follow_up_type == FollowUpType.COMPLIANCE_FRAMEWORKS:
                follow_up_data = self._ask_compliance_frameworks(question)

            elif question.follow_up_type == FollowUpType.CUSTOM_LABELS:
                follow_up_data = self._ask_custom_labels(question)

            # elif question.follow_up_type == FollowUpType.RESOURCE_LIMITS:
            #     follow_up_data = self._ask_resource_limits(question)

        except Exception as e:
            print(f"Error in follow-up question: {e}")
            print("Skipping follow-up data collection.")

        return follow_up_data

    def _ask_registry_list(self, question: Question) -> Dict[str, Any]:
        """Ask for comma-separated list of allowed registries."""
        print(f"\n{question.follow_up_prompt}")
        print("Examples: docker.io, gcr.io, quay.io, your-registry.com")

        while True:
            try:
                registries_input = input("Registries: ").strip()

                if not registries_input:
                    print("Please enter at least one registry or press Enter to skip.")
                    skip = input("Skip registry configuration? (y/n): ").strip().lower()
                    if skip in ["y", "yes"]:
                        return {"registries": []}
                    continue

                # Parse and validate registries
                registries = [
                    r.strip() for r in registries_input.split(",") if r.strip()
                ]

                if not registries:
                    print("No valid registries found. Please try again.")
                    continue

                # Basic validation
                valid_registries = []
                for registry in registries:
                    if self._validate_registry_format(registry):
                        valid_registries.append(registry)
                    else:
                        print(
                            f"Warning: '{registry}' may not be a valid registry format"
                        )
                        valid_registries.append(registry)  # Include anyway

                self.registries.extend(valid_registries)
                return {"registries": valid_registries}

            except EOFError:
                return {"registries": []}

    def _ask_compliance_frameworks(self, question: Question) -> Dict[str, Any]:
        """Ask for compliance framework selection."""
        frameworks = self.question_bank.get_compliance_frameworks()

        print(f"\n{question.follow_up_prompt}")
        print("Available frameworks:")
        for i, framework in enumerate(frameworks, 1):
            print(f"  {i}. {framework['name']} ({framework['id']})")

        print(
            "\nEnter numbers separated by commas (e.g., 1,3,5) or press Enter to skip:"
        )

        try:
            selection = input("Frameworks: ").strip()

            if not selection:
                return {"compliance_frameworks": []}

            # Parse selections
            selected_frameworks = []
            try:
                indices = [
                    int(x.strip()) - 1 for x in selection.split(",") if x.strip()
                ]

                for idx in indices:
                    if 0 <= idx < len(frameworks):
                        selected_frameworks.append(frameworks[idx]["id"])
                    else:
                        print(f"Warning: Invalid selection {idx + 1}, skipping.")

            except ValueError:
                print("Invalid input format. Skipping compliance framework selection.")
                return {"compliance_frameworks": []}

            self.compliance_frameworks.extend(selected_frameworks)
            return {"compliance_frameworks": selected_frameworks}

        except EOFError:
            return {"compliance_frameworks": []}

    def _ask_custom_labels(self, question: Question) -> Dict[str, Any]:
        """Ask for custom label requirements."""
        print(f"\n{question.follow_up_prompt}")
        print("Examples: environment, team, cost-center")
        # ================================================================================
        while True:
            try:
                labels_input = input("Labels: ").strip()

                if not labels_input:
                    print("Please enter at least one label or press Enter to skip.")
                    skip = input("Skip label configuration? (y/n): ").strip().lower()
                    if skip in ["y", "yes"]:
                        return {"custom_labels": []}
                    continue

                # Parse and validate labels
                labels = [l.strip() for l in labels_input.split(",") if l.strip()]

                if not labels:
                    print("No valid labels found. Please try again.")
                    continue

                self.custom_labels.extend(labels)
                return {"custom_labels": labels}

            except EOFError:
                return {"custom_labels": []}
        # ================================================================================
        try:
            labels_input = input("Labels: ").strip()

            if not labels_input:
                return {"custom_labels": {}}

            # Parse labels
            labels = {}
            try:
                for label_pair in labels_input.split(","):
                    label_pair = label_pair.strip()
                    if "=" in label_pair:
                        key, value = label_pair.split("=", 1)
                        labels[key.strip()] = value.strip()
                    else:
                        print(
                            f"Warning: Invalid label format '{label_pair}', skipping."
                        )

            except Exception as e:
                print(f"Error parsing labels: {e}")
                return {"custom_labels": {}}

            self.custom_labels.update(labels)
            return {"custom_labels": labels}

        except EOFError:
            return {"custom_labels": {}}

    # def _ask_resource_limits(self, question: Question) -> Dict[str, Any]:
    #     """Ask for resource limit specifications."""
    #     print(f"\n{question.follow_up_prompt}")
    #     print("Examples: cpu=500m, memory=512Mi, storage=1Gi")
    #     print("You can specify default, min, and max values for each resource type.")

    #     try:
    #         limits_input = input("Resource limits: ").strip()

    #         if not limits_input:
    #             print("Please enter resource limits or press Enter to skip.")
    #             skip = (
    #                 input("Skip resource limits configuration? (y/n): ").strip().lower()
    #             )
    #             if skip in ["y", "yes"]:
    #                 return {"resource_limits": {}}
    #             return self._ask_resource_limits(question)  # Ask again

    #         # Parse resource limits
    #         limits = {}
    #         try:
    #             for limit_pair in limits_input.split(","):
    #                 limit_pair = limit_pair.strip()
    #                 if "=" in limit_pair:
    #                     resource, value = limit_pair.split("=", 1)
    #                     limits[resource.strip()] = value.strip()
    #                 else:
    #                     print(
    #                         f"Warning: Invalid limit format '{limit_pair}', skipping."
    #                     )

    #         except Exception as e:
    #             print(f"Error parsing resource limits: {e}")
    #             return {"resource_limits": {}}

    #         return {"resource_limits": limits}

    #     except EOFError:
    #         return {"resource_limits": {}}

    def _validate_registry_format(self, registry: str) -> bool:
        """Basic validation for registry format."""
        # Simple validation - check for basic domain format
        if not registry:
            return False

        # Allow localhost and IP addresses for development
        if (
            registry.startswith("localhost")
            or registry.replace(".", "").replace(":", "").isdigit()
        ):
            return True

        # Basic domain validation
        parts = registry.split(".")
        return len(parts) >= 2 and all(part for part in parts)

    def _build_governance_requirements(self) -> GovernanceRequirements:
        """Build the final governance requirements object."""
        return GovernanceRequirements(
            answers=self.answers,
            registries=self.registries,
            compliance_frameworks=self.compliance_frameworks,
            custom_labels=self.custom_labels,
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of collected requirements."""
        yes_answers = sum(1 for answer in self.answers if answer.answer)
        no_answers = len(self.answers) - yes_answers

        categories = {}
        for answer in self.answers:
            if answer.category not in categories:
                categories[answer.category] = {"yes": 0, "no": 0}

            if answer.answer:
                categories[answer.category]["yes"] += 1
            else:
                categories[answer.category]["no"] += 1

        return {
            "total_questions": len(self.answers),
            "yes_answers": yes_answers,
            "no_answers": no_answers,
            "categories": categories,
            "registries_count": len(self.registries),
            "compliance_frameworks_count": len(self.compliance_frameworks),
            "custom_labels_count": len(self.custom_labels),
        }

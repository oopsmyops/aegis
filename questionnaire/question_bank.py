"""
Question bank for AEGIS governance questionnaire.
Contains exactly 20 governance-related yes/no questions with follow-up logic.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum


class FollowUpType(Enum):
    """Types of follow-up questions."""

    REGISTRY_LIST = "registry_list"
    COMPLIANCE_FRAMEWORKS = "compliance_frameworks"
    CUSTOM_LABELS = "custom_labels"
    RESOURCE_LIMITS = "resource_limits"
    NONE = "none"


@dataclass
class Question:
    """Represents a governance question."""

    id: str
    text: str
    category: str
    follow_up_type: FollowUpType = FollowUpType.NONE
    follow_up_prompt: Optional[str] = None


class QuestionBank:
    """Repository of exactly 20 governance questions."""

    def __init__(self):
        self._questions = self._initialize_questions()

    def _initialize_questions(self) -> List[Question]:
        """Initialize the fixed set of 19 governance questions."""
        return [
            # Image Security Questions (4)
            Question(
                id="img_registry_enforcement",
                text="Do you want to enforce allowed container image registries?",
                category="image_security",
                follow_up_type=FollowUpType.REGISTRY_LIST,
                follow_up_prompt="Please enter comma-separated list of allowed registries (e.g., docker.io,gcr.io,quay.io):",
            ),
            Question(
                id="img_signature_verification",
                text="Do you require container image signature verification?",
                category="image_security",
            ),
            Question(
                id="img_vulnerability_scanning",
                text="Do you want to enforce vulnerability scanning for container images?",
                category="image_security",
            ),
            Question(
                id="img_latest_tag_prevention",
                text="Do you want to prevent the use of 'latest' tags in production?",
                category="image_security",
            ),
            # Resource Management Questions (4)
            Question(
                id="res_limits_required",
                text="Do you want to require resource limits (CPU/memory) for all containers?",
                category="resource_management",
            ),
            Question(
                id="res_requests_required",
                text="Do you want to require resource requests for all containers?",
                category="resource_management",
            ),
            Question(
                id="res_quota_enforcement",
                text="Do you want to enforce namespace resource quotas?",
                category="resource_management",
            ),
            Question(
                id="res_limit_ranges",
                text="Do you want to enforce limit ranges for pods and containers?",
                category="resource_management",
                follow_up_type=FollowUpType.RESOURCE_LIMITS,
                follow_up_prompt="Please specify resource limits (e.g., cpu=500m,memory=512Mi,storage=1Gi):",
            ),
            # Security Context Questions (4)
            Question(
                id="sec_non_root_required",
                text="Do you want to require containers to run as non-root users?",
                category="security_context",
            ),
            Question(
                id="sec_privileged_prevention",
                text="Do you want to prevent privileged containers?",
                category="security_context",
            ),
            Question(
                id="sec_capabilities_restriction",
                text="Do you want to restrict Linux capabilities for containers?",
                category="security_context",
            ),
            Question(
                id="sec_readonly_filesystem",
                text="Do you want to enforce read-only root filesystems for containers?",
                category="security_context",
            ),
            # Network Security Questions (3)
            Question(
                id="net_policies_required",
                text="Do you want to require network policies for pod-to-pod communication?",
                category="network_security",
            ),
            Question(
                id="net_ingress_restrictions",
                text="Do you want to restrict ingress traffic to specific sources?",
                category="network_security",
            ),
            Question(
                id="net_service_mesh_enforcement",
                text="Do you want to enforce service mesh policies for inter-service communication?",
                category="network_security",
            ),
            # Compliance and Governance Questions (4)
            Question(
                id="comp_framework_adherence",
                text="Do you need to adhere to specific compliance frameworks?",
                category="compliance",
                follow_up_type=FollowUpType.COMPLIANCE_FRAMEWORKS,
                follow_up_prompt="Please select applicable compliance frameworks:",
            ),
            Question(
                id="comp_labeling_standards",
                text="Do you want to enforce mandatory labeling standards?",
                category="compliance",
                follow_up_type=FollowUpType.CUSTOM_LABELS,
                follow_up_prompt="Please enter required labels in key=value format (comma-separated):",
            ),
            Question(
                id="comp_pod_disruption_budgets",
                text="Do you want to require Pod Disruption Budgets for high-availability workloads?",
                category="compliance",
            ),
            Question(
                id="comp_audit_logging",
                text="Do you want to enforce audit logging and monitoring requirements?",
                category="compliance",
            ),
        ]

    def get_all_questions(self) -> List[Question]:
        """Get all 20 questions."""
        return self._questions.copy()

    def get_question_by_id(self, question_id: str) -> Optional[Question]:
        """Get a specific question by ID."""
        for question in self._questions:
            if question.id == question_id:
                return question
        return None

    def get_questions_by_category(self, category: str) -> List[Question]:
        """Get all questions in a specific category."""
        return [q for q in self._questions if q.category == category]

    def get_compliance_frameworks(self) -> List[Dict[str, str]]:
        """Get available compliance frameworks for selection."""
        return [
            {"id": "cis", "name": "CIS Kubernetes Benchmark"},
            {"id": "nist", "name": "NIST Cybersecurity Framework"},
            {"id": "pci", "name": "PCI DSS"},
            {"id": "hipaa", "name": "HIPAA"},
            {"id": "sox", "name": "Sarbanes-Oxley (SOX)"},
            {"id": "gdpr", "name": "GDPR"},
            {"id": "iso27001", "name": "ISO 27001"},
            {"id": "fedramp", "name": "FedRAMP"},
        ]

    def validate_question_count(self) -> bool:
        """Validate that exactly 19 questions are defined."""
        return len(self._questions) == 19

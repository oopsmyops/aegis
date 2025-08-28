"""
Core data models for AEGIS CLI tool.
Defines data structures for cluster information, policies, and requirements.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ControllerType(Enum):
    """Types of third-party controllers."""

    GITOPS = "gitops"
    SERVICE_MESH = "service-mesh"
    INGRESS = "ingress"
    SECRETS = "secrets"
    MONITORING = "monitoring"
    SECURITY = "security"


@dataclass
class ThirdPartyController:
    """Represents a third-party controller in the cluster."""

    name: str
    type: ControllerType
    namespace: str
    version: Optional[str] = None
    configuration: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClusterInfo:
    """Comprehensive cluster information model."""

    version: str
    managed_service: Optional[str] = None  # EKS, AKS, GKE, etc.
    node_count: int = 0
    namespace_count: int = 0
    third_party_controllers: List[ThirdPartyController] = field(default_factory=list)
    security_features: Dict[str, bool] = field(default_factory=dict)
    compliance_frameworks: List[str] = field(default_factory=list)
    resource_types: List[str] = field(default_factory=list)
    discovery_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PolicyCatalogEntry:
    """Represents a policy in the catalog."""

    name: str
    category: str
    description: str
    relative_path: str  # Path to policy file in catalog
    test_directory: Optional[str] = None  # Path to directory containing test files
    source_repo: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class PolicyIndex:
    """Index of all policies in the catalog."""

    categories: Dict[str, List[PolicyCatalogEntry]] = field(default_factory=dict)
    total_policies: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

    def get_policies_by_category(
        self, category: str, limit: Optional[int] = None
    ) -> List[PolicyCatalogEntry]:
        """Get policies for a category."""
        if category not in self.categories:
            return []

        policies = self.categories[category]
        if limit:
            return policies[:limit]
        return policies


@dataclass
class RequirementAnswer:
    """Represents an answer to a questionnaire question."""

    question_id: str
    answer: bool
    follow_up_data: Optional[Dict[str, Any]] = None
    category: str = ""


@dataclass
class GovernanceRequirements:
    """Collection of governance requirements from questionnaire."""

    answers: List[RequirementAnswer] = field(default_factory=list)
    registries: List[str] = field(default_factory=list)
    compliance_frameworks: List[str] = field(default_factory=list)
    custom_labels: Dict[str, str] = field(default_factory=dict)
    collection_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RecommendedPolicy:
    """Represents a recommended policy with customizations."""

    original_policy: PolicyCatalogEntry
    customized_content: str
    test_content: Optional[str] = None
    category: str = ""
    validation_status: str = "pending"  # pending, passed, failed
    customizations_applied: List[str] = field(default_factory=list)


@dataclass
class PolicyRecommendation:
    """Complete policy recommendation result."""

    cluster_info: ClusterInfo
    requirements: GovernanceRequirements
    recommended_policies: List[RecommendedPolicy] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    generation_timestamp: datetime = field(default_factory=datetime.now)
    ai_model_used: str = ""
    validation_summary: Dict[str, int] = field(default_factory=dict)

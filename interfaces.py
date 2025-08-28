"""
Core interfaces and abstract base classes for AEGIS components.
Defines contracts for cluster discovery, questionnaire, catalog management, and AI selection.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

# Handle imports for both development and binary execution
try:
    from models import (
        ClusterInfo,
        GovernanceRequirements,
        PolicyIndex,
        PolicyCatalogEntry,
        RecommendedPolicy,
        PolicyRecommendation,
    )
except ImportError:
    try:
        from aegis.models import (
            ClusterInfo,
            GovernanceRequirements,
            PolicyIndex,
            PolicyCatalogEntry,
            RecommendedPolicy,
            PolicyRecommendation,
        )
    except ImportError:
        # Fallback for binary execution - define minimal types
        import os
        import sys

        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        try:
            from models import (
                ClusterInfo,
                GovernanceRequirements,
                PolicyIndex,
                PolicyCatalogEntry,
                RecommendedPolicy,
                PolicyRecommendation,
            )
        except ImportError:
            # Final fallback - use Any for type hints
            ClusterInfo = Any
            GovernanceRequirements = Any
            PolicyIndex = Any
            PolicyCatalogEntry = Any
            RecommendedPolicy = Any
            PolicyRecommendation = Any


class ClusterDiscoveryInterface(ABC):
    """Interface for cluster discovery functionality."""

    @abstractmethod
    def discover_cluster(self) -> ClusterInfo:
        """Discover comprehensive cluster information."""
        pass

    @abstractmethod
    def detect_managed_service(self) -> Optional[str]:
        """Detect if cluster is EKS, AKS, GKE, etc."""
        pass

    @abstractmethod
    def scan_third_party_controllers(self) -> List[Dict[str, Any]]:
        """Identify GitOps, service mesh, ingress controllers."""
        pass

    @abstractmethod
    def export_to_yaml(self, cluster_info: ClusterInfo, output_path: str) -> None:
        """Export discovery results to YAML."""
        pass


class QuestionnaireInterface(ABC):
    """Interface for interactive questionnaire functionality."""

    @abstractmethod
    def run_questionnaire(self) -> GovernanceRequirements:
        """Execute interactive questionnaire with fixed set of questions."""
        pass

    @abstractmethod
    def ask_follow_up_questions(self, answer: str, question_id: str) -> Dict[str, Any]:
        """Handle follow-up questions for yes responses."""
        pass

    @abstractmethod
    def append_to_cluster_yaml(
        self, requirements: GovernanceRequirements, yaml_path: str
    ) -> None:
        """Append answers to existing cluster discovery YAML."""
        pass


class PolicyCatalogInterface(ABC):
    """Interface for policy catalog management."""

    @abstractmethod
    def create_catalog_from_repos(self, repo_urls: List[str]) -> None:
        """Create policy catalog from GitHub repositories."""
        pass

    @abstractmethod
    def build_policy_index(self) -> PolicyIndex:
        """Build lightweight metadata index with policy paths and summaries."""
        pass

    @abstractmethod
    def get_all_policies_lightweight(self) -> List[Dict[str, Any]]:
        """Get all policies with minimal metadata for Phase 1 AI filtering."""
        pass

    @abstractmethod
    def get_policies_detailed(self, policy_names: List[str]) -> List[Dict[str, Any]]:
        """Get detailed policy information for Phase 2 AI selection."""
        pass


class AIPolicySelectorInterface(ABC):
    """Interface for AI-powered policy selection and customization."""

    @abstractmethod
    def select_policies(
        self, cluster_info: ClusterInfo, requirements: GovernanceRequirements
    ) -> List[PolicyCatalogEntry]:
        """Select appropriate policies using AI."""
        pass

    @abstractmethod
    def determine_categories(
        self, cluster_info: ClusterInfo, selected_policies: List[PolicyCatalogEntry]
    ) -> List[str]:
        """Dynamically determine output categories using AI."""
        pass

    @abstractmethod
    def customize_policies(
        self, policies: List[PolicyCatalogEntry], requirements: GovernanceRequirements
    ) -> List[RecommendedPolicy]:
        """Customize policies based on requirements."""
        pass

    @abstractmethod
    def validate_and_fix_policies(
        self, policies: List[RecommendedPolicy]
    ) -> List[RecommendedPolicy]:
        """Run Kyverno tests and fix failures."""
        pass


class BedrockClientInterface(ABC):
    """Interface for AWS Bedrock integration."""

    @abstractmethod
    def send_request(self, prompt: str, max_tokens: int = 4000) -> str:
        """Send request to AWS Bedrock and return response."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if Bedrock service is available."""
        pass


class PolicyValidatorInterface(ABC):
    """Interface for policy validation functionality."""

    @abstractmethod
    def validate_policy(
        self, policy_content: str, test_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate a single policy using Kyverno CLI."""
        pass

    @abstractmethod
    def fix_policy_issues(
        self, policy_content: str, validation_errors: List[str]
    ) -> str:
        """Attempt to fix common policy issues."""
        pass

    @abstractmethod
    def generate_test_case(self, policy_content: str) -> str:
        """Generate test case for policy if missing."""
        pass


class ConfigurationInterface(ABC):
    """Interface for configuration management."""

    @abstractmethod
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from file."""
        pass

    @abstractmethod
    def save_config(
        self, config: Dict[str, Any], config_path: Optional[str] = None
    ) -> None:
        """Save configuration to file."""
        pass

    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values."""
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration structure and values."""
        pass

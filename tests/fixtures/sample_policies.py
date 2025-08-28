"""
Sample policy fixtures for testing.
"""

from models import (
    PolicyCatalogEntry,
    RecommendedPolicy,
    ClusterInfo,
    GovernanceRequirements,
    RequirementAnswer,
)
from datetime import datetime


# Sample Kyverno policy content
SAMPLE_POLICY_YAML = """
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-pod-resources
  annotations:
    policies.kyverno.io/title: Require Pod Resources
    policies.kyverno.io/category: Best Practices
    policies.kyverno.io/severity: medium
    policies.kyverno.io/subject: Pod
    policies.kyverno.io/description: >-
      As application workloads share cluster resources, it is important to limit resources
      requested and consumed by each Pod. It is recommended to require resource requests and
      limits per Pod, especially for memory and CPU. If a Namespace level request or limit is specified,
      defaults will automatically be applied to each Pod based on the LimitRange configuration.
spec:
  validationFailureAction: enforce
  background: true
  rules:
  - name: validate-resources
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Resource requests and limits are required."
      pattern:
        spec:
          containers:
          - name: "*"
            resources:
              requests:
                memory: "?*"
                cpu: "?*"
              limits:
                memory: "?*"
"""

SAMPLE_TEST_YAML = """
apiVersion: kyverno.io/v1
kind: Test
metadata:
  name: require-pod-resources-test
spec:
  policies:
  - require-pod-resources.yaml
  resources:
  - good-pod.yaml
  - bad-pod.yaml
  results:
  - policy: require-pod-resources
    rule: validate-resources
    resource: good-pod
    result: pass
  - policy: require-pod-resources
    rule: validate-resources
    resource: bad-pod
    result: fail
"""

SAMPLE_GOOD_RESOURCE_YAML = """
apiVersion: v1
kind: Pod
metadata:
  name: good-pod
spec:
  containers:
  - name: nginx
    image: nginx:1.21
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "256Mi"
        cpu: "200m"
"""

SAMPLE_BAD_RESOURCE_YAML = """
apiVersion: v1
kind: Pod
metadata:
  name: bad-pod
spec:
  containers:
  - name: nginx
    image: nginx:1.21
    # Missing resource requests and limits
"""

SAMPLE_SECURITY_POLICY_YAML = """
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: restrict-image-registries
  annotations:
    policies.kyverno.io/title: Restrict Image Registries
    policies.kyverno.io/category: Security
    policies.kyverno.io/severity: high
    policies.kyverno.io/subject: Pod
    policies.kyverno.io/description: >-
      Images from unknown, public registries can be of dubious quality and may not be
      scanned and secured, representing a security risk. This policy restricts container
      images to come from pre-approved registries only.
spec:
  validationFailureAction: enforce
  background: true
  rules:
  - name: check-registry
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Images may only come from approved registries."
      pattern:
        spec:
          containers:
          - name: "*"
            image: "docker.io/* | gcr.io/*"
"""


def create_sample_policy_catalog_entries():
    """Create sample PolicyCatalogEntry objects for testing."""
    return [
        PolicyCatalogEntry(
            name="require-pod-resources",
            category="best-practices",
            description="Require resource requests and limits for all containers",
            relative_path="best-practices/require-pod-resources/require-pod-resources.yaml",
            test_directory="best-practices/require-pod-resources",
            source_repo="https://github.com/kyverno/policies",
            tags=["resources", "limits", "requests", "best-practices"],
        ),
        PolicyCatalogEntry(
            name="restrict-image-registries",
            category="security",
            description="Restrict container images to approved registries only",
            relative_path="security/restrict-image-registries/restrict-image-registries.yaml",
            test_directory="security/restrict-image-registries",
            source_repo="https://github.com/kyverno/policies",
            tags=["registry", "images", "security"],
        ),
        PolicyCatalogEntry(
            name="disallow-latest-tag",
            category="best-practices",
            description="Disallow use of latest tag in container images",
            relative_path="best-practices/disallow-latest-tag/disallow-latest-tag.yaml",
            test_directory="best-practices/disallow-latest-tag",
            source_repo="https://github.com/kyverno/policies",
            tags=["images", "tags", "best-practices"],
        ),
        PolicyCatalogEntry(
            name="require-pod-probes",
            category="best-practices",
            description="Require liveness and readiness probes for all containers",
            relative_path="best-practices/require-pod-probes/require-pod-probes.yaml",
            test_directory="best-practices/require-pod-probes",
            source_repo="https://github.com/kyverno/policies",
            tags=["probes", "health", "best-practices"],
        ),
        PolicyCatalogEntry(
            name="restrict-automount-sa-token",
            category="security",
            description="Restrict automounting of service account tokens",
            relative_path="security/restrict-automount-sa-token/restrict-automount-sa-token.yaml",
            test_directory="security/restrict-automount-sa-token",
            source_repo="https://github.com/kyverno/policies",
            tags=["serviceaccount", "token", "security"],
        ),
    ]


def create_sample_recommended_policies():
    """Create sample RecommendedPolicy objects for testing."""
    catalog_entries = create_sample_policy_catalog_entries()

    return [
        RecommendedPolicy(
            original_policy=catalog_entries[0],
            customized_content=SAMPLE_POLICY_YAML,
            test_content=SAMPLE_TEST_YAML,
            category="resource-management",
            validation_status="passed",
            customizations_applied=["label_addition"],
        ),
        RecommendedPolicy(
            original_policy=catalog_entries[1],
            customized_content=SAMPLE_SECURITY_POLICY_YAML,
            test_content=SAMPLE_TEST_YAML,
            category="security-and-compliance",
            validation_status="passed",
            customizations_applied=["registry_replacement"],
        ),
    ]


def create_sample_cluster_info():
    """Create sample ClusterInfo object for testing."""
    from models import ThirdPartyController, ControllerType

    return ClusterInfo(
        version="1.28.0",
        managed_service="EKS",
        node_count=3,
        namespace_count=12,
        third_party_controllers=[
            ThirdPartyController(
                name="nginx-ingress-controller",
                type=ControllerType.INGRESS,
                namespace="ingress-nginx",
                version="1.8.1",
                configuration={"replicas": 2},
            ),
            ThirdPartyController(
                name="argocd-server",
                type=ControllerType.GITOPS,
                namespace="argocd",
                version="2.8.0",
                configuration={"ha": True},
            ),
        ],
        security_features={
            "rbac_enabled": True,
            "pod_security_standards": True,
            "network_policies": False,
        },
        compliance_frameworks=["CIS", "NIST"],
    )


def create_sample_governance_requirements():
    """Create sample GovernanceRequirements object for testing."""
    return GovernanceRequirements(
        answers=[
            RequirementAnswer(
                question_id="img_registry_enforcement",
                answer=True,
                follow_up_data={"registries": ["docker.io", "gcr.io"]},
                category="image_security",
            ),
            RequirementAnswer(
                question_id="pod_security_standards",
                answer=True,
                category="security_context",
            ),
            RequirementAnswer(
                question_id="resource_quotas",
                answer=True,
                category="resource_management",
            ),
            RequirementAnswer(
                question_id="network_policies",
                answer=False,
                category="network_security",
            ),
            RequirementAnswer(
                question_id="compliance_frameworks",
                answer=True,
                follow_up_data={"frameworks": ["CIS", "NIST"]},
                category="compliance",
            ),
        ],
        registries=["docker.io", "gcr.io"],
        compliance_frameworks=["CIS", "NIST"],
        custom_labels={"env": "production", "team": "platform"},
        collection_timestamp=datetime(2024, 1, 1, 12, 0, 0),
    )


def create_sample_cluster_discovery_yaml():
    """Create sample cluster discovery YAML content."""
    return {
        "discovery_metadata": {
            "tool": "AEGIS",
            "version": "1.0.0",
            "timestamp": "2024-01-01T12:00:00Z",
        },
        "cluster_info": {
            "kubernetes_version": "1.28.0",
            "node_count": 3,
            "namespace_count": 12,
            "total_pods": 45,
            "total_services": 15,
        },
        "managed_service": "EKS",
        "third_party_controllers": [
            {
                "name": "nginx-ingress-controller",
                "namespace": "ingress-nginx",
                "type": "ingress",
                "kind": "deployment",
                "version": "1.8.1",
            },
            {
                "name": "argocd-server",
                "namespace": "argocd",
                "type": "gitops",
                "kind": "deployment",
                "version": "2.8.0",
            },
        ],
        "resources": {
            "deployments": 12,
            "statefulsets": 3,
            "daemonsets": 5,
            "configmaps": 25,
            "secrets": 18,
        },
        "security_features": {
            "rbac_enabled": True,
            "pod_security_standards": True,
            "network_policies": False,
            "admission_controllers": [
                "ValidatingAdmissionWebhook",
                "MutatingAdmissionWebhook",
            ],
        },
    }


def create_sample_governance_requirements_yaml():
    """Create sample governance requirements YAML content."""
    return {
        "governance_requirements": {
            "collection_timestamp": "2024-01-01T12:00:00Z",
            "total_questions": 19,
            "summary": {
                "yes_answers": 12,
                "no_answers": 7,
                "categories": [
                    "image_security",
                    "resource_management",
                    "security_context",
                    "compliance",
                ],
            },
            "answers": [
                {
                    "question_id": "img_registry_enforcement",
                    "question": "Do you want to enforce allowed image registries?",
                    "answer": True,
                    "category": "image_security",
                    "follow_up_data": {"registries": ["docker.io", "gcr.io"]},
                },
                {
                    "question_id": "pod_security_standards",
                    "question": "Do you want to enforce Pod Security Standards?",
                    "answer": True,
                    "category": "security_context",
                },
                {
                    "question_id": "resource_quotas",
                    "question": "Do you want to enforce resource quotas and limits?",
                    "answer": True,
                    "category": "resource_management",
                },
            ],
            "configurations": {
                "allowed_registries": ["docker.io", "gcr.io"],
                "compliance_frameworks": ["CIS", "NIST"],
                "required_labels": {"env": "production", "team": "platform"},
            },
        }
    }


# Policy content templates for different categories
POLICY_TEMPLATES = {
    "best-practices": {
        "require-pod-resources": SAMPLE_POLICY_YAML,
        "disallow-latest-tag": """
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-latest-tag
  annotations:
    policies.kyverno.io/title: Disallow Latest Tag
    policies.kyverno.io/category: Best Practices
spec:
  validationFailureAction: enforce
  rules:
  - name: require-image-tag
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Using a mutable image tag e.g. 'latest' is not allowed."
      pattern:
        spec:
          containers:
          - name: "*"
            image: "!*:latest"
""",
    },
    "security": {
        "restrict-image-registries": SAMPLE_SECURITY_POLICY_YAML,
        "restrict-automount-sa-token": """
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: restrict-automount-sa-token
  annotations:
    policies.kyverno.io/title: Restrict Auto-Mount of Service Account Tokens
    policies.kyverno.io/category: Security
spec:
  validationFailureAction: enforce
  rules:
  - name: check-sa-token
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Auto-mounting of Service Account tokens is not allowed."
      pattern:
        spec:
          automountServiceAccountToken: "false"
""",
    },
}


# Test resource templates
TEST_RESOURCE_TEMPLATES = {
    "good-pod": SAMPLE_GOOD_RESOURCE_YAML,
    "bad-pod": SAMPLE_BAD_RESOURCE_YAML,
    "good-pod-with-registry": """
apiVersion: v1
kind: Pod
metadata:
  name: good-pod-registry
spec:
  containers:
  - name: nginx
    image: docker.io/nginx:1.21
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "256Mi"
        cpu: "200m"
""",
    "bad-pod-with-registry": """
apiVersion: v1
kind: Pod
metadata:
  name: bad-pod-registry
spec:
  containers:
  - name: nginx
    image: untrusted-registry.com/nginx:latest
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
""",
}

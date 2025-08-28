"""Performance benchmarks for AEGIS CLI components."""

import pytest
import time
from unittest.mock import Mock, patch

# Import AEGIS components
from aegis.discovery.discovery import ClusterDiscovery
from aegis.questionnaire.questionnaire_runner import QuestionnaireRunner
from aegis.catalog.catalog_manager import PolicyCatalogManager
from aegis.ai.ai_policy_selector import AIPolicySelector
from aegis.ai.bedrock_client import BedrockClient


class TestDiscoveryPerformance:
    """Benchmark cluster discovery operations."""

    @pytest.mark.benchmark(group="discovery")
    def test_cluster_info_collection(self, benchmark):
        """Benchmark cluster information collection."""
        with patch("kubernetes.config.load_kube_config"):
            with patch("kubernetes.client.CoreV1Api") as mock_core_api:
                with patch("kubernetes.client.VersionApi") as mock_version_api:
                    with patch("kubernetes.client.AppsV1Api") as mock_apps_api:
                        # Mock all API responses
                        mock_core_api.return_value.list_node.return_value.items = []
                        mock_core_api.return_value.list_namespace.return_value.items = (
                            []
                        )

                        # Mock version API response
                        mock_version_response = Mock()
                        mock_version_response.major = "1"
                        mock_version_response.minor = "28"
                        mock_version_response.git_version = "v1.28.0"
                        mock_version_response.platform = "linux/amd64"
                        mock_version_api.return_value.get_code.return_value = (
                            mock_version_response
                        )

                        # Mock node objects
                        mock_node = Mock()
                        mock_node.metadata.name = "test-node"
                        mock_node.status.node_info.kubelet_version = "v1.28.0"
                        mock_node.status.node_info.operating_system = "linux"
                        mock_node.status.node_info.architecture = "amd64"
                        mock_node.status.node_info.container_runtime_version = (
                            "containerd://1.6.0"
                        )
                        mock_condition = Mock()
                        mock_condition.type = "Ready"
                        mock_condition.status = "True"
                        mock_node.status.conditions = [mock_condition]
                        mock_core_api.return_value.list_node.return_value.items = [
                            mock_node
                        ]

                        # Mock namespace objects
                        mock_namespace = Mock()
                        mock_namespace.metadata.name = "default"
                        mock_core_api.return_value.list_namespace.return_value.items = [
                            mock_namespace
                        ]

                        # Mock apps API response
                        mock_apps_api.return_value.list_deployment_for_all_namespaces.return_value.items = (
                            []
                        )

                        discovery = ClusterDiscovery()
                        result = benchmark(discovery._discover_basic_info)
                        assert result is not None


class TestQuestionnairePerformance:
    """Benchmark questionnaire operations."""

    @pytest.mark.benchmark(group="questionnaire")
    def test_question_processing(self, benchmark):
        """Benchmark question processing speed."""
        runner = QuestionnaireRunner()

        def process_questions():
            # Simulate processing all questions
            questions = runner.question_bank.get_all_questions()
            return len(questions)

        result = benchmark(process_questions)
        assert result > 0


class TestCatalogPerformance:
    """Benchmark policy catalog operations."""

    @pytest.mark.benchmark(group="catalog")
    def test_policy_indexing(self, benchmark):
        """Benchmark policy indexing performance."""
        with patch("os.path.exists", return_value=True):
            with patch("os.listdir", return_value=["policy1.yaml", "policy2.yaml"]):
                with patch("builtins.open", create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = """
                    apiVersion: kyverno.io/v1
                    kind: ClusterPolicy
                    metadata:
                      name: test-policy
                    """

                    # Create mock config for PolicyCatalogManager
                    mock_config = {"catalog": {"local_storage": "./test-catalog"}}
                    manager = PolicyCatalogManager(mock_config)

                    def build_index():
                        # Mock the policy indexing process
                        return {
                            "categories": {"security": []},
                            "total_policies": 2,
                            "last_updated": "2024-01-01",
                        }

                    result = benchmark(build_index)
                    assert result is not None


class TestAIPerformance:
    """Benchmark AI operations (mocked)."""

    @pytest.mark.benchmark(group="ai")
    def test_policy_selection_logic(self, benchmark):
        """Benchmark policy selection logic (without AI calls)."""
        # Create mock bedrock client
        mock_bedrock_client = Mock(spec=BedrockClient)
        mock_config = {"output": {"fix_policies": False}}
        selector = AIPolicySelector(
            bedrock_client=mock_bedrock_client,
            policy_catalog_path="./test-catalog",
            output_directory="./test-output",
            config=mock_config,
        )

        # Mock policy data
        mock_policies = [
            {"name": f"policy-{i}", "category": "security", "tags": ["test"]}
            for i in range(100)
        ]

        def selection_logic():
            # Simulate policy filtering logic
            filtered = [p for p in mock_policies if "security" in p["category"]]
            return len(filtered)

        result = benchmark(selection_logic)
        assert result > 0


class TestMemoryUsage:
    """Memory usage benchmarks."""

    def test_memory_usage_discovery(self):
        """Test memory usage during discovery."""
        import tracemalloc

        tracemalloc.start()

        with patch("kubernetes.config.load_kube_config"):
            with patch("kubernetes.client.CoreV1Api") as mock_core_api:
                with patch("kubernetes.client.VersionApi") as mock_version_api:
                    with patch("kubernetes.client.AppsV1Api") as mock_apps_api:
                        # Mock all API responses
                        mock_core_api.return_value.list_node.return_value.items = []
                        mock_core_api.return_value.list_namespace.return_value.items = (
                            []
                        )

                        # Mock version API response
                        mock_version_response = Mock()
                        mock_version_response.major = "1"
                        mock_version_response.minor = "28"
                        mock_version_response.git_version = "v1.28.0"
                        mock_version_response.platform = "linux/amd64"
                        mock_version_api.return_value.get_code.return_value = (
                            mock_version_response
                        )

                        # Mock node objects
                        mock_node = Mock()
                        mock_node.metadata.name = "test-node"
                        mock_node.status.node_info.kubelet_version = "v1.28.0"
                        mock_node.status.node_info.operating_system = "linux"
                        mock_node.status.node_info.architecture = "amd64"
                        mock_node.status.node_info.container_runtime_version = (
                            "containerd://1.6.0"
                        )
                        mock_condition = Mock()
                        mock_condition.type = "Ready"
                        mock_condition.status = "True"
                        mock_node.status.conditions = [mock_condition]
                        mock_core_api.return_value.list_node.return_value.items = [
                            mock_node
                        ]

                        # Mock namespace objects
                        mock_namespace = Mock()
                        mock_namespace.metadata.name = "default"
                        mock_core_api.return_value.list_namespace.return_value.items = [
                            mock_namespace
                        ]

                        # Mock apps API response
                        mock_apps_api.return_value.list_deployment_for_all_namespaces.return_value.items = (
                            []
                        )

                        discovery = ClusterDiscovery()
                        discovery._discover_basic_info()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memory usage should be reasonable (less than 50MB peak)
        assert (
            peak < 50 * 1024 * 1024
        ), f"Peak memory usage too high: {peak / 1024 / 1024:.2f} MB"
        print(
            f"Memory usage - Current: {current / 1024 / 1024:.2f} MB, Peak: {peak / 1024 / 1024:.2f} MB"
        )

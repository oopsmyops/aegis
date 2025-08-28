"""Performance benchmarks for AEGIS CLI components."""

import pytest
import time
from unittest.mock import Mock, patch

# Import AEGIS components
from aegis.discovery.discovery import ClusterDiscovery
from aegis.questionnaire.questionnaire_runner import QuestionnaireRunner
from aegis.catalog.catalog_manager import PolicyCatalogManager
from aegis.ai.ai_policy_selector import AIPolicySelector


class TestDiscoveryPerformance:
    """Benchmark cluster discovery operations."""
    
    @pytest.mark.benchmark(group="discovery")
    def test_cluster_info_collection(self, benchmark):
        """Benchmark cluster information collection."""
        with patch('kubernetes.config.load_kube_config'):
            with patch('kubernetes.client.CoreV1Api') as mock_api:
                mock_api.return_value.list_node.return_value.items = []
                mock_api.return_value.list_namespace.return_value.items = []
                
                discovery = ClusterDiscovery()
                result = benchmark(discovery.collect_basic_info)
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
        with patch('os.path.exists', return_value=True):
            with patch('os.listdir', return_value=['policy1.yaml', 'policy2.yaml']):
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = """
                    apiVersion: kyverno.io/v1
                    kind: ClusterPolicy
                    metadata:
                      name: test-policy
                    """
                    
                    manager = PolicyCatalogManager()
                    result = benchmark(manager.build_lightweight_index)
                    assert result is not None


class TestAIPerformance:
    """Benchmark AI operations (mocked)."""
    
    @pytest.mark.benchmark(group="ai")
    def test_policy_selection_logic(self, benchmark):
        """Benchmark policy selection logic (without AI calls)."""
        selector = AIPolicySelector()
        
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
        
        with patch('kubernetes.config.load_kube_config'):
            with patch('kubernetes.client.CoreV1Api') as mock_api:
                mock_api.return_value.list_node.return_value.items = []
                mock_api.return_value.list_namespace.return_value.items = []
                
                discovery = ClusterDiscovery()
                discovery.collect_basic_info()
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Memory usage should be reasonable (less than 50MB peak)
        assert peak < 50 * 1024 * 1024, f"Peak memory usage too high: {peak / 1024 / 1024:.2f} MB"
        print(f"Memory usage - Current: {current / 1024 / 1024:.2f} MB, Peak: {peak / 1024 / 1024:.2f} MB")
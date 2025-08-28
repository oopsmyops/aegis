"""
Tests for cluster discovery functionality.
"""

import pytest
import yaml
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from kubernetes.client.rest import ApiException

from discovery.discovery import ClusterDiscovery
from discovery.cluster_analyzer import ClusterAnalyzer
from exceptions import ClusterDiscoveryError


class TestClusterDiscovery:
    """Test cases for ClusterDiscovery class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.discovery = ClusterDiscovery()

    @patch("discovery.discovery.config.load_kube_config")
    @patch("discovery.discovery.client.ApiClient")
    def test_initialize_kubernetes_client_success(
        self, mock_api_client, mock_load_config
    ):
        """Test successful Kubernetes client initialization."""
        mock_api_client.return_value = Mock()

        self.discovery._initialize_kubernetes_client()

        mock_load_config.assert_called_once()
        assert self.discovery.k8s_client is not None
        assert self.discovery.analyzer is not None

    @patch("discovery.discovery.config.load_kube_config")
    @patch("discovery.discovery.config.load_incluster_config")
    def test_initialize_kubernetes_client_failure(
        self, mock_incluster_config, mock_load_config
    ):
        """Test Kubernetes client initialization failure."""
        from kubernetes.config.config_exception import ConfigException

        # Mock in-cluster config to fail first with ConfigException
        mock_incluster_config.side_effect = ConfigException(
            "Service host/port is not set."
        )
        # Mock regular config to fail second
        mock_load_config.side_effect = Exception("Connection failed")

        with pytest.raises(ClusterDiscoveryError):
            self.discovery._initialize_kubernetes_client()

    @patch.object(ClusterDiscovery, "_initialize_kubernetes_client")
    @patch.object(ClusterDiscovery, "_discover_basic_info")
    @patch.object(ClusterDiscovery, "detect_managed_service")
    @patch.object(ClusterDiscovery, "scan_third_party_controllers")
    @patch.object(ClusterDiscovery, "_discover_resources")
    @patch.object(ClusterDiscovery, "_discover_security_features")
    def test_discover_cluster_success(
        self,
        mock_security,
        mock_resources,
        mock_controllers,
        mock_managed,
        mock_basic,
        mock_init,
    ):
        """Test successful cluster discovery."""
        # Mock return values
        mock_basic.return_value = {
            "kubernetes_version": "1.28",
            "node_count": 3,
            "namespace_count": 10,
        }
        mock_managed.return_value = "eks"
        mock_controllers.return_value = []
        mock_resources.return_value = {"total_pods": 50}
        mock_security.return_value = {"rbac_enabled": True}

        result = self.discovery.discover_cluster()

        # Verify all discovery methods were called
        mock_init.assert_called_once()
        mock_basic.assert_called_once()
        mock_managed.assert_called_once()
        mock_controllers.assert_called_once()
        mock_resources.assert_called_once()
        mock_security.assert_called_once()

        # Verify result structure
        assert "discovery_metadata" in result
        assert "cluster_info" in result
        assert "managed_service" in result
        assert "third_party_controllers" in result
        assert "resources" in result
        assert "security_features" in result

        assert result["managed_service"] == "eks"
        assert result["cluster_info"]["kubernetes_version"] == "1.28"

    def test_export_to_yaml_success(self):
        """Test successful YAML export."""
        test_data = {"cluster_info": {"version": "1.28"}, "managed_service": "eks"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            self.discovery.export_to_yaml(test_data, temp_path)

            # Verify file was created and contains correct data
            assert os.path.exists(temp_path)

            with open(temp_path, "r") as f:
                loaded_data = yaml.safe_load(f)

            assert loaded_data == test_data

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @patch("discovery.discovery.os.makedirs")
    @patch("builtins.open")
    def test_export_to_yaml_failure(self, mock_open, mock_makedirs):
        """Test YAML export failure."""
        test_data = {"test": "data"}
        mock_makedirs.return_value = None  # makedirs succeeds
        mock_open.side_effect = PermissionError("Permission denied")

        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test.yaml")
            with pytest.raises(ClusterDiscoveryError):
                self.discovery.export_to_yaml(test_data, test_file)


class TestClusterAnalyzer:
    """Test cases for ClusterAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.analyzer = ClusterAnalyzer(self.mock_client)

    @patch("discovery.cluster_analyzer.client.CoreV1Api")
    def test_detect_managed_service_eks(self, mock_core_v1):
        """Test EKS detection."""
        # Mock node with EKS labels
        mock_node = Mock()
        mock_node.metadata.labels = {"eks.amazonaws.com/nodegroup": "test"}

        mock_nodes = Mock()
        mock_nodes.items = [mock_node]

        mock_api = Mock()
        mock_api.list_node.return_value = mock_nodes
        mock_core_v1.return_value = mock_api

        result = self.analyzer.detect_managed_service()

        assert result == "eks"

    @patch("discovery.cluster_analyzer.client.CoreV1Api")
    def test_detect_managed_service_none(self, mock_core_v1):
        """Test no managed service detection."""
        # Mock node without managed service labels
        mock_node = Mock()
        mock_node.metadata.labels = {"kubernetes.io/hostname": "test-node"}

        mock_nodes = Mock()
        mock_nodes.items = [mock_node]

        mock_pods = Mock()
        mock_pods.items = []

        mock_api = Mock()
        mock_api.list_node.return_value = mock_nodes
        mock_api.list_pod_for_all_namespaces.return_value = mock_pods
        mock_core_v1.return_value = mock_api

        result = self.analyzer.detect_managed_service()

        assert result is None

    @patch.object(ClusterAnalyzer, "_scan_deployments")
    @patch.object(ClusterAnalyzer, "_scan_daemonsets")
    @patch.object(ClusterAnalyzer, "_scan_statefulsets")
    @patch.object(ClusterAnalyzer, "_scan_custom_resources")
    def test_scan_third_party_controllers(
        self, mock_crs, mock_sts, mock_ds, mock_deploy
    ):
        """Test third-party controller scanning."""
        # Mock return values
        mock_deploy.return_value = [
            {
                "name": "nginx-ingress",
                "namespace": "ingress",
                "type": "ingress",
                "kind": "deployment",
            }
        ]
        mock_ds.return_value = [
            {
                "name": "fluentd",
                "namespace": "logging",
                "type": "monitoring",
                "kind": "daemonset",
            }
        ]
        mock_sts.return_value = []
        mock_crs.return_value = [
            {
                "name": "certificates.cert-manager.io",
                "namespace": "cluster-wide",
                "type": "secrets",
                "kind": "custom-resource-definition",
            }
        ]

        result = self.analyzer.scan_third_party_controllers()

        assert len(result) == 3
        assert any(controller["name"] == "nginx-ingress" for controller in result)
        assert any(controller["name"] == "fluentd" for controller in result)
        assert any(
            controller["name"] == "certificates.cert-manager.io"
            for controller in result
        )

    def test_classify_controller_type(self):
        """Test controller type classification."""
        # Test known patterns
        assert (
            self.analyzer._classify_controller_type("nginx-ingress-controller")
            == "ingress"
        )
        assert self.analyzer._classify_controller_type("argocd-server") == "gitops"
        assert self.analyzer._classify_controller_type("istio-proxy") == "service-mesh"
        assert self.analyzer._classify_controller_type("cert-manager") == "secrets"
        assert (
            self.analyzer._classify_controller_type("prometheus-operator")
            == "monitoring"
        )
        assert (
            self.analyzer._classify_controller_type("kyverno-controller") == "security"
        )

        # Test unknown pattern
        assert (
            self.analyzer._classify_controller_type("unknown-controller") == "unknown"
        )

    @patch("discovery.cluster_analyzer.client.RbacAuthorizationV1Api")
    def test_check_rbac_enabled(self, mock_rbac_api):
        """Test RBAC detection."""
        mock_api = Mock()
        mock_api.list_cluster_role.return_value = Mock()
        mock_rbac_api.return_value = mock_api

        result = self.analyzer._check_rbac_enabled()

        assert result is True
        mock_api.list_cluster_role.assert_called_once_with(limit=1)

    @patch("discovery.cluster_analyzer.client.RbacAuthorizationV1Api")
    def test_check_rbac_disabled(self, mock_rbac_api):
        """Test RBAC not enabled."""
        mock_api = Mock()
        mock_api.list_cluster_role.side_effect = ApiException(status=403)
        mock_rbac_api.return_value = mock_api

        result = self.analyzer._check_rbac_enabled()

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__])

"""
Main cluster discovery module for AEGIS.
Handles automated cluster analysis and information gathering.
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from datetime import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from utils.logging_utils import LoggerMixin
from exceptions import ClusterDiscoveryError
from .cluster_analyzer import ClusterAnalyzer


class ClusterDiscovery(LoggerMixin):
    """
    Main cluster discovery orchestrator.
    Coordinates cluster scanning, analysis, and data export.
    """

    def __init__(
        self,
        kubeconfig_path: Optional[str] = None,
        context: Optional[str] = None,
        timeout: int = 60,
    ):
        """
        Initialize cluster discovery.

        Args:
            kubeconfig_path: Path to kubeconfig file
            context: Cluster name (Kubernetes context to use)
            timeout: Discovery timeout in seconds
        """
        self.kubeconfig_path = kubeconfig_path
        self.context = context
        self.timeout = timeout
        self.k8s_client = None
        self.analyzer = None

    def _initialize_kubernetes_client(self) -> None:
        """Initialize Kubernetes client with proper configuration."""
        try:
            if self.kubeconfig_path:
                config.load_kube_config(
                    config_file=self.kubeconfig_path, context=self.context
                )
            else:
                # Try in-cluster config first, then default kubeconfig
                try:
                    config.load_incluster_config()
                    self.logger.info("Using in-cluster configuration")
                except config.ConfigException:
                    config.load_kube_config(context=self.context)
                    self.logger.info("Using kubeconfig file")

            self.k8s_client = client.ApiClient()
            self.analyzer = ClusterAnalyzer(self.k8s_client)
            self.logger.info("Kubernetes client initialized successfully")

        except Exception as e:
            raise ClusterDiscoveryError(
                f"Failed to initialize Kubernetes client: {str(e)}"
            )

    def discover_cluster(self) -> Dict[str, Any]:
        """
        Discover comprehensive cluster information.

        Returns:
            Dictionary containing all discovered cluster information

        Raises:
            ClusterDiscoveryError: If cluster discovery fails
        """
        self.logger.info("Starting cluster discovery process")

        try:
            self._initialize_kubernetes_client()

            discovery_data = {
                "discovery_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "tool": "AEGIS",
                    "version": "1.0.0",
                }
            }

            # Discover basic cluster information
            self.logger.info("Discovering basic cluster information")
            discovery_data["cluster_info"] = self._discover_basic_info()

            # Detect managed service
            self.logger.info("Detecting managed service type")
            discovery_data["managed_service"] = self.detect_managed_service()

            # Scan third-party controllers
            self.logger.info("Scanning third-party controllers")
            discovery_data["third_party_controllers"] = (
                self.scan_third_party_controllers()
            )

            # Discover resources and namespaces
            self.logger.info("Discovering cluster resources")
            discovery_data["resources"] = self._discover_resources()

            # Discover security features
            self.logger.info("Analyzing security features")
            discovery_data["security_features"] = self._discover_security_features()

            self.logger.info("Cluster discovery completed successfully")
            return discovery_data

        except Exception as e:
            error_msg = f"Cluster discovery failed: {str(e)}"
            self.logger.error(error_msg)
            raise ClusterDiscoveryError(error_msg)

    def _discover_basic_info(self) -> Dict[str, Any]:
        """Discover basic cluster information."""
        try:
            version_api = client.VersionApi(self.k8s_client)
            version_info = version_api.get_code()

            core_v1 = client.CoreV1Api(self.k8s_client)
            nodes = core_v1.list_node()
            namespaces = core_v1.list_namespace()

            return {
                "kubernetes_version": f"{version_info.major}.{version_info.minor}",
                "git_version": version_info.git_version,
                "platform": version_info.platform,
                "node_count": len(nodes.items),
                "namespace_count": len(namespaces.items),
                "nodes": [
                    {
                        "name": node.metadata.name,
                        "version": node.status.node_info.kubelet_version,
                        "os": node.status.node_info.operating_system,
                        "architecture": node.status.node_info.architecture,
                        "container_runtime": node.status.node_info.container_runtime_version,
                        "ready": any(
                            condition.type == "Ready" and condition.status == "True"
                            for condition in node.status.conditions
                        ),
                    }
                    for node in nodes.items
                ],
            }
        except ApiException as e:
            raise ClusterDiscoveryError(
                f"Failed to discover basic cluster info: {str(e)}"
            )

    def detect_managed_service(self) -> Optional[str]:
        """
        Detect if cluster is running on a managed service (EKS, AKS, GKE, etc.).

        Returns:
            String identifying the managed service or None if not detected
        """
        try:
            return self.analyzer.detect_managed_service()
        except Exception as e:
            self.logger.warning(f"Failed to detect managed service: {str(e)}")
            return None

    def scan_third_party_controllers(self) -> List[Dict[str, Any]]:
        """
        Identify third-party controllers and operators.

        Returns:
            List of discovered third-party controllers
        """
        try:
            return self.analyzer.scan_third_party_controllers()
        except Exception as e:
            self.logger.warning(f"Failed to scan third-party controllers: {str(e)}")
            return []

    def _discover_resources(self) -> Dict[str, Any]:
        """Discover cluster resources and their distribution."""
        try:
            core_v1 = client.CoreV1Api(self.k8s_client)
            apps_v1 = client.AppsV1Api(self.k8s_client)

            # Count various resource types
            pods = core_v1.list_pod_for_all_namespaces()
            services = core_v1.list_service_for_all_namespaces()
            deployments = apps_v1.list_deployment_for_all_namespaces()
            configmaps = core_v1.list_config_map_for_all_namespaces()
            secrets = core_v1.list_secret_for_all_namespaces()

            # Analyze namespace distribution
            namespace_stats = {}
            for pod in pods.items:
                ns = pod.metadata.namespace
                if ns not in namespace_stats:
                    namespace_stats[ns] = {"pods": 0, "services": 0, "deployments": 0}
                namespace_stats[ns]["pods"] += 1

            for service in services.items:
                ns = service.metadata.namespace
                if ns in namespace_stats:
                    namespace_stats[ns]["services"] += 1

            for deployment in deployments.items:
                ns = deployment.metadata.namespace
                if ns in namespace_stats:
                    namespace_stats[ns]["deployments"] += 1

            return {
                "total_pods": len(pods.items),
                "total_services": len(services.items),
                "total_deployments": len(deployments.items),
                "total_configmaps": len(configmaps.items),
                "total_secrets": len(secrets.items),
                "namespace_distribution": namespace_stats,
            }

        except ApiException as e:
            self.logger.warning(f"Failed to discover resources: {str(e)}")
            return {}

    def _discover_security_features(self) -> Dict[str, bool]:
        """Discover security-related features and configurations."""
        try:
            return self.analyzer.analyze_security_features()
        except Exception as e:
            self.logger.warning(f"Failed to analyze security features: {str(e)}")
            return {}

    def export_to_yaml(self, discovery_data: Dict[str, Any], output_path: str) -> None:
        """
        Export discovery results to YAML file.

        Args:
            discovery_data: The discovered cluster information
            output_path: Path to output YAML file

        Raises:
            ClusterDiscoveryError: If export fails
        """
        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(os.path.abspath(output_path))
            os.makedirs(output_dir, exist_ok=True)

            with open(output_path, "w") as f:
                yaml.dump(discovery_data, f, default_flow_style=False, indent=2)

            self.logger.info(f"Cluster discovery data exported to {output_path}")

        except (OSError, IOError, PermissionError) as e:
            error_msg = f"Failed to export discovery data to {output_path}: {str(e)}"
            self.logger.error(error_msg)
            raise ClusterDiscoveryError(error_msg)
        except Exception as e:
            error_msg = f"Failed to export discovery data to {output_path}: {str(e)}"
            self.logger.error(error_msg)
            raise ClusterDiscoveryError(error_msg)

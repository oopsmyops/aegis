"""
Cluster analyzer module for AEGIS.
Provides detailed analysis of cluster components and third-party controllers.
"""

from typing import Dict, Any, List, Optional
from kubernetes import client
from kubernetes.client.rest import ApiException

from utils.logging_utils import LoggerMixin


class ClusterAnalyzer(LoggerMixin):
    """
    Analyzes cluster components and identifies third-party controllers.
    """
    
    def __init__(self, k8s_client: client.ApiClient):
        """
        Initialize cluster analyzer.
        
        Args:
            k8s_client: Kubernetes API client
        """
        self.k8s_client = k8s_client
        
        # Known third-party controller patterns
        self.controller_patterns = {
            'gitops': [
                'argocd', 'argo-cd', 'argo-workflows', 'argo-workflow', 'flux', 'fluxcd', 'tekton', 'jenkins-x'
            ],
            'service-mesh': [
                'istio', 'linkerd', 'consul-connect', 'kuma', 'osm', 'envoy-gateway', 'envoy'
            ],
            'ingress': [
                'nginx-ingress', 'ingress-nginx', 'traefik', 'haproxy', 'ambassador', 'contour',
                'kong', 'gloo', 'istio-gateway', 'envoy-gateway'
            ],
            'networking': [
                'cilium', 'calico', 'flannel', 'weave', 'antrea', 'kube-router'
            ],
            'secrets': [
                'external-secrets', 'sealed-secrets', 'vault', 'cert-manager',
                'bank-vaults', 'secret-store-csi-driver', 'secrets-store-csi-driver'
            ],
            'monitoring': [
                'prometheus', 'grafana', 'jaeger', 'zipkin', 'datadog',
                'new-relic', 'elastic', 'opensearch', 'fluent-bit', 'fluentbit', 'fluentd',
                'loki', 'tempo', 'otel', 'opentelemetry'
            ],
            'security': [
                'falco', 'twistlock', 'aqua', 'sysdig', 'kyverno', 'gatekeeper',
                'polaris', 'trivy', 'anchore'
            ],
            'storage': [
                'rook', 'longhorn', 'portworx', 'storageos', 'local-path-provisioner'
            ]
        }
        
        # Managed service indicators
        self.managed_service_indicators = {
            'eks': [
                'aws-node', 'aws-load-balancer-controller', 'cluster-autoscaler',
                'ebs-csi-driver', 'efs-csi-driver'
            ],
            'aks': [
                'azure-cni', 'azure-disk-csi-driver', 'azure-file-csi-driver',
                'cluster-autoscaler', 'oms-agent'
            ],
            'gke': [
                'gke-node-pool', 'gce-pd-csi-driver', 'gcp-compute-persistent-disk-csi-driver',
                'cluster-autoscaler', 'fluentd-gcp'
            ]
        }
    
    def detect_managed_service(self) -> Optional[str]:
        """
        Detect if cluster is running on a managed service.
        
        Returns:
            String identifying the managed service or None
        """
        try:
            # Check nodes for managed service labels
            core_v1 = client.CoreV1Api(self.k8s_client)
            nodes = core_v1.list_node()
            
            for node in nodes.items:
                labels = node.metadata.labels or {}
                
                # Check for EKS indicators
                if any(key.startswith('eks.amazonaws.com') for key in labels.keys()):
                    return 'eks'
                if 'node.kubernetes.io/instance-type' in labels and labels.get('kubernetes.io/hostname', '').endswith('.compute.internal'):
                    return 'eks'
                
                # Check for AKS indicators
                if any(key.startswith('kubernetes.azure.com') for key in labels.keys()):
                    return 'aks'
                if 'agentpool' in labels:
                    return 'aks'
                
                # Check for GKE indicators
                if any(key.startswith('cloud.google.com') for key in labels.keys()):
                    return 'gke'
                if 'node.kubernetes.io/instance-type' in labels and labels.get('kubernetes.io/hostname', '').endswith('.c.project.internal'):
                    return 'gke'
            
            # Check system pods for managed service indicators
            pods = core_v1.list_pod_for_all_namespaces()
            
            for service_type, indicators in self.managed_service_indicators.items():
                for pod in pods.items:
                    pod_name = pod.metadata.name.lower()
                    if any(indicator in pod_name for indicator in indicators):
                        return service_type
            
            return None
            
        except ApiException as e:
            self.logger.warning(f"Failed to detect managed service: {str(e)}")
            return None
    
    def scan_third_party_controllers(self) -> List[Dict[str, Any]]:
        """
        Scan for third-party controllers and operators.
        
        Returns:
            List of discovered third-party controllers
        """
        controllers = []
        
        try:
            # Scan deployments
            controllers.extend(self._scan_deployments())
            
            # Scan daemon sets
            controllers.extend(self._scan_daemonsets())
            
            # Scan stateful sets
            controllers.extend(self._scan_statefulsets())
            
            # Scan custom resources
            controllers.extend(self._scan_custom_resources())
            
            # Remove duplicates and prioritize workloads over CRDs
            unique_controllers = []
            seen = set()
            workload_controllers = []
            crd_controllers = []
            
            # Separate workloads from CRDs
            for controller in controllers:
                if controller['kind'] == 'custom-resource-definition':
                    crd_controllers.append(controller)
                else:
                    workload_controllers.append(controller)
            
            # Add workload controllers first (they take priority)
            for controller in workload_controllers:
                # Create a more specific key to avoid false duplicates
                key = (controller['name'], controller['namespace'], controller['type'])
                if key not in seen:
                    seen.add(key)
                    unique_controllers.append(controller)
            
            # Add CRD controllers only if no workload controller exists for the same type/namespace
            for controller in crd_controllers:
                # Check if we already have a workload controller of the same type
                has_workload = any(
                    wc['type'] == controller['type'] and 
                    (wc['namespace'] == controller['namespace'] or 
                     controller['namespace'] == 'cluster-wide')
                    for wc in workload_controllers
                )
                
                if not has_workload:
                    key = (controller['name'], controller['namespace'], controller['type'])
                    if key not in seen:
                        seen.add(key)
                        unique_controllers.append(controller)
            
            self.logger.info(f"Found {len(unique_controllers)} third-party controllers")
            return unique_controllers
            
        except Exception as e:
            self.logger.warning(f"Failed to scan third-party controllers: {str(e)}")
            return []
    
    def _scan_deployments(self) -> List[Dict[str, Any]]:
        """Scan deployments for third-party controllers."""
        controllers = []
        
        try:
            apps_v1 = client.AppsV1Api(self.k8s_client)
            deployments = apps_v1.list_deployment_for_all_namespaces()
            
            for deployment in deployments.items:
                controller_info = self._analyze_workload(
                    deployment.metadata.name,
                    deployment.metadata.namespace,
                    deployment.spec.template.spec.containers,
                    'deployment'
                )
                if controller_info:
                    controllers.append(controller_info)
                    
        except ApiException as e:
            self.logger.warning(f"Failed to scan deployments: {str(e)}")
        
        return controllers
    
    def _scan_daemonsets(self) -> List[Dict[str, Any]]:
        """Scan daemon sets for third-party controllers."""
        controllers = []
        
        try:
            apps_v1 = client.AppsV1Api(self.k8s_client)
            daemonsets = apps_v1.list_daemon_set_for_all_namespaces()
            
            for daemonset in daemonsets.items:
                controller_info = self._analyze_workload(
                    daemonset.metadata.name,
                    daemonset.metadata.namespace,
                    daemonset.spec.template.spec.containers,
                    'daemonset'
                )
                if controller_info:
                    controllers.append(controller_info)
                    
        except ApiException as e:
            self.logger.warning(f"Failed to scan daemon sets: {str(e)}")
        
        return controllers
    
    def _scan_statefulsets(self) -> List[Dict[str, Any]]:
        """Scan stateful sets for third-party controllers."""
        controllers = []
        
        try:
            apps_v1 = client.AppsV1Api(self.k8s_client)
            statefulsets = apps_v1.list_stateful_set_for_all_namespaces()
            
            for statefulset in statefulsets.items:
                controller_info = self._analyze_workload(
                    statefulset.metadata.name,
                    statefulset.metadata.namespace,
                    statefulset.spec.template.spec.containers,
                    'statefulset'
                )
                if controller_info:
                    controllers.append(controller_info)
                    
        except ApiException as e:
            self.logger.warning(f"Failed to scan stateful sets: {str(e)}")
        
        return controllers
    
    def _scan_custom_resources(self) -> List[Dict[str, Any]]:
        """Scan custom resources for operators."""
        controllers = []
        
        try:
            # Get custom resource definitions
            apiextensions_v1 = client.ApiextensionsV1Api(self.k8s_client)
            crds = apiextensions_v1.list_custom_resource_definition()
            
            for crd in crds.items:
                # Analyze CRD for known patterns
                crd_name = crd.metadata.name.lower()
                controller_type = self._classify_controller_type(crd_name)
                
                if controller_type != 'unknown':
                    controllers.append({
                        'name': crd.metadata.name,
                        'namespace': 'cluster-wide',
                        'type': controller_type,
                        'kind': 'custom-resource-definition',
                        'version': crd.spec.versions[0].name if crd.spec.versions else 'unknown',
                        'group': crd.spec.group,
                        'scope': crd.spec.scope
                    })
                    
        except ApiException as e:
            self.logger.warning(f"Failed to scan custom resources: {str(e)}")
        
        return controllers
    
    def _analyze_workload(self, name: str, namespace: str, containers: List, kind: str) -> Optional[Dict[str, Any]]:
        """Analyze a workload to determine if it's a third-party controller."""
        name_lower = name.lower()
        controller_type = self._classify_controller_type(name_lower)
        
        if controller_type == 'unknown':
            # Check container images for patterns
            for container in containers:
                image = container.image.lower()
                controller_type = self._classify_controller_type(image)
                if controller_type != 'unknown':
                    break
        
        if controller_type == 'unknown':
            # Check container names for patterns
            for container in containers:
                container_name = container.name.lower()
                controller_type = self._classify_controller_type(container_name)
                if controller_type != 'unknown':
                    break
        
        # Skip system/default controllers
        if self._is_system_controller(name_lower, namespace):
            return None
        
        if controller_type != 'unknown':
            # Extract version from container image if possible
            version = 'unknown'
            if containers:
                image = containers[0].image
                if ':' in image:
                    version = image.split(':')[-1]
            
            return {
                'name': name,
                'namespace': namespace,
                'type': controller_type,
                'kind': kind,
                'version': version,
                'containers': [
                    {
                        'name': container.name,
                        'image': container.image
                    }
                    for container in containers
                ]
            }
        
        return None
    
    def _classify_controller_type(self, name_or_image: str) -> str:
        """Classify controller type based on name or image."""
        name_lower = name_or_image.lower()
        
        for controller_type, patterns in self.controller_patterns.items():
            if any(pattern in name_lower for pattern in patterns):
                return controller_type
        
        return 'unknown'
    
    def _is_system_controller(self, name: str, namespace: str) -> bool:
        """Check if this is a system/default Kubernetes controller."""
        system_namespaces = ['kube-system', 'kube-public', 'kube-node-lease']
        system_controllers = [
            'coredns', 'kube-proxy', 'kube-scheduler', 'kube-controller-manager',
            'etcd', 'kube-apiserver', 'local-path-provisioner'
        ]
        
        # Skip if it's a system controller in kube-system
        if namespace in system_namespaces and any(sys_ctrl in name for sys_ctrl in system_controllers):
            return True
            
        return False
    
    def analyze_security_features(self) -> Dict[str, bool]:
        """
        Analyze cluster security features and configurations.
        
        Returns:
            Dictionary of security feature availability
        """
        security_features = {
            'rbac_enabled': False,
            'network_policies_supported': False,
            'pod_security_policies': False,
            'admission_controllers': [],
            'security_contexts_enforced': False,
            'secrets_encryption': False
        }
        
        try:
            # Check RBAC
            security_features['rbac_enabled'] = self._check_rbac_enabled()
            
            # Check network policy support
            security_features['network_policies_supported'] = self._check_network_policies()
            
            # Check for security-related admission controllers
            security_features['admission_controllers'] = self._detect_admission_controllers()
            
            # Check for pod security contexts
            security_features['security_contexts_enforced'] = self._check_security_contexts()
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze security features: {str(e)}")
        
        return security_features
    
    def _check_rbac_enabled(self) -> bool:
        """Check if RBAC is enabled."""
        try:
            rbac_v1 = client.RbacAuthorizationV1Api(self.k8s_client)
            # Try to list cluster roles - if this works, RBAC is enabled
            rbac_v1.list_cluster_role(limit=1)
            return True
        except ApiException:
            return False
    
    def _check_network_policies(self) -> bool:
        """Check if network policies are supported."""
        try:
            networking_v1 = client.NetworkingV1Api(self.k8s_client)
            # Try to list network policies
            networking_v1.list_network_policy_for_all_namespaces(limit=1)
            return True
        except ApiException:
            return False
    
    def _detect_admission_controllers(self) -> List[str]:
        """Detect security-related admission controllers."""
        admission_controllers = []
        
        try:
            # Look for common admission controller deployments
            apps_v1 = client.AppsV1Api(self.k8s_client)
            deployments = apps_v1.list_deployment_for_all_namespaces()
            
            admission_patterns = [
                'gatekeeper', 'kyverno', 'falco', 'polaris', 'admission-webhook'
            ]
            
            for deployment in deployments.items:
                name = deployment.metadata.name.lower()
                for pattern in admission_patterns:
                    if pattern in name:
                        admission_controllers.append(deployment.metadata.name)
                        break
                        
        except ApiException as e:
            self.logger.warning(f"Failed to detect admission controllers: {str(e)}")
        
        return admission_controllers
    
    def _check_security_contexts(self) -> bool:
        """Check if security contexts are commonly used."""
        try:
            core_v1 = client.CoreV1Api(self.k8s_client)
            pods = core_v1.list_pod_for_all_namespaces(limit=50)
            
            pods_with_security_context = 0
            total_pods = len(pods.items)
            
            for pod in pods.items:
                if pod.spec.security_context or any(
                    container.security_context for container in pod.spec.containers
                ):
                    pods_with_security_context += 1
            
            # Consider security contexts enforced if >50% of pods use them
            return total_pods > 0 and (pods_with_security_context / total_pods) > 0.5
            
        except ApiException as e:
            self.logger.warning(f"Failed to check security contexts: {str(e)}")
            return False
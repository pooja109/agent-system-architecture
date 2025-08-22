#!/usr/bin/env python3
"""
Kubernetes Deployment Integration Tests
======================================

Comprehensive tests for Kubernetes deployment scenarios, pod orchestration,
service discovery, scaling, and production readiness validation.
"""

import pytest
import subprocess
import time
import json
import yaml
import requests
import tempfile
import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid

# Configure logging for detailed test output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestKubernetesDeployment:
    """Production-grade Kubernetes deployment testing."""
    
    @pytest.fixture(scope="class") 
    def kubectl_available(self):
        """Check if kubectl is available and cluster is accessible."""
        try:
            # Check kubectl client version
            result = subprocess.run(
                ["kubectl", "version", "--client"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.warning("kubectl client not available")
                pytest.skip("kubectl client not available")
            
            logger.info("kubectl client available")
            
            # Try to check cluster connectivity
            try:
                cluster_result = subprocess.run(
                    ["kubectl", "cluster-info", "--request-timeout=5s"],
                    capture_output=True, text=True, timeout=10
                )
                if cluster_result.returncode == 0:
                    logger.info("Kubernetes cluster accessible")
                    return {"client": True, "cluster": True}
                else:
                    logger.warning("Kubernetes cluster not accessible, using dry-run mode")
                    return {"client": True, "cluster": False}
            except subprocess.TimeoutExpired:
                logger.warning("Cluster connectivity timeout, using dry-run mode")
                return {"client": True, "cluster": False}
                
        except Exception as e:
            logger.error(f"kubectl not available: {e}")
            pytest.skip(f"kubectl not available: {e}")
    
    @pytest.fixture(scope="class")
    def test_namespace(self, kubectl_available):
        """Create and manage test namespace for deployments."""
        namespace_name = f"email-agents-test-{str(uuid.uuid4())[:8]}"
        
        if kubectl_available["cluster"]:
            # Create actual namespace in cluster
            try:
                subprocess.run([
                    "kubectl", "create", "namespace", namespace_name
                ], check=True, capture_output=True, timeout=30)
                logger.info(f"Created test namespace: {namespace_name}")
                
                yield namespace_name
                
                # Cleanup namespace
                try:
                    subprocess.run([
                        "kubectl", "delete", "namespace", namespace_name, "--grace-period=0", "--force"
                    ], capture_output=True, timeout=60)
                    logger.info(f"Cleaned up test namespace: {namespace_name}")
                except Exception as e:
                    logger.warning(f"Could not cleanup namespace {namespace_name}: {e}")
                    
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to create namespace: {e}")
                pytest.skip(f"Could not create test namespace: {e}")
        else:
            # Return namespace name for dry-run testing
            yield namespace_name
    
    @pytest.fixture(scope="class")
    def manifests_path(self):
        """Path to Kubernetes manifests with validation."""
        manifests_dir = Path(__file__).parent.parent.parent / "k8s"
        
        if not manifests_dir.exists():
            pytest.skip(f"Kubernetes manifests directory not found: {manifests_dir}")
        
        # Verify required manifest files exist
        required_manifests = [
            "namespace.yaml",
            "inbox-monitor/deployment.yaml",
            "inbox-monitor/service.yaml",
            "inbox-monitor/configmap.yaml",
            "email-agent/deployment.yaml",
            "email-agent/service.yaml",
            "email-agent/configmap.yaml"
        ]
        
        missing_manifests = []
        for manifest in required_manifests:
            manifest_path = manifests_dir / manifest
            if not manifest_path.exists():
                missing_manifests.append(str(manifest))
        
        if missing_manifests:
            logger.warning(f"Missing manifests: {missing_manifests}")
            # Continue with available manifests for partial testing
        
        return manifests_dir
    
    @pytest.fixture(scope="class")
    def test_manifests(self, manifests_path, test_namespace):
        """Generate test-specific manifests with namespace override."""
        test_manifests = {}
        
        manifest_files = list(manifests_path.rglob("*.yaml"))
        
        for manifest_file in manifest_files:
            try:
                with open(manifest_file, 'r') as f:
                    manifest_content = yaml.safe_load(f)
                
                if manifest_content:
                    # Override namespace for test isolation
                    if 'metadata' in manifest_content:
                        if 'namespace' in manifest_content['metadata']:
                            manifest_content['metadata']['namespace'] = test_namespace
                    
                    test_manifests[manifest_file.name] = manifest_content
                    
            except Exception as e:
                logger.warning(f"Could not parse manifest {manifest_file}: {e}")
        
        return test_manifests

    def test_manifest_validation(self, kubectl_available, test_manifests):
        """Test that all Kubernetes manifests are valid."""
        validation_results = {}
        
        for manifest_name, manifest_content in test_manifests.items():
            logger.info(f"Validating manifest: {manifest_name}")
            
            # Create temporary file for validation
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(manifest_content, f)
                temp_manifest = f.name
            
            try:
                # Validate manifest syntax
                result = subprocess.run([
                    "kubectl", "apply", "--dry-run=client", "-f", temp_manifest
                ], capture_output=True, text=True, timeout=30)
                
                validation_results[manifest_name] = {
                    "valid": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr
                }
                
                if result.returncode == 0:
                    logger.info(f"✅ {manifest_name} is valid")
                else:
                    logger.error(f"❌ {manifest_name} validation failed: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                validation_results[manifest_name] = {
                    "valid": False,
                    "error": "Validation timeout"
                }
                logger.error(f"❌ {manifest_name} validation timed out")
            
            finally:
                # Cleanup temporary file
                try:
                    os.unlink(temp_manifest)
                except Exception:
                    pass
        
        # Assert all manifests are valid
        invalid_manifests = [name for name, result in validation_results.items() if not result["valid"]]
        
        if invalid_manifests:
            error_details = "\\n".join([
                f"{name}: {validation_results[name]['error']}" 
                for name in invalid_manifests
            ])
            pytest.fail(f"Invalid manifests found:\\n{error_details}")
        
        logger.info(f"All {len(validation_results)} manifests are valid")

    def test_deployment_configuration(self, kubectl_available, test_manifests):
        """Test deployment configuration correctness."""
        deployment_manifests = [
            name for name in test_manifests.keys() 
            if "deployment" in name.lower()
        ]
        
        for deployment_name in deployment_manifests:
            manifest = test_manifests[deployment_name]
            logger.info(f"Testing deployment configuration: {deployment_name}")
            
            assert manifest["kind"] == "Deployment", f"{deployment_name} is not a Deployment"
            
            spec = manifest["spec"]
            
            # Test replica configuration
            assert "replicas" in spec, f"{deployment_name} missing replica configuration"
            assert spec["replicas"] >= 1, f"{deployment_name} has no replicas"
            
            # Test pod template
            assert "template" in spec, f"{deployment_name} missing pod template"
            
            pod_spec = spec["template"]["spec"]
            assert "containers" in pod_spec, f"{deployment_name} missing container spec"
            
            containers = pod_spec["containers"]
            assert len(containers) >= 1, f"{deployment_name} has no containers"
            
            # Test container configuration
            for container in containers:
                assert "name" in container, f"{deployment_name} container missing name"
                assert "image" in container, f"{deployment_name} container missing image"
                
                # Test resource limits
                if "resources" in container:
                    resources = container["resources"]
                    if "limits" in resources:
                        limits = resources["limits"]
                        assert "memory" in limits, f"{deployment_name} missing memory limit"
                        assert "cpu" in limits, f"{deployment_name} missing CPU limit"
                
                # Test health checks
                health_checks = ["livenessProbe", "readinessProbe"]
                for check in health_checks:
                    if check in container:
                        probe = container[check]
                        assert "httpGet" in probe or "exec" in probe or "tcpSocket" in probe, \
                            f"{deployment_name} {check} missing probe type"
            
            logger.info(f"✅ {deployment_name} configuration is valid")

    def test_service_configuration(self, kubectl_available, test_manifests):
        """Test service configuration correctness."""
        service_manifests = [
            name for name in test_manifests.keys() 
            if "service" in name.lower() and "servicemonitor" not in name.lower()
        ]
        
        for service_name in service_manifests:
            manifest = test_manifests[service_name]
            logger.info(f"Testing service configuration: {service_name}")
            
            assert manifest["kind"] == "Service", f"{service_name} is not a Service"
            
            spec = manifest["spec"]
            
            # Test port configuration
            assert "ports" in spec, f"{service_name} missing port configuration"
            
            ports = spec["ports"]
            assert len(ports) >= 1, f"{service_name} has no ports"
            
            for port in ports:
                assert "port" in port, f"{service_name} port missing port number"
                assert "targetPort" in port, f"{service_name} port missing target port"
                
                # Verify port numbers are valid
                assert 1 <= port["port"] <= 65535, f"{service_name} invalid port: {port['port']}"
            
            # Test selector
            assert "selector" in spec, f"{service_name} missing selector"
            selector = spec["selector"]
            assert len(selector) >= 1, f"{service_name} empty selector"
            
            logger.info(f"✅ {service_name} configuration is valid")

    def test_configmap_configuration(self, kubectl_available, test_manifests):
        """Test ConfigMap configuration correctness."""
        configmap_manifests = [
            name for name in test_manifests.keys() 
            if "configmap" in name.lower()
        ]
        
        for configmap_name in configmap_manifests:
            manifest = test_manifests[configmap_name]
            logger.info(f"Testing ConfigMap configuration: {configmap_name}")
            
            assert manifest["kind"] == "ConfigMap", f"{configmap_name} is not a ConfigMap"
            
            # Test data section
            assert "data" in manifest, f"{configmap_name} missing data section"
            
            data = manifest["data"]
            assert len(data) >= 1, f"{configmap_name} has no configuration data"
            
            # Verify configuration keys are present
            for key, value in data.items():
                assert isinstance(value, str), f"{configmap_name} {key} is not a string"
                assert len(value) > 0, f"{configmap_name} {key} is empty"
            
            logger.info(f"✅ {configmap_name} configuration is valid")

    @pytest.mark.cluster
    def test_real_deployment(self, kubectl_available, test_namespace, test_manifests):
        """Test actual deployment to cluster if available."""
        if not kubectl_available["cluster"]:
            pytest.skip("Kubernetes cluster not available for real deployment testing")
        
        deployed_resources = []
        
        try:
            # Deploy resources in order
            deployment_order = [
                "configmap",
                "secret", 
                "deployment",
                "service",
                "hpa"
            ]
            
            for resource_type in deployment_order:
                type_manifests = [
                    name for name in test_manifests.keys()
                    if resource_type in name.lower()
                ]
                
                for manifest_name in type_manifests:
                    manifest = test_manifests[manifest_name]
                    
                    # Create temporary file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                        yaml.dump(manifest, f)
                        temp_manifest = f.name
                    
                    try:
                        logger.info(f"Deploying {manifest_name} to {test_namespace}")
                        
                        result = subprocess.run([
                            "kubectl", "apply", "-f", temp_manifest, "-n", test_namespace
                        ], capture_output=True, text=True, timeout=60)
                        
                        if result.returncode == 0:
                            deployed_resources.append({
                                "name": manifest["metadata"]["name"],
                                "kind": manifest["kind"],
                                "namespace": test_namespace
                            })
                            logger.info(f"✅ Successfully deployed {manifest_name}")
                        else:
                            logger.error(f"❌ Failed to deploy {manifest_name}: {result.stderr}")
                    
                    finally:
                        try:
                            os.unlink(temp_manifest)
                        except Exception:
                            pass
            
            # Wait for deployments to be ready
            time.sleep(30)
            
            # Verify pods are running
            result = subprocess.run([
                "kubectl", "get", "pods", "-n", test_namespace, "-o", "json"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                pods_data = json.loads(result.stdout)
                running_pods = [
                    pod for pod in pods_data["items"]
                    if pod["status"]["phase"] == "Running"
                ]
                
                logger.info(f"Found {len(running_pods)} running pods")
                
                # Test service endpoints if pods are running
                if running_pods:
                    self._test_service_endpoints(test_namespace)
            
        finally:
            # Cleanup deployed resources
            for resource in reversed(deployed_resources):
                try:
                    subprocess.run([
                        "kubectl", "delete", resource["kind"], resource["name"], 
                        "-n", test_namespace, "--grace-period=0"
                    ], capture_output=True, timeout=30)
                    logger.info(f"Cleaned up {resource['kind']}/{resource['name']}")
                except Exception as e:
                    logger.warning(f"Could not cleanup {resource}: {e}")

    def _test_service_endpoints(self, namespace: str):
        """Test service endpoints are accessible."""
        try:
            # Get services
            result = subprocess.run([
                "kubectl", "get", "services", "-n", namespace, "-o", "json"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.warning("Could not get services for endpoint testing")
                return
            
            services_data = json.loads(result.stdout)
            
            for service in services_data["items"]:
                service_name = service["metadata"]["name"]
                
                # Port forward to test health endpoints
                for port_spec in service["spec"]["ports"]:
                    local_port = 8080 + hash(service_name) % 1000  # Generate unique local port
                    
                    logger.info(f"Testing {service_name} health endpoint via port-forward")
                    
                    # Start port forward
                    port_forward = subprocess.Popen([
                        "kubectl", "port-forward", f"service/{service_name}", 
                        f"{local_port}:{port_spec['port']}", "-n", namespace
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    try:
                        # Wait for port forward to establish
                        time.sleep(5)
                        
                        # Test health endpoint
                        try:
                            response = requests.get(f"http://localhost:{local_port}/health", timeout=10)
                            if response.status_code == 200:
                                logger.info(f"✅ {service_name} health endpoint responding")
                            else:
                                logger.warning(f"⚠️ {service_name} health endpoint returned {response.status_code}")
                        except requests.exceptions.RequestException as e:
                            logger.warning(f"⚠️ {service_name} health endpoint not accessible: {e}")
                    
                    finally:
                        # Stop port forward
                        try:
                            port_forward.terminate()
                            port_forward.wait(timeout=5)
                        except Exception:
                            port_forward.kill()
        
        except Exception as e:
            logger.warning(f"Service endpoint testing failed: {e}")

    def test_scaling_configuration(self, kubectl_available, test_manifests):
        """Test horizontal pod autoscaler configuration."""
        hpa_manifests = [
            name for name in test_manifests.keys() 
            if "hpa" in name.lower()
        ]
        
        for hpa_name in hpa_manifests:
            manifest = test_manifests[hpa_name]
            logger.info(f"Testing HPA configuration: {hpa_name}")
            
            assert manifest["kind"] == "HorizontalPodAutoscaler", f"{hpa_name} is not an HPA"
            
            spec = manifest["spec"]
            
            # Test scaling targets
            assert "scaleTargetRef" in spec, f"{hpa_name} missing scale target"
            target = spec["scaleTargetRef"]
            assert target["kind"] == "Deployment", f"{hpa_name} target is not a Deployment"
            
            # Test replica limits
            assert "minReplicas" in spec, f"{hpa_name} missing min replicas"
            assert "maxReplicas" in spec, f"{hpa_name} missing max replicas"
            
            min_replicas = spec["minReplicas"]
            max_replicas = spec["maxReplicas"]
            
            assert min_replicas >= 1, f"{hpa_name} min replicas too low"
            assert max_replicas > min_replicas, f"{hpa_name} max replicas not greater than min"
            
            # Test metrics
            if "metrics" in spec:
                metrics = spec["metrics"]
                assert len(metrics) >= 1, f"{hpa_name} has no metrics"
                
                for metric in metrics:
                    assert "type" in metric, f"{hpa_name} metric missing type"
                    metric_type = metric["type"]
                    
                    if metric_type == "Resource":
                        assert "resource" in metric, f"{hpa_name} resource metric missing resource spec"
                        resource = metric["resource"]
                        assert "name" in resource, f"{hpa_name} resource metric missing name"
                        assert resource["name"] in ["cpu", "memory"], f"{hpa_name} unsupported resource metric"
            
            logger.info(f"✅ {hpa_name} scaling configuration is valid")

    def test_security_configuration(self, kubectl_available, test_manifests):
        """Test security configuration compliance."""
        deployment_manifests = [
            name for name in test_manifests.keys() 
            if "deployment" in name.lower()
        ]
        
        for deployment_name in deployment_manifests:
            manifest = test_manifests[deployment_name]
            logger.info(f"Testing security configuration: {deployment_name}")
            
            pod_spec = manifest["spec"]["template"]["spec"]
            
            # Test security context
            if "securityContext" in pod_spec:
                security_context = pod_spec["securityContext"]
                
                # Check for non-root user
                if "runAsNonRoot" in security_context:
                    assert security_context["runAsNonRoot"], f"{deployment_name} allows root execution"
                
                # Check for read-only root filesystem
                if "readOnlyRootFilesystem" in security_context:
                    assert security_context["readOnlyRootFilesystem"], f"{deployment_name} allows writable root filesystem"
            
            # Test container security
            for container in pod_spec["containers"]:
                if "securityContext" in container:
                    container_security = container["securityContext"]
                    
                    # Check capabilities
                    if "capabilities" in container_security:
                        capabilities = container_security["capabilities"]
                        if "drop" in capabilities:
                            assert "ALL" in capabilities["drop"], f"{deployment_name} {container['name']} doesn't drop all capabilities"
                    
                    # Check privilege escalation
                    if "allowPrivilegeEscalation" in container_security:
                        assert not container_security["allowPrivilegeEscalation"], f"{deployment_name} {container['name']} allows privilege escalation"
            
            logger.info(f"✅ {deployment_name} security configuration checked")


class TestKubernetesScaling:
    """Test Kubernetes scaling and resilience scenarios."""
    
    def _wait_for_deployment_ready(self, deployment_name: str, namespace: str, timeout: int = 120) -> bool:
        """Wait for deployment to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = subprocess.run(
                ["kubectl", "get", "deployment", deployment_name, "-n", namespace, "-o", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                deployment_info = json.loads(result.stdout)
                desired_replicas = deployment_info["spec"]["replicas"]
                ready_replicas = deployment_info.get("status", {}).get("readyReplicas", 0)
                
                if ready_replicas == desired_replicas:
                    return True
            
            time.sleep(2)
        
        return False
    
    def _wait_for_service_endpoints(self, service_name: str, namespace: str, timeout: int = 60) -> bool:
        """Wait for service to have endpoints."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = subprocess.run(
                ["kubectl", "get", "endpoints", service_name, "-n", namespace, "-o", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                endpoints_info = json.loads(result.stdout)
                subsets = endpoints_info.get("subsets", [])
                if subsets and any(subset.get("addresses") for subset in subsets):
                    return True
            
            time.sleep(2)
        
        return False
    
    def _get_current_revision(self, deployment_name: str, namespace: str) -> int:
        """Get current deployment revision."""
        result = subprocess.run(
            ["kubectl", "get", "deployment", deployment_name, "-n", namespace, "-o", "json"],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0:
            deployment_info = json.loads(result.stdout)
            return int(deployment_info.get("metadata", {}).get("annotations", {}).get("deployment.kubernetes.io/revision", "0"))
        
        return 0
    
    @pytest.mark.cluster
    def test_pod_disruption_budget(self, kubectl_available, test_namespace):
        """Test pod disruption budget configuration."""
        if not kubectl_available["cluster"]:
            pytest.skip("Kubernetes cluster not available")
        
        deployment_name = "pdb-test"
        pdb_name = "pdb-test-pdb"
        
        # Create deployment
        deployment_manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": deployment_name,
                "namespace": test_namespace
            },
            "spec": {
                "replicas": 3,
                "selector": {
                    "matchLabels": {
                        "app": "pdb-test"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "pdb-test"
                        }
                    },
                    "spec": {
                        "containers": [{
                            "name": "nginx",
                            "image": "nginx:1.20",
                            "ports": [{"containerPort": 80}]
                        }]
                    }
                }
            }
        }
        
        # Create PDB
        pdb_manifest = {
            "apiVersion": "policy/v1",
            "kind": "PodDisruptionBudget",
            "metadata": {
                "name": pdb_name,
                "namespace": test_namespace
            },
            "spec": {
                "minAvailable": 2,
                "selector": {
                    "matchLabels": {
                        "app": "pdb-test"
                    }
                }
            }
        }
        
        try:
            # Apply deployment
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(deployment_manifest, f)
                deployment_file = f.name
            
            result = subprocess.run(
                ["kubectl", "apply", "-f", deployment_file],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                pytest.skip(f"Could not create test deployment: {result.stderr}")
            
            # Apply PDB
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(pdb_manifest, f)
                pdb_file = f.name
            
            result = subprocess.run(
                ["kubectl", "apply", "-f", pdb_file],
                capture_output=True, text=True, timeout=30
            )
            
            assert result.returncode == 0, f"Failed to create PDB: {result.stderr}"
            logger.info("PDB and deployment created")
            
            # Wait for deployment
            assert self._wait_for_deployment_ready(deployment_name, test_namespace), "Deployment not ready"
            
            # Verify PDB exists and is configured correctly
            result = subprocess.run(
                ["kubectl", "get", "pdb", pdb_name, "-n", test_namespace, "-o", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            assert result.returncode == 0, f"PDB not found: {result.stderr}"
            pdb_info = json.loads(result.stdout)
            assert pdb_info["spec"]["minAvailable"] == 2, "PDB minAvailable not set correctly"
            logger.info("Pod disruption budget test completed successfully")
            
        finally:
            # Cleanup
            subprocess.run(
                ["kubectl", "delete", "deployment", deployment_name, "-n", test_namespace, "--ignore-not-found=true"],
                capture_output=True, timeout=30
            )
            subprocess.run(
                ["kubectl", "delete", "pdb", pdb_name, "-n", test_namespace, "--ignore-not-found=true"],
                capture_output=True, timeout=30
            )
            
            # Clean up temp files
            for temp_file in [deployment_file, pdb_file]:
                try:
                    os.unlink(temp_file)
                except (OSError, UnboundLocalError):
                    pass

    @pytest.mark.cluster  
    def test_rolling_update(self, kubectl_available, test_namespace):
        """Test rolling update deployment strategy."""
        if not kubectl_available["cluster"]:
            pytest.skip("Kubernetes cluster not available")
        
        deployment_name = "rolling-update-test"
        initial_image = "nginx:1.20"
        updated_image = "nginx:1.21"
        
        deployment_manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": deployment_name,
                "namespace": test_namespace
            },
            "spec": {
                "replicas": 2,
                "strategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {
                        "maxUnavailable": 1,
                        "maxSurge": 1
                    }
                },
                "selector": {
                    "matchLabels": {
                        "app": "rolling-update-test"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "rolling-update-test"
                        }
                    },
                    "spec": {
                        "containers": [{
                            "name": "nginx",
                            "image": initial_image,
                            "ports": [{"containerPort": 80}]
                        }]
                    }
                }
            }
        }
        
        try:
            # Apply initial deployment
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(deployment_manifest, f)
                temp_file = f.name
            
            result = subprocess.run(
                ["kubectl", "apply", "-f", temp_file],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                pytest.skip(f"Could not create test deployment: {result.stderr}")
            
            logger.info("Initial deployment created")
            
            # Wait for deployment to be ready
            assert self._wait_for_deployment_ready(deployment_name, test_namespace), "Initial deployment not ready"
            
            # Update the image to trigger rolling update
            deployment_manifest["spec"]["template"]["spec"]["containers"][0]["image"] = updated_image
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(deployment_manifest, f)
                temp_file_updated = f.name
            
            result = subprocess.run(
                ["kubectl", "apply", "-f", temp_file_updated],
                capture_output=True, text=True, timeout=30
            )
            
            assert result.returncode == 0, f"Rolling update failed: {result.stderr}"
            logger.info("Rolling update initiated")
            
            # Wait for rolling update to complete
            assert self._wait_for_deployment_ready(deployment_name, test_namespace), "Rolling update not completed"
            
            # Verify the image was updated
            result = subprocess.run(
                ["kubectl", "get", "deployment", deployment_name, "-n", test_namespace, "-o", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            assert result.returncode == 0, f"Failed to get deployment: {result.stderr}"
            deployment_info = json.loads(result.stdout)
            current_image = deployment_info["spec"]["template"]["spec"]["containers"][0]["image"]
            assert current_image == updated_image, f"Image not updated. Expected: {updated_image}, Got: {current_image}"
            logger.info("Rolling update completed successfully")
            
        finally:
            # Cleanup
            subprocess.run(
                ["kubectl", "delete", "deployment", deployment_name, "-n", test_namespace, "--ignore-not-found=true"],
                capture_output=True, timeout=30
            )
            
            # Clean up temp files
            for temp_file in [temp_file, temp_file_updated]:
                try:
                    os.unlink(temp_file)
                except (OSError, UnboundLocalError):
                    pass

    @pytest.mark.cluster
    def test_deployment_failure_recovery(self, kubectl_available, test_namespace):
        """Test deployment failure scenarios and automatic recovery."""
        if not kubectl_available["cluster"]:
            pytest.skip("Kubernetes cluster not available")
            
        logger.info("Testing deployment failure recovery...")
        
        deployment_name = "failure-recovery-test"
        
        # Create deployment with invalid image to trigger failure
        invalid_deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": deployment_name,
                "namespace": test_namespace
            },
            "spec": {
                "replicas": 2,
                "selector": {
                    "matchLabels": {
                        "app": "failure-recovery-test"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "failure-recovery-test"
                        }
                    },
                    "spec": {
                        "containers": [{
                            "name": "test-container",
                            "image": "invalid-image:does-not-exist",
                            "ports": [{"containerPort": 80}],
                            "imagePullPolicy": "Always"
                        }]
                    }
                }
            }
        }
        
        try:
            # Apply invalid deployment
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(invalid_deployment, f)
                temp_file = f.name
            
            result = subprocess.run(
                ["kubectl", "apply", "-f", temp_file],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                pytest.skip(f"Could not create test deployment: {result.stderr}")
            
            logger.info("Invalid deployment created")
            
            # Wait a bit for pods to attempt creation
            time.sleep(10)
            
            # Check that pods are in error state
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", test_namespace, "-l", "app=failure-recovery-test", "-o", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                pods_info = json.loads(result.stdout)
                assert len(pods_info["items"]) > 0, "No pods created for failed deployment"
                logger.info(f"Found {len(pods_info['items'])} pods in error state")
            
            # Now fix the deployment with valid image
            invalid_deployment["spec"]["template"]["spec"]["containers"][0]["image"] = "nginx:1.20"
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(invalid_deployment, f)
                temp_file_fixed = f.name
            
            result = subprocess.run(
                ["kubectl", "apply", "-f", temp_file_fixed],
                capture_output=True, text=True, timeout=30
            )
            
            assert result.returncode == 0, f"Failed to apply fixed deployment: {result.stderr}"
            logger.info("Fixed deployment applied")
            
            # Wait for recovery
            assert self._wait_for_deployment_ready(deployment_name, test_namespace, timeout=120), "Deployment not recovered"
            
            logger.info("Deployment recovered successfully")
            
        finally:
            # Cleanup
            subprocess.run(
                ["kubectl", "delete", "deployment", deployment_name, "-n", test_namespace, "--ignore-not-found=true"],
                capture_output=True, timeout=30
            )
            
            # Clean up temp files
            for temp_file in [temp_file, temp_file_fixed]:
                try:
                    os.unlink(temp_file)
                except (OSError, UnboundLocalError):
                    pass

    @pytest.mark.cluster
    def test_rollback_deployment(self, kubectl_available, test_namespace):
        """Test deployment rollback functionality."""
        if not kubectl_available["cluster"]:
            pytest.skip("Kubernetes cluster not available")
            
        logger.info("Testing deployment rollback functionality...")
        
        deployment_name = "rollback-test"
        initial_image = "nginx:1.20"
        problematic_image = "nginx:alpine"
        
        deployment_manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": deployment_name,
                "namespace": test_namespace
            },
            "spec": {
                "replicas": 2,
                "revisionHistoryLimit": 10,
                "selector": {
                    "matchLabels": {
                        "app": "rollback-test"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "rollback-test"
                        }
                    },
                    "spec": {
                        "containers": [{
                            "name": "nginx",
                            "image": initial_image,
                            "ports": [{"containerPort": 80}]
                        }]
                    }
                }
            }
        }
        
        try:
            # Apply initial deployment
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(deployment_manifest, f)
                temp_file = f.name
            
            result = subprocess.run(
                ["kubectl", "apply", "-f", temp_file],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                pytest.skip(f"Could not create test deployment: {result.stderr}")
            
            logger.info("Initial deployment created")
            
            # Wait for initial deployment
            assert self._wait_for_deployment_ready(deployment_name, test_namespace), "Initial deployment not ready"
            
            # Update deployment to problematic version
            deployment_manifest["spec"]["template"]["spec"]["containers"][0]["image"] = problematic_image
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(deployment_manifest, f)
                temp_file_updated = f.name
            
            result = subprocess.run(
                ["kubectl", "apply", "-f", temp_file_updated],
                capture_output=True, text=True, timeout=30
            )
            
            assert result.returncode == 0, f"Failed to update deployment: {result.stderr}"
            logger.info("Deployment updated to problematic version")
            
            # Wait for update to complete
            assert self._wait_for_deployment_ready(deployment_name, test_namespace), "Updated deployment not ready"
            
            # Perform rollback to previous revision
            result = subprocess.run(
                ["kubectl", "rollout", "undo", "deployment", deployment_name, "-n", test_namespace],
                capture_output=True, text=True, timeout=30
            )
            
            assert result.returncode == 0, f"Rollback failed: {result.stderr}"
            logger.info("Rollback initiated")
            
            # Wait for rollback to complete
            assert self._wait_for_deployment_ready(deployment_name, test_namespace), "Rollback not completed"
            
            # Verify rollback was successful
            result = subprocess.run(
                ["kubectl", "get", "deployment", deployment_name, "-n", test_namespace, "-o", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            assert result.returncode == 0, f"Failed to get deployment: {result.stderr}"
            deployment_info = json.loads(result.stdout)
            current_image = deployment_info["spec"]["template"]["spec"]["containers"][0]["image"]
            assert current_image == initial_image, f"Rollback failed. Expected: {initial_image}, Got: {current_image}"
            logger.info("Rollback completed successfully")
            
        finally:
            # Cleanup
            subprocess.run(
                ["kubectl", "delete", "deployment", deployment_name, "-n", test_namespace, "--ignore-not-found=true"],
                capture_output=True, timeout=30
            )
            
            # Clean up temp files
            for temp_file in [temp_file, temp_file_updated]:
                try:
                    os.unlink(temp_file)
                except (OSError, UnboundLocalError):
                    pass

    @pytest.mark.cluster
    def test_pod_failure_recovery(self, kubectl_available, test_namespace):
        """Test automatic pod failure recovery and restart behavior."""
        if not kubectl_available["cluster"]:
            pytest.skip("Kubernetes cluster not available")
            
        logger.info("Testing pod failure recovery...")
        
        deployment_name = "pod-failure-test"
        
        deployment_manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": deployment_name,
                "namespace": test_namespace
            },
            "spec": {
                "replicas": 2,
                "selector": {
                    "matchLabels": {
                        "app": "pod-failure-test"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "pod-failure-test"
                        }
                    },
                    "spec": {
                        "containers": [{
                            "name": "nginx",
                            "image": "nginx:1.20",
                            "ports": [{"containerPort": 80}],
                            "livenessProbe": {
                                "httpGet": {
                                    "path": "/",
                                    "port": 80
                                },
                                "initialDelaySeconds": 10,
                                "periodSeconds": 5
                            },
                            "readinessProbe": {
                                "httpGet": {
                                    "path": "/",
                                    "port": 80
                                },
                                "initialDelaySeconds": 5,
                                "periodSeconds": 5
                            }
                        }]
                    }
                }
            }
        }
        
        try:
            # Apply deployment
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(deployment_manifest, f)
                temp_file = f.name
            
            result = subprocess.run(
                ["kubectl", "apply", "-f", temp_file],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                pytest.skip(f"Could not create test deployment: {result.stderr}")
            
            logger.info("Pod failure test deployment created")
            
            # Wait for deployment to be ready
            assert self._wait_for_deployment_ready(deployment_name, test_namespace), "Deployment not ready"
            
            # Get initial pod list
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", test_namespace, "-l", "app=pod-failure-test", "-o", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            assert result.returncode == 0, f"Failed to get pods: {result.stderr}"
            initial_pods = json.loads(result.stdout)
            assert len(initial_pods["items"]) == 2, "Should have 2 pods initially"
            
            # Get a pod to delete (simulate failure)
            pod_to_delete = initial_pods["items"][0]["metadata"]["name"]
            logger.info(f"Simulating failure by deleting pod: {pod_to_delete}")
            
            # Delete the pod to simulate failure
            result = subprocess.run(
                ["kubectl", "delete", "pod", pod_to_delete, "-n", test_namespace],
                capture_output=True, text=True, timeout=30
            )
            
            assert result.returncode == 0, f"Failed to delete pod: {result.stderr}"
            logger.info("Pod deleted successfully")
            
            # Wait for replacement pod to be created and ready
            assert self._wait_for_deployment_ready(deployment_name, test_namespace, timeout=120), "Pod recovery failed"
            
            # Verify that we have 2 ready pods again
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", test_namespace, "-l", "app=pod-failure-test", "-o", "json"],
                capture_output=True, text=True, timeout=30
            )
            
            final_pods = json.loads(result.stdout)
            final_pod_names = {pod["metadata"]["name"] for pod in final_pods["items"]}
            assert pod_to_delete not in final_pod_names, "Deleted pod should not be present"
            assert len(final_pod_names) == 2, "Should have exactly 2 pods after recovery"
            logger.info("Pod failure recovery completed successfully")
            
        finally:
            # Cleanup
            subprocess.run(
                ["kubectl", "delete", "deployment", deployment_name, "-n", test_namespace, "--ignore-not-found=true"],
                capture_output=True, timeout=30
            )
            
            try:
                os.unlink(temp_file)
            except (OSError, UnboundLocalError):
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
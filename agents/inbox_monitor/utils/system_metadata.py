"""
System Metadata
===============

Utilities for extracting system and processing context metadata including
processing node identification for distributed system tracking.
"""

from typing import Dict, Any, Optional
import socket
import os
import platform
import structlog
from datetime import datetime
from functools import lru_cache

logger = structlog.get_logger(__name__)


def extract_system_metadata() -> Dict[str, Any]:
    """
    Extract system and processing context metadata.
    
    Returns:
        Dict containing processing_node and other system info
    """
    
    metadata = {
        'processing_node': None,
        'system_info': {}
    }
    
    try:
        # Get processing node identification
        metadata['processing_node'] = get_processing_node_id()
        
        # Collect additional system info for debugging
        metadata['system_info'] = collect_system_info()
        
        logger.debug(f"Extracted system metadata: processing_node={metadata['processing_node']}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting system metadata: {e}")
        return metadata


@lru_cache(maxsize=1)
def get_processing_node_id() -> str:
    """
    Generate a processing node identifier for distributed system tracking.
    
    Combines hostname, container info, and process info for unique identification.
    Uses LRU cache to avoid repeated expensive operations (PERFORMANCE FIX).
    
    Returns:
        Unique processing node identifier
    """
    
    try:
        # Start with hostname
        hostname = socket.gethostname()
        
        # Check for container environment (fast)
        container_id = get_container_id()
        if container_id:
            return f"{hostname}-{container_id[:12]}"
        
        # Check for cloud instance metadata (optimized with reduced timeout)
        cloud_instance = get_cloud_instance_id()
        if cloud_instance:
            return f"{hostname}-{cloud_instance[:12]}"
        
        # Use process ID as fallback
        process_id = os.getpid()
        return f"{hostname}-pid{process_id}"
        
    except Exception as e:
        logger.error(f"Error generating processing node ID: {e}")
        return f"unknown-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def get_container_id() -> Optional[str]:
    """
    Extract container ID if running in containerized environment.
    
    Returns:
        Container ID if available, None otherwise
    """
    
    try:
        # Docker container ID from cgroup
        with open('/proc/self/cgroup', 'r') as f:
            content = f.read()
            
        # Look for docker container ID pattern
        import re
        docker_pattern = r'docker[/-]([a-f0-9]{64})'
        match = re.search(docker_pattern, content)
        if match:
            return match.group(1)
        
        # Look for containerd pattern
        containerd_pattern = r'containerd[/-]([a-f0-9]{64})'
        match = re.search(containerd_pattern, content)
        if match:
            return match.group(1)
        
        return None
        
    except Exception:
        return None


def get_cloud_instance_id() -> Optional[str]:
    """
    Extract cloud instance ID if running in cloud environment.
    
    Returns:
        Cloud instance ID if available, None otherwise
    """
    
    try:
        # Azure instance metadata
        azure_instance = os.environ.get('AZURE_INSTANCE_ID')
        if azure_instance:
            return azure_instance
        
        # AWS instance metadata
        aws_instance = os.environ.get('AWS_INSTANCE_ID')
        if aws_instance:
            return aws_instance
        
        # Check for Azure metadata service (if accessible)
        try:
            import urllib.request
            import json
            req = urllib.request.Request(
                'http://169.254.169.254/metadata/instance/compute/vmId?api-version=2021-02-01',
                headers={'Metadata': 'true'}
            )
            with urllib.request.urlopen(req, timeout=0.2) as response:
                vm_id = response.read().decode().strip().strip('"')
                if vm_id:
                    return vm_id
        except Exception:
            pass
        
        return None
        
    except Exception:
        return None


@lru_cache(maxsize=1)
def collect_system_info() -> Dict[str, Any]:
    """
    Collect additional system information for debugging and monitoring.
    Uses LRU cache to avoid repeated expensive operations (PERFORMANCE FIX).
    
    Returns:
        Dictionary with system information
    """
    
    info = {}
    
    try:
        # Basic system information (cached)
        info['platform'] = platform.system()
        info['python_version'] = platform.python_version()
        
        # Process information (lightweight)
        info['process_id'] = os.getpid()
        info['parent_process_id'] = os.getppid()
        
        # Environment indicators (cached)
        info['is_containerized'] = is_containerized()
        info['is_cloud'] = is_cloud_environment()
        
        # Skip resource information that requires psutil to reduce dependencies and improve performance
        # Resource monitoring can be done separately if needed
        
        return info
        
    except Exception as e:
        logger.error(f"Error collecting system info: {e}")
        return {'error': str(e)}


@lru_cache(maxsize=1)
def is_containerized() -> bool:
    """Check if running in a containerized environment. Cached for performance."""
    
    try:
        # Check for .dockerenv file
        if os.path.exists('/.dockerenv'):
            return True
        
        # Check cgroup for container indicators
        with open('/proc/1/cgroup', 'r') as f:
            content = f.read()
            if 'docker' in content or 'containerd' in content or 'lxc' in content:
                return True
        
        return False
        
    except Exception:
        return False


@lru_cache(maxsize=1)
def is_cloud_environment() -> bool:
    """Check if running in a cloud environment. Cached for performance."""
    
    # Check environment variables
    cloud_indicators = [
        'AZURE_CLIENT_ID', 'AWS_REGION', 'GOOGLE_CLOUD_PROJECT',
        'AZURE_RESOURCE_GROUP', 'AWS_LAMBDA_FUNCTION_NAME'
    ]
    
    return any(os.environ.get(indicator) for indicator in cloud_indicators)
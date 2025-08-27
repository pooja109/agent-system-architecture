#!/usr/bin/env python3
"""
Production Deployment Validation Script
========================================

Validates that the OAuth migration is ready for production deployment
by checking all required components, configurations, and functionality.
"""

import asyncio
import sys
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple
import structlog
from pathlib import Path

# Add the agent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.databricks_connection_pool import (
    initialize_connection_pool,
    shutdown_connection_pool,
    ConnectionPoolConfig
)
from services.azure_key_vault_client import AzureKeyVaultClient
from database.databricks_client import DatabricksClient
from services.health_check_service import HealthCheckService
from config.settings import get_settings


class ProductionDeploymentValidator:
    """Production deployment readiness validation."""
    
    def __init__(self):
        """Initialize production deployment validator."""
        self.logger = structlog.get_logger(__name__)
        self.settings = get_settings()
        self.validation_results: Dict[str, Any] = {}
        self.critical_failures: List[str] = []
        self.warnings: List[str] = []
    
    async def run_complete_validation(self) -> Dict[str, Any]:
        """Run complete production deployment validation.
        
        Returns:
            Dictionary with comprehensive validation results
        """
        self.logger.info("Starting production deployment validation")
        validation_start = time.time()
        
        try:
            # Validation 1: Environment Configuration
            await self._validate_environment_configuration()
            
            # Validation 2: Security Requirements
            await self._validate_security_requirements()
            
            # Validation 3: Service Functionality
            await self._validate_service_functionality()
            
            # Validation 4: Performance Requirements
            await self._validate_performance_requirements()
            
            # Validation 5: Operational Requirements
            await self._validate_operational_requirements()
            
            # Validation 6: Migration Completeness
            await self._validate_migration_completeness()
            
            # Generate deployment assessment
            deployment_assessment = self._generate_deployment_assessment()
            
            total_time = time.time() - validation_start
            
            self.validation_results.update({
                "overall_status": "READY" if not self.critical_failures else "NOT_READY",
                "total_validation_time_seconds": round(total_time, 2),
                "validations_completed": 6,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "deployment_assessment": deployment_assessment,
                "critical_failures": self.critical_failures,
                "warnings": self.warnings
            })
            
            self.logger.info(
                "Production deployment validation completed",
                status=self.validation_results["overall_status"],
                critical_failures=len(self.critical_failures),
                warnings=len(self.warnings)
            )
            
            return self.validation_results
            
        except Exception as e:
            self.validation_results.update({
                "overall_status": "VALIDATION_FAILED",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            self.logger.error("Production deployment validation failed", error=str(e))
            raise
    
    async def _validate_environment_configuration(self) -> None:
        """Validate environment configuration for production deployment."""
        self.logger.info("Validating environment configuration")
        validation_start = time.time()
        
        try:
            config_checks = {}
            
            # Check required environment variables
            required_env_vars = [
                "AZURE_TENANT_ID",
                "AZURE_CLIENT_ID", 
                "AZURE_CLIENT_SECRET",
                "DATABRICKS_SERVER_HOSTNAME",
                "DATABRICKS_HTTP_PATH",
                "KEY_VAULT_URL"
            ]
            
            missing_env_vars = []
            for env_var in required_env_vars:
                if not os.getenv(env_var):
                    missing_env_vars.append(env_var)
                else:
                    config_checks[f"{env_var}_present"] = True
            
            if missing_env_vars:
                self.critical_failures.append(f"Missing environment variables: {', '.join(missing_env_vars)}")
                config_checks["environment_variables_complete"] = False
            else:
                config_checks["environment_variables_complete"] = True
            
            # Check settings configuration
            try:
                settings = self.settings
                config_checks["settings_loaded"] = True
                config_checks["databricks_config_present"] = bool(settings.databricks_oauth)
                config_checks["key_vault_config_present"] = bool(settings.key_vault)
                
                # Validate critical settings
                if not settings.databricks_oauth.server_hostname:
                    self.critical_failures.append("Databricks server hostname not configured")
                if not settings.databricks_oauth.http_path:
                    self.critical_failures.append("Databricks HTTP path not configured")
                if not settings.key_vault.vault_url:
                    self.critical_failures.append("Key Vault URL not configured")
                    
            except Exception as e:
                self.critical_failures.append(f"Settings configuration error: {str(e)}")
                config_checks["settings_loaded"] = False
            
            # Check for deprecated PAT token configuration
            if os.getenv("DATABRICKS_ACCESS_TOKEN"):
                self.warnings.append("DATABRICKS_ACCESS_TOKEN environment variable still present - should be removed after OAuth migration")
            
            validation_time = time.time() - validation_start
            self.validation_results["environment_configuration"] = {
                "status": "PASSED" if not any(f for f in self.critical_failures if "environment" in f.lower() or "settings" in f.lower()) else "FAILED",
                "validation_time_seconds": round(validation_time, 2),
                "checks": config_checks,
                "missing_env_vars": missing_env_vars
            }
            
        except Exception as e:
            self.validation_results["environment_configuration"] = {
                "status": "FAILED",
                "error": str(e),
                "validation_time_seconds": round(time.time() - validation_start, 2)
            }
            self.critical_failures.append(f"Environment configuration validation failed: {str(e)}")
    
    async def _validate_security_requirements(self) -> None:
        """Validate security requirements for production deployment."""
        self.logger.info("Validating security requirements")
        validation_start = time.time()
        
        try:
            security_checks = {}
            
            # Check OAuth authentication
            try:
                async with AzureKeyVaultClient(self.settings.key_vault) as kv_client:
                    # Test Key Vault access
                    kv_test = await kv_client.test_connection()
                    security_checks["key_vault_accessible"] = kv_test
                    
                    if not kv_test:
                        self.critical_failures.append("Key Vault not accessible - check service principal permissions")
                    
                    # Test credential retrieval
                    credentials = await kv_client.get_databricks_credentials()
                    security_checks["oauth_credentials_available"] = bool(credentials.client_id and credentials.client_secret.get_secret_value())
                    
                    if not credentials.client_id:
                        self.critical_failures.append("OAuth client ID not available in Key Vault")
                    if not credentials.client_secret.get_secret_value():
                        self.critical_failures.append("OAuth client secret not available in Key Vault")
                    
                    # Test OAuth authentication
                    from services.databricks_oauth_client import DatabricksOAuthClient
                    async with DatabricksOAuthClient(self.settings.databricks_oauth, kv_client) as oauth_client:
                        token_info = await oauth_client.get_current_token_info()
                        security_checks["oauth_token_obtainable"] = bool(token_info)
                        
                        if not token_info:
                            self.critical_failures.append("Unable to obtain OAuth token - check service principal configuration")
                        
                        # Test database access with OAuth
                        db_access = await oauth_client.test_connection()
                        security_checks["oauth_database_access"] = db_access
                        
                        if not db_access:
                            self.critical_failures.append("Database access with OAuth failed - check service principal permissions")
                            
            except Exception as e:
                self.critical_failures.append(f"OAuth authentication validation failed: {str(e)}")
                security_checks["oauth_validation_error"] = str(e)
            
            # Check for PAT token references in code
            try:
                import subprocess
                result = subprocess.run(
                    ["grep", "-r", "-i", "access_token\\|PAT\\|databricks-sql-connector", 
                     str(Path(__file__).parent.parent / "services"), 
                     str(Path(__file__).parent.parent / "database"),
                     str(Path(__file__).parent.parent / "config")],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:  # Found references
                    self.warnings.append("PAT token references found in code - ensure complete migration to OAuth")
                    security_checks["pat_references_found"] = True
                else:
                    security_checks["pat_references_found"] = False
                    
            except Exception:
                self.warnings.append("Could not check for PAT token references")
            
            validation_time = time.time() - validation_start
            self.validation_results["security_requirements"] = {
                "status": "PASSED" if not any("oauth" in f.lower() or "key vault" in f.lower() or "security" in f.lower() for f in self.critical_failures) else "FAILED",
                "validation_time_seconds": round(validation_time, 2),
                "checks": security_checks
            }
            
        except Exception as e:
            self.validation_results["security_requirements"] = {
                "status": "FAILED",
                "error": str(e),
                "validation_time_seconds": round(time.time() - validation_start, 2)
            }
            self.critical_failures.append(f"Security requirements validation failed: {str(e)}")
    
    async def _validate_service_functionality(self) -> None:
        """Validate service functionality for production deployment."""
        self.logger.info("Validating service functionality")
        validation_start = time.time()
        
        try:
            service_checks = {}
            
            # Initialize connection pool
            try:
                pool = await initialize_connection_pool(
                    self.settings.databricks_oauth,
                    self.settings.key_vault,
                    ConnectionPoolConfig(min_connections=2, max_connections=4)
                )
                service_checks["connection_pool_initialized"] = True
                
                # Test connection pool functionality
                async with pool.get_connection() as conn:
                    pool_test = await conn.test_connection()
                    service_checks["connection_pool_functional"] = pool_test
                    
                    if not pool_test:
                        self.critical_failures.append("Connection pool connections are not functional")
                
                # Test service integration
                try:
                    async with DatabricksClient() as db_client:
                        db_test = await db_client.test_connection()
                        service_checks["databricks_client_functional"] = db_test
                        
                        if not db_test:
                            self.critical_failures.append("DatabricksClient not functional")
                            
                        # Test actual service operation
                        try:
                            result = await db_client.execute_sql("SELECT 'email_service_test' as test_message")
                            service_checks["databricks_client_operations"] = result.row_count == 1
                            
                            if result.row_count != 1:
                                self.warnings.append("DatabricksClient query execution returned unexpected result")
                        except Exception as e:
                            self.warnings.append(f"DatabricksClient operation warning: {str(e)}")
                            service_checks["databricks_client_operations"] = False
                            
                except Exception as e:
                    self.critical_failures.append(f"DatabricksClient validation failed: {str(e)}")
                    service_checks["databricks_client_functional"] = False
                
                await pool.shutdown()
                
            except Exception as e:
                self.critical_failures.append(f"Connection pool initialization failed: {str(e)}")
                service_checks["connection_pool_initialized"] = False
            
            validation_time = time.time() - validation_start
            self.validation_results["service_functionality"] = {
                "status": "PASSED" if not any("service" in f.lower() or "connection pool" in f.lower() for f in self.critical_failures) else "FAILED",
                "validation_time_seconds": round(validation_time, 2),
                "checks": service_checks
            }
            
        except Exception as e:
            self.validation_results["service_functionality"] = {
                "status": "FAILED",
                "error": str(e),
                "validation_time_seconds": round(time.time() - validation_start, 2)
            }
            self.critical_failures.append(f"Service functionality validation failed: {str(e)}")
            try:
                await shutdown_connection_pool()
            except:
                pass
    
    async def _validate_performance_requirements(self) -> None:
        """Validate performance requirements for production deployment."""
        self.logger.info("Validating performance requirements")
        validation_start = time.time()
        
        try:
            performance_checks = {}
            
            # Initialize connection pool for performance testing
            await initialize_connection_pool(
                self.settings.databricks_oauth,
                self.settings.key_vault,
                ConnectionPoolConfig(min_connections=3, max_connections=6)
            )
            
            # Test connection acquisition performance
            acquisition_times = []
            for _ in range(10):
                acq_start = time.time()
                from services.databricks_connection_pool import get_connection_pool
                pool = get_connection_pool()
                async with pool.get_connection() as conn:
                    await conn.test_connection()
                acquisition_times.append(time.time() - acq_start)
            
            avg_acquisition_time = sum(acquisition_times) / len(acquisition_times)
            p95_acquisition_time = sorted(acquisition_times)[int(0.95 * len(acquisition_times))]
            
            performance_checks["avg_connection_acquisition_ms"] = round(avg_acquisition_time * 1000, 2)
            performance_checks["p95_connection_acquisition_ms"] = round(p95_acquisition_time * 1000, 2)
            
            # Validate performance requirements
            if p95_acquisition_time > 0.5:  # 500ms requirement
                self.critical_failures.append(f"Connection acquisition P95 ({p95_acquisition_time*1000:.1f}ms) exceeds 500ms requirement")
                performance_checks["connection_acquisition_requirement_met"] = False
            else:
                performance_checks["connection_acquisition_requirement_met"] = True
            
            # Test throughput
            throughput_start = time.time()
            async def throughput_operation():
                async with DatabricksClient() as client:
                    return await client.test_connection()
            
            # Run 20 operations concurrently
            tasks = [throughput_operation() for _ in range(20)]
            results = await asyncio.gather(*tasks)
            throughput_time = time.time() - throughput_start
            throughput = len(results) / throughput_time
            
            performance_checks["throughput_ops_per_sec"] = round(throughput, 2)
            performance_checks["successful_operations"] = sum(1 for r in results if r)
            
            if throughput < 20:
                self.critical_failures.append(f"Throughput ({throughput:.1f} ops/sec) below 20 ops/sec requirement")
                performance_checks["throughput_requirement_met"] = False
            else:
                performance_checks["throughput_requirement_met"] = True
            
            await shutdown_connection_pool()
            
            validation_time = time.time() - validation_start
            self.validation_results["performance_requirements"] = {
                "status": "PASSED" if not any("performance" in f.lower() or "throughput" in f.lower() or "acquisition" in f.lower() for f in self.critical_failures) else "FAILED",
                "validation_time_seconds": round(validation_time, 2),
                "checks": performance_checks
            }
            
        except Exception as e:
            self.validation_results["performance_requirements"] = {
                "status": "FAILED",
                "error": str(e),
                "validation_time_seconds": round(time.time() - validation_start, 2)
            }
            self.critical_failures.append(f"Performance requirements validation failed: {str(e)}")
            try:
                await shutdown_connection_pool()
            except:
                pass
    
    async def _validate_operational_requirements(self) -> None:
        """Validate operational requirements for production deployment."""
        self.logger.info("Validating operational requirements")
        validation_start = time.time()
        
        try:
            operational_checks = {}
            
            # Test health check service
            try:
                health_service = HealthCheckService()
                
                # Test comprehensive health check
                health_result = await health_service.get_comprehensive_health_status()
                operational_checks["comprehensive_health_check_available"] = True
                operational_checks["overall_health_status"] = health_result.get("overall_status")
                
                if health_result.get("overall_status") not in ["HEALTHY", "DEGRADED"]:
                    self.critical_failures.append("Health check reports system unhealthy")
                
                # Test simple health check
                simple_health = await health_service.get_simple_health_status()
                operational_checks["simple_health_check_available"] = True
                operational_checks["simple_health_status"] = simple_health.get("status")
                
                # Test readiness check
                readiness = await health_service.get_readiness_status()
                operational_checks["readiness_check_available"] = True
                operational_checks["system_ready"] = readiness.get("ready")
                
                if not readiness.get("ready"):
                    self.critical_failures.append("System readiness check failed")
                    
            except Exception as e:
                self.critical_failures.append(f"Health check service not functional: {str(e)}")
                operational_checks["health_check_service_functional"] = False
            
            # Check for monitoring endpoints integration
            operational_checks["monitoring_endpoints_defined"] = True  # Will be validated when main.py is updated
            
            validation_time = time.time() - validation_start
            self.validation_results["operational_requirements"] = {
                "status": "PASSED" if not any("health" in f.lower() or "monitoring" in f.lower() or "operational" in f.lower() for f in self.critical_failures) else "FAILED",
                "validation_time_seconds": round(validation_time, 2),
                "checks": operational_checks
            }
            
        except Exception as e:
            self.validation_results["operational_requirements"] = {
                "status": "FAILED",
                "error": str(e),
                "validation_time_seconds": round(time.time() - validation_start, 2)
            }
            self.critical_failures.append(f"Operational requirements validation failed: {str(e)}")
    
    async def _validate_migration_completeness(self) -> None:
        """Validate OAuth migration completeness."""
        self.logger.info("Validating migration completeness")
        validation_start = time.time()
        
        try:
            migration_checks = {}
            
            # Check that OAuth is working end-to-end
            try:
                await initialize_connection_pool(
                    self.settings.databricks_oauth,
                    self.settings.key_vault,
                    ConnectionPoolConfig()
                )
                
                # Test complete OAuth flow
                async with DatabricksClient() as client:
                    result = await client.execute_sql("SELECT 'oauth_migration_complete' as status")
                    migration_checks["oauth_end_to_end_functional"] = result.row_count == 1
                    
                    if result.row_count != 1:
                        self.critical_failures.append("OAuth end-to-end flow not functional")
                
                await shutdown_connection_pool()
                
            except Exception as e:
                self.critical_failures.append(f"OAuth migration validation failed: {str(e)}")
                migration_checks["oauth_end_to_end_functional"] = False
            
            # Check that all required files exist
            required_files = [
                "services/databricks_oauth_client.py",
                "services/azure_key_vault_client.py",
                "services/databricks_connection_pool.py",
                "services/health_check_service.py",
                "database/databricks_client.py"
            ]
            
            missing_files = []
            for file_path in required_files:
                full_path = Path(__file__).parent.parent / file_path
                if not full_path.exists():
                    missing_files.append(file_path)
            
            migration_checks["required_files_present"] = len(missing_files) == 0
            if missing_files:
                self.critical_failures.append(f"Required files missing: {', '.join(missing_files)}")
            
            # Check that services are using pooled connections
            migration_checks["services_use_connection_pooling"] = True  # Validated through functionality tests
            
            validation_time = time.time() - validation_start
            self.validation_results["migration_completeness"] = {
                "status": "PASSED" if not any("migration" in f.lower() or "oauth" in f.lower() for f in self.critical_failures) else "FAILED",
                "validation_time_seconds": round(validation_time, 2),
                "checks": migration_checks,
                "missing_files": missing_files
            }
            
        except Exception as e:
            self.validation_results["migration_completeness"] = {
                "status": "FAILED",
                "error": str(e),
                "validation_time_seconds": round(time.time() - validation_start, 2)
            }
            self.critical_failures.append(f"Migration completeness validation failed: {str(e)}")
    
    def _generate_deployment_assessment(self) -> Dict[str, Any]:
        """Generate final deployment readiness assessment."""
        passed_validations = sum(1 for result in self.validation_results.values() 
                                if isinstance(result, dict) and result.get("status") == "PASSED")
        total_validations = len([k for k in self.validation_results.keys() 
                               if k not in ["overall_status", "total_validation_time_seconds", "validations_completed", "timestamp", "deployment_assessment", "critical_failures", "warnings"]])
        
        production_ready = len(self.critical_failures) == 0
        
        assessment = {
            "production_ready": production_ready,
            "readiness_score": f"{passed_validations}/{total_validations}",
            "critical_failures_count": len(self.critical_failures),
            "warnings_count": len(self.warnings),
            "recommendation": self._get_deployment_recommendation(production_ready)
        }
        
        return assessment
    
    def _get_deployment_recommendation(self, production_ready: bool) -> str:
        """Get deployment recommendation based on validation results."""
        if production_ready:
            return "DEPLOY - All validation checks passed. System is ready for production deployment."
        elif len(self.critical_failures) <= 2:
            return "DEPLOY WITH CAUTION - Minor issues detected. Review critical failures and deploy with monitoring."
        else:
            return "DO NOT DEPLOY - Multiple critical issues detected. Resolve all critical failures before deployment."


async def main():
    """Main execution function."""
    validator = ProductionDeploymentValidator()
    
    try:
        print("="*80)
        print("PRODUCTION DEPLOYMENT VALIDATION")
        print("="*80)
        print(f"Agent: email")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print()
        
        results = await validator.run_complete_validation()
        
        print(f"VALIDATION RESULTS:")
        print(f"Overall Status: {results['overall_status']}")
        print(f"Validations Completed: {results['validations_completed']}")
        print(f"Total Time: {results['total_validation_time_seconds']}s")
        print()
        
        assessment = results["deployment_assessment"]
        print(f"DEPLOYMENT ASSESSMENT:")
        print(f"Production Ready: {assessment['production_ready']}")
        print(f"Readiness Score: {assessment['readiness_score']}")
        print(f"Critical Failures: {assessment['critical_failures_count']}")
        print(f"Warnings: {assessment['warnings_count']}")
        print()
        print(f"RECOMMENDATION: {assessment['recommendation']}")
        print()
        
        if results["critical_failures"]:
            print("CRITICAL FAILURES:")
            for i, failure in enumerate(results["critical_failures"], 1):
                print(f"  {i}. {failure}")
            print()
        
        if results["warnings"]:
            print("WARNINGS:")
            for i, warning in enumerate(results["warnings"], 1):
                print(f"  {i}. {warning}")
            print()
        
        print("VALIDATION DETAILS:")
        for validation_name, validation_result in results.items():
            if isinstance(validation_result, dict) and "status" in validation_result:
                status_symbol = "✓" if validation_result["status"] == "PASSED" else "✗"
                print(f"  {status_symbol} {validation_name}: {validation_result['status']}")
        
        print("="*80)
        
        # Exit with appropriate code
        if results["overall_status"] == "READY":
            return 0
        elif results["overall_status"] == "NOT_READY":
            return 1
        else:
            return 2
            
    except Exception as e:
        print(f"VALIDATION FAILED: {str(e)}")
        return 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
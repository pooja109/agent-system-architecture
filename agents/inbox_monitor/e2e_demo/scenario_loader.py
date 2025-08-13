"""
Scenario YAML Loader - Load and Validate Custom Scenarios
"""

import yaml
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass
import jsonschema
from jsonschema import validate, ValidationError

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env from the repo root (three levels up from this file: e2e_demo -> agents -> inbox_monitor -> repo_root)
    env_path = Path(__file__).parent.parent.parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    # python-dotenv not available, skip loading
    pass


@dataclass
class Scenario:
    """Represents a test scenario with business context."""
    id: int
    name: str
    description: str
    email_data: Dict[str, Any]
    expected_outcome: str
    category: str  # 'support', 'inquiry', 'no_longer_works'
    tags: list[str]  # Tags for filtering: 'support', 'inquiry', 'no_longer_works', etc.


@dataclass
class ScenarioResult:
    """Results from scenario execution."""
    scenario: Scenario
    success: bool
    duration: float
    business_outcome: Optional[str] = None
    technical_details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            'scenario_id': self.scenario.id,
            'scenario_name': self.scenario.name,
            'success': self.success,
            'duration': self.duration,
            'business_outcome': self.business_outcome,
            'technical_details': self.technical_details,
            'error': self.error
        }


# Scenario schema for validation
SCENARIO_SCHEMA = {
    "type": "object",
    "required": ["id", "name", "category", "email"],
    "properties": {
        "id": {
            "type": "integer",
            "minimum": 1,
            "maximum": 999
        },
        "name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100
        },
        "description": {
            "type": "string"
        },
        "category": {
            "type": "string",
            "enum": ["support", "inquiry", "no_longer_works", "positive", "negative", "invalid", "out_of_office", "custom"]
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"}
        },
        "email": {
            "type": "object",
            "required": ["from", "subject", "body"],
            "properties": {
                "from": {"type": "string"},
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "attachments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "size": {"type": "integer"}
                        }
                    }
                }
            }
        },
        "expected_outcome": {
            "type": "string"
        },
        "validation": {
            "type": "object",
            "properties": {
                "required_fields": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "success_criteria": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        },
        "mock_response": {
            "type": "object",
            "properties": {
                "delay": {"type": "number"},
                "success_rate": {"type": "number", "minimum": 0, "maximum": 1},
                "response_data": {"type": "object"}
            }
        }
    }
}


class ScenarioLoader:
    """Loads and validates scenarios from YAML files."""
    
    def __init__(self, scenarios_dir: str = "scenarios"):
        self.scenarios_dir = Path(scenarios_dir)
        self.loaded_scenarios = {}
        self.validation_errors = []
        
        # Create scenarios directory if it doesn't exist
        self.scenarios_dir.mkdir(exist_ok=True)
        
        # Create default scenarios if none exist
        if not list(self.scenarios_dir.glob("*.yaml")):
            self._create_default_scenarios()
    
    def load_all_scenarios(self) -> Dict[int, Scenario]:
        """Load all scenarios from YAML files."""
        self.loaded_scenarios = {}
        self.validation_errors = []
        
        # Load built-in scenarios first (5-10)
        self._load_builtin_scenarios()
        
        # Load custom scenarios from YAML files
        for yaml_file in self.scenarios_dir.glob("*.yaml"):
            try:
                scenarios = self._load_yaml_file(yaml_file)
                for scenario_data in scenarios:
                    if self._validate_scenario(scenario_data):
                        scenario = self._create_scenario(scenario_data)
                        self.loaded_scenarios[scenario.id] = scenario
            except Exception as e:
                self.validation_errors.append(f"Error loading {yaml_file}: {e}")
        
        return self.loaded_scenarios
    
    def load_scenario(self, scenario_id: int) -> Optional[Scenario]:
        """Load a specific scenario by ID."""
        if scenario_id in self.loaded_scenarios:
            return self.loaded_scenarios[scenario_id]
        
        # Try to load from all sources
        self.load_all_scenarios()
        return self.loaded_scenarios.get(scenario_id)
    
    def _load_yaml_file(self, filepath: Path) -> List[Dict[str, Any]]:
        """Load scenarios from a YAML file."""
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        
        # Handle both single scenario and list of scenarios
        if isinstance(data, dict):
            # Check if it's a scenarios wrapper or single scenario
            if "scenarios" in data:
                return data["scenarios"]
            else:
                return [data]
        elif isinstance(data, list):
            return data
        else:
            raise ValueError(f"Invalid YAML structure in {filepath}")
    
    def _validate_scenario(self, scenario_data: Dict[str, Any]) -> bool:
        """Validate scenario data against schema."""
        try:
            validate(instance=scenario_data, schema=SCENARIO_SCHEMA)
            return True
        except ValidationError as e:
            self.validation_errors.append(f"Scenario {scenario_data.get('id', 'unknown')}: {e.message}")
            return False
    
    def _create_scenario(self, data: Dict[str, Any]) -> Scenario:
        """Create Scenario object from validated data."""
        return Scenario(
            id=data['id'],
            name=data['name'],
            description=data.get('description', ''),
            category=data['category'],
            email_data={
                'from': data['email']['from'],
                'to': data['email'].get('to', 'inbox@company.com'),
                'subject': data['email']['subject'],
                'body': data['email']['body'],
                'attachments': data['email'].get('attachments', [])
            },
            expected_outcome=data.get('expected_outcome', 'Processed'),
            tags=data.get('tags', [])
        )
    
    def _load_builtin_scenarios(self):
        """Load built-in scenarios 5-10."""
        # Load environment variables for test mode
        import os
        try:
            from dotenv import load_dotenv
            from pathlib import Path
            # Load .env from repo root 
            env_path = Path(__file__).parent.parent.parent.parent / '.env'
            load_dotenv(env_path)
        except ImportError:
            pass
        
        # Get test email sender from environment
        test_email_sender = os.getenv('TEST_EMAIL_SENDER', 'jgroenlund@microsoft.com')
        
        builtin = [
            {
                'id': 5,
                'name': 'Scenario 5: Positive Response',
                'description': 'Customer expresses interest in services',
                'category': 'positive',
                'tags': ['support', 'positive'],
                'email': {
                    'from': test_email_sender,
                    'subject': 'Re: Your services look very interesting',
                    'body': "Hi there! I'm very interested in learning more about your solutions. Could you please have someone call me at 555-1234 to discuss this further? I think this could be exactly what we need for our company."
                },
                'expected_outcome': 'Positive engagement processed'
            },
            {
                'id': 6,
                'name': 'Scenario 6: Negative Response',
                'description': 'Customer requests to stop contact',
                'category': 'negative',
                'tags': ['support', 'negative'],
                'email': {
                    'from': 'unsubscribe@example.com',
                    'subject': 'Stop contacting me immediately',
                    'body': "I'm not interested in your services at all. Please remove me from your contact list immediately and don't contact me again. This is harassment."
                },
                'expected_outcome': 'Contact removed from lists'
            },
            {
                'id': 7,
                'name': 'Scenario 7: Service Inquiry',
                'description': 'Customer has question about order tracking',
                'category': 'inquiry',
                'tags': ['inquiry', 'support'],
                'email': {
                    'from': 'customer@example.com',
                    'subject': 'Question about my recent order #12345',
                    'body': "Hi, I have a question about my recent order. The tracking number you provided isn't working and I can't see the delivery status. Can you help me track my package?"
                },
                'expected_outcome': 'Service inquiry response sent'
            },
            {
                'id': 8,
                'name': 'Scenario 8: Out of Office',
                'description': 'Automated out of office reply received',
                'category': 'out_of_office',
                'tags': ['out_of_office', 'temporary'],
                'email': {
                    'from': 'customer@example.com',
                    'subject': 'Automatic reply: Out of Office',
                    'body': "Thank you for your email. I am currently out of the office and will return on Monday, July 22nd. If this is urgent, please contact my assistant at assistant@company.com."
                },
                'expected_outcome': 'Contact marked as temporarily away'
            },
            {
                'id': 9,
                'name': 'Scenario 9: Invalid Email',
                'description': 'Bounce notification for invalid email address',
                'category': 'invalid',
                'tags': ['invalid', 'bounce'],
                'email': {
                    'from': 'mailer-daemon@example.com',
                    'subject': 'Delivery Status Notification (Failure)',
                    'body': '''Your message could not be delivered to customer@example.com.

The email address may be invalid or the mailbox may be full. Please verify the email address and try again.

Original Message:
Subject: Your recent outreach
From: customer@example.com

This is an automated bounce notification generated for integration testing.'''
                },
                'expected_outcome': 'Contact marked as invalid email'
            },
            {
                'id': 10,
                'name': 'Scenario 10: No Longer Works',
                'description': 'Employee no longer works at company',
                'category': 'no_longer_works',
                'tags': ['no_longer_works', 'status_change'],
                'email': {
                    'from': 'hr@example.com',
                    'subject': 'Re: Your recent outreach',
                    'body': "Hi, John no longer works at this company. He left last month to pursue other opportunities."
                },
                'expected_outcome': 'Contact marked as no longer works'
            }
        ]
        
        for data in builtin:
            if self._validate_scenario(data):
                scenario = self._create_scenario(data)
                self.loaded_scenarios[scenario.id] = scenario
    
    def _create_default_scenarios(self):
        """Create default scenario YAML files."""
        default_scenario = """# Example Custom Scenario
id: 20
name: Custom Scenario Example
description: Template for creating custom scenarios
category: custom
tags:
  - example
  - template

email:
  from: sender@example.com
  to: support@company.com
  subject: Example Subject
  body: |
    This is a multi-line email body.
    It can contain multiple paragraphs.
    
    Use this as a template for your custom scenarios.

expected_outcome: Case created and assigned to support team

validation:
  required_fields:
    - from
    - subject
    - body
  success_criteria:
    - Case ID generated
    - Assignment completed
    - Response sent

mock_response:
  delay: 0.5
  success_rate: 0.95
  response_data:
    case_id: "CASE-12345"
    assigned_to: "support_team"
"""
        
        # Save default scenario
        default_file = self.scenarios_dir / "example_scenario.yaml"
        with open(default_file, 'w') as f:
            f.write(default_scenario)
    
    def save_scenario(self, scenario: Scenario, filename: str):
        """Save a scenario to YAML file."""
        data = {
            'id': scenario.id,
            'name': scenario.name,
            'description': scenario.description,
            'category': scenario.category,
            'tags': getattr(scenario, 'tags', []),
            'email': scenario.email_data,
            'expected_outcome': scenario.expected_outcome
        }
        
        filepath = self.scenarios_dir / filename
        with open(filepath, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def get_validation_report(self) -> str:
        """Get validation errors report."""
        if not self.validation_errors:
            return "All scenarios validated successfully."
        
        report = "Scenario Validation Errors:\n"
        report += "\n".join(f"  - {error}" for error in self.validation_errors)
        return report


class ScenarioFactory:
    """Creates scenario instances with business-focused test data."""
    
    def __init__(self):
        self.yaml_loader = None
        self._initialize_yaml_loader()
    
    def _initialize_yaml_loader(self):
        """Initialize YAML loader for custom scenarios."""
        try:
            self.yaml_loader = ScenarioLoader()
        except ImportError:
            # YAML loader not available, use built-in scenarios only
            self.yaml_loader = None
    
    def create(self, scenario_id: int) -> Scenario:
        """Create a scenario by ID from built-in or YAML scenarios."""
        # Try YAML loader first for custom scenarios
        if self.yaml_loader:
            yaml_scenario = self.yaml_loader.load_scenario(scenario_id)
            if yaml_scenario:
                return yaml_scenario
        
        # Fall back to built-in scenarios
        scenarios = self._get_scenarios()
        if scenario_id not in scenarios:
            raise ValueError(f"Scenario {scenario_id} not found in built-in or custom scenarios")
        return scenarios[scenario_id]
    
    def get_all_scenarios(self) -> Dict[int, Scenario]:
        """Get all available scenarios (built-in + YAML)."""
        scenarios = self._get_scenarios()
        
        # Add YAML scenarios if available
        if self.yaml_loader:
            yaml_scenarios = self.yaml_loader.load_all_scenarios()
            scenarios.update(yaml_scenarios)
        
        return scenarios
    
    def _get_scenarios(self) -> Dict[int, Scenario]:
        """Define all scenarios with CORRECT business context from legacy system."""
        # Get the test email sender from environment, with fallback
        test_email_sender = os.getenv('TEST_EMAIL_SENDER', 'jgroenlund@microsoft.com')
        
        return {
            5: Scenario(
                id=5,
                name="Scenario 5: Positive Response",
                description="Customer expresses interest in services",
                email_data={
                    'subject': 'Re: Your services look very interesting',
                    'from': test_email_sender,
                    'body': "Hi there! I'm very interested in learning more about your solutions. Could you please have someone call me at 555-1234 to discuss this further? I think this could be exactly what we need for our company."
                },
                expected_outcome="Positive engagement processed",
                category="positive",
                tags=["support", "positive"]
            ),
            
            6: Scenario(
                id=6,
                name="Scenario 6: Negative Response",
                description="Customer requests to stop contact",
                email_data={
                    'subject': 'Stop contacting me immediately',
                    'from': 'unsubscribe@example.com',
                    'body': "I'm not interested in your services at all. Please remove me from your contact list immediately and don't contact me again. This is harassment."
                },
                expected_outcome="Contact removed from lists",
                category="negative",
                tags=["support", "negative"]
            ),
            
            7: Scenario(
                id=7,
                name="Scenario 7: Service Inquiry",
                description="Customer has question about order tracking",
                email_data={
                    'subject': 'Question about my recent order #12345',
                    'from': 'customer@example.com',
                    'body': "Hi, I have a question about my recent order. The tracking number you provided isn't working and I can't see the delivery status. Can you help me track my package?"
                },
                expected_outcome="Service inquiry response sent",
                category="inquiry",
                tags=["inquiry", "support"]
            ),
            
            8: Scenario(
                id=8,
                name="Scenario 8: Out of Office",
                description="Automated out of office reply received",
                email_data={
                    'subject': 'Automatic reply: Out of Office',
                    'from': 'customer@example.com',
                    'body': "Thank you for your email. I am currently out of the office and will return on Monday, July 22nd. If this is urgent, please contact my assistant at assistant@company.com."
                },
                expected_outcome="Contact marked as temporarily away",
                category="out_of_office",
                tags=["out_of_office", "temporary"]
            ),
            
            9: Scenario(
                id=9,
                name="Scenario 9: Invalid Email",
                description="Bounce notification for invalid email address",
                email_data={
                    'subject': 'Delivery Status Notification (Failure)',
                    'from': 'mailer-daemon@example.com',
                    'body': '''Your message could not be delivered to customer@example.com.

The email address may be invalid or the mailbox may be full. Please verify the email address and try again.

Original Message:
Subject: Your recent outreach
From: customer@example.com

This is an automated bounce notification generated for integration testing.'''
                },
                expected_outcome="Contact marked as invalid email",
                category="invalid",
                tags=["invalid", "bounce"]
            ),
            
            10: Scenario(
                id=10,
                name="Scenario 10: No Longer Works",
                description="Employee no longer works at company",
                email_data={
                    'subject': 'Re: Your recent outreach',
                    'from': 'hr@example.com',
                    'body': "Hi, John no longer works at this company. He left last month to pursue other opportunities."
                },
                expected_outcome="Contact marked as no longer works",
                category="no_longer_works",
                tags=["no_longer_works", "status_change"]
            )
        }
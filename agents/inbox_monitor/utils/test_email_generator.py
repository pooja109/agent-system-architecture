#!/usr/bin/env python3
"""
Email Generator for AI Agent Intent Testing
===========================================

Generates and sends 20 personalized test emails to test various AI Agent intents and scenarios.
This version uses Azure Key Vault for secure credential management, with environment variable
fallback for development environments.

Security Features:
- Retrieves ACS credentials from Azure Key Vault (azure-communication-connection-string, azure-communication-sender-email)
- Falls back to environment variables (ACS_CONNECTION_STRING, ACS_SENDER_EMAIL) if Key Vault unavailable
- Never hardcodes credentials in source code
- Supports simulation mode for testing without real email sending
"""

import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv

# Load .env file from the main repo directory
repo_root = Path(__file__).parent.parent.parent.parent
env_file = repo_root / ".env"
load_dotenv(env_file)

# Azure Key Vault and Communication Services
from azure.keyvault.secrets import SecretClient
from azure.identity import ClientSecretCredential
from azure.communication.email import EmailClient

# Define EmailIntent enum locally to avoid complex dependencies
class EmailIntent(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative" 
    SERVICE_INQUIRY = "service_inquiry"
    OUT_OF_OFFICE = "out_of_office"
    NO_LONGER_WORKS = "no_longer_works"
    EMAIL_INVALID = "email_invalid"
    UNKNOWN = "unknown"

class AzureKeyVaultClient:
    """Azure Key Vault client for retrieving credentials."""
    
    def __init__(self):
        self.client: Optional[SecretClient] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Key Vault client with service principal credentials."""
        try:
            # Get Key Vault configuration from environment
            key_vault_url = os.getenv("AZURE_KEY_VAULT_URL")
            tenant_id = os.getenv("AZURE_TENANT_ID")
            client_id = os.getenv("AZURE_CLIENT_ID")
            client_secret = os.getenv("AZURE_CLIENT_SECRET")
            
            if not all([key_vault_url, tenant_id, client_id, client_secret]):
                print("⚠️  Key Vault credentials not fully configured, using environment fallback")
                return
            
            # Create credential and client
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            
            self.client = SecretClient(vault_url=key_vault_url, credential=credential)
            print("✅ Key Vault client initialized successfully")
            
        except Exception as e:
            print(f"⚠️  Could not initialize Key Vault client: {e}")
            print("   Falling back to environment variables")
    
    def get_secret(self, secret_name: str, fallback_env_var: str = None) -> Optional[str]:
        """
        Get secret from Key Vault with environment variable fallback.
        
        Args:
            secret_name: Name of secret in Key Vault
            fallback_env_var: Environment variable to use if Key Vault unavailable
        
        Returns:
            Secret value or None if not found
        """
        try:
            if self.client:
                secret = self.client.get_secret(secret_name)
                print(f"✅ Retrieved secret '{secret_name}' from Key Vault")
                return secret.value
        except Exception as e:
            print(f"⚠️  Could not retrieve secret '{secret_name}' from Key Vault: {e}")
        
        # Fallback to environment variable
        if fallback_env_var:
            value = os.getenv(fallback_env_var)
            if value:
                print(f"✅ Using fallback environment variable '{fallback_env_var}'")
                return value
        
        print(f"❌ Could not retrieve secret '{secret_name}' from any source")
        return None


class SimpleACSEmailSender:
    """Simple Azure Communication Services email sender for testing."""
    
    def __init__(self):
        self.client = None
        
    async def initialize(self, connection_string: str):
        """Initialize the ACS email client."""
        if not connection_string:
            raise ValueError("ACS connection string is required")
        self.client = EmailClient.from_connection_string(connection_string)
        
    async def send_email(self, recipient: str, subject: str, html_content: str, 
                        sender_email: str, reply_to_email: str = None, headers: dict = None):
        """Send email using ACS."""
        if not self.client:
            return {"success": False, "error": "Client not initialized"}
            
        try:
            # Prepare message
            message = {
                "senderAddress": sender_email,
                "recipients": {"to": [{"address": recipient}]},
                "content": {"subject": subject, "html": html_content}
            }
            
            # Add reply-to if specified
            if reply_to_email:
                message["replyTo"] = [{"address": reply_to_email}]
                
            # Add headers if specified
            if headers:
                message["headers"] = headers
                
            # Send email
            poller = self.client.begin_send(message)
            result = poller.result()
            
            if result:
                # Handle both object and dictionary responses
                if hasattr(result, 'status'):
                    status = result.status
                    message_id = getattr(result, 'id', None)
                elif isinstance(result, dict):
                    status = result.get('status')
                    message_id = result.get('id')
                else:
                    return {"success": False, "error": f"Unrecognized result format: {result}"}
                
                if status == "Succeeded":
                    return {"success": True, "message_id": message_id}
                else:
                    return {"success": False, "error": f"Send failed with status: {status}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

# Test scenarios to generate - 20 unique scenarios covering all EmailIntent types
TEST_SCENARIOS = [
    # POSITIVE responses (6 scenarios)
    {
        "name": "Positive Response - Very Interested",
        "intent": EmailIntent.POSITIVE,
        "company": "GreenTech Solutions",
        "contact_name": "Sarah Mitchell",
        "industry": "renewable energy",
        "subject_line": "Streamline Your Clean Energy Operations with Smart Automation",
        "outreach_approach": "sustainability_efficiency",
        "response_template": "Thank you for reaching out! This sounds like exactly what we need for our solar farm operations. We're currently managing 15+ renewable energy projects manually, and automation could be a game-changer. I'd love to schedule a call to discuss our specific needs around permit tracking and compliance reporting. When would be a good time this week? Also, do you have any case studies from other renewable energy companies?"
    },
    {
        "name": "Positive Response - Budget Ready", 
        "intent": EmailIntent.POSITIVE,
        "company": "DataFlow Analytics",
        "contact_name": "Marcus Johnson",
        "industry": "data analytics",
        "subject_line": "ROI-Driven Data Analytics Automation - Let's Talk Numbers",
        "outreach_approach": "roi_focused",
        "response_template": "Hi there! I'm definitely interested in learning more about your automation solutions for data analytics. Your ROI numbers are compelling - we're currently spending about 20 hours/week on manual report generation. Can you send me some pricing information and perhaps schedule a demo? Our budget for Q1 is around $50-75k, and if we can demonstrate clear ROI, we might be able to expand that for the right solution."
    },
    {
        "name": "Positive Response - Urgent Need",
        "intent": EmailIntent.POSITIVE,
        "company": "FastTrack Logistics",
        "contact_name": "Rachel Kim",
        "industry": "logistics and shipping",
        "subject_line": "Accelerate Your Supply Chain Operations with Intelligent Automation",
        "outreach_approach": "urgency_transformation",
        "response_template": "This is perfect timing! We're in the middle of a major digital transformation focused on supply chain optimization, and automation is a key component of our strategy. Our CEO just approved budget for process automation initiatives. Can we schedule a meeting this week? I'd love to discuss how your logistics automation can integrate with our new SAP implementation. Time is critical for us - we want to have solutions in place by Q2."
    },
    {
        "name": "Positive Response - Expansion Plans",
        "intent": EmailIntent.POSITIVE,
        "company": "HealthTech Innovations",
        "contact_name": "Dr. Anthony Lee",
        "industry": "healthcare technology",
        "subject_line": "HIPAA-Compliant Healthcare Automation for Patient Care Excellence",
        "outreach_approach": "compliance_scalability",
        "response_template": "Your automation platform could be exactly what we need for our expansion into telemedicine. We're projecting 300% growth in telehealth appointments over the next 18 months, and our current manual processes won't scale. I'd like to discuss how this could help us automate patient data processing while maintaining HIPAA compliance. Are you available for a call next Tuesday? I'd also like to include our Chief Compliance Officer in the discussion."
    },
    {
        "name": "Positive Response - Team Interested",
        "intent": EmailIntent.POSITIVE,
        "company": "EduStream Technologies",
        "contact_name": "Linda Zhang",
        "industry": "educational technology",
        "subject_line": "Transform Student Assessment Workflows - EdTech Automation Success Stories",
        "outreach_approach": "case_study_focused",
        "response_template": "I shared your email with our development team and they're excited about the possibilities! We're processing over 50,000 student assessments monthly across 200+ schools, and the manual scoring bottleneck is becoming critical. Your case study numbers are impressive - 75% reduction in grading time would be transformational for us. Can you provide some detailed case studies in the education sector? Also, we'd love to understand your integration capabilities with Canvas and Google Classroom."
    },
    {
        "name": "Positive Response - ROI Focused",
        "intent": EmailIntent.POSITIVE,
        "company": "FinanceFlow Corp",
        "contact_name": "Robert Chen",
        "industry": "financial services",
        "subject_line": "Reduce Compliance Costs by 40% - Financial Services Automation Demo",
        "outreach_approach": "cost_reduction_demo",
        "response_template": "The ROI potential you mentioned is compelling - 40% cost reduction in compliance reporting would save us approximately $200k annually. We're currently spending 160 hours per month on regulatory reporting across our 4 compliance analysts. I'd like to set up a demo to see how your solution handles financial data automation, specifically SEC reporting and regulatory filings. Can you also walk us through your audit trail capabilities and data security measures?"
    },

    # SERVICE_INQUIRY responses (5 scenarios)
    {
        "name": "Service Inquiry - Technical Questions",
        "intent": EmailIntent.SERVICE_INQUIRY,
        "company": "CloudFirst Corp", 
        "contact_name": "Jennifer Davis",
        "industry": "cloud computing",
        "subject_line": "AWS Integration Questions - Cloud Infrastructure Automation",
        "outreach_approach": "technical_integration",
        "response_template": "I received your email about automation solutions. As our Lead Cloud Architect, I have a few technical questions before we can move forward: 1) Do you support AWS Lambda integration with our existing API Gateway setup? 2) What's your typical implementation timeline for a company our size (500+ employees)? 3) Do you provide 24/7 support, and what's your SLA for critical issues? 4) Can your platform handle our current volume of 10M+ transactions per month? I'd appreciate detailed technical documentation if available."
    },
    {
        "name": "Service Inquiry - Demo Request",
        "intent": EmailIntent.SERVICE_INQUIRY,
        "company": "RetailMax Inc",
        "contact_name": "David Chen", 
        "industry": "retail automation",
        "subject_line": "Inventory Management Demo Request - Retail Automation Solutions",
        "outreach_approach": "demo_scheduling",
        "response_template": "Hello! Your automation platform looks promising for our retail operations. We operate 50+ retail locations with complex inventory management needs - multi-channel sales, seasonal fluctuations, and supplier integration challenges. Could we schedule a demo next week? I'd specifically like to see how it handles real-time inventory sync, automated reorder points, and integration with our existing POS system (Square). Also, can it handle our peak holiday season volumes?"
    },
    {
        "name": "Service Inquiry - Integration Questions",
        "intent": EmailIntent.SERVICE_INQUIRY,
        "company": "ManufacturingPro Solutions",
        "contact_name": "Tom Rodriguez",
        "industry": "manufacturing",
        "subject_line": "SAP Integration Inquiry - Manufacturing Process Automation",
        "outreach_approach": "enterprise_integration",
        "response_template": "Thanks for your outreach. Before we proceed, I need to understand: Does your platform integrate with SAP? What about custom API endpoints? We have a complex manufacturing setup that requires specific integrations."
    },
    {
        "name": "Service Inquiry - Pricing Information",
        "intent": EmailIntent.SERVICE_INQUIRY,
        "company": "StartupAccelerator Hub",
        "contact_name": "Jessica Park",
        "industry": "startup consulting",
        "subject_line": "Scalable Pricing for Growing Startups - Portfolio Solutions",
        "outreach_approach": "startup_pricing",
        "response_template": "Hi! Your automation solution sounds interesting for our portfolio companies. Could you provide detailed pricing tiers? We work with startups of various sizes and need scalable options."
    },
    {
        "name": "Service Inquiry - Security Concerns",
        "intent": EmailIntent.SERVICE_INQUIRY,
        "company": "SecureBank Financial",
        "contact_name": "William Martinez",
        "industry": "banking",
        "subject_line": "SOC 2 Compliance & Security - Enterprise Banking Automation",
        "outreach_approach": "security_compliance",
        "response_template": "Your automation platform caught our attention, but we have strict security requirements. Can you provide information about SOC 2 compliance, data encryption, and audit capabilities? We need to ensure full regulatory compliance."
    },

    # NEGATIVE responses (4 scenarios)
    {
        "name": "Negative Response - Not Interested",
        "intent": EmailIntent.NEGATIVE,
        "company": "TechStart Ventures",
        "contact_name": "Emily Rodriguez",
        "industry": "startup consulting",
        "subject_line": "Quick Question About Your Current Workflow Challenges",
        "outreach_approach": "soft_inquiry",
        "response_template": "Thanks for reaching out, but we're not interested in automation solutions at this time. We're a bootstrapped startup focused on product-market fit and customer acquisition - operational efficiency isn't our biggest pain point right now. We're focusing on growth and fundraising this quarter. Please remove me from your mailing list, but feel free to reach out again in 6-9 months when we might be ready to optimize our operations."
    },
    {
        "name": "Negative Response - Already Have Solution",
        "intent": EmailIntent.NEGATIVE, 
        "company": "Enterprise Solutions Ltd",
        "contact_name": "Michael Thompson",
        "industry": "enterprise software",
        "subject_line": "Explore Next-Generation Enterprise Automation Beyond Power Automate",
        "outreach_approach": "competitive_positioning",
        "response_template": "Hello, we already have a comprehensive automation platform in place with Microsoft Power Automate that handles most of our workflow needs. Our IT team spent 8 months implementing it across all departments, and we're not looking to switch vendors at this time. We're also heavily invested in the Microsoft ecosystem (Office 365, Teams, Azure), so staying within that environment makes sense for us. Thanks for thinking of us though."
    },
    {
        "name": "Negative Response - Budget Constraints",
        "intent": EmailIntent.NEGATIVE,
        "company": "SmallBiz Operations",
        "contact_name": "Carol Johnson",
        "industry": "small business services",
        "subject_line": "Small Business Automation - Start Small, Scale Smart",
        "outreach_approach": "budget_friendly",
        "response_template": "Thank you for the information, but automation solutions are outside our current budget right now. We're a small 8-person operation and honestly, we're still working on getting our basic systems in place - CRM, accounting software, HR processes. Automation feels like a luxury we can't afford until we grow to at least 20+ employees and have more predictable revenue. Maybe revisit this conversation in 12-18 months?"
    },
    {
        "name": "Negative Response - Wrong Timing",
        "intent": EmailIntent.NEGATIVE,
        "company": "GrowthStage Startup",
        "contact_name": "Alex Rivera",
        "industry": "technology startup",
        "subject_line": "Perfect Timing for Your Product Pivot - Automation Support",
        "outreach_approach": "timing_strategic",
        "response_template": "Appreciate you reaching out. While your solution looks good, we're in the middle of a major product pivot and can't take on new vendor relationships right now. Maybe check back in 6 months."
    },

    # OUT_OF_OFFICE responses (3 scenarios)
    {
        "name": "Out of Office - Vacation",
        "intent": EmailIntent.OUT_OF_OFFICE,
        "company": "Global Manufacturing Co",
        "contact_name": "Lisa Wang", 
        "industry": "manufacturing",
        "subject_line": "Manufacturing Efficiency Gains - Worth Discussing?",
        "outreach_approach": "efficiency_gains",
        "response_template": "Thank you for your email. I am currently out of the office until January 15th with limited email access. For urgent matters, please contact my assistant at assistant@globalmanufacturing.com. I will respond to your message when I return."
    },
    {
        "name": "Out of Office - Conference",
        "intent": EmailIntent.OUT_OF_OFFICE,
        "company": "InnovateTech Labs",
        "contact_name": "Robert Kim",
        "industry": "research and development",
        "subject_line": "R&D Process Automation - Innovation Lab Partnership Opportunity",
        "outreach_approach": "innovation_partnership",
        "response_template": "I'm currently attending the AI Innovation Conference through December 20th. I'll have limited email access but will respond to all messages upon my return. For immediate assistance, please contact our main office."
    },
    {
        "name": "Out of Office - Medical Leave",
        "intent": EmailIntent.OUT_OF_OFFICE,
        "company": "ConsultingPro Services",
        "contact_name": "Maria Santos",
        "industry": "business consulting",
        "subject_line": "Consulting Firm Workflow Optimization - Free Assessment",
        "outreach_approach": "free_assessment",
        "response_template": "Thank you for your email. I am currently on medical leave and will return to the office on February 1st. For immediate assistance with automation solutions, please contact my colleague John Smith at jsmith@consultingpro.com."
    },

    # NO_LONGER_WORKS responses (3 scenarios)
    {
        "name": "No Longer Works - Left Company", 
        "intent": EmailIntent.NO_LONGER_WORKS,
        "company": "StartupHub Inc",
        "contact_name": "Amanda Foster",
        "industry": "business incubation",
        "subject_line": "Startup Portfolio Automation - Scale Your Incubator Operations",
        "outreach_approach": "portfolio_scaling",
        "response_template": "Thank you for your email. Amanda Foster is no longer with StartupHub Inc. For inquiries regarding automation solutions, please contact our new Operations Director at operations@startuphub.com."
    },
    {
        "name": "No Longer Works - Promotion",
        "intent": EmailIntent.NO_LONGER_WORKS,
        "company": "Growth Dynamics Corp",
        "contact_name": "James Wilson", 
        "industry": "business consulting",
        "subject_line": "Strategic Growth Through Process Automation - Executive Briefing",
        "outreach_approach": "executive_briefing",
        "response_template": "Hi there! I've recently been promoted to VP of Strategy and no longer handle vendor evaluations. Please redirect your automation solution inquiry to our new Operations Manager, Sandra Lee at slee@growthdynamics.com."
    },
    {
        "name": "No Longer Works - Department Change",
        "intent": EmailIntent.NO_LONGER_WORKS,
        "company": "TechCorp Industries",
        "contact_name": "Steven Adams",
        "industry": "technology consulting",
        "subject_line": "Technology Consulting Automation - Client Delivery Excellence",
        "outreach_approach": "client_delivery",
        "response_template": "Thanks for reaching out. I've moved to a different department and no longer handle technology procurement. Please contact our IT Director, Michelle Brown at mbrown@techcorp.com for automation solution inquiries."
    },

    # EMAIL_INVALID responses (2 scenarios) 
    {
        "name": "Email Invalid - Bounce",
        "intent": EmailIntent.EMAIL_INVALID,
        "company": "TechCorp Solutions",
        "contact_name": "Invalid Email",
        "industry": "technology",
        "subject_line": "Technology Solutions Automation - Digital Transformation Opportunity",
        "outreach_approach": "digital_transformation",
        "response_template": "MAILER-DAEMON: The email address you're trying to reach no longer exists. This mailbox has been decommissioned. Please verify the recipient's email address and try again."
    },
    {
        "name": "Email Invalid - Domain Error",
        "intent": EmailIntent.EMAIL_INVALID,
        "company": "OldCompany Corp",
        "contact_name": "Former Employee",
        "industry": "defunct business",
        "subject_line": "Business Process Automation - Competitive Advantage",
        "outreach_approach": "competitive_advantage",
        "response_template": "550 5.1.1 The email account that you tried to reach does not exist. Please check the recipient's email address for typos or unnecessary spaces."
    }
]

class EmailGenerator:
    """Generate realistic test emails for AI Agent intent testing."""
    
    def __init__(self):
        self.key_vault_client = AzureKeyVaultClient()
        self.email_client = SimpleACSEmailSender()
        self._acs_connection_string: Optional[str] = None
        self._acs_sender_email: Optional[str] = None
    
    def _get_acs_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """Get ACS credentials from Key Vault or environment variables."""
        if self._acs_connection_string and self._acs_sender_email:
            return self._acs_connection_string, self._acs_sender_email
        
        # Try to get from Key Vault first, then fall back to environment variables
        connection_string = self.key_vault_client.get_secret(
            "azure-communication-connection-string", 
            "ACS_CONNECTION_STRING"
        )
        
        sender_email = self.key_vault_client.get_secret(
            "azure-communication-sender-email",
            "ACS_SENDER_EMAIL"
        )
        
        # Cache for subsequent calls
        self._acs_connection_string = connection_string
        self._acs_sender_email = sender_email
        
        return connection_string, sender_email
        
    def generate_outreach_email(self, scenario: Dict[str, Any]) -> str:
        """Generate a personalized outreach email using diverse templates."""
        
        outreach_approach = scenario.get('outreach_approach', 'general')
        company = scenario['company']
        contact_name = scenario['contact_name']
        industry = scenario['industry']
        
        # Define different outreach templates based on approach
        templates = {
            'sustainability_efficiency': f"""Hi {contact_name},

I noticed {company} is making impressive strides in {industry} - particularly your commitment to sustainable operations.

Many clean energy companies are discovering that intelligent process automation can reduce their operational footprint by 30-40% while accelerating project timelines.

Our platform specifically helps renewable energy firms:
• Automate permit tracking and compliance reporting
• Streamline project milestone workflows
• Reduce manual data collection from IoT sensors
• Integrate seamlessly with existing clean energy management systems

Would you be interested in a brief conversation about how automation is transforming operations in the renewable energy sector?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'roi_focused': f"""Hi {contact_name},

I came across {company} and was impressed by your data analytics capabilities. 

Companies similar to yours typically see 3-5x ROI within the first year when they automate their data processing workflows.

Here's what we're seeing in the {industry} space:
• 60% reduction in manual report generation time
• 85% fewer data entry errors
• $50-75k average annual savings per analyst
• Faster time-to-insight for strategic decisions

Our automation platform integrates with your existing analytics stack and can demonstrate ROI within the first 90 days.

Would you like to see a 15-minute demo focused specifically on data analytics automation ROI?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'urgency_transformation': f"""Hi {contact_name},

I understand {company} is in the middle of a major digital transformation - congratulations on taking this important step!

During transformation initiatives, the companies that succeed fastest are those that automate their core operational processes early in the journey.

Our logistics automation platform can help you:
• Accelerate your transformation timeline by 40%
• Reduce operational disruption during the transition
• Provide immediate efficiency gains while you implement larger changes
• Integrate with both legacy and new systems

We've helped 50+ logistics companies through similar transformations. Would you like to discuss how automation can support your current initiative?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'compliance_scalability': f"""Hi Dr. {contact_name.split()[-1]},

I noticed {company}'s expansion into telemedicine - an exciting and rapidly growing field that requires robust, HIPAA-compliant processes.

Healthcare organizations scaling into telehealth need automation that can:
• Ensure consistent HIPAA compliance across all patient interactions
• Scale patient data processing without adding administrative overhead
• Integrate securely with EHR systems and telehealth platforms
• Maintain audit trails for regulatory requirements

Our healthcare automation platform is specifically designed for organizations like yours that are scaling while maintaining the highest compliance standards.

Would you be available for a brief discussion about compliant automation for telehealth expansion?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'case_study_focused': f"""Hi {contact_name},

Your team at {company} is doing innovative work in educational technology. I thought you might be interested in how other EdTech companies are transforming their student assessment workflows.

Recent case study: A similar EdTech company automated their assessment processing and saw:
• 75% reduction in grading turnaround time
• 90% fewer manual scoring errors
• Ability to process 5x more assessments with the same team
• Real-time analytics for educators and students

Our education-focused automation platform integrates with existing LMS systems and maintains all necessary student data privacy protections.

Would your development team be interested in a technical deep-dive into these EdTech automation success stories?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'cost_reduction_demo': f"""Hi {contact_name},

Financial services firms using our automation platform typically reduce their compliance reporting costs by 40% in the first year alone.

Here's a specific example relevant to {industry}:
→ Previous manual process: 40 hours/week for compliance reporting
→ After automation: 8 hours/week (80% reduction)
→ Annual savings: $85,000+ per compliance analyst
→ Added benefit: 95% reduction in reporting errors

Our platform specifically handles:
• Automated regulatory report generation
• Real-time compliance monitoring
• Audit trail documentation
• Integration with existing financial systems

Would you like to see a live demo showing exactly how this works with financial compliance workflows?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'technical_integration': f"""Hi {contact_name},

I noticed {company} has a sophisticated cloud infrastructure. Many cloud-first companies are looking for automation solutions that integrate seamlessly with their existing AWS/Azure environments.

Technical highlights of our platform:
• Native AWS Lambda and Azure Functions support
• RESTful APIs for custom integrations
• Kubernetes-ready containerized deployment
• Support for Infrastructure as Code (Terraform/CloudFormation)
• 24/7 technical support with cloud architecture specialists

Our implementation typically takes 2-4 weeks and includes full technical documentation and DevOps team training.

Would your technical team be interested in a architecture-focused demo showing our cloud integrations?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'demo_scheduling': f"""Hi {contact_name},

Retail operations teams love seeing our inventory management automation in action because the benefits are immediately visible.

A typical demo shows:
• Real-time inventory sync across multiple channels
• Automated reorder point calculations
• Supply chain disruption alerts
• Integration with existing POS and ERP systems

The demo is interactive - you can bring your actual inventory challenges and we'll show exactly how our platform would handle them.

Are you available for a 30-minute demo next Tuesday or Wednesday? I can tailor it specifically to RetailMax's inventory management needs.

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'enterprise_integration': f"""Hi {contact_name},

Manufacturing companies with complex SAP environments need automation solutions that integrate seamlessly without disrupting existing processes.

Our manufacturing automation platform offers:
• Pre-built SAP connectors (no custom development required)
• Custom API endpoint support for proprietary systems
• Real-time data synchronization with ERP systems
• Comprehensive testing environment for integration validation

We typically complete SAP integrations in 3-4 weeks with full rollback capabilities and minimal production impact.

Would you like to discuss your specific SAP integration requirements? I can connect you directly with our manufacturing integration specialists.

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'startup_pricing': f"""Hi {contact_name},

Accelerators need automation solutions that can scale with their portfolio companies - from early-stage startups to Series B+ companies.

Our startup-friendly pricing includes:
• Free tier for companies < 10 employees
• Graduated pricing that scales with company growth
• Portfolio-wide licensing discounts for accelerators
• No long-term contracts (month-to-month options available)

Many accelerators use our platform to:
• Standardize operations across portfolio companies
• Provide shared automation resources
• Track portfolio company operational metrics
• Reduce administrative overhead for their teams

Could we schedule a brief call to discuss pricing options for your portfolio companies?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'security_compliance': f"""Hi {contact_name},

Banking institutions require automation platforms that meet the highest security and compliance standards.

Our platform's security credentials:
• SOC 2 Type II compliant
• PCI DSS Level 1 certified
• Bank-grade 256-bit encryption (data in transit and at rest)
• Comprehensive audit logging and reporting
• Regular third-party security assessments

We also provide:
• Detailed security documentation for internal audits
• Compliance team training and support
• Custom security configurations for specific regulatory requirements
• Dedicated security liaison for enterprise accounts

Would you like to review our complete security and compliance documentation? I can also arrange a call with our Chief Security Officer.

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            # Negative response approaches (more consultative)
            'soft_inquiry': f"""Hi {contact_name},

I hope you're having a great quarter at {company}.

Quick question - are you currently handling any repetitive administrative tasks that take time away from your core consulting work?

Many {industry} firms mention they spend 15-20 hours per week on routine tasks like:
• Client report generation
• Data compilation and analysis
• Meeting scheduling and follow-ups
• Document processing

If this resonates, I'd love to share how automation is freeing up strategic time for consulting teams.

Would a brief 10-minute conversation be valuable?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'competitive_positioning': f"""Hi {contact_name},

I know {company} is already using Microsoft Power Automate - that's a solid foundation for basic workflow automation.

Companies with mature automation practices are now looking at next-generation solutions that offer:
• Advanced AI-driven decision making (beyond simple if/then workflows)
• Enterprise-scale processing capabilities
• Advanced integration options with legacy systems
• Sophisticated analytics and optimization features

We often work alongside existing Power Automate implementations, handling the more complex automation scenarios that require advanced capabilities.

Would a brief conversation about next-generation automation be valuable for your planning?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'budget_friendly': f"""Hi {contact_name},

I understand that as a small business, every technology investment needs to deliver immediate, measurable value.

That's exactly why we created our small business automation starter package:
• Low monthly cost (starts at $99/month)
• No setup fees or long-term contracts
• Pre-built templates for common small business needs
• 30-day money-back guarantee

Typical small business results:
• Save 8-12 hours per week on routine tasks
• ROI positive within 60 days
• Scale operations without hiring additional staff

Would a 15-minute conversation about budget-friendly automation options be helpful?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'timing_strategic': f"""Hi {contact_name},

Product pivots are exciting but incredibly demanding on operational resources. Many growing companies find that automating routine processes during pivots helps them:

• Focus technical resources on core product development
• Maintain operational continuity during strategic changes
• Reduce administrative overhead when every hour counts
• Set up scalable processes for post-pivot growth

Even if automation isn't a priority right now, I'd love to send you our "Automation During Growth Transitions" guide - it might be useful for your planning.

Would that be helpful? No pressure on timing - just want to provide a useful resource.

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567"""
        }
        
        # Add more general approaches for remaining scenarios
        default_approaches = {
            'efficiency_gains': f"""Hi {contact_name},

Manufacturing efficiency is more critical than ever, and I noticed {company} has been growing in the {industry} space.

Top manufacturing companies are using intelligent automation to:
• Reduce production planning time by 40%
• Minimize manual quality control processes
• Automate compliance documentation
• Optimize resource allocation across production lines

Would you be interested in learning how similar manufacturing companies are achieving these efficiency gains?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'innovation_partnership': f"""Hi {contact_name},

R&D environments require automation solutions that are flexible enough to adapt to constantly evolving research needs.

Our platform helps research organizations:
• Automate data collection from experimental setups
• Streamline research documentation and compliance
• Integrate with specialized research software and equipment
• Scale data processing for large research projects

Many R&D teams appreciate our flexible APIs that adapt to their unique research workflows.

Would your team be interested in exploring how automation can enhance your research processes?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'free_assessment': f"""Hi {contact_name},

Consulting firms often have complex workflow requirements that vary by client engagement.

We're offering complimentary workflow assessments for consulting firms to identify automation opportunities that could:
• Reduce client deliverable preparation time
• Standardize processes across different client engagements
• Improve project tracking and reporting
• Free up consultants to focus on high-value client work

The assessment takes about 30 minutes and provides a customized automation roadmap with no obligation.

Would a free workflow assessment be valuable for ConsultingPro Services?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'portfolio_scaling': f"""Hi {contact_name},

Business incubators have unique operational challenges - managing multiple portfolio companies while providing consistent support and tracking progress.

Our platform helps incubators:
• Standardize reporting across portfolio companies
• Automate investor update compilation
• Track key metrics across multiple startups
• Streamline mentor scheduling and feedback collection

Many incubators find this especially valuable during due diligence and investor reporting periods.

Would you like to explore how automation could scale your portfolio management operations?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'executive_briefing': f"""Hi {contact_name},

Congratulations on your promotion to VP of Strategy! Strategic roles often require significant data analysis and reporting to support key business decisions.

Executive-focused automation solutions can help with:
• Automated competitive intelligence gathering
• Strategic KPI dashboard generation
• Board presentation data compilation
• Market analysis report automation

Even though you may not handle vendor evaluations directly anymore, this might be valuable for your strategic planning initiatives.

Would a brief executive briefing on strategic automation be valuable?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'client_delivery': f"""Hi {contact_name},

Technology consulting firms need to deliver exceptional results for their clients while maintaining operational efficiency.

Our platform helps consulting firms:
• Automate client deliverable generation
• Standardize project documentation processes
• Streamline client communication workflows
• Track project milestones and resource allocation

This allows consultants to focus on high-value strategic work rather than administrative tasks.

Would this be relevant for your client delivery excellence initiatives?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'digital_transformation': f"""Hi {contact_name},

Digital transformation initiatives require robust automation foundations to be successful.

Companies achieving the best transformation results typically:
• Automate core business processes early in their transformation
• Use automation to bridge legacy and new systems
• Implement scalable workflows that grow with the business
• Focus on processes that deliver immediate efficiency gains

Our transformation-focused automation platform is designed specifically to support these initiatives.

Would a digital transformation automation briefing be valuable for your planning?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567""",

            'competitive_advantage': f"""Hi {contact_name},

In today's competitive business environment, operational efficiency can be a significant differentiator.

Companies that leverage intelligent automation gain advantages through:
• Faster response times to customer requests
• More consistent service delivery
• Reduced operational costs
• Ability to scale without proportional cost increases

Our platform helps businesses build these competitive advantages into their core operations.

Would you be interested in learning how automation creates sustainable competitive advantages?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567"""
        }
        
        # Combine all templates
        all_templates = {**templates, **default_approaches}
        
        # Use specific template or fall back to general approach
        template = all_templates.get(outreach_approach, templates.get('soft_inquiry', ''))
        
        return template

    def create_email_headers(self, original_subject: str) -> Dict[str, str]:
        """Create realistic email headers that make it look like a reply."""
        
        # Generate realistic email threading headers
        original_msg_id = f"<{uuid.uuid4()}@staples.com>"
        thread_topic = original_subject.replace("Re: ", "")
        
        return {
            "In-Reply-To": original_msg_id,
            "References": original_msg_id,
            "Thread-Topic": thread_topic,
            "Thread-Index": f"AQH{uuid.uuid4().hex[:16].upper()}"
        }
    
    def convert_text_to_html(self, text_content: str) -> str:
        """Convert plain text email to properly formatted HTML."""
        import html
        
        # Split content into lines
        lines = text_content.split('\n')
        html_lines = []
        
        open_divs = []  # Track open div tags to close them properly
        
        for line in lines:
            line_stripped = line.strip()
            
            # HTML escape the content
            safe_line = html.escape(line_stripped)
            
            # Detect sections for special formatting
            if line_stripped.startswith("-----Original Message-----"):
                # Close any open signature div first
                if open_divs:
                    html_lines.append('</div>')
                    open_divs.pop()
                
                # Start original message section
                html_lines.append('<div style="margin-top: 20px; border-top: 1px solid #ccc; padding-top: 10px;">')
                html_lines.append(f'<p style="font-weight: bold; color: #666; margin-bottom: 10px;">{safe_line}</p>')
                open_divs.append('original_message')
                
            elif line_stripped.startswith("Best regards,"):
                # Start signature section
                html_lines.append('<div style="margin-top: 15px;">')
                html_lines.append(f'<p style="margin-bottom: 5px;">{safe_line}</p>')
                open_divs.append('signature')
                
            elif line_stripped.startswith(">"):
                # Quoted original email content
                quoted_text = html.escape(line_stripped[1:].strip())  # Remove ">" and extra spaces
                if quoted_text:  # Only add non-empty quoted lines
                    html_lines.append(f'<p style="margin: 5px 0 5px 15px; color: #666; border-left: 3px solid #ccc; padding-left: 10px;">{quoted_text}</p>')
                
            elif line_stripped.startswith("•"):
                # Bullet points
                bullet_text = html.escape(line_stripped[1:].strip())  # Remove "•" and extra spaces
                html_lines.append(f'<p style="margin: 5px 0 5px 20px;">• {bullet_text}</p>')
                
            elif line_stripped == "":
                # Empty lines become paragraph breaks (but not too many)
                html_lines.append('<br>')
                
            else:
                # Regular content
                if safe_line:
                    html_lines.append(f'<p style="margin: 5px 0;">{safe_line}</p>')
        
        # Close any remaining open divs
        while open_divs:
            html_lines.append('</div>')
            open_divs.pop()
        
        # Wrap in a proper HTML body with styling
        html_content = f"""<div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333;">
{''.join(html_lines)}
</div>"""
        
        return html_content

    def format_email_as_reply(self, original_outreach: str, customer_response: str, scenario: Dict[str, Any]) -> str:
        """Format customer response as a realistic email reply."""
        
        # Simulate original email being quoted at bottom
        original_date = (datetime.now() - timedelta(days=random.randint(1, 7))).strftime("%A, %B %d, %Y %I:%M %p")
        quoted_original = "\n".join([f"> {line}" for line in original_outreach.split("\n")])
        
        signature = f"""

Best regards,
{scenario['contact_name']}
{random.choice(['VP Operations', 'Director of Technology', 'Operations Manager', 'IT Director'])}
{scenario['company']}
{scenario['contact_name'].lower().replace(' ', '.')}@{scenario['company'].lower().replace(' ', '').replace(',', '').replace('.', '')}.com"""

        original_subject = scenario.get('subject_line', f"AI-Powered Automation Solutions for {scenario['company']}")
        
        return f"""{customer_response}{signature}

-----Original Message-----
From: Alex Thompson <athompson@staples.com>
Sent: {original_date}
To: {scenario['contact_name']} <{scenario['contact_name'].lower().replace(' ', '.')}@{scenario['company'].lower().replace(' ', '').replace(',', '').replace('.', '')}.com>
Subject: {original_subject}

{quoted_original}"""

    async def send_test_email(self, scenario: Dict[str, Any], email_content: str) -> bool:
        """Send a test email via Azure Communication Services."""
        
        try:
            # Get test email settings from environment
            to_email = os.getenv("TEST_EMAIL_OVERRIDE", "")
            reply_to_email = os.getenv("GRAPH_API_MONITORED_EMAIL", "Victoria_Grant@staples.com")
            
            if not to_email:
                print(f"❌ Missing email configuration: TEST_EMAIL_OVERRIDE={to_email}")
                return False
            
            # Create subject line using the scenario's subject_line or fallback
            original_subject = scenario.get('subject_line', f"AI-Powered Automation Solutions for {scenario['company']}")
            subject = f"Re: {original_subject}"
            
            # Create email headers for threading
            headers = self.create_email_headers(subject)
            
            # Convert plain text to proper HTML with preserved formatting
            html_content = self.convert_text_to_html(email_content)
            
            # Get ACS credentials
            acs_connection_string, acs_sender_email = self._get_acs_credentials()
            
            # Check if we're in simulation mode or credentials are unavailable
            if not acs_connection_string or not acs_sender_email or "mock" in str(acs_connection_string).lower():
                # Simulate email sending
                message_id = f"sim_{uuid.uuid4().hex[:8]}"
                print(f"🧪 [SIMULATION] Email would be sent:")
                print(f"   📧 To: {to_email}")
                print(f"   📝 Subject: {subject}")
                print(f"   🎯 Intent: {scenario['intent'].value}")
                print(f"   🆔 Simulated ID: {message_id}")
                return True
            else:
                # Send email using real ACS client
                result = await self.email_client.send_email(
                    recipient=to_email,
                    subject=subject,
                    html_content=html_content,
                    sender_email=acs_sender_email,
                    reply_to_email=reply_to_email,
                    headers=headers
                )
                
                if result["success"]:
                    print(f"✅ Sent: {scenario['name']} → {result.get('message_id', 'Unknown ID')}")
                    return True
                else:
                    print(f"❌ Failed to send {scenario['name']}: {result.get('error', 'Unknown error')}")
                    return False
                
        except Exception as e:
            print(f"❌ Error sending email for {scenario['name']}: {e}")
            return False

    async def generate_and_send_test_emails(self, num_emails: int = 20) -> Dict[str, Any]:
        """Generate and send test emails for various scenarios."""
        
        # With exactly 20 scenarios for 20 emails, we can use a simple 1:1 mapping
        scenarios_to_use = TEST_SCENARIOS[:num_emails]  # Take only the number we need
        
        # Get ACS credentials first
        acs_connection_string, acs_sender_email = self._get_acs_credentials()
        
        print(f"🚀 Starting test email generation and sending...")
        print(f"📧 Target: {os.getenv('TEST_EMAIL_OVERRIDE', 'NOT_SET')}")
        print(f"📬 From: {acs_sender_email or 'NOT_SET'}")
        print(f"↩️  Reply-To: {os.getenv('GRAPH_API_MONITORED_EMAIL', 'StaplesBusiness@Staples.com')}")
        print(f"📊 Generating {num_emails} emails using {len(scenarios_to_use)} unique scenarios\\n")
        
        # Initialize ACS email client (skip if in simulation mode or credentials unavailable)
        if acs_connection_string and acs_sender_email and "mock" not in str(acs_connection_string).lower():
            await self.email_client.initialize(acs_connection_string)
        else:
            print("🧪 Running in simulation mode - no real emails will be sent")
        
        results = {
            "total_generated": 0,
            "total_sent": 0,
            "scenarios_used": [],
            "send_failures": [],
            "emails_generated": []
        }
        
        try:
            for email_count, scenario in enumerate(scenarios_to_use, 1):
                        print(f"📝 Generating email {email_count}/{num_emails}: {scenario['name']}")
                        
                        try:
                            # Generate personalized outreach
                            print(f"   🎯 Generating outreach email...")
                            original_outreach = self.generate_outreach_email(scenario)
                            print(f"   ✅ Outreach generated ({len(original_outreach)} chars)")
                            
                            # Create customer response
                            print(f"   📝 Creating customer response...")
                            customer_response = scenario['response_template']
                            print(f"   ✅ Response created ({len(customer_response)} chars)")
                            
                            # Format as reply email
                            print(f"   📧 Formatting as reply email...")
                            final_email = self.format_email_as_reply(original_outreach, customer_response, scenario)
                            print(f"   ✅ Email formatted ({len(final_email)} chars)")
                            
                            results['total_generated'] += 1
                            results['emails_generated'].append({
                                "scenario": scenario['name'],
                                "intent": scenario['intent'].value,
                                "company": scenario['company'],
                                "contact": scenario['contact_name'],
                                "content_preview": customer_response[:100] + "..."
                            })
                            
                            # Send email
                            print(f"   📤 Sending email via ACS...")
                            sent_successfully = await self.send_test_email(scenario, final_email)
                            
                            if sent_successfully:
                                results['total_sent'] += 1
                                results['scenarios_used'].append(scenario['name'])
                                print(f"   ✅ Email sent successfully!")
                            else:
                                results['send_failures'].append(scenario['name'])
                                print(f"   ❌ Email send failed")
                            
                            # Small delay between sends
                            print(f"   ⏱️  Waiting 1 second before next email...")
                            await asyncio.sleep(1)
                            
                        except Exception as e:
                            print(f"❌ Error processing scenario {scenario['name']}: {e}")
                            import traceback
                            traceback.print_exc()
                            results['send_failures'].append(f"{scenario['name']}: {str(e)}")
        
        except Exception as e:
            print(f"❌ Error in email generation process: {e}")
            results['send_failures'].append(f"Process error: {str(e)}")
        
        # Print summary
        print(f"\\n✅ Test email generation complete!")
        print(f"📊 Generated: {results['total_generated']} emails")  
        print(f"📧 Sent: {results['total_sent']} emails")
        print(f"❌ Failed: {len(results['send_failures'])} emails")
        
        if results['send_failures']:
            print(f"\\n❌ Send failures:")
            for failure in results['send_failures']:
                print(f"   • {failure}")
        
        print(f"\\n🧪 Intent distribution:")
        intent_counts = {}
        for email_info in results['emails_generated']:
            intent = email_info['intent']
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        for intent, count in intent_counts.items():
            print(f"   • {intent.upper()}: {count} emails")
        
        return results

async def main():
    """Main test execution."""
    
    print("🧪 Email Generator for AI Agent Intent Testing")
    print("=" * 50)
    print("🚀 Will send 20 test emails covering all intent types")
    print()
    
    try:
        # Check required environment variables
        to_email = os.getenv("TEST_EMAIL_OVERRIDE", "")
        if not to_email:
            print("❌ Missing required environment variable: TEST_EMAIL_OVERRIDE")
            print("Please set: export TEST_EMAIL_OVERRIDE=your_email@example.com")
            return
        
        # Create generator (credentials will be retrieved from Key Vault/environment)
        print("📧 Creating email generator...")
        generator = EmailGenerator()
        print("✅ Email generator created successfully")
        
        # Test credential retrieval
        acs_connection_string, acs_sender_email = generator._get_acs_credentials()
        print(f"📧 ACS Connection: {'✅ Available' if acs_connection_string else '❌ Not configured'}")
        print(f"📬 ACS Sender: {acs_sender_email or '❌ Not configured'}")
        
        print("🚀 Starting comprehensive email generation...")
        results = await generator.generate_and_send_test_emails(20)
        
        print(f"\\n✅ EMAIL GENERATION COMPLETE!")
        print(f"📊 Total generated: {results['total_generated']}")
        print(f"📧 Total sent: {results['total_sent']}")
        print(f"❌ Total failures: {len(results['send_failures'])}")
        
        print(f"\\n🎯 Next Steps:")
        print(f"1. Check inbox {to_email} for test emails")
        print(f"2. Run: python main.py check")
        print(f"3. Monitor AI Agent processing and scenario classification")
        print(f"4. Test responses by replying to emails")
        
    except Exception as e:
        print(f"❌ Email generation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
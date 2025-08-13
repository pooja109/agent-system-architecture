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
        "response_template": "Thank you for reaching out! This sounds like exactly what we need. I'd love to schedule a call to discuss our renewable energy automation needs further. When would be a good time this week?"
    },
    {
        "name": "Positive Response - Budget Ready", 
        "intent": EmailIntent.POSITIVE,
        "company": "DataFlow Analytics",
        "contact_name": "Marcus Johnson",
        "industry": "data analytics",
        "response_template": "Hi there! I'm definitely interested in learning more about your automation solutions for data analytics. Can you send me some pricing information? Our budget for Q1 is around $50-75k."
    },
    {
        "name": "Positive Response - Urgent Need",
        "intent": EmailIntent.POSITIVE,
        "company": "FastTrack Logistics",
        "contact_name": "Rachel Kim",
        "industry": "logistics and shipping",
        "response_template": "This is perfect timing! We're in the middle of a major digital transformation and need automation solutions ASAP. Can we schedule a meeting this week? Our CEO is very interested."
    },
    {
        "name": "Positive Response - Expansion Plans",
        "intent": EmailIntent.POSITIVE,
        "company": "HealthTech Innovations",
        "contact_name": "Dr. Anthony Lee",
        "industry": "healthcare technology",
        "response_template": "Your automation platform could be exactly what we need for our expansion into telemedicine. I'd like to discuss how this could help us scale our patient data processing. Are you available for a call next Tuesday?"
    },
    {
        "name": "Positive Response - Team Interested",
        "intent": EmailIntent.POSITIVE,
        "company": "EduStream Technologies",
        "contact_name": "Linda Zhang",
        "industry": "educational technology",
        "response_template": "I shared your email with our development team and they're excited about the possibilities! We're looking to automate our student assessment workflows. Can you provide some case studies in the education sector?"
    },
    {
        "name": "Positive Response - ROI Focused",
        "intent": EmailIntent.POSITIVE,
        "company": "FinanceFlow Corp",
        "contact_name": "Robert Chen",
        "industry": "financial services",
        "response_template": "The ROI potential you mentioned is compelling. We're always looking for ways to streamline our compliance reporting. I'd like to set up a demo to see how your solution handles financial data automation."
    },

    # SERVICE_INQUIRY responses (5 scenarios)
    {
        "name": "Service Inquiry - Technical Questions",
        "intent": EmailIntent.SERVICE_INQUIRY,
        "company": "CloudFirst Corp", 
        "contact_name": "Jennifer Davis",
        "industry": "cloud computing",
        "response_template": "I received your email about automation solutions. I have a few technical questions: 1) Do you support AWS Lambda integration? 2) What's your typical implementation timeline? 3) Do you provide 24/7 support?"
    },
    {
        "name": "Service Inquiry - Demo Request",
        "intent": EmailIntent.SERVICE_INQUIRY,
        "company": "RetailMax Inc",
        "contact_name": "David Chen", 
        "industry": "retail automation",
        "response_template": "Hello! Your automation platform looks promising for our retail operations. Could we schedule a demo next week? I'd like to see how it handles inventory management workflows."
    },
    {
        "name": "Service Inquiry - Integration Questions",
        "intent": EmailIntent.SERVICE_INQUIRY,
        "company": "ManufacturingPro Solutions",
        "contact_name": "Tom Rodriguez",
        "industry": "manufacturing",
        "response_template": "Thanks for your outreach. Before we proceed, I need to understand: Does your platform integrate with SAP? What about custom API endpoints? We have a complex manufacturing setup that requires specific integrations."
    },
    {
        "name": "Service Inquiry - Pricing Information",
        "intent": EmailIntent.SERVICE_INQUIRY,
        "company": "StartupAccelerator Hub",
        "contact_name": "Jessica Park",
        "industry": "startup consulting",
        "response_template": "Hi! Your automation solution sounds interesting for our portfolio companies. Could you provide detailed pricing tiers? We work with startups of various sizes and need scalable options."
    },
    {
        "name": "Service Inquiry - Security Concerns",
        "intent": EmailIntent.SERVICE_INQUIRY,
        "company": "SecureBank Financial",
        "contact_name": "William Martinez",
        "industry": "banking",
        "response_template": "Your automation platform caught our attention, but we have strict security requirements. Can you provide information about SOC 2 compliance, data encryption, and audit capabilities? We need to ensure full regulatory compliance."
    },

    # NEGATIVE responses (4 scenarios)
    {
        "name": "Negative Response - Not Interested",
        "intent": EmailIntent.NEGATIVE,
        "company": "TechStart Ventures",
        "contact_name": "Emily Rodriguez",
        "industry": "startup consulting",
        "response_template": "Thanks for reaching out, but we're not interested in automation solutions at this time. We're focusing on other priorities this quarter. Please remove me from your mailing list."
    },
    {
        "name": "Negative Response - Already Have Solution",
        "intent": EmailIntent.NEGATIVE, 
        "company": "Enterprise Solutions Ltd",
        "contact_name": "Michael Thompson",
        "industry": "enterprise software",
        "response_template": "Hello, we already have a comprehensive automation platform in place with Microsoft Power Automate. We're not looking to switch vendors at this time."
    },
    {
        "name": "Negative Response - Budget Constraints",
        "intent": EmailIntent.NEGATIVE,
        "company": "SmallBiz Operations",
        "contact_name": "Carol Johnson",
        "industry": "small business services",
        "response_template": "Thank you for the information, but automation solutions are outside our current budget. We're a small operation and need to focus on basic operational needs first."
    },
    {
        "name": "Negative Response - Wrong Timing",
        "intent": EmailIntent.NEGATIVE,
        "company": "GrowthStage Startup",
        "contact_name": "Alex Rivera",
        "industry": "technology startup",
        "response_template": "Appreciate you reaching out. While your solution looks good, we're in the middle of a major product pivot and can't take on new vendor relationships right now. Maybe check back in 6 months."
    },

    # OUT_OF_OFFICE responses (3 scenarios)
    {
        "name": "Out of Office - Vacation",
        "intent": EmailIntent.OUT_OF_OFFICE,
        "company": "Global Manufacturing Co",
        "contact_name": "Lisa Wang", 
        "industry": "manufacturing",
        "response_template": "Thank you for your email. I am currently out of the office until January 15th with limited email access. For urgent matters, please contact my assistant at assistant@globalmanufacturing.com. I will respond to your message when I return."
    },
    {
        "name": "Out of Office - Conference",
        "intent": EmailIntent.OUT_OF_OFFICE,
        "company": "InnovateTech Labs",
        "contact_name": "Robert Kim",
        "industry": "research and development",
        "response_template": "I'm currently attending the AI Innovation Conference through December 20th. I'll have limited email access but will respond to all messages upon my return. For immediate assistance, please contact our main office."
    },
    {
        "name": "Out of Office - Medical Leave",
        "intent": EmailIntent.OUT_OF_OFFICE,
        "company": "ConsultingPro Services",
        "contact_name": "Maria Santos",
        "industry": "business consulting",
        "response_template": "Thank you for your email. I am currently on medical leave and will return to the office on February 1st. For immediate assistance with automation solutions, please contact my colleague John Smith at jsmith@consultingpro.com."
    },

    # NO_LONGER_WORKS responses (3 scenarios)
    {
        "name": "No Longer Works - Left Company", 
        "intent": EmailIntent.NO_LONGER_WORKS,
        "company": "StartupHub Inc",
        "contact_name": "Amanda Foster",
        "industry": "business incubation",
        "response_template": "Thank you for your email. Amanda Foster is no longer with StartupHub Inc. For inquiries regarding automation solutions, please contact our new Operations Director at operations@startuphub.com."
    },
    {
        "name": "No Longer Works - Promotion",
        "intent": EmailIntent.NO_LONGER_WORKS,
        "company": "Growth Dynamics Corp",
        "contact_name": "James Wilson", 
        "industry": "business consulting",
        "response_template": "Hi there! I've recently been promoted to VP of Strategy and no longer handle vendor evaluations. Please redirect your automation solution inquiry to our new Operations Manager, Sandra Lee at slee@growthdynamics.com."
    },
    {
        "name": "No Longer Works - Department Change",
        "intent": EmailIntent.NO_LONGER_WORKS,
        "company": "TechCorp Industries",
        "contact_name": "Steven Adams",
        "industry": "technology consulting",
        "response_template": "Thanks for reaching out. I've moved to a different department and no longer handle technology procurement. Please contact our IT Director, Michelle Brown at mbrown@techcorp.com for automation solution inquiries."
    },

    # EMAIL_INVALID responses (2 scenarios) 
    {
        "name": "Email Invalid - Bounce",
        "intent": EmailIntent.EMAIL_INVALID,
        "company": "TechCorp Solutions",
        "contact_name": "Invalid Email",
        "industry": "technology",
        "response_template": "MAILER-DAEMON: The email address you're trying to reach no longer exists. This mailbox has been decommissioned. Please verify the recipient's email address and try again."
    },
    {
        "name": "Email Invalid - Domain Error",
        "intent": EmailIntent.EMAIL_INVALID,
        "company": "OldCompany Corp",
        "contact_name": "Former Employee",
        "industry": "defunct business",
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
        """Generate a personalized outreach email using templates."""
        
        # Simple template-based generation (avoids complex AI dependencies)
        return f"""Hi {scenario['contact_name']},

I hope you're doing well. I came across {scenario['company']} and was impressed by your work in {scenario['industry']}.

At Staples Business Solutions, we help companies automate time-consuming manual processes so teams can focus on strategic work. 

Our AI-powered automation platform helps businesses:
• Streamline workflows across multiple systems
• Reduce manual data entry and processing
• Automate routine tasks and notifications
• Improve accuracy and compliance

I'd love to explore how automation could benefit {scenario['company']}. Would you be open to a brief 15-minute conversation next week?

Best regards,
Alex Thompson
Senior Solutions Consultant
Staples Business Solutions
athompson@staples.com | (555) 123-4567"""

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

        return f"""{customer_response}{signature}

-----Original Message-----
From: Alex Thompson <athompson@staples.com>
Sent: {original_date}
To: {scenario['contact_name']} <{scenario['contact_name'].lower().replace(' ', '.')}@{scenario['company'].lower().replace(' ', '').replace(',', '').replace('.', '')}.com>
Subject: AI-Powered Automation Solutions for {scenario['company']}

{quoted_original}"""

    async def send_test_email(self, scenario: Dict[str, Any], email_content: str) -> bool:
        """Send a test email via Azure Communication Services."""
        
        try:
            # Get test email settings from environment
            to_email = os.getenv("TEST_EMAIL_OVERRIDE", "")
            reply_to_email = os.getenv("GRAPH_API_MONITORED_EMAIL", "StaplesBusiness@Staples.com")
            
            if not to_email:
                print(f"❌ Missing email configuration: TEST_EMAIL_OVERRIDE={to_email}")
                return False
            
            # Create subject line
            subject = f"Re: AI-Powered Automation Solutions for {scenario['company']}"
            
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
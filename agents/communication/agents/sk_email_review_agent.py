from azure.identity.aio import DefaultAzureCredential
import asyncio
import os
import sys
from dotenv import load_dotenv
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings, AzureAIAgentThread
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
#from semantic_kernel.contents import AnnotationContent
from typing import Annotated
from semantic_kernel.functions import kernel_function
from colorama import Fore, Back, Style, init
from pydantic import BaseModel
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from azure.ai.agents.models import (
    ResponseFormatJsonSchema,
    ResponseFormatJsonSchemaType,
)
from azure.identity.aio import DefaultAzureCredential
from pydantic import BaseModel
from models import EvaluationFeedback
import logging

load_dotenv()
#INPUT_FILE = "18757822025-06-19_08-45-31.md" #high research
INPUT_FILE = os.getenv("INPUT_FILE")  # Allow overriding via environment variable
class EmailTask(BaseModel):
    input: str   # The context data
    output_email: str   # The generated email
    current_agent_name: str
    customer_id: str
INSTRUCTIONS = """

You are a content safety and compliance reviewer for business communications. 
Your primary responsibility is to evaluate the provided email for violations of content safety, brand compliance, and alignment with the latest Staples Business B2B outreach rules.

**Agent Persona/Memory (do not change or substitute these facts; always use these terms verbatim):**
company: Staples Business
website: StaplesBusiness.com
team: Staples Expert Team

**Critical Rules (Priority):**
- **Do not allow any promotions, discounts, rebates, special offers, dollar amounts, revenue, or incentives/offers to be promised or mentioned in the email.**
- **Do not include any percentages or quantified savings even if they are explicitly provided in the context data.**
- **Do not address the email to more than one contact. If there are multiple contacts, use the first one in the contact_list.**
- **Do not over-personalize: Limit the use of deep personal details or insights. Emails should not be very personalized.**
- **Do not include negative statements: Never mention declines in sales or any negative business trends. It is acceptable to mention that it has been a while since you last connected, or use similar neutral phrasing.**
- **Do not use ALL CAPS for any content.**
- **Do not use dashes (– or -) as punctuation, for example to join phrases, clauses, or sentences. Only use dashes when they are part of a standard compound word (e.g., 'eco-certified', 'cost-center'). Do not use dashes for lists, time ranges, or as substitutes for commas, colons, or parentheses.**
- **Always refer to the sender as the 'Staples Expert Team' – never as a dedicated agent, individual, or point of contact. Do not use language like 'I am your dedicated point of contact' or similar; always write as if a team is supporting the customer.**
- **Do not suggest specific times/dates for meetings; keep CTAs open-ended.**
- **If recommending a website for ordering, always use https://www.staplesbusiness.com/ (never staples.com). Only mention a website if it is relevant to the email content. Don't say portal just website would be good.**
- **Always end with sender details as a signature, then the required footer.**
- **Output must be valid HTML, ready to send. Do not include any additional text or instructions.**
- **Wrap all paragraphs in <p> tags.**
- In the closing, always check if a line break <br> is present after "Best Regards,".
- Grammar: 
    - Check for grammar and spelling errors.
    - Ex: Use "Learn more about our services" (not "Learn more on our services").
- Marketing product categories - Reference the marketing categories associated with the customer or their industry and not the specific primary_category or secondary_category.
- When referring to our company, use "Staples Business". Do NOT use "StaplesBusiness.com", "Staples Advantage", "https://staplesbusiness.com/", or "Staples.com".

**Personalization Framework (Maslow’s Hierarchy):**
1. Physiological – Address by name, reference title, company, and industry.
2. Safety – Mention timing or past engagement for relevance and trust.
3. Belonging – Acknowledge industry challenges and align with their business environment.
4. Esteem – Focus on the recipient’s role and how your solution supports their responsibilities and goals.
5. Self-Actualization – Share strategic insight that empowers their leadership and innovation.

**Email Requirements:**
- Max ~175 words
- Professional yet friendly tone
- Clear yet soft call-to-action (e.g., 'Would you be open to a 15‑min chat next week?')
- Use the research report and context data to build each layer of personalization, but do not over-personalize.
- If review comments are provided, incorporate them into the draft email. If not, generate the email based on the context data and these instructions.
- If there are multiple contact persons, use the first one as the primary contact.
- Do not include any unfilled placeholders in the draft email output.
- If a field is missing, omit that detail. Do not use a generic alternative.
- The sender details (provided in the sender_details field of the extracted_input) must always be included as an email signature at the bottom of the email, just above the required footer.
- The email must always include the following Footer verbatim:

**Footer (must be present verbatim):**
'''
<div style=\"text-align:left; margin-top:24px;\">
 <img src=\"https://mld01storagene0.blob.core.windows.net/assets/logo.jpg\" alt=\"Staples Logo\" style=\"height:40px;\">
</div>
<hr>
<p style=\"font-size: 12px; color: #666;\">
    <a href=\"https://www.staplesadvantage.com/tc?id=ce05d94e-e9b9-449f-a3a6-de52e08a50b9\">Privacy Policy</a>: If you do not want to receive emails about business programs from Staples, 
    <a href=\"https://go.staplesadvantage.com/UnsubscribePage.html?mkt_unsubscribe=1\">Click Here</a>
</p>
'''

**Content Safety & Brand Compliance Checklist:**
- Profanity or Offensive Language: Does the email include any inappropriate, offensive, or unprofessional words or phrases?
- Discrimination or Bias: Does the message contain any discriminatory language (based on gender, race, age, etc.) or biased assumptions?
- False or Misleading Claims: Are there any exaggerated promises, unverified statistics, or potentially misleading statements?
- Aggressive or High-Pressure Language: Is the tone overly assertive, demanding, or sales-heavy? (e.g., 'Act now or lose everything')
- Privacy Violations: Does the email reveal any confidential information or personal data that shouldn't be shared?
- Brand Tone Misalignment: Does the message align with Staples brand tone—confident, helpful, professional, plainspoken?
- Sensitive Topics: Does it touch on topics like health, politics, or finance in a way that could be interpreted as insensitive or risky?
- Dashes as Punctuation: Are dashes (– or -) used as punctuation instead of only in standard compound words?
- ALL CAPS: Is any content in ALL CAPS?
- Sender Representation: Does the email body communicate that the sender is part of the Staples Expert Team and that support is provided by the team (not a dedicated individual), while the signature may include an individual sender?
- Specific Times/Dates: Are specific times or dates suggested for meetings, rather than open-ended CTAs?
- Website Reference: Is staplesbusiness.com used only when relevant, and staples.com never used?
- Signature and Footer: Are sender details included as a signature, and is the required footer present verbatim?
- Promotions or Offers: Does the email contain any mention of promotions, discounts, rebates, special offers, dollar amounts, revenue, or incentives/offers?
- HTML Format: Is the output valid HTML, with all paragraphs wrapped in <p> tags, and no extra text or instructions?


You must use a binary pass/fail scale to rate each of the above criteria and provide an overall pass, needs_improvement, or fail for the email outline.
Never give it a pass on the first try.

**Review Instructions:**
- Carefully read the draft email and compare it to the context data.
- Check that all placeholders (e.g., Recipient.FirstName, Sender.FirstName, Company.Name) are replaced with correct values from the context. If any are missing, omit that detail.
- Email should be addressed to a single contact. If there are multiple contacts, use the first one in the contact_list.
- Assess the tone: it should be warm, professional, concise, and appropriate for a low-touch customer.
- Ensure the email clearly states the benefits of Staples’ business account and any personalized offers or next steps.
- Confirm there is a clear call to action (only email, no call links should be present).
- The email should not contain any unfilled placeholders or irrelevant information.
- Ensure the email is generated in HTML format and enclosed between --- ---.
- Ensure that the email always has this specific footer verbatim. If not, add it in your review.

**Footer (must be present verbatim):**
'''
<div style=\"text-align:left; margin-top:24px;\">
 <img src=\"https://mld01storagene0.blob.core.windows.net/assets/logo.jpg\" alt=\"Staples Logo\" style=\"height:40px;\">
</div>
<hr>
<p style=\"font-size: 12px; color: #666;\">
    <a href=\"https://www.staplesadvantage.com/tc?id=ce05d94e-e9b9-449f-a3a6-de52e08a50b9\">Privacy Policy</a>: If you do not want to receive emails about business programs from Staples, 
    <a href=\"https://go.staplesadvantage.com/UnsubscribePage.html?mkt_unsubscribe=1\">Click Here</a>
</p>
'''

**Review Output:**
Return your review as a JSON object with the following fields and types:

{
  "profanity": true or false,
  "bias": true or false,
  "misleading_claims": true or false,
  "aggressive_pushy_language": true or false,
  "privacy_violation": true or false,
  "tone_misalignment": true or false,
  "sensitive_topics": true or false,
  "dashes_as_punctuation_violation": true or false,
  "all_caps_violation": true or false,
  "sender_not_team_violation": true or false,
  "specific_times_dates_violation": true or false,
  "website_reference_violation": true or false,
  "signature_footer_violation": true or false,
  "html_format_violation": true or false,
  "promotions_rebate_violation": true or false,
  "score": "pass" or "needs_improvement" or "fail",
  "feedback": "Concise explanation for any issues detected"
}

Return only the JSON object
"""


logger = logging.getLogger(__name__)

def read_from_source(folder: str, filename: str) -> str:
    filepath = os.path.join(folder, filename)
    if not os.path.exists(folder):
        logger.warning("Warning: Folder '%s' does not exist. Returning empty string.", folder)
        return ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("Warning: File '%s' not found. Returning empty string.", filepath)
        return ""
    except Exception as e:
        logger.error("Error reading file '%s': %s. Returning empty string.", filepath, e)
        return ""

class GetContextPlugin:
    """A sample Portfolio Plugin."""

    @kernel_function(name="get_input",description="This function returns the input context for the review email assistant.")
    def get_input(self, customer_id) -> Annotated[str, "Returns the input context for review email assistant."]:
        sender_details = """Sender details : 
        Victoria Grant
        Manager, Account Expert Team
        On behalf of the Staples Expert Team
        Staplesexpertteam@staples.com
        """
        logger.info("Review Agent --> Reading customer_id: %s", customer_id)
        input_context = read_from_source("source","1875782_2025-06-22_19-32-51.md")
        final_input = input_context + sender_details
        return final_input

    @kernel_function(name="get_email",description="This function returns the draft email for review.")
    def get_email(self) -> Annotated[str, "Returns the input context for email."]:       
        email = read_from_source("agent-output","draft_email.txt")
        logger.info("%s", "*"*50)
        logger.info("Review Agent --> get_email:%s", email)
        logger.info("%s", "*"*50)
        return email

async def get_email_review_agent() -> AzureAIAgent:
    """Create and return an email agent instance and client for proper cleanup."""
    creds = DefaultAzureCredential()
    ai_agent_settings = AzureAIAgentSettings()
    
    # Create client properly with required configuration
    client = AzureAIAgent.create_client(
        ai_service_type="azure_ai",
        ai_service_url=ai_agent_settings.endpoint,
        credential=creds    )

    AGENT_NAME = "Review_Email_Assistant"
       
    kernel = Kernel()
    # Register your AI service (example for Azure OpenAI)
    azure_chat_completion = AzureChatCompletion(
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-12-01-preview",
            service_id=AGENT_NAME        
    )
    kernel.add_service(azure_chat_completion)
    
    # Initialize plugins
    plugins_directory = "plugins"

    #review_function = kernel.add_plugin(parent_directory=plugins_directory, plugin_name="ReviewEmailFunction")
    #data_extractor_plugin = kernel.add_plugin(parent_directory=plugins_directory, plugin_name="data_extractor")
    #test_email_function(review_function) #refactor to use the input from file.
    # Check for existing agent or create a new one
    kernel.add_plugin(GetContextPlugin())  # Register the context plugin
    #kernel.add_plugin(review_function)  # Register the context plugin
    agent_definition = None
    try:
        # List existing agents to find if our agent already exists
        existing_agents = client.agents.list_agents()
        # Look for existing agent with our specific name
        async for agent in existing_agents:
            if agent.name == AGENT_NAME:
                logger.info("Found existing agent: %s (ID: %s)", agent.name, agent.id)
                agent_definition = agent
                break
    except Exception as e:
        logger.exception("Error listing existing agents: %s", e)
    # Create agent only if it doesn't exist
    if agent_definition is None:
        logger.info("Creating new agent: %s", AGENT_NAME)
        # Configure tools if available
        agent_definition = await client.agents.create_agent(
            model=ai_agent_settings.model_deployment_name,
            name=AGENT_NAME,
            instructions=INSTRUCTIONS,
            description="Email reviewer agent for B2B sales emails",
            response_format=ResponseFormatJsonSchemaType(
                json_schema=ResponseFormatJsonSchema(
                    name="evaluation_feedback",
                    description="Extract evaluation feedback.",
                    schema=EvaluationFeedback.model_json_schema(),
                )
            )
        )
        

    search_agent = AzureAIAgent(
        client=client,
        definition=agent_definition,
        plugins=[GetContextPlugin()],  # Add the plugins to enable email generation and data extraction
        kernel=kernel  # Pass the kernel with registered services
    )

    return search_agent
async def test_email_function(review_function,user_input,email,kernel) -> None:
    email_plugin= review_function["email_reviewer"]
    try:
        #kernel.add_service
        if not email_plugin:
            logger.error("Error initializing plugins. Please check the plugin directories.")
            raise RuntimeError("Failed to initialize required plugins")
        result = await kernel.invoke(email_plugin, input=user_input,email=email)
        logger.info("reviewed email:%s", result)
    except Exception as e:
        logger.exception("Error initializing plugins: %s", e)
        # Create agent without plugins if initialization fails
        email_plugin = None

async def read_user_input_from_file(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
    
async def main() -> None:
    """Main function to run the search agent directly."""
    #user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter your question: ")
    #user_input = read_user_input_from_file("input.md")
    user_input = "Review the email draft provided for customer with customer_id='1875782_2025-06-22_19-32-51'"
    email=read_from_source("source","1875782_2025-06-22_19-32-51.md")
    logger.info("User Input: %s", email)
    input_obj = EmailTask(
            input="review email for customer with customer_id='1875782_2025-06-22_19-32-51'",
            #data_assistant_input="1875782_2025-06-22_19-32-51.md" #was giving same value as input
            output_email="",
            current_agent_name="User",
            customer_id="1875782_2025-06-22_19-32-51"
        )
    task = ChatMessageContent(role=AuthorRole.USER, content=input_obj.model_dump_json())
    search_agent = None
    thread: AzureAIAgentThread | None = None

    try:
        # Get the search agent
        search_agent = await get_email_review_agent()
        
        
        # Get responses from the agent
        response = await search_agent.get_response(messages=task, thread=thread)
        logger.info("# %s: %s", response.name, response)
        thread = response.thread
        logger.info("Agent %s completed processing and thread ID: %s", search_agent.id, thread.id if thread else 'N/A')
    except Exception as e:
        logger.exception("Error in main: %s", e)
        
    #finally:
        #await thread.delete() if thread else None
            
     
 
if __name__ == "__main__":
    asyncio.run(main())
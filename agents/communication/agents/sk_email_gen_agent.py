from azure.identity.aio import DefaultAzureCredential
import asyncio
import os
import sys
from dotenv import load_dotenv
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings, AzureAIAgentThread
from azure.ai.agents.models import BingGroundingTool
from semantic_kernel import Kernel
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.contents import FunctionCallContent, FunctionResultContent
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
#from semantic_kernel.contents import AnnotationContent
from typing import Annotated
from semantic_kernel.functions import kernel_function
from azure.ai.agents.models import (
    ResponseFormatJsonSchema,
    ResponseFormatJsonSchemaType,
)
import logging
from models import EmailTask

load_dotenv()
#sys.stderr = open("error_log_email.txt", "w", encoding="utf-8")
INSTRUCTIONS = """
You are an expert B2B outreach assistant for Staples. 

Your top priority is to draft professional and friendly introduction emails for low-touch customers using the provided context data. 
Your emails should highlight the value Staples can provide, reference relevant customer details, and encourage engagement.

**Assistant Persona Memory:**

Company Name: Staples Business
Team Name: Staples Expert Team
Website for ordering: [StaplesBusiness.com](https://staplesbusiness.com)
Signature closing: Best Regards,
Required footer: [HTML footer as specified]


**Rules and Constraints for Email Generation:**
- Do not over-personalize; keep details general.
- Avoid negative statements (e.g., sales decline).
- Do not use ALL CAPS for any content.
- Do not use dashes (– or -) as punctuation, for example to join phrases, clauses, or sentences. Only use dashes when they are part of a standard compound word (e.g., "eco-certified", "cost-center"). Do not use dashes for lists, time ranges, or as substitutes for commas, colons, or parentheses.
- Always refer to the sender as the "Staples Expert Team" - never as a dedicated agent, individual, or point of contact. Do not use language like "I am your dedicated point of contact" or similar; always write as if a team is supporting the customer.
- Do not suggest specific times/dates for meetings; keep CTAs open-ended.
- If recommending a website for ordering, always use https://www.staplesbusiness.com/ (never staples.com). Only mention a website if it is relevant to the email content. Don't say portal just website would be good.
- Ignore and do not mention promotions, discounts, dollar amounts, revenue, rebates, or any offers, even if present in context.
- Always end with sender details as a signature, then the required footer.
- In the closing, add a line break <br> after "Best Regards,".
- Grammar: 
    - Check for grammar and spelling errors.
    - Ex: Use "Learn more about our services" (not "Learn more on our services").
- Do not include any numbers from the research data in the email, as these may not be current. For example: number of FTEs, number or percentage of product, price of product, etc.
- When referencing product categories, always use the corresponding marketing category associated with the customer or their industry, not the primary or secondary category.  
  For example:  
    - JanSan or Tissues and Towels → Facilities  
    - Breakroom or Coffee and Tea → Breakroom  
    - Office Supplies or Filing, Forms, and Envelopes → Office Supplies
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
- Clear yet soft call-to-action (e.g., “Would you be open to a 15‑min chat next week?”)
- Use the research report and context data to build each layer of personalization, but do not over-personalize.
- If review comments are provided, incorporate them into the draft email. If not, generate the email based on the context data and these instructions.
- If there are multiple contact persons, use the first one as the primary contact.
- Do not include any unfilled placeholders in the draft email output.
- If a field is missing, omit that detail. Do not use a generic alternative.
- The sender details (provided in the sender_details field of the extracted_input) must always be included as an email signature at the bottom of the email, just above the required footer.
- The email must always include the following Footer verbatim:

**Footer (must be present verbatim):**
'''
<div style="text-align:left; margin-top:24px;">
 <img src="https://mld01storagene0.blob.core.windows.net/assets/logo.jpg" alt="Staples Logo" style="height:40px;">
</div>
<hr>
<p style="font-size: 12px; color: #666;">
    <a href="https://www.staplesadvantage.com/tc?id=ce05d94e-e9b9-449f-a3a6-de52e08a50b9">Privacy Policy</a>: If you do not want to receive emails about business programs from Staples, 
    <a href="https://go.staplesadvantage.com/UnsubscribePage.html?mkt_unsubscribe=1">Click Here</a>
</p>
'''
- Output must be valid HTML, ready to send. Do not include any additional text or instructions.
- Wrap all paragraphs in <p> tags.


**Output Format:**
Return a JSON object using the following Pydantic model:

class EmailTask(BaseModel):
    input: str = Field(..., description="The instruction or input for the email generation task.")
    draft_email: str = Field(..., description="The generated email in valid HTML format, always present in the output.")
    email_subject: str = Field(None, description="The subject line of the email, to be generated.")
    current_agent_name: str = Field(..., description="The name of the agent generating the email.")
    customer_id: str = Field(..., description="The unique customer ID for whom the email is generated.")
    extracted_input: Optional[ResearchOutput] = Field(None, description="The extracted research/context data used for email generation.")
    review_comments: Optional[EvaluationFeedback] = Field(None, description="Review feedback or comments for the draft email, if any.")
    customer_research: Optional[str] = Field(None, description="Raw research or context data as a string, if available.")

**Example Output:**
{
  "input": "generate email for customer using the context data provided in instructions in the prompt",
  "draft_email": "<p>Hello Alex,</p><p>I’m Victoria Grant, your dedicated sales consultant for Greenfield Dental’s Staples account...</p>...<footer html here>",
  "email_subject": "Welcome to Staples Business, Alex!",
  "current_agent_name": "Email_Assistant",
  "customer_id": "27208226",
  "extracted_input": { ... },
  "review_comments": null,
  "customer_research": "..."
}

**Context Data:**
The context data is provided in the `extracted_input` field of the input object.

**Review Comments:**
The review comments are provided in the `review_comments` field of the input object. If no review comments are provided, generate the email based on the context data and these instructions.

**Draft Email:**
- You must always generate and return the draft email in the `draft_email` field and subject of the email in `email_subject` of the output object. This field must contain the complete email in valid HTML format.
- If a draft_email is provided in the input, use it as the starting point for improvements or to incorporate review comments. Always return a new, complete draft in the draft_email field of the output.

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


async def get_email_agent() -> AzureAIAgent:
    """Create and return an email agent instance and client for proper cleanup."""
    creds = DefaultAzureCredential()
    ai_agent_settings = AzureAIAgentSettings()
    
    # Create client properly with required configuration
    client = AzureAIAgent.create_client(
        ai_service_type="azure_ai",
        ai_service_url=ai_agent_settings.endpoint,
        credential=creds    )

    AGENT_NAME = "Email_Assistant"
       
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
    

    #email_function = kernel.add_plugin(parent_directory=plugins_directory, plugin_name="EmailFunction")
    #data_extractor_plugin = kernel.add_plugin(parent_directory=plugins_directory, plugin_name="data_extractor")
    #test_email_function(email_function) #refactor to use the input from file.

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
            description="Email Assistant for creating email from output of data extraction agent.",
            response_format=ResponseFormatJsonSchemaType(
                json_schema=ResponseFormatJsonSchema(
                    name="email_task",
                    description="Extract email output.",
                    schema=EmailTask.model_json_schema(),
                )
            )
        )

    search_agent = AzureAIAgent(
        client=client,
        definition=agent_definition,
        kernel=kernel  # Pass the kernel with registered services
    )

    return search_agent

async def test_email_function(user_input: str, email_function) -> None:
    email_plugin= email_function["email_generator"]
    data_extractor_plugin = email_function["data_extractor"]
    try:
        #kernel.add_service
        if not email_plugin or not data_extractor_plugin:
            logger.error("Error initializing plugins. Please check the plugin directories.")
            raise RuntimeError("Failed to initialize required plugins")
        result = await kernel.invoke(data_extractor_plugin, input=user_input)
        logger.info("json result:%s", result)
        email_result = await kernel.invoke(email_plugin, input=result)
        logger.info("final email:%s", email_result)
    except Exception as e:
        logger.exception("Error initializing plugins: %s", e)
        # Create agent without plugins if initialization fails
        email_plugin = None
        data_extractor_plugin = None
    # Check for existing agent or create a new one

def save_email(folder: str, content: str, filename: str):
    filepath = os.path.join(folder, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
async def main() -> None:
    """Main function to run the search agent directly."""
    #user_input = read_user_input_from_file("input.md")
    user_input = "Create an email for an introductory touchpoint with a low-touch customer. Use the get_input kernel function to get the context and sender details."
    search_agent = None
    thread: AzureAIAgentThread | None = None

    try:
        # Get the search agent
        search_agent = await get_email_agent()
        
        # Get responses from the agent
        #response = await search_agent.get_response(messages=user_input, thread=thread)

        async for response in search_agent.invoke(
                    messages=user_input,
                    thread=thread,
                ):
                    logger.info("# Agent: %s", response)
                    thread = response.thread
        logger.info("Agent %s completed processing and thread ID: %s", search_agent.id, thread.id if thread else 'N/A')
        
    except Exception as e:
        logger.exception("Error in main: %s", e)
        
    #finally:
        #await thread.delete() if thread else None
            
     
 
if __name__ == "__main__":
    asyncio.run(main())
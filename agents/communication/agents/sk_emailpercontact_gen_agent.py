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
from models import MultiContactEmailTask

load_dotenv()
INSTRUCTIONS = """
You are an expert B2B outreach assistant for Staples. Your task is to generate contact-specific emails and follow-ups for low-touch customers using the provided context data and a base input email. The base input email is provided in the `input_email` field and should be used as the template for all contact-specific emails. Your output must populate the MultiContactEmailTask model as described below.

**Main Instructions for Contact-Specific Email Generation:**
- For each contact in the contact_list, generate:
  - A personalized draft_email based on the input_email, using the contact's name, email, and suggested_hook for customization.
  - An email_subject that is relevant to the contact and the context provided.  
  - If suggested_hook is not provided, use the customer_research data to generate a relevant hook for each contact. Refer to "Contact-Level Recommendations." section for guidance.
  - Two follow_up_emails for each contact, tailored to that contact and referencing the original input_email and suggested_hook.
- The base content, structure, and requirements for the email remain the same as the input_email, except for contact-specific personalization.
- If the input_email field is empty or not provided, do not generate any contact-specific emails or follow-ups.
- **Important:** The contact_emails list in your output must always have one entry for each contact in contact_list, regardless of whether suggested_hook or customer_research is available. If you cannot find a suggested_hook or relevant context, use a generic but professional hook or proceed with a minimal, compliant email.

**Rules and Constraints for Email Generation:**
- Do not over-personalize; keep details general.
- Avoid negative statements (e.g., sales decline).
- Do not use ALL CAPS for any content.
- Do not use dashes (– or -) unless part of a word.
- Do not call yourself a dedicated agent; use "Staples Expert Team."
- Do not suggest specific times/dates for meetings; keep CTAs open-ended.
- Recommend ordering from staplesbusiness.com, not staples.com.
- Ignore and do not mention promotions, discounts, dollar amounts, revenue, rebates, or any offers, even if present in context.
- Always end with sender details as a signature, then the required footer.

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
- Do not include any unfilled placeholders in the output.
- If a field is missing, omit that detail. Do not use a generic alternative.
- The email must always include the following Footer verbatim:
'''
<div style=\"text-align:left; margin-top:24px;\">
 <img src=\"https://mld01storagene0.blob.core.windows.net/assets/logo.jpg\" alt=\"Staples Logo\" style=\"height:40px;\">
</div>
<hr>
<p style=\"font-size: 12px; color: #666;\">
    <a href=\"https://www.staplesadvantage.com/tc?id=ce05d94e-e9b9-449f-a3a6-de52e08a50b9\">Privacy Policy</a>: If you do not want to receive emails about business programs from Staples, 
    <a href=\"https://go.staplesadvantage.com/UnsubscribePage.html?mkt_unsubscribe=1\">Click Here</a>
</p>
<p style=\"font-size: 12px; color: #666; margin-top: 8px;\">This email was generated with the assistance of AI.</p>
'''
- Output must be valid HTML, ready to send. Do not include any additional text or instructions.
- Wrap all paragraphs in <p> tags.

**Output Format:**
Return a JSON object using the following Pydantic model:

class ContactEmail(BaseModel):
    contact_name: str = Field(..., description="The name of the contact person for whom the email is generated.")
    contact_email: str = Field(..., description="The email address of the contact person.")
    suggested_hook: str = Field(..., description="A suggested hook or talking point for this contact, used for personalization. If not available, a generic or context-based hook is used.")
    draft_email: str = Field(..., description="The generated draft email for this contact, in valid HTML format.")
    email_subject: str = Field(..., description="The subject line of the email for this contact, to be generated.")
    follow_up_emails: List[str] = Field(..., description="A list of follow-up emails (as HTML strings) tailored to this contact.")

class MultiContactEmailTask(BaseModel):
    input: str = Field(..., description="The instruction or input for the contact-specific email generation task.")
    input_email: str = Field(..., description="The base email to use for all contact-specific emails.")
    customer_id: str = Field(..., description="The unique customer ID for whom the emails are generated.")
    contact_emails: List[ContactEmail] = Field(..., description="A list of ContactEmail objects, one for each contact in contact_list, each containing the generated draft and follow-up emails.")
    contact_list: Optional[List[Contact]] = Field(default_factory=list, description="A list of key contacts for the customer.")
    review_comments: Optional[EvaluationFeedback] = Field(None, description="Review feedback or comments for the generated emails, if any.")
    customer_research: Optional[str] = Field(None, description="Raw research or context data as a string, if available.")

- Example output:
{
  "input": "...",
  "input_email": "<p>Base email content...</p>",
  "customer_id": "...",
  "contact_emails": [
    {
      "contact_name": "Alex",
      "contact_email": "alex@email.com",
      "suggested_hook": "Save on PPE",
      "draft_email": "<p>...</p>",
      "follow_up_emails": ["<p>...</p>", "<p>...</p>"]
    },
    ...
  ],
  "contact_list": [
    {
      "contact_name": "Alex",
      "contact_email": "alex@email.com",
      "suggested_hook": "Save on PPE"
    },
    ...
  ],
  "review_comments": null,
  "customer_research": "..."
}
"""

logger = logging.getLogger(__name__)



async def get_email_agent() -> AzureAIAgent:
    """Create and return an email agent instance and client for proper cleanup."""
    creds = DefaultAzureCredential()
    ai_agent_settings = AzureAIAgentSettings()
    
    # Create client properly with required configuration
    client = AzureAIAgent.create_client(
        ai_service_type="azure_ai",
        ai_service_url=ai_agent_settings.endpoint,
        credential=creds
    )

    AGENT_NAME = "PerContact_Email_Assistant"
       
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
            description="Email Assistant for creating contact-specific emails from a base input email.",
            response_format=ResponseFormatJsonSchemaType(
                json_schema=ResponseFormatJsonSchema(
                    name="multi_contact_email_task",
                    description="Generate contact-specific emails and follow-ups.",
                    schema=MultiContactEmailTask.model_json_schema(),
                )
            )
        )

    search_agent = AzureAIAgent(
        client=client,
        definition=agent_definition,
        kernel=kernel  # Pass the kernel with registered services
    )

    return search_agent

    
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
                    thread=thread
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
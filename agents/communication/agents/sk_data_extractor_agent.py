from azure.identity.aio import DefaultAzureCredential
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings, AzureAIAgentThread
from azure.ai.agents.models import BingGroundingTool
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
#from semantic_kernel.contents import AnnotationContent
from typing import Annotated
from semantic_kernel.functions import kernel_function
from pydantic import BaseModel
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
#from semantic_kernel.arguments import KernelArguments
from azure.ai.agents.models import (
    ResponseFormatJsonSchema,
    ResponseFormatJsonSchemaType,
)
from models import ResearchOutput,Contact, Company, Account, SenderDetails

load_dotenv()
#sys.stderr = open("error_log_email.txt", "w", encoding="utf-8")
logger = logging.getLogger(__name__)
#INPUT_FILE = "b_270669152025-06-18_13-40-59.md" #good
#INPUT_FILE = "b_270669202025-06-18_13-41-55.md" #no user
#INPUT_FILE = "340036492025-06-18_17-05-07.md"
#INPUT_FILE = "340038282025-06-18_17-04-49.md" #good
#INPUT_FILE = "18757822025-06-19_08-45-31.md" #high research
INPUT_FILE = os.getenv("INPUT_FILE")

INSTRUCTIONS = """
You are an expert data extraction assistant.


Instructions:
- Extract all available information for the required fields listed below from the context data.
- Output only a valid JSON object, enclosed strictly between --- --- (three dashes on a line before and after).
- Do not include any extra text, comments, or explanations outside the JSON object.
- If a field is missing in the context, set its value to null or an empty string.
- The output must be directly parsable as JSON.

Required output fields:
- customer_name
- customer_id
- customer_zip
- customer_state
- division
- primary_reason_for_outreach
- issue
- sender_details: { first_name, last_name, full_name, email, title, phone, team }
- contact_list: [ { first_name, last_name, full_name, email, title, phone, salesforce_account_id, salesforce_contact_id } ]
- summary
- recommendations (as a list of strings)
- sample_email_subject
- sample_email_body
- citations (as a list of strings)
- url_citations (as a list of strings)
- marketing_and_category_insights (as a list of CategoryInsight objects; see below for structure)
- other_fields (object for any extra data)
- company (object, if company info is present)
- account (object, if account info is present)

Each CategoryInsight object should have the following structure:
{
  "primary_category": string,  // e.g., "Office Supplies"
  "secondary_categories": [string] | null, // e.g., ["Toner", "Paper"]
  "marketing_categories": [string] | null, // e.g., ["Print & Marketing", "Ink & Toner"]
  "value": string | null, // e.g., "$1,200.50"
  "opportunity": string | null // e.g., "Suggest toner bundle discount. Customer has not purchased toner in 6 months."
}

Example output (strictly follow this format):

---
{
  "customer_name": "HOLMES ELECTRIC INC",
  "customer_id": "27208226",
  "customer_zip": "30303",
  "customer_state": "GA",
  "division": "ATL",
  "primary_reason_for_outreach": "Retention",
  "issue": "Customer spend has fallen to $0 in the last 6 months, compared to $11.6K two years ago.",
  "sender_details": {
    "first_name": "Victoria",
    "last_name": "Grant",
    "full_name": "Victoria Grant",
    "email": "Staplesexpertteam@staples.com",
    "title": "Manager, Account Expert Team",
    "phone": null,
    "team": "On behalf of the Staples Expert Team"
  },
  "contact_list": [
    {
      "first_name": "Duncan",
      "last_name": "Hubbard",
      "full_name": "Duncan Hubbard",
      "email": "dhubbard@holmeselectricsecurity.com",
      "title": null,
      "phone": null,
      "salesforce_account_id": "0013t00002dCbkcAAC",
      "salesforce_contact_id": "0033800002pDRPDAA4"
    }
  ],
  "summary": "This report can guide strategic discussions on re-engagement opportunities with Holmes Electric, focusing on tailored solutions to recapture spend while aligning with their compliance and sustainability goals.",
  "recommendations": [
    "Automate Office Supplies replenishment for job sites.",
    "Provide FSC-certified writing pads and recycled-content pens.",
    "Develop pre-approved 'Electrical Crew Pad & Pen' bundles.",
    "Introduce real-time spend dashboards."
  ],
  "sample_email_subject": "Keeping Your Crews Supplied – A Faster, Compliant Way to Restock Pads & Pens",
  "sample_email_body": "Hi Duncan, ... [rest of email body here] ...",
  "citations": [
    "customer row: DIV ATL | CUST_ID 27208226 | ...",
    "transactions row: TOTAL_SALES_AMOUNT_24M 11651.64 ...",
    "websearch: Holmes Electric’s participation in ELECTRI International’s discussion ..."
  ],
  "url_citations": [
    "https://www.einnews.com/pr_news/827335937/7-million-lost-in-h1-2025-new-tcpa-rules-hit-the-u-s-home-services-industry"
  ],
  "company": {
    "name": "HOLMES ELECTRIC INC"
  },
  "account": {
    "summary": "Account summary here.",
    "observations": "Observations here.",
    "action_plan": "Action plan here.",
    "expected_upside": "10-15% savings",
    "justification": "Justification here.",
    "citations": "Citations here."
  },
  "marketing_and_category_insights": [
    {
      "primary_category": "Office Supplies",
      "secondary_categories": ["Toner", "Paper"],
      "marketing_categories": ["Print & Marketing", "Ink & Toner"],
      "value": "$1,200.50",
      "opportunity": "Suggest toner bundle discount. Customer has not purchased toner in 6 months."
    },
    {
      "primary_category": "Breakroom",
      "secondary_categories": ["Coffee", "Snacks"],
      "marketing_categories": ["Breakroom Supplies"],
      "value": "$800.00",
      "opportunity": "Introduce new eco-friendly breakroom products. Purchases are stable year-over-year."
    }
  ],
  "other_fields": {}
}
---

Return only the JSON object as shown above, enclosed between the --- --- lines.

** Context Data: ** 
    - Provided as input data
"""
def read_from_source(filename: str) -> str:
    filepath = os.path.join("source", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
class EmailTask(BaseModel):
    input: str   # The context data
    output_email: str   # The generated email
    current_agent_name: str
    customer_id: str
    
    

async def get_data_agent() -> AzureAIAgent:
    """Create and return an email agent instance and client for proper cleanup."""
    creds = DefaultAzureCredential()
    ai_agent_settings = AzureAIAgentSettings()
    
    # Create client properly with required configuration
    client = AzureAIAgent.create_client(
        ai_service_type="azure_ai",
        ai_service_url=ai_agent_settings.endpoint,
        credential=creds    )

    AGENT_NAME = "Data_Assistant"
       
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

    #email_function = kernel.add_plugin(parent_directory=plugins_directory, plugin_name="DataExtractorFunction")
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
            description="Data Extractor Assistant for extracting data from input context",
            response_format=ResponseFormatJsonSchemaType(
                json_schema=ResponseFormatJsonSchema(
                    name="research_output",
                    description="Extract research output.",
                    schema=ResearchOutput.model_json_schema(),
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
            logger.info("Error initializing plugins. Please check the plugin directories.")
            raise RuntimeError("Failed to initialize required plugins")
        result = await kernel.invoke(data_extractor_plugin, input=user_input)
        logger.info("json result: %s", result)
        email_result = await kernel.invoke(email_plugin, input=result)
        logger.info("final email: %s", email_result)
    except Exception as e:
        logger.exception("Error initializing plugins: %s", e)
        # Create agent without plugins if initialization fails
        email_plugin = None
        data_extractor_plugin = None
    # Check for existing agent or create a new one

def save_file(folder: str, content: str, filename: str):
    filepath = os.path.join(folder, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
async def main() -> None:
    """Main function to run the search agent directly."""
    #user_input = read_user_input_from_file("input.md")
    #user_input = "Extract the data from the input context and return it in JSON format. Use the get_input kernel function to get the context."
    input_obj = EmailTask(
            input="generate email for customer with customer_id='1875782_2025-06-22_19-32-51' using the get_data_input function in the Data Assistant agent",
            #data_assistant_input="1875782_2025-06-22_19-32-51.md" #was giving same value as input
            output_email="",
            current_agent_name="User",
            customer_id="1875782_2025-06-22_19-32-51"
    )
    user_input = ChatMessageContent(role=AuthorRole.USER, content=input_obj.model_dump_json())
    search_agent = None
    thread: AzureAIAgentThread | None = None

    try:
        # Get the search agent
        search_agent = await get_data_agent()
        #
        response = await search_agent.get_response(messages=user_input, thread=thread)
        logger.info("# %s: %s", response.name, response)
        thread = response.thread
        email_text = response.message.content  # or adjust as needed for your response object
        save_file("input",email_text, "agent_extracted_data.txt")
        logger.info("Agent %s completed processing and thread ID: %s", search_agent.id, thread.id if thread else 'N/A')
        
    except Exception as e:
        logger.exception("Error in main: %s", e)
        
    #finally:
        #await thread.delete() if thread else None
            
     
 
if __name__ == "__main__":
    asyncio.run(main())
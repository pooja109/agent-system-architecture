import os, sys, json, tools, logging, asyncio
import pandas as pd

from openai import AzureOpenAI, OpenAI
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import MessageRole, BingGroundingTool, ListSortOrder
from azure.storage.queue import QueueServiceClient, QueueClient
from azure.ai.agents.models import ListSortOrder, AgentsResponseFormat, RunStatus

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from databricks import sql
from uszipcode import SearchEngine
from researchreviewer import WebSearchResultsExtraction, review_research

# Load environment variables
load_dotenv()


#print("\n\nFoundry Endpoint: ", os.getenv("ST_AI_FOUNDRY_ENDPOINT"), "  API Key: ", os.getenv("ST_AZURE_OPENAI_API_KEY"))


# ===================== Constants ====================

RESEARCH_AGENT_NAME = "Research_Agent"  # The agent name to use for the research agent - chat completion
FORMAT_AGENT_NAME = "Markdown_Agent"    # The agent name to use for formatting the content in a markdown format
AGENT_NAME = "Bing_Search_Assistant"    # The agent name to use for the Bing Search Assistant
REASONING_MODEL_NAME = os.getenv("REASONING_MODEL_NAME", "o3")  # The reasoning model name to use for the o3 reasoning model
FORMAT_JSON_AGENT_NAME = "JSON_Agent"

BATCH_ID = datetime.now().strftime("%Y%m%d%H%M%S")              # Batch ID for the run, based on current date and time
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AI_FOUNDRY_ENDPOINT = os.getenv("ST_AI_FOUNDRY_ENDPOINT")
AI_FOUNDRY_API_KEY = os.getenv("ST_AI_FOUNDRY_API_KEY")
BING_CONNECTION_NAME = os.environ["ST_BING_CONNECTION_NAME"]    # Default connection name for Bing Grounding Tool
DATABRICKS_STATUS_CATALOG_NAME = os.getenv("DATABRICKS_STATUS_CATALOG_NAME")
DATABRICKS_STATUS_SCHEMA_NAME = os.getenv("DATABRICKS_STATUS_SCHEMA_NAME")
DATABRICKS_STATUS_TABLE_NAME = os.getenv("DATABRICKS_STATUS_TABLE_NAME")
status_table_name = f"{DATABRICKS_STATUS_CATALOG_NAME}.{DATABRICKS_STATUS_SCHEMA_NAME}.{DATABRICKS_STATUS_TABLE_NAME}"
source_queue_name = os.getenv("AZURE_SRC_QUEUE_NAME")   # Source queue name for the research agent
queue_name = os.getenv("AZURE_TGT_QUEUE_NAME")          # Target queue name for the research agent
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES"))           # Maximum number of messages to process at once
status_cols = ["batch_id", "run_date", "agent_name", "status", "customer_id", "customer_name", "output_file", "blob_date_folder","processed_by", "created_at"]
client = AzureOpenAI(api_version=os.getenv("ST_API_VERSION"),    
                     azure_endpoint=os.getenv("ST_AZURE_OPENAI_ENDPOINT"),    
                     api_key=os.getenv("ST_AZURE_OPENAI_API_KEY"))




#MAX_MESSAGES = 5

# ===================== Logging Configuration ====================

# Creating a separate logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

#log_file = 'research_agent_'+ datetime.now().strftime("%Y%m%d") +'.log'
#file_handler = logging.FileHandler(log_file)
#file_handler.setFormatter(formatter)
#file_handler.setLevel(logging.INFO)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)

#logger.addHandler(file_handler)
logger.addHandler(stream_handler)   






# ==================== Function to get results from Grounding with Bing Seach   ====================

#async def get_bing_search_results(query: str):
async def get_bing_search_results(CUSTOMER_PROFILE: dict, query: str):                          # research reviewer code
    """
    Retrieves Bing Search results for a given query using the Bing Grounding Tool.
    
    Args:
        query (str): The search query to use
        max_results (int): The maximum number of results to return (default: 5)
        
    Returns:
        pd.DataFrame: A DataFrame containing the search results
    """
    project_client = AIProjectClient(
    endpoint=AI_FOUNDRY_ENDPOINT,
    credential=DefaultAzureCredential(),
    )

    # [START create_agent_with_bing_grounding_tool]
    conn_name = BING_CONNECTION_NAME
    search_results = ""
    search_citations = ""
    review_research_results:List[WebSearchResultsExtraction] = []                           # research reviewer code
    
    # Create agent with the bing tool and process agent run
    with project_client:
        agents_client = project_client.agents
        try:
            bing_conn_name =  project_client.connections.get(name=conn_name)
            bing_conn_id = bing_conn_name.id    
            logger.info(f"Using Bing connection: {bing_conn_name.name} (ID: {bing_conn_id})")    
            bing_grounding_tool = BingGroundingTool(connection_id=bing_conn_id)
        except Exception as e:
            logger.error(f"❌ Error initializing Bing grounding tool: {e}")
            logger.error(f"   Make sure ST_BING_CONNECTION_NAME is set in your environment")
            # Create agent without tools if Bing connection fails
            bing_grounding_tool = None



        # Check for existing agent or create a new one
        agent_definition = None
        try:
            # List existing agents to find if our agent already exists
            existing_agents = project_client.agents.list_agents()
            # Look for existing agent with our specific name
            for agent in existing_agents:
                if agent.name == AGENT_NAME:
                    logger.info(f"Found existing agent: {agent.name} (ID: {agent.id})")
                    agent_definition = agent
                    break
        except Exception as e:
            logger.error(f"❌ Error listing existing agents: {e}")
        
        
        
        # Create agent only if it doesn't exist
        if agent_definition is None:
            logger.info(f"Creating new agent: {AGENT_NAME}")
            # Configure tools if available
            tools = bing_grounding_tool.definitions if bing_grounding_tool else []
            
            agent = agents_client.create_agent(
            model=os.environ["ST_MODEL_DEPLOYMENT_NAME"],
            name=AGENT_NAME,
            instructions="""You are a search assistant that finds current information from the web using Bing search.

                Your role:
                - Search for current information, news, facts, and data
                - Provide accurate, up-to-date information from reliable web sources  
                - When coordinating with other agents, focus on your search capabilities
                - Always respond helpfully to search requests
                - If you cannot find specific information, explain what you searched for and suggest alternatives

                Guidelines:
                - Use web search to find the most current information available
                - Cite sources when possible
                - Provide factual, objective information""",
            tools=bing_grounding_tool.definitions if bing_grounding_tool else [],
        )
            logger.info(f"Created agent, ID: {agent.id}")
        # [END create_agent_with_bing_grounding_tool]
        

        # Create thread for communication
        thread = agents_client.threads.create()
        logger.info(f"Created thread, ID: {thread.id} for Bing Search")

        
        # Create message to thread
        message = agents_client.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=query,
        )
        logger.info(f"Created message, ID: {message.id} for Bing Search")

        # Create and process agent run in thread with tools
        run = agents_client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
        logger.info(f"BING SEARCH COMPLETE WITH STATUS: {run.status}")

        if run.status == "failed":
            logger.error(f"❌ Bing Search Run failed: {run.last_error}")

        # Fetch run steps to get the details of the agent run
        run_steps = agents_client.run_steps.list(thread_id=thread.id, run_id=run.id)
        for step in run_steps:
            logger.info(f"Step {step['id']} status: {step['status']}")
            step_details = step.get("step_details", {})
            tool_calls = step_details.get("tool_calls", [])

            if tool_calls:
                logger.info("  Tool calls:")
                for call in tool_calls:
                    logger.info(f"    Tool Call ID: {call.get('id')}")
                    logger.info(f"    Type: {call.get('type')}")

                    bing_grounding_details = call.get("bing_grounding", {})
                    if bing_grounding_details:
                        print(f"    Bing Grounding ID: {bing_grounding_details.get('requesturl')}")

            print()  # add an extra newline between steps



        # Print the Agent's response message with optional citation
        response_message = agents_client.messages.get_last_message_by_role(thread_id=thread.id, role=MessageRole.AGENT)
    
        if response_message:
            #logger.info(f"Agent response message ID: {response_message}")
            # convert the response message to a JSON string
            # pass the response_message to an LLM to format it as a json object
            response_message_json = await format_response_message_as_json(response_message)
            #print("\n\nFormatted Response Message JSON:\n", response_message_json)
            #print("\n\n")

            #review_research_results = await review_research(CUSTOMER_PROFILE, response_message.model_dump_json())           # research reviewer code
            review_research_results = await review_research(CUSTOMER_PROFILE, response_message_json)                        # research reviewer code
            for text_message in response_message.text_messages:
                print(f"Agent response: {text_message.text.value}")
                search_results += text_message.text.value + "\n"
            for annotation in response_message.url_citation_annotations:
                print(f"URL Citation: [{annotation.url_citation.title}]({annotation.url_citation.url})")
                search_citations += "\n\nURL Citation:\n" + annotation.url_citation.title + " : " + annotation.url_citation.url


    return search_results, search_citations, review_research_results                                        # research reviewer code
    #return search_results, search_citations


# ==================== Function to return State Code based off Zip Code  ====================

async def get_state_from_zip(zip_code):
    """
    Retrieves the state name (abbreviation) for a given US ZIP code.

    Args:
        zip_code (str): The five-digit US ZIP code as a string.

    Returns:
        str or None: The two-letter state abbreviation if found, otherwise None.
    """
    search = SearchEngine()
    zip_info = search.by_zipcode(zip_code)
    
    if zip_info and zip_info.state:
        logger.info(f"Found state for ZIP code {zip_code}: {zip_info.state}")
        return zip_info.state
    else:
        logger.warning(f"State not found for ZIP code {zip_code}")
        return None
    




# ==================== Function to save status in databricks  ====================


async def update_status_in_databricks(status_cols, status_vals, table_name, status):
    st_cols =  ({', '.join(status_cols)})
    st_vals =  status_vals.__str__().replace("[(","(").replace(")]",")")
    #print(f"INSERT INTO {table_name} ({', '.join(status_cols)}) VALUES {st_vals}") 
    #print(f"INSERT INTO {table_name} ({', '.join(status_cols)}) VALUES ({', '.join(['%s'] * len(status_vals))})", status_vals)
    try:
        # Establish a connection to Databricks
        with sql.connect(
            server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
            http_path=os.getenv("DATABRICKS_HTTP_PATH"),
            access_token=os.getenv("DATABRICKS_TOKEN")
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"INSERT INTO {table_name} ({', '.join(status_cols)}) VALUES {st_vals}")

                connection.commit()
                print(f"Updated execution status in {table_name} successfully.")
        
    except Exception as e:
        print(f"Error updating execution status into {table_name}: {e}")
        raise e    



# =================== Function to format content as JSON ====================

async def format_response_message_as_json(response_message):
    load_dotenv()
    if not response_message:
        return "{}"
    
    system_prompt = """You are an assistant that formats the response_message into a json format without changing any of the content. Return only valid JSON."""
    user_prompt = str(response_message)
    
    # Use the existing AzureOpenAI client
    try:
        response = client.chat.completions.create(
            model=os.environ["ST_MODEL_DEPLOYMENT_NAME"],  # Use the same model as other parts
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user", 
                    "content": user_prompt
                },
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract the JSON content from the response
        json_content = response.choices[0].message.content
        
        # Try to parse it to ensure it's valid JSON
        import json as json_module
        parsed_json = json_module.loads(json_content)
        return parsed_json
        
    except Exception as e:
        logger.error(f"Error formatting response message as JSON: {e}")
        # Fallback to creating a simple JSON structure
        try:
            # Create a basic JSON representation of the response message
            fallback_json = {
                "id": getattr(response_message, 'id', None),
                "role": getattr(response_message, 'role', None),
                "content": str(response_message),
                "created_at": getattr(response_message, 'created_at', None),
                "thread_id": getattr(response_message, 'thread_id', None),
                "text_messages": [
                    {
                        "text": {"value": text_msg.text.value if hasattr(text_msg, 'text') and hasattr(text_msg.text, 'value') else str(text_msg)}
                    } for text_msg in (response_message.text_messages if hasattr(response_message, 'text_messages') else [])
                ],
                "url_citation_annotations": [
                    {
                        "url_citation": {
                            "title": getattr(annotation.url_citation, 'title', '') if hasattr(annotation, 'url_citation') else '',
                            "url": getattr(annotation.url_citation, 'url', '') if hasattr(annotation, 'url_citation') else ''
                        }
                    } for annotation in (response_message.url_citation_annotations if hasattr(response_message, 'url_citation_annotations') else [])
                ],
                "error": str(e),
                "message": "Fallback JSON structure created due to formatting error."
            }
            return fallback_json
        except Exception as fallback_error:
            logger.error(f"Error creating fallback JSON: {fallback_error}")
            return {
                "error": str(e),
                "fallback_error": str(fallback_error),
                "message": "Failed to format response message as JSON."
            }


'''
async def format_response_message_as_json(response_message) -> json:
    """
    Formats the response message from the agent into a JSON string.
    
    Args:
        response_message: The response message object from the agent
        
    Returns:
        str: The formatted JSON string
    """
    load_dotenv()
    if not response_message:
        return "{}"
    
    project_client = AIProjectClient(
            credential=DefaultAzureCredential(), 
            endpoint=os.getenv("ST_AI_FOUNDRY_ENDPOINT")
        )

    with project_client:
        agents_client = project_client.agents
        # Check for existing agent or create a new one
        agent_definition = None
        try:
            # List existing agents to find if our agent already exists
            existing_agents = project_client.agents.list_agents()
            # Look for existing agent with our specific name
            for agent in existing_agents:
                if agent.name == FORMAT_JSON_AGENT_NAME:
                    print(f"Found existing agent: {agent.name} (ID: {agent.id})")
                    agent_definition = agent
                    break
        except Exception as e:
            print(f"Error listing existing agents: {e}")
            logger.error(f"❌ Error listing existing agents: {e}")


        # Create agent only if it doesn't exist
        if agent_definition is None:
            print(f"Creating new agent: {FORMAT_JSON_AGENT_NAME}")
            # Configure tools if available
            agent = agents_client.create_agent(
                    model=os.environ["ST_MODEL_DEPLOYMENT_NAME"],
                    name=FORMAT_JSON_AGENT_NAME,
                    instructions="""You are an assistant that formats the response_message into a json format without changing any of the content.""",
                    response_format=AgentsResponseFormat(type="json_object")
            )
            print(f"Created agent, ID: {agent.id}")


        # Create thread for communication
        thread = agents_client.threads.create()
        print(f"Created thread, ID: {thread.id}")

        message = project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=response_message)

        run = project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent.id)

        print("Json Formatting agent run status: ", run.status)

        if run.status == "failed":
            print(f"Run failed: {run.last_error}")
        else:
            response_message = project_client.agents.messages.get_last_message_by_role(thread_id=thread.id, role=MessageRole.AGENT, order=ListSortOrder.ASCENDING)
            if response_message:
                for text_message in response_message.text_messages:
                    print(f"Json Formatting agent response: {text_message.text.value}")
                    formatted_content += text_message.text.value + "\n"
                
    return formatted_content

'''







# ==================== Function to format content in a markdown format  ====================

async def format_content(content: str) -> str:
    """
    Formats the markdown content
    
    Args:
        content (str): The content to format
        
    Returns:
        str: The formatted content
    """
    
    formatted_content = ""

    if not content:
        return ""
    else:
        project_client = AIProjectClient(
            credential=DefaultAzureCredential(), 
            endpoint=os.getenv("ST_AI_FOUNDRY_ENDPOINT")
        )

        with project_client:
            agents_client = project_client.agents
            # Check for existing agent or create a new one
            agent_definition = None
            try:
                # List existing agents to find if our agent already exists
                existing_agents = project_client.agents.list_agents()
                # Look for existing agent with our specific name
                for agent in existing_agents:
                    if agent.name == FORMAT_AGENT_NAME:
                        print(f"Found existing agent: {agent.name} (ID: {agent.id})")
                        agent_definition = agent
                        break
            except Exception as e:
                print(f"Error listing existing agents: {e}")
                logger.error(f"❌ Error listing existing agents: {e}")
    
    
            # Create agent only if it doesn't exist
            if agent_definition is None:
                print(f"Creating new agent: {FORMAT_AGENT_NAME}")
                # Configure tools if available
                agent = agents_client.create_agent(
                        model=os.environ["ST_MODEL_DEPLOYMENT_NAME"],
                        name=FORMAT_AGENT_NAME,
                        instructions="""You are an assistant that formats this markdown better without changing any of the content. The idea is to use this markdown in a presentation to executives. 
                        Need it to be visually appealing and easy to read. Do not change any content or add any new content. 
                        Do not change FIRST_NAME, LAST_NAME or swap them. 
                        Do not change the names of Categories or swap them. Show them in a single table.
                        Just format the content better.""",
                )
                print(f"Created agent, ID: {agent.id}")

                #Do not change the names of Primary Categories, Secondary Categories, Marketing Primary Categories. Show them in a table format.
#           agent = project.agents.get_agent(FORMAT_AGENT_NAME)

            # Create thread for communication
            thread = agents_client.threads.create()
            print(f"Created thread, ID: {thread.id}")

            message = project_client.agents.messages.create(
                thread_id=thread.id,
                role="user",
                content=content)

            run = project_client.agents.runs.create_and_process(
                thread_id=thread.id,
                agent_id=agent.id)

            if run.status == "failed":
                print(f"Run failed: {run.last_error}")
            else:
                response_message = project_client.agents.messages.get_last_message_by_role(thread_id=thread.id, role=MessageRole.AGENT, order=ListSortOrder.ASCENDING)
                if response_message:
                    for text_message in response_message.text_messages:
                        formatted_content += text_message.text.value + "\n"
                
    return formatted_content






# ==================== Function To Save Research Report in Azure Container ====================

async def save_research_report(container_name, blob_name, file_content):
    """
    Creates a new Research file for every customer in the Azure Blob Storage container 'lowtouch'
    """
    try:
        # Azure Blob Storage configuration
        account_url = STORAGE_CONNECTION_STRING
        
        # Initialize Azure credentials
        credential = DefaultAzureCredential()

        logger.info(f"Creating file {blob_name} in container {container_name}...")
        logger.info(f"Using account URL: {account_url}")

        # Create BlobServiceClient
        blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
        
        # Get container client
        container_client = blob_service_client.get_container_client(container_name)
        
        # Check if container exists, create if it doesn't
        try:
            container_properties = container_client.get_container_properties()
            logger.info(f"Container {container_name} exists.")
        except Exception:
            print(f"Container {container_name} does not exist. Creating it...")
            container_client.create_container()
            logger.info(f"Container {container_name} created successfully.")

        # Get blob client
        blob_client = container_client.get_blob_client(blob_name)
        
        # Upload the content to create the file
        blob_client.upload_blob(file_content, overwrite=True)
        
        logger.info(f"✅ Successfully created {blob_name} in container {container_name}!")
        logger.info(f"File URL: {blob_client.url}")
        
        # Verify the file was created by checking its properties
        blob_properties = blob_client.get_blob_properties()
        logger.info(f"File size: {blob_properties.size} bytes")
        logger.info(f"Last modified: {blob_properties.last_modified}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating file in Azure Blob Storage: {e}")
        return False






# ==================== Function to call the o3 reasoning model with tool calling functionality  ====================

async def o3call(prompt, reasoning_effort, tools=None, tool_choice="auto", response_format=None):
    """
    Call the o3 model with optional tool calling functionality.
    
    Args:
        prompt (str): The user's query or prompt
        reasoning_effort (str): The reasoning effort level (low, medium, high)
        tools (list, optional): List of tool definitions for function calling
        tool_choice (str or dict, optional): Tool selection strategy
        response_format (dict, optional): Structured output format
        
    Returns:
        dict or str: The model's response, potentially including tool results
    """
  
    system_message = """
    You are a helpful AI assistant that analyzes Low Touch Customer Accounts for Staples.
    """
    
    # Create the base parameters for the API call
    params = {
        "model": REASONING_MODEL_NAME,
        "messages": [
            {
                "role": "user", 
                "content": system_message + " " + prompt
            }
        ],
        "reasoning_effort": reasoning_effort
    }
    
    # Add tools if provided
    if tools is not None:
        params["tools"] = tools
        params["tool_choice"] = tool_choice
    
    # Make the initial API call
    response = client.chat.completions.create(**params)
    response_message = response.choices[0].message
    
    # Check if the model wants to call a function
    if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
        # Process function calls and get results
        tool_results = []
        
        for tool_call in response_message.tool_calls:
            # Extract function call details
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            # Execute the function
            result = tools.execute_tool_function(function_name, function_args)
            
            tool_results.append({
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(result)
            })
        
        # Format the datasets from tool calls
        datasets_from_tool_calls = ""
        for result in tool_results:
            datasets_from_tool_calls += f"\n### Results from {result['name']}:\n"
            datasets_from_tool_calls += f"```json\n{result['content']}\n```\n"
        
        # Generate a new prompt with the tool call results incorporated
        new_prompt = f"""
        {prompt}
        
        Here is additional data retrieved to help with your analysis:
        {datasets_from_tool_calls}
        
        Please use this data to enhance your analysis.
        """
        
        # Create parameters for the second call with the new prompt
        second_params = {
            "model": "o3",
            "messages": [
                {
                    "role": "user", 
                    "content": system_message + " " + new_prompt
                }
            ],
            "reasoning_effort": reasoning_effort,
            "summary": "detailed",
        }
        
        # Add response_format if provided
        if response_format is not None:
            second_params["response_format"] = response_format
            completion = client.beta.chat.completions.parse(**second_params)
            if hasattr(completion.choices[0].message, 'parsed'):
                return completion.choices[0].message.parsed
            else:
                return completion.choices[0].message.content
        else:
            completion = client.chat.completions.create(**second_params)
            return completion.choices[0].message.content
    
    # Handle the case where no function call is made
    if response_format is not None:
        # Switch to using parse for structured output
        parse_params = params.copy()
        parse_params["response_format"] = response_format
        completion = client.beta.chat.completions.parse(**parse_params)
        if hasattr(completion.choices[0].message, 'parsed'):
            return completion.choices[0].message.parsed
        else:
            return completion.choices[0].message.content
    else:
        return response_message.content
    







async def main() -> None:

    ###############     Define inputs       ############### 

    context = """
    Low-touch customers are those that don't have a dedicated sales rep. As a result, they don't get frequent outreaches and Staples is seeing a decline in spend from them. 
    You have access to the three dataset below. The customer dataset has all the information about the account and the primary and secondary categories that they have bought. 
    The column (PRIMARY_CAT_1) represents the primary category and the column (PRIMARY_CAT_1_Value) represents the potential revenue in that category. 
    Secondary category are more granular than primary categories. They are the children of primary and so on. 
    The columns like PRIMARY_CAT_2, SECONDARY_CAT_2 etc. represent the second category of items bough and their potential of revenue or loss from customer dataset. 
    The column named Category with the value of Growth and Retention determine if the dollar values in PRIMARY_CAT_1_Value are potential of growth or decline. 
    When doing research take into consideration whether they are a growth account or retention account. Provide recommendations for all the primary categories in the customer dataset.
    """




    # Define optional variables here- if they are commented out in lower sections, they will simply be blank strings.
    few_shot_examples="No few shot examples provided"
    provided_rules_and_policies="No provided rules and policies"






    #########################################     Datasets       ######################################### 

    # dataset1 is the main dataset for analysis
    # It includes data for Lowtouch Customers who belong to 3 verticals: Commercial, Healthcare, Sled
    # The Priority Reason for outreach is Retention or Growth across different Category of Products

    # Create a connection to the source queue researchagent queue which will pull the initial dataset from databricks for each customer from the Azure Storage Research Queue
    # Create a connection to communicationagentqueue01 azure storage queue which will push the research report for each customer to the Azure Storage Communication Queue



    # Get connection string and validate
    queue_url = os.getenv("AZURE_QUEUE_URL")
    print(f"\n\nQueue Connection String: {queue_url}")

    if not queue_url:
        logger.error("❌ AZURE_QUEUE_URL environment variable is not set")
        raise ValueError("AZURE_QUEUE_URL environment variable is required")

    logger.info(f"Initializing Azure Queue connection for queue: {queue_name}")

    try:

        
        credential = DefaultAzureCredential()
        queue_client = QueueClient(queue_url, queue_name, credential=credential)
        source_queue_client = QueueClient(queue_url, source_queue_name, credential=credential)

    # Test the connection
        queue_properties = queue_client.get_queue_properties()
        logger.info(f"✅ Successfully connected to source queue '{source_queue_name}'")
        logger.info(f"✅ Successfully connected to target queue '{queue_name}'")
        
    except Exception as e:
        # If queue doesn't exist, try to create it
        if "QueueNotFound" in str(e):
            try:
                queue_service_client = QueueServiceClient.from_connection_string(queue_url)
                queue_service_client.create_queue(queue_name)
                source_queue_client = QueueClient.from_connection_string(queue_url, source_queue_name)
                queue_client = QueueClient.from_connection_string(queue_url, queue_name)
                logger.info(f"✅ Created and connected to new queue '{queue_name}'")
            except Exception as create_error:
                logger.error(f"❌ Failed to create queue '{queue_name}': {create_error}")
                raise
        else:
            logger.error(f"❌ Failed to connect to queue '{queue_name}': {e}")
            raise



    # Define the rules and policies that the model should follow
    provided_rules_and_policies="""
    **Rule:** Use the provided datasets to analyze the Low Touch Customer Accounts and provide the Priority Reason and a detailed report for each customer.
    Use only existing Primary and Secondary Categories for the Customers. Do not make up any categories or values or bundles or discounts or rebates or percent off or credit. 
    Only mention categories in the customer dataset. Do not recommend any other products or categories that are not in customer dataset.
    For each customer in the customer dataset, identify target categories by utilizing both Primary and Secondary Categories. 
    Provide prioritized recommendation for Primary Category 1 and Secondary Category 1 first, followed by Primary Category 2 and Secondary Category 2 maintaining this order of importance in the output.
    Use Total Sales Amount for the Primary and Secondary Categories to show the historical sales amount for that Customer.
    **Policy:** All recommendations should be future-facing (after """ + datetime.now().strftime("%Y-%m-%d") + """) and should not reference any past dates or events.
    **Policy:** These customer are B2B customers so reference Staples Business instead of Staples.com or Staplesbusiness.com.
    """



    class Citation(BaseModel):
        dataset_citation: str = Field(..., description="The exact datapoint, text, or section of provided data that supports the claim made in the analysis.")
        reason_for_citation: str = Field(..., description="A reason for why this datapoint is relevant to the analysis.")

    class Response(BaseModel):
        citations: list[Citation] = Field(..., 
            description="A list of citations of specific data points, text, or sections of provided data that supports the claim made in the analysis.")
        response_to_input_task: str = Field(..., 
            description="A comprehensive response to instruction or task that has been given..")
        justification: str = Field(..., 
            description="A comprehensive overview of the decisions made, the specific data points made, for the purpose of audit logging and tracking decisioning..")
        flag_for_human_review: bool = Field(..., 
            description="If the outcome of the analysis is not clear, or if the analysis is not conclusive, then flag the case study for human review.")



    
    logger.info("STARTING PROCESSING FOR LOW TOUCH CUSTOMERS from " + source_queue_name + " queue")

    # ==================== Main Execution Loop ====================
    while True:
        messages = source_queue_client.receive_messages(max_messages=MAX_MESSAGES, visibility_timeout=300)  # Increased timeout to 5 minutes
        #messages = source_queue_client.receive_messages(max_messages=10, visibility_timeout=300)  # execute for 10 customers at a time
        
        for msg_batch in messages.by_page():
            for msg in msg_batch:
                # Store the message reference for deletion
                message_to_delete = msg
                
                # "Process" the message
                try:
                    data = json.loads(msg.content)
                    cust = data.get("customer_id", "Unknown")
                    #print(f"Processing message: {data}")
                except json.JSONDecodeError:
                    print(f"⚠️ Invalid JSON, deleting: {msg.content}")
                    try:
                        source_queue_client.delete_message(message_to_delete)
                        logger.error("✅ Deleted invalid JSON message")
                    except Exception as delete_error:
                        logger.error(f"❌ Failed to delete invalid message: {delete_error}")
                    continue
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}.")
                    continue
                
                #get BATCH_ID from the message
                MSG_BATCH_ID = data.get("batch_id", BATCH_ID)
                
                # Convert the data to DataFrames
                try:
                    i2a_data = data.get("i2a_data", "Unknown")
                    #convert i2a data to dataframe
                    if isinstance(i2a_data, str):
                        i2a_data = json.loads(i2a_data)
                    if isinstance(i2a_data, list):
                        i2a_data = pd.DataFrame(i2a_data)
                    elif isinstance(i2a_data, dict):
                        i2a_data = pd.DataFrame([i2a_data])
                    else:
                        i2a_data = pd.DataFrame()

                    transactions_data = data.get("transactions_data", "Unknown")
                    # convert transactions data to dataframe
                    if isinstance(transactions_data, str):
                        transactions_data = json.loads(transactions_data)
                    if isinstance(transactions_data, list):
                        transactions_data = pd.DataFrame(transactions_data)
                    elif isinstance(transactions_data, dict):
                        transactions_data = pd.DataFrame([transactions_data])
                    else:
                        transactions_data = pd.DataFrame()

                    dnb_data = data.get("dnb_data", "Unknown")
                    # convert dnb data to dataframe
                    if isinstance(dnb_data, str):
                        dnb_data = json.loads(dnb_data)
                    if isinstance(dnb_data, list):  
                        dnb_data = pd.DataFrame(dnb_data)
                    elif isinstance(dnb_data, dict):
                        dnb_data = pd.DataFrame([dnb_data])
                    else:
                        dnb_data = pd.DataFrame()

                    marketing_data = data.get("marketing_data", "Unknown")
                    # convert marketing data to dataframe
                    if isinstance(marketing_data, str):
                        marketing_data = json.loads(marketing_data)
                    if isinstance(marketing_data, list):
                        marketing_data = pd.DataFrame(marketing_data)
                    elif isinstance(marketing_data, dict):
                        marketing_data = pd.DataFrame([marketing_data])
                    else:
                        marketing_data = pd.DataFrame()
                except Exception as e:
                    logger.error(f"❌ Error converting data to DataFrame: {e}. ")
                    continue
        
                # Let the service know we're finished with the message and it can be safely deleted.
                #source_queue_client.delete_message(msg)
                #print(f"✅ Processed and deleted message: {data['customer_id']}\n\n")


            
                logger.info("=" * 100)
                logger.info("START: PROCESSING CUSTOMER ID: %s", cust)
                logger.info("=" * 100)
                
                print("-" * 100)
                print(f"\n\n****************************         Customer ID: {cust}     ****************************")
                print("-" * 100)
                
                b_cust = f"{cust}"
                
                #print("Categories in Filtered I2A Data for the specific customer: ", i2a_data['PRIMARY_CAT_1'].values[0], ";",i2a_data['PRIMARY_CAT_2'].values[0],  ";", i2a_data['PRIMARY_CAT_3'].values[0])

                # check if i2a_data['PRIMARY_CAT_1'].values[0] is not None and i2a_data['PRIMARY_CAT_2'].values[0] is not None and i2a_data['PRIMARY_CAT_3'].values[0] is not None
                if not i2a_data['PRIMARY_CAT_1'].values[0] is None :
                    cat1 = i2a_data['PRIMARY_CAT_1'].values[0]
                    print("Primary Category 1: ", cat1, " and Marketing Category 1: ", i2a_data['MARKETING_CAT_1'].values[0])
                else:
                    cat1 = None
                    print("No Primary Category 1 found for this customer.") 
                
                if not i2a_data['PRIMARY_CAT_2'].values[0] is None :
                    cat2 = i2a_data['PRIMARY_CAT_2'].values[0]
                    print("Primary Category 2: ", cat2, " and Marketing Category 2: ", i2a_data['MARKETING_CAT_2'].values[0])
                else:
                    cat2 = None
                    print("No Primary Category 2 found for this customer.")

                # Commented out the below code to remove Primary Category 3 
                '''
                if not i2a_data['PRIMARY_CAT_3'].values[0] is None:
                    cat3 = i2a_data['PRIMARY_CAT_3'].values[0]
                    print("Primary Category 3: ", cat3, " and Marketing Category 3: ", i2a_data['MARKETING_CAT_3'].values[0])
                else:
                    cat3 = None
                    print("No Primary Category 3 found for this customer.")
                '''

            
                City_code = i2a_data['DIV'].values[0] if not i2a_data.empty else None
                cust_name = i2a_data['CUST_NAME'].values[0] if not i2a_data.empty else None
                cust_industry = i2a_data['INDUSTRY'].values[0] if not i2a_data.empty else None
                cust_zip_code = i2a_data['CUST_ZIP'].values[0] if not i2a_data.empty else None
                cust_website = dnb_data['website'].values[0] if not dnb_data.empty else None
                business_name = dnb_data['business_name'].values[0] if not dnb_data.empty else None


                # Create CUSTOMER_PROFILE dictionary
                CUSTOMER_PROFILE = {
                    "name": cust_name,
                    "business_name": business_name,
                    "industry": cust_industry,
                    "location": City_code,  # You may want to use a more descriptive location if available
                    "domain_hint": cust_website
                }


                print("Customer Name : ", cust_name, "   and Website: ", cust_website)
                print("Customer Zip Code : ", cust_zip_code)
                print("Customer Industry : ", cust_industry)
            



                logger.info("START: GET STATE FROM ZIP CODE")
                cust_state = await get_state_from_zip(cust_zip_code)          # Get the state code from the zip code
                logger.info("END: GET STATE FROM ZIP CODE")
                cust_state = cust_state.strip().replace(" ", "_").replace("-", "_").replace(".", "_").replace(",", "_").replace("'", "_") # remove any leading or trailing whitespace
                msg = ""
                    
                # Added code to use Bing Search data for all customers
                try:
                    msg=""
                    websearch_content = ""
                    curr_date = datetime.now().strftime("%Y-%m-%d")

                    if business_name is not None and business_name != "":
                        query = f"Show me the latest news from past 3 months from {curr_date}, for {cust_name} or {business_name}, a company operating in the {cust_industry} industry. "
                    else:
                        query = f"Show me the latest news from past 3 months from {curr_date}, for {cust_name}, a company operating in the {cust_industry} industry. "
                    
                    if cust_website is not None and cust_website != "": 
                        query += "You could also search their website "+ cust_website + " for the latest news."
                    
                    logger.info("START: BING SEARCH")
                    logger.info(f"Querying Bing Search with query: {query}")
                    #search_results , search_citations = await get_bing_search_results(query=query)         # Get Bing Search results
                    review_research_results: List[WebSearchResultsExtraction] = []                                                                  # research reviewer code
                    search_results , search_citations, review_research_results = await get_bing_search_results(CUSTOMER_PROFILE, query=query)       # research reviewer code
                    logger.info(f"Received search results: {search_results}")
                    logger.info(f"Received search citations: {search_citations}")
                    logger.info(f"Received review research results: {review_research_results}")  # research reviewer code
                    
                    # Filter review_research_results for only relevant results
                    relevant_web_results = []
                    
                    if review_research_results:
                        for res in review_research_results:
                            # If using Pydantic objects, use res.is_relevant; if dict, use res.get('is_relevant')
                            # Prefer direct attribute access when `res` is a Pydantic model
                            try:
                                is_relevant = res.is_relevant
                            except AttributeError:
                                is_relevant = None
                            if is_relevant is None and isinstance(res, dict):
                                is_relevant = res.get('is_relevant')
                            if is_relevant:
                                # Use the original search result text if available
                                try:
                                    snippet = res.search_results
                                except AttributeError:
                                    snippet = ""
                                relevant_web_results.append(snippet)

                    # Only use relevant web results in the prompt
                    if relevant_web_results:
                        websearch_content = snippet
                    else:
                        websearch_content = ""
                    
                    logger.info(f"Relevant web search results: {relevant_web_results}")

                    logger.info("END: BING SEARCH")
                except Exception as e:
                    logger.error(f"❌ Error during Bing Search: {e}")
                    search_results = "No search results found."
                    search_citations = "No citations found."
                    msg = "Bing Search failed, using default message."
                    logger.info("END: BING SEARCH")

                
                contacts = transactions_data[['SF_ACCOUNT_ID', 'SF_CONTACT_ID', 'FIRST_NAME', 'LAST_NAME','EMAIL']].drop_duplicates()
                categories = i2a_data[['PRIMARY_CAT_1', 'PRIMARY_CAT_2', 'SECONDARY_CAT_1', 'SECONDARY_CAT_2', 'MARKETING_CAT_1', 'MARKETING_CAT_2',]].drop_duplicates()

                # Commented out the below code to remove Primary Category 3 and Secondary Category 3
                #categories = i2a_data[['PRIMARY_CAT_1', 'PRIMARY_CAT_2', 'PRIMARY_CAT_3',
                #                        'SECONDARY_CAT_1', 'SECONDARY_CAT_2', 'SECONDARY_CAT_3',
                #                        'MARKETING_CAT_1', 'MARKETING_CAT_2', 'MARKETING_CAT_3']].drop_duplicates()


                ## Instructions and Tasks

                instructions_and_task="""
                    You are an AI research assistant that helps the Staples B2B team research their low-touch customers and create hyper-personalized outreach report for the contacts. 
                    Specify the priority reason for outreach, which can be either Retention or Growth.
                    Analyze and Research the data for """ + cust_name + """ and create a research report for the customer and their contact details. 
                    The research report and recommendations will be used to create hyper-personalized report for """ + cust_name + """. 
                    Recommendations should be based on the Primary and Secondary Categories in the customer dataset. Use all the Primary categories to target that Customer.
                    Use data from marketing to propose additional products. Use Bing Search to enhance the research report.
                    Provide a contact wise generic report in the output along with your other research output and recommendations. 
                """



                ################     Prompt for the Use Case       ###############

                # removed   <websearch> {search_results} </websearch> from the dataset and added    <websearch> {websearch_content} </websearch> for # research reviewer code
                    

                prompt=f"""

                You are helping process input data into an output format.

                Here are the datasets:
                <datasets>
                    <customer> {i2a_data} </customer>
                    <transactions> {transactions_data} </transactions>
                    <dnb> {dnb_data} </dnb>
                    <websearch> {websearch_content} </websearch>
                    <marketing> {marketing_data} </marketing>
                </datasets>

                Here are the instructions and tasks to perform:
                <instructions_and_task>
                {instructions_and_task}
                </instructions_and_task>

                This is the context of the task:
                <context>
                {context}
                </context>


                Here is background information and rules and policies to follow:
                <provided_rules_and_policies>
                {provided_rules_and_policies}
                </provided_rules_and_policies>

                """

                #logger.info(prompt)






                ################     PREDICTION       ###############

                # Generate a prediction
                logger.info("START: CALL REASONING MODEL FOR RESEARCH")
                result = await o3call(
                        prompt=prompt,
                        reasoning_effort="high",
                        tool_choice="auto",
                        response_format=Response
                )
                
                #print(result)
                logger.info("END: CALL REASONING MODEL FOR RESEARCH")

                try:
                    if isinstance(result, Response):
                        # See the model's response to the input task.
                        #logger.info(result.response_to_input_task)
                        markdown_content = result.response_to_input_task.__str__()+ "\n\n" if result.response_to_input_task else result.content

                        markdown_content += "\n\nCustomer's State: " + cust_state + "     Zip Code: " + cust_zip_code

                        markdown_content += "\n\nI2A Primary, Secondary Categories and Marketing Primary Categories: \n" + categories.__str__()+ "\n\n"
                        
                        #markdown_content += "Mkt : \n" + marketing_data.__str__() + "\n\n"

                        markdown_content += "Contacts : \n" + contacts.__str__() + "\n\n"

                        logger.info("START: FORMATTING CONTENT IN MARKDOWN FORMAT")
                        formatted_content = await format_content(markdown_content)  # Format the content in markdown format
                        logger.info("END: FORMATTING CONTENT IN MARKDOWN FORMAT")


                        #cat_string = ';'.join(categories.astype(str))
                        # see the categories referenced in the research report. Values separated by semicolon
                        formatted_content += "\nCategories Referenced in the Research Report: \n" + categories.__str__() + "\n\n"

                        #formatted_content += "Marketing Categories referenced : \n" + marketing_data.__str__() + "\n\n"
                        
                        # See the explanation of why the model made the decision it did. Note this is an open field of research- for numerical calculations, with step by step reasoning that arrives at an answer, this is reliable.
                        formatted_content += "\n\nJustification : \n" + result.justification.__str__() + "\n\n"

                        # See the data points the model used to make the decision it did.
                        formatted_content += "\n\nCitation : \n" + result.citations.__str__() + "\n\n"

                        formatted_content += "\n\nBing Search Results and Citation : \n" + msg + "\n" + search_results + "\n" + search_citations + "\n\n"
                        
                        #file name and path
                        current_datetime = datetime.now()
                        folder_name = current_datetime.strftime("%Y%m%d")
                        #research_file = "research_output\\" + current_datetime.strftime("%Y%m%d") + "\\" + b_cust + current_datetime.strftime("_%Y-%m-%d_%H-%M-%S")+".md"
                        research_file =  folder_name + "\\" + b_cust + "\\research_output\\" + b_cust + current_datetime.strftime("_%Y-%m-%d_%H-%M-%S")+".md"

                        logger.info(f"START: SAVING RESEARCH REPORT: {research_file}")
                        
                        await save_research_report(
                            container_name=CONTAINER_NAME,             # changed from "lowtouch" to "mld01blobcontainerne0"
                            blob_name=research_file,
                            file_content=formatted_content                      # changed from markdown_content to formatted_content
                        )
                        logger.info(f"END: SAVING RESEARCH REPORT: {research_file}")

                        logger.info("START: PUSHING THE MESSAGE TO QUEUE")
                        
                        run_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
                        # Send the research report to the Azure Storage Queue
                        research_msg = {
                            "batch_id": MSG_BATCH_ID,
                            "run_date": run_date,
                            "agent_name": RESEARCH_AGENT_NAME,
                            "status": "S",
                            "cust_id": b_cust,
                            "agent_output": formatted_content,
                            "agent_output_path": research_file
                        }

                        queue_client.send_message(json.dumps(research_msg))                # Uncomment to send message to queue
                        logger.info(f"Message pushed to queue '{queue_name}' : Batch Id : {MSG_BATCH_ID} ; AgentName : {RESEARCH_AGENT_NAME} ; Customer Id : {b_cust}")
                        
                        # Let the service know we're finished with the message and it can be safely deleted.
                        try:
                            source_queue_client.delete_message(message_to_delete)
                            logger.info(f"✅ Successfully deleted message for customer {b_cust} from source queue {source_queue_name} after processing.")
                        except Exception as delete_error:
                            logger.error(f"❌ Failed to delete message for customer {b_cust} from source queue {source_queue_name} : {delete_error}")
                            # Continue processing anyway since the main work is done

                        logger.info("END: PUSHING THE MESSAGE TO QUEUE")

                        logger.info(f"START: UPDATE STATUS IN DATABRICKS for customer {b_cust}")
                        
                        # Update the status in Databricks
                        status_vals = [(
                            int(MSG_BATCH_ID),
                            run_date,
                            RESEARCH_AGENT_NAME,
                            "S",
                            b_cust,
                            cust_name,
                            research_file,
                            folder_name,
                            RESEARCH_AGENT_NAME,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )]

                        #status_cols = ["batch_id", "run_date", "agent_name", "status", "customer_id", "customer_name", "output_file", "blob_date_folder","created_at"]
                        try:
                            await update_status_in_databricks(status_cols=status_cols, status_vals=status_vals, table_name=status_table_name, status="S")
                            logger.info(f"END: UPDATE STATUS IN DATABRICKS for customer {b_cust}")
                        except Exception as e:
                            logger.error(f"Error updating status in Databricks for customer {b_cust}: {e}")
                        
                    else:    
                        logger.error(f"❌ Model did not return a valid response for customer {b_cust}.")
                        logger.info(result)
                    logger.info("END: PROCESSING CUSTOMER ID: %s", cust)
                    logger.info("=" * 100)
                except Exception as e:
                    logger.error(f"❌ Error processing customer {cust}: {e}")
                    print(f"❌ Error processing customer {cust}: {e}")
                    continue





if __name__ == "__main__":
    asyncio.run(main())
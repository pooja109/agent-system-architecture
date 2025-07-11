import os, PyPDF2, json, tools, logging
import pandas as pd

from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import MessageRole, BingGroundingTool, ListSortOrder

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from databricks import sql
from uszipcode import SearchEngine


# Load environment variables
load_dotenv("./.env")


client = AzureOpenAI( api_version="2024-12-01-preview",    
                     azure_endpoint=os.getenv("ST_AZURE_OPENAI_ENDPOINT"),    
                     api_key=os.getenv("ST_AZURE_OPENAI_API_KEY"))


RESEARCH_AGENT_NAME = "Research_Agent"  # The agent name to use for the research agent - chat completion
FORMAT_AGENT_NAME = "Markdown_Agent"  # The agent name to use for formatting the content in a markdown format
AGENT_NAME = "Bing_Search_Assistant"  # The agent name to use for the Bing Search Assistant



# ===================== Logging Configuration ====================

# Creating a separate logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

log_file = './logs/research_agent_'+ datetime.now().strftime("%Y%m%d") +'.log'
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)   





# ==================== Function to get results from Grounding with Bing Seach   ====================

def get_bing_search_results(query: str):
    """
    Retrieves Bing Search results for a given query using the Bing Grounding Tool.
    
    Args:
        query (str): The search query to use
        max_results (int): The maximum number of results to return (default: 5)
        
    Returns:
        pd.DataFrame: A DataFrame containing the search results
    """
    project_client = AIProjectClient(
    endpoint=os.environ["ST_AI_FOUNDRY_ENDPOINT"],
    credential=DefaultAzureCredential(),
    )

    # [START create_agent_with_bing_grounding_tool]
    conn_name = os.environ["ST_BING_CONNECTION_NAME"]
    search_results = ""
    search_citations = ""

    
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
            for text_message in response_message.text_messages:
                print(f"Agent response: {text_message.text.value}")
                search_results = text_message.text.value
            for annotation in response_message.url_citation_annotations:
                print(f"URL Citation: [{annotation.url_citation.title}]({annotation.url_citation.url})")
                search_citations = "\n\nURL Citation:\n" + annotation.url_citation.title + " : " + annotation.url_citation.url
    
    
    return search_results, search_citations




# ==================== Function to return State Code based off Zip Code  ====================

def get_state_from_zip(zip_code):
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

def save_run_status(status: str, cust_id: str, cust_name: str, cust_zip: str, cust_state: str):
    """
    Saves the status of the research report in Databricks.
    
    Args:
        status (str): The status message to save
        
    Returns:
        None
    """
    # Here you would implement the logic to save the status in Databricks
    # batch_id	run_date	agent_name	status	input_file	output_file	is_reviewed	review_notes	is_approved	approved_notes	is_email_sent
    # For now, write the status of execution to a csv file in output folder
    
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_file = f"data/output/run_status.csv"
    #with open(output_file, 'a') as f:
    
    print(f"Saving status for Customer ID: {cust_id}")
    print(f"Status: {status}")



# ==================== Function to format content in a markdown format  ====================

def format_content(content: str) -> str:
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
                        instructions="""You are an assistant that formats this markdown better without changing any of the content. The idea is to use this markdown in a presentation to executives. Need it to be visually appealing and easy to read."""
                )
                print(f"Created agent, ID: {agent.id}")


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

def save_research_report(container_name, blob_name, file_content):
    """
    Creates a new Research file for every customer in the Azure Blob Storage container 'lowtouch'
    """
    try:
        # Azure Blob Storage configuration
        account_url = os.getenv("ST_STORAGE_ACCOUNT_URL")
        
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

def o3call(prompt, reasoning_effort, tools=None, tool_choice="auto", response_format=None):
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
        "model": "o3",
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
    






###############     Define inputs       ############### 

context = """
Low-touch customers are those that don't have a dedicated sales rep. As a result, they don't get frequent outreaches and Staples is seeing a decline in spend from them. 
You have access to the three dataset below. The customer dataset has all the information about the account and the primary and secondary categories that they have bought. 
The column (PRIMARY_CAT_1) represents the primary category and the column (PRIMARY_CAT_1_Value) represents the potential revenue in that category. 
Secondary category are more granular than primary categories. They are the children of primary and so on. 
The columns like PRIMARY_CAT_2, SECONDARY_CAT_2 etc. represent the second category of items bough and their potential of revenue or loss from customer dataset. 
The column named Category with the value of Growth and Retention determine if the dollar values in PRIMARY_CAT_1_Value are potential of growth or decline. 
When doing research take into consideration whether they are a growth account or retention account. 
"""




# Define optional variables here- if they are commented out in lower sections, they will simply be blank strings.
few_shot_examples="No few shot examples provided"
provided_rules_and_policies="No provided rules and policies"






#########################################     Datasets       ######################################### 

# dataset1 is the main dataset for analysis
# It includes data for Lowtouch Customers who belong to 3 verticals: Commercial, Healthcare, Sled
# The Priority Reason for outreach is Retention or Growth across different Category of Products


# =============================================================================
#               Databricks Configuration and Connection
# ============================================================================= 


###########################    Using Databricks SQL Connector for Python     ########################

# Ensure these environment variables are set or replace with your actual values
# os.environ["DATABRICKS_SERVER_HOSTNAME"] = "<your-server-hostname>"
# os.environ["DATABRICKS_HTTP_PATH"] = "<your-http-path>"
# os.environ["DATABRICKS_TOKEN"] = "<your-personal-access-token>"


sql_i2a = "select * from " \
"(select * from snowflake_ml_dev.mlops.i2a_lowtouch WHERE VERTICAL =='Commercial' AND CUST_ID in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t) and cust_id in (10016125, 10047395, 10052129, 10194024, 10214965, 10220156, 10223539, 10240492, 1231878, 1429218, 1464442, 1498928, 1557042, 1572192, 1590135, 27034414, 27112442, 27247439, 27439750, 70103197 )) Comm " \
"UNION " \
"select * from (select * from snowflake_ml_dev.mlops.i2a_lowtouch WHERE VERTICAL =='Healthcare' AND CUST_ID in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t) and cust_id in (10017414, 10131399, 1568642, 70102823)) Health " \
"UNION " \
"SELECT * from (select * from snowflake_ml_dev.mlops.i2a_lowtouch WHERE VERTICAL =='Sled' AND CUST_ID in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t) and cust_id in (10252150, 1041385, 1044436, 1046110, 1066276, 1066693)) Sled"


sql_txn = "select * from snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t where cust_id in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch)"    

#sql_dnb = "select distinct cust_id, business_name, tradestyle, physical_street_address_1, physical_street_address_2, " \
#            "physical_city, physical_state, physical_zip, country_name,state_name, county_name, telephone, ceo_full_name, ceo_first_name, ceo_middle_initial, " \
#            "ceo_last_name, ceo_suffix, ceo_prefix, sales_volume, annual_sales_local_currency,currency_code, employees_total, employees_here, year_started, " \
#            "subsidiary_indicator, manufacturing_indicator, small_business_indicator, minority_owned_indicator,public_private_indicator, owns_rents, square_footage, " \
#            "global_ultimate_indicator, percent_growth_sales_3yr, percent_growth_employees_3yr, percent_growth_sales_5yr,percent_growth_employees_5yr, naics_codes, " \
#            "naics_description, white_collar_flag, wholesale_office_sup_buy_index, wholesale_sup_buy_index_code, new_indicator, media_response_indicator, website, business_status " \
#            "from snowflake_ml_dev.mlops.i2a_lowtouch_dnb_account_source_t " \
#            "where cust_id in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch)"

sql_dnb = "select distinct cust_id, business_name, website from snowflake_ml_dev.mlops.i2a_lowtouch_dnb_account_source_t where cust_id in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch)"

dataset1 = pd.DataFrame()  # Initialize an empty DataFrame for dataset1
df_txn = pd.DataFrame()    # Initialize an empty DataFrame for transaction data

logger.info("START: LOADING DATASETS")
logger.info("  Databricks Server: " + os.getenv("DATABRICKS_SERVER_HOSTNAME"))
logger.info("  HTTP Path: " + os.getenv("DATABRICKS_HTTP_PATH"))

try:
    with sql.connect(
        server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN")
    ) as connection:
        with connection.cursor() as cursor:
            # Accessing a table in an external catalog (e.g., Unity Catalog)
            
            cursor.execute(sql_i2a)                                                             # I2A Low Touch Customer Data - currently limited to 5 Customers
            result = cursor.fetchall()      
            dataset1 = pd.DataFrame(result, columns=[col[0] for col in cursor.description])     
            
            cursor.execute(sql_txn)                                                             # Transaction Data
            result = cursor.fetchall()
            df_txn = pd.DataFrame(result, columns=[col[0] for col in cursor.description])

            cursor.execute(sql_dnb)
            result = cursor.fetchall()
            df_dnb = pd.DataFrame(result, columns=[col[0] for col in cursor.description])

            cursor.close()
            connection.close()

except Exception as e:
    logger.error(f"Error connecting to Databricks or querying table: {e}")


logger.info("END: LOADING DATASETS")






# Define the rules and policies that the model should follow
provided_rules_and_policies="""
**Rule:** Use the provided datasets to analyze the Low Touch Customer Accounts and provide the Priority Reason and a detailed report for each customer.
Use only existing Primary and Secondary Categories for the Customers. Do not make up any categories or values or bundles or discounts or rebates or percent off or credit. 
Only mention categories in the customer dataset. Do not recommend any other products or categories that are not in customer dataset.
For each customer in the customer dataset, identify target categories by utilizing both Primary and Secondary Categories. 
Prioritize Primary Category 1 and Secondary Category 1 first, followed by Primary Category 2 and Secondary Category 2, maintaining this order of importance in the output.
Use Total Sales Amount for the Primary and Secondary Categories to show the historical sales amount for that Customer.
**Policy:** All recommendations should be future-facing (after """ + datetime.now().strftime("%Y-%m-%d") + """) and should not reference any past dates or events.
**Policy:** These customer are B2B customers so reference Staples Business (Staplesbusiness.com) instead of Staples.com.
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




logger.info("STARTING PROCESSING FOR LOW TOUCH CUSTOMERS")

# ==================== Main Execution Loop ====================
for cust in dataset1['CUST_ID']:
    logger.info("=" * 100)
    logger.info("START: PROCESSING CUSTOMER ID: %s", cust)
    logger.info("=" * 100)
    
    print("-" * 100)
    print(f"\n\n****************************         Customer ID: {cust}     ****************************")
    print("-" * 100)
    
    b_cust = f"{cust}"
    
    filtered_df = dataset1[dataset1['CUST_ID'] == b_cust]         # Filtered I2A Data for the specific customer
    filtered_txn_df = df_txn[df_txn['CUST_ID'] == b_cust]         # Filtered Transaction Data for the specific customer
    filtered_dnb_df = df_dnb[df_dnb['cust_id'] == b_cust]         # Filtered DNB Data for the specific customer
    
    City_code = filtered_df['DIV'].values[0] if not filtered_df.empty else None
    cust_name = filtered_df['CUST_NAME'].values[0] if not filtered_df.empty else None
    cust_industry = filtered_df['INDUSTRY'].values[0] if not filtered_df.empty else None
    cust_zip_code = filtered_df['CUST_ZIP'].values[0] if not filtered_df.empty else None
    cust_website = filtered_dnb_df['website'].values[0] if not filtered_dnb_df.empty else None
    business_name = filtered_dnb_df['business_name'].values[0] if not filtered_dnb_df.empty else None

    print("Customer Name : ", cust_name, "   and Website: ", cust_website)
    print("Customer Zip Code : ", cust_zip_code)
    print("Customer Industry : ", cust_industry)
   
    
    logger.info("START: GET STATE FROM ZIP CODE")
    cust_state = get_state_from_zip(cust_zip_code)          # Get the state code from the zip code
    logger.info("END: GET STATE FROM ZIP CODE")
    cust_state = cust_state.strip().replace(" ", "_").replace("-", "_").replace(".", "_").replace(",", "_").replace("'", "_") # remove any leading or trailing whitespace
    msg = ""
    
    # If zip_code is not in California, then use Bing Search data
    if cust_state == "CA":
        msg = "City Zip Code found in California, so not using external Web search data."
        tools = None  # No tools needed for California customers
        df_bing = pd.DataFrame()
        search_results , search_citations = "", ""    
        logger.info(msg)  
    else:
        msg=""
        query = f"Show me the latest news from past 3 months for {cust_name} or {business_name}, a company operating in the {cust_industry} industry. You could also search their website {cust_website} for the latest news."
        logger.info("START: BING SEARCH")
        search_results , search_citations = get_bing_search_results(query=query)  # Get Bing Search results
        #logger.info("Bing Search Results:", search_results)
        #logger.info("Bing Search Citations:", search_citations)
        logger.info("END: BING SEARCH")

    contacts = filtered_txn_df[['SF_ACCOUNT_ID', 'SF_CONTACT_ID', 'FIRST_NAME', 'LAST_NAME','EMAIL']].drop_duplicates()
    categories = filtered_df[['PRIMARY_CAT_1', 'PRIMARY_CAT_2', 'PRIMARY_CAT_3',
                              'SECONDARY_CAT_1', 'SECONDARY_CAT_2', 'SECONDARY_CAT_3']].drop_duplicates()
        
    ## Instructions and Tasks

    instructions_and_task="""
        You are an AI research assistant that helps the Staples B2B team research their low-touch customers and create hyper-personalized outreach report for the contacts. 
        Specify the priority reason for outreach, which can be either Retention or Growth.
        Analyze and Research the data for """ + cust_name + """ and create a research report for the customer and their contact details. 
        The research report and recommendations will be used to create hyper-personalized report for """ + cust_name + """. 
        Recommendations should be based on the Primary and Secondary Categories in the customer dataset for the categories to target that Customer.
        Provide a contact wise generic report in the output along with your other research output and recommendations. 
    """


    #instructions_and_task="""
    #    You are an AI research assistant that helps the Staples B2B team research their low-touch customers and create hyper-personalized outreach report for the contacts. 
    #    Specify the priority reason for outreach, which can be either Retention or Growth.
    #    Analyze and Research the data for """ + cust_name + """ and create a research report for the customer and their contact details. 
    #    The research report and recommendations will be used to create hyper-personalized report for """ + cust_name + """. 
    #    Provide a contact wise sample report in the output along with your other research output and recommendations. 
    #"""


    ################     Prompt for the Use Case       ###############

    prompt=f"""

    You are helping process input data into an output format.

    Here are the datasets:
    <datasets>
        <customer> {filtered_df} </customer>
        <transactions> {filtered_txn_df} </transactions>
        <dnb> {filtered_dnb_df} </dnb>
        <websearch> {search_results} </websearch>
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
    result = o3call(
            prompt=prompt,
            reasoning_effort="high",
            tool_choice="auto",
            response_format=Response
    )
    
    #print(result)
    logger.info("END: CALL REASONING MODEL FOR RESEARCH")

    # See the model's response to the input task.
    #logger.info(result.response_to_input_task)
    markdown_content = result.response_to_input_task.__str__()+ "\n\n"

    markdown_content += "\n\nPrimary and Secondary Categories : \n" + categories.__str__()+ "\n\n"
    markdown_content += "Contacts : \n" + contacts.__str__() + "\n\n"

    logger.info("START: FORMATTING CONTENT IN MARKDOWN FORMAT")
    formatted_content = format_content(markdown_content)  # Format the content in markdown format
    logger.info("END: FORMATTING CONTENT IN MARKDOWN FORMAT")

    # See the explanation of why the model made the decision it did. Note this is an open field of research- for numerical calculations, with step by step reasoning that arrives at an answer, this is reliable.
    #print("\n\nJustification : \n",result.justification)
    formatted_content += "\n\nJustification : \n" + result.justification.__str__() + "\n\n"

    # See the data points the model used to make the decision it did.
    #print("\n\nCitation : \n",result.citations)
    formatted_content += "\n\nCitation : \n" + result.citations.__str__() + "\n\n"

    formatted_content += "\n\nBing Search Results and Citation : \n" + msg + "\n" + search_results + "\n" + search_citations + "\n\n"
    
    #file name and path
    current_datetime = datetime.now()
    #research_file = "research_output\\" + current_datetime.strftime("%Y%m%d") + "\\" + b_cust + current_datetime.strftime("_%Y-%m-%d_%H-%M-%S")+".md"
    research_file = current_datetime.strftime("%Y%m%d") + "\\" + b_cust + "\\research_output\\" + b_cust + current_datetime.strftime("_%Y-%m-%d_%H-%M-%S")+".md"

    logger.info(f"START: SAVING RESEARCH REPORT: {research_file}")
    
    save_research_report(
        container_name="lowtouch",              # changed from "lowtouch" to "mld01blobcontainerne0"
        blob_name=research_file,
        file_content=formatted_content          # changed from markdown_content to formatted_content
    )
    logger.info(f"END: SAVING RESEARCH REPORT: {research_file}")
    logger.info("END: PROCESSING CUSTOMER ID: %s", cust)
    logger.info("=" * 100)
    
import os, sys, json, logging, asyncio
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from databricks import sql
from azure.storage.queue import QueueServiceClient, QueueClient
from azure.identity import DefaultAzureCredential



# Add the project root to Python path so we can import utils
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)
print("\nProject Root Path: ", project_root)

#from utils.azurequeuehelper import AzureQueueHelper
#from utils.models import AgentBatchRecord
#from utils.agentloghelper import AgentBatchRecord, createRecords, serializeRecords


async def get_data_from_databricks(query: str) -> pd.DataFrame:
    """
    Fetch data from Databricks using the provided SQL query.
    
    Args:
        query (str): The SQL query to execute.
    
    Returns:
        pd.DataFrame: DataFrame containing the results of the query.
    """
    try:
        # Load environment variables
        load_dotenv()
        
        # Connect to Databricks
        with sql.connect(
        server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN")
        ) as connection:
            with connection.cursor() as cursor:
                # Accessing a table in an external catalog (e.g., Unity Catalog)
                
                cursor.execute(query)                                                             # I2A Low Touch Customer Data - currently limited to 5 Customers
                result = cursor.fetchall()      
                df = pd.DataFrame(result, columns=[col[0] for col in cursor.description])  
        return df
    except Exception as e:
        logging.error(f"Error fetching data from Databricks: {e}")
        raise





async def main() -> None:
    
    # Creating a separate logger for this module
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)

    #logger.addHandler(file_handler)
    logger.addHandler(stream_handler)  

    BATCH_ID = datetime.now().strftime("%Y%m%d%H%M%S")
    
    logger.info("Getting data from Databricks...")
    try:
        sql_i2a = "select * from " \
        "(select * from snowflake_ml_dev.mlops.i2a_lowtouch WHERE VERTICAL =='Commercial' AND CUST_ID in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t) LIMIT 10) Comm " \
        "UNION " \
        "select * from (select * from snowflake_ml_dev.mlops.i2a_lowtouch WHERE VERTICAL =='Healthcare' AND CUST_ID in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t) LIMIT 5) Health " \
        "UNION " \
        "SELECT * from (select * from snowflake_ml_dev.mlops.i2a_lowtouch WHERE VERTICAL =='Sled' AND CUST_ID in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t) LIMIT 5) Sled"

        sql_txn = "select * from snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t where cust_id in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch)"    

        sql_dnb = "select distinct cust_id, business_name, website from snowflake_ml_dev.mlops.i2a_lowtouch_dnb_account_source_t where cust_id in (select distinct cust_id from snowflake_ml_dev.mlops.i2a_lowtouch)"

        df_i2a = await get_data_from_databricks(sql_i2a)
        df_txn = await get_data_from_databricks(sql_txn)
        df_dnb = await get_data_from_databricks(sql_dnb)

        logger.info("Data fetched successfully from Databricks")


        #print(df_i2a.head(5))
    except Exception as e:
        logger.error(f"Error fetching data from Databricks: {e}")
        return
    
 
    # create a connection to researchagentqueue01 azure storage queue
    # This queue will be used to send the research report for each customer to the Azure Storage Communication Queue


    queue_name = "researchagentqueue01"

    # Get connection string and validate
    connection_string = os.getenv("AZURE_QUEUE_CONNECTION_STRING")
    #print(f"\n\nQueue Connection String: {connection_string}")

    if not connection_string:
        logger.error("❌ AZURE_QUEUE_CONNECTION_STRING environment variable is not set")
        raise ValueError("AZURE_QUEUE_CONNECTION_STRING environment variable is required")

    logger.info(f"Initializing Azure Queue connection for queue: {queue_name}")

    try:

        credential = DefaultAzureCredential()
        queue_client = QueueClient(connection_string, queue_name, credential=credential)

    # Test the connection
        queue_properties = queue_client.get_queue_properties()
        logger.info(f"✅ Successfully connected to queue '{queue_name}'")
        
    except Exception as e:
        # If queue doesn't exist, try to create it
        if "QueueNotFound" in str(e):
            try:
                queue_service_client = QueueServiceClient.from_connection_string(connection_string)
                queue_service_client.create_queue(queue_name)
                queue_client = QueueClient.from_connection_string(connection_string, queue_name)
                logger.info(f"✅ Created and connected to new queue '{queue_name}'")
            except Exception as create_error:
                logger.error(f"❌ Failed to create queue '{queue_name}': {create_error}")
                raise
        else:
            logger.error(f"❌ Failed to connect to queue '{queue_name}': {e}")
            raise

    # ==================== Main Execution Loop ====================
    for cust in df_i2a['CUST_ID']:
        logger.info("PROCESSING CUSTOMER ID: %s", cust)
                
        b_cust = f"{cust}"
        
        filtered_df = df_i2a[df_i2a['CUST_ID'] == b_cust]               # Filtered I2A Data for the specific customer
        filtered_txn_df = df_txn[df_txn['CUST_ID'] == b_cust]           # Filtered Transaction Data for the specific customer
        filtered_dnb_df = df_dnb[df_dnb['cust_id'] == b_cust]           # Filtered DNB Data for the specific customer
        
        current_datetime = datetime.now()

        # convert the DataFrame to a dictionary and then to a JSON string
        # This is to ensure that the data is in a format that can be sent to the Azure Queue
        filtered_df_json = filtered_df.to_json(orient='records')
        filtered_txn_df_json = filtered_txn_df.to_json(orient='records')
        filtered_dnb_df_json = filtered_dnb_df.to_json(orient='records')

        # Create a json object for the customer with details from each DataFrame
        customer_data = {
            "batch_id": BATCH_ID,
            "run_date": current_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "agent_name": "dbDataAgent",
            "status": "S",
            "customer_id": b_cust,
            "i2a_data": filtered_df_json,
            "transactions_data": filtered_txn_df_json,
            "dnb_data": filtered_dnb_df_json
        }

        try:
            queue_client.send_message(json.dumps(customer_data))
            logger.info(f"Message pushed to queue '{queue_name}': {b_cust}")
        except Exception as e:
            logger.error(f"Error pushing message to queue '{queue_name}' for customer {b_cust}: {e}")
        





if __name__ == "__main__":
    asyncio.run(main())
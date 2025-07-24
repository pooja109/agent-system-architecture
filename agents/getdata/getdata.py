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
#print("\nProject Root Path: ", project_root)

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
       
        # Connect to Databricks
        with sql.connect(
        server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN")
        ) as connection:
            with connection.cursor() as cursor:
                # Accessing a table in an external catalog (e.g., Unity Catalog)
                
                cursor.execute(query)
                result = cursor.fetchall()      
                df = pd.DataFrame(result, columns=[col[0] for col in cursor.description])  
        return df
    except Exception as e:
        logging.error(f"Error fetching data from Databricks: {e}")
        raise




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







async def main() -> None:
    
     # Load environment variables
    load_dotenv()
        
    BATCH_ID = datetime.now().strftime("%Y%m%d%H%M%S")
    queue_name = "researchagentqueue01"

    # Creating a separate logger for this module
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)

    #logger.addHandler(file_handler)
    logger.addHandler(stream_handler)  

    
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

        sql_marketing = "select * from mld01_sandbox_de.ai_garage.marketing_category_hierarchy"

        sql_i2a_marketing = "select * from mld01_sandbox_de.ai_garage.i2a_to_marketing_category_map"

        df_i2a = await get_data_from_databricks(sql_i2a)
        df_txn = await get_data_from_databricks(sql_txn)
        df_dnb = await get_data_from_databricks(sql_dnb)
        df_marketing = await get_data_from_databricks(sql_marketing)
        df_i2a_marketing = await get_data_from_databricks(sql_i2a_marketing)
        
        logger.info("Data fetched successfully from Databricks")

        #print(df_i2a.head(5))
    except Exception as e:
        logger.error(f"Error fetching data from Databricks: {e}")
        return
    
    try:
        # Merge the marketing data and i2a marketing data on Marketing Category
        if not df_marketing.empty and not df_i2a_marketing.empty:
            df_marketing = pd.merge(df_marketing, df_i2a_marketing, on="Marketing_Primary_Category", how="outer")
            logger.info("Successfully merged marketing data.")
    except Exception as e:
        logger.error(f"Error merging marketing data: {e}")
        df_marketing = pd.DataFrame()

    # create a connection to researchagentqueue01 azure storage queue
    # This queue will be used to send the research report for each customer to the Azure Storage Communication Queue

    # Get connection string and validate
    connection_string = os.getenv("AZURE_QUEUE_CONNECTION_STRING")
    
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

    status_cols = [
    "batch_id",
    "run_date",
    "agent_name",
    "status",
    "customer_id",
    "customer_name",
    "created_at"
    ]
    
    
    
    # ==================== Main Execution Loop ====================
    for cust in df_i2a['CUST_ID']:
        logger.info("PROCESSING CUSTOMER ID: %s", cust)
                
        b_cust = f"{cust}"
        

        filtered_df = df_i2a[df_i2a['CUST_ID'] == b_cust]               # Filtered I2A Data for the specific customer
        filtered_txn_df = df_txn[df_txn['CUST_ID'] == b_cust]           # Filtered Transaction Data for the specific customer
        filtered_dnb_df = df_dnb[df_dnb['cust_id'] == b_cust]           # Filtered DNB Data for the specific customer

        cust_name = filtered_df['CUST_NAME'].values[0] if not filtered_df.empty else None

        if not filtered_df['PRIMARY_CAT_1'].values[0] is None :
            cat1 = filtered_df['PRIMARY_CAT_1'].values[0]
            filtered_df = filtered_df.merge(df_i2a_marketing[['I2A_Primary_Category', 'Marketing_Primary_Category']], left_on='PRIMARY_CAT_1', right_on='I2A_Primary_Category', how='left', suffixes=('', 'M_'))
            filtered_df.rename(columns={'Marketing_Primary_Category': 'MARKETING_CAT_1'}, inplace=True)
            filtered_df.drop(columns=['I2A_Primary_Category'], inplace=True)
            #print("Primary Category 1: ", cat1, " and Marketing Category 1: ", filtered_df['MARKETING_CAT_1'].values[0])
        else:
            cat1 = None
            filtered_df['MARKETING_CAT_1'] = None
            #print("No Primary Category 1 found for this customer.")

        if not filtered_df['PRIMARY_CAT_2'].values[0] is None :
            cat2 = filtered_df['PRIMARY_CAT_2'].values[0]
            filtered_df = filtered_df.merge(df_i2a_marketing[['I2A_Primary_Category', 'Marketing_Primary_Category']], left_on='PRIMARY_CAT_2', right_on='I2A_Primary_Category', how='left', suffixes=('', 'M_'))
            filtered_df.rename(columns={'Marketing_Primary_Category': 'MARKETING_CAT_2'}, inplace=True)
            filtered_df.drop(columns=['I2A_Primary_Category'], inplace=True)
            #print("Primary Category 2: ", cat2, " and Marketing Category 2: ", filtered_df['MARKETING_CAT_2'].values[0])
        else:
            cat2 = None
            filtered_df['MARKETING_CAT_2'] = None
            #print("No Primary Category 2 found for this customer.")

        if not filtered_df['PRIMARY_CAT_3'].values[0] is None:
            cat3 = filtered_df['PRIMARY_CAT_3'].values[0]
            filtered_df = filtered_df.merge(df_i2a_marketing[['I2A_Primary_Category', 'Marketing_Primary_Category']], left_on='PRIMARY_CAT_3', right_on='I2A_Primary_Category', how='left', suffixes=('', 'M_'))
            filtered_df.rename(columns={'Marketing_Primary_Category': 'MARKETING_CAT_3'}, inplace=True)
            filtered_df.drop(columns=['I2A_Primary_Category'], inplace=True)
            #print("Primary Category 3: ", cat3, " and Marketing Category 3: ", filtered_df['MARKETING_CAT_3'].values[0])
        else:
            cat3 = None
            filtered_df['MARKETING_CAT_3'] = None
            #print("No Primary Category 3 found for this customer.")

        # Filter the marketing data for the specific customer based on Primary Categories
        if cat1 is None and cat2 is None and cat3 is None:
            filtered_marketing_df = df_marketing[df_marketing['I2A_Primary_Category'].isnull()]
        else:
            filtered_marketing_df = df_marketing[(df_marketing['I2A_Primary_Category'] == cat1) | (df_marketing['I2A_Primary_Category'] == cat2) | (df_marketing['I2A_Primary_Category'] == cat3)]

        # Store only Marketing Secondary Category in the filtered_marketing_df. Remove any duplicate records based on 'Marketing Secondary Category'
        if not filtered_marketing_df.empty:
            filtered_marketing_df = filtered_marketing_df[['Marketing_Secondary_Category']]
            # remove duplicate records based on 'Marketing Secondary Category'
            filtered_marketing_df = filtered_marketing_df.drop_duplicates(subset=['Marketing_Secondary_Category'])
    


        current_datetime = datetime.now()

        # convert the DataFrame to a dictionary and then to a JSON string
        # This is to ensure that the data is in a format that can be sent to the Azure Queue
        filtered_df_json = filtered_df.to_json(orient='records') if not filtered_df.empty else "[]"
        filtered_txn_df_json = filtered_txn_df.to_json(orient='records') if not filtered_txn_df.empty else "[]"
        filtered_dnb_df_json = filtered_dnb_df.to_json(orient='records') if not filtered_dnb_df.empty else "[]"
        marketing_json = filtered_marketing_df.to_json(orient='records') if not filtered_marketing_df.empty else "[]"
        #i2a_marketing_json = df_i2a_marketing.to_json(orient='records') if not df_i2a_marketing.empty else "[]"

        run_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        # Create a json object for the customer with details from each DataFrame
        customer_data = {
            "batch_id": BATCH_ID,
            "run_date": run_date,
            "agent_name": "dbDataAgent",
            "status": "S",
            "customer_id": b_cust,
            "i2a_data": filtered_df_json,
            "transactions_data": filtered_txn_df_json,
            "dnb_data": filtered_dnb_df_json,
            "marketing_data": marketing_json
        }

        try:
            queue_client.send_message(json.dumps(customer_data))
            logger.info(f"Message pushed to queue '{queue_name}': {b_cust}")
        except Exception as e:
            logger.error(f"Error pushing message to queue '{queue_name}' for customer {b_cust}: {e}")
        

        # Update the status in Databricks
        status_vals = [(
            int(BATCH_ID),
            run_date,
            "dbDataAgent",
            "S",
            b_cust,
            cust_name,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )]

        await update_status_in_databricks(status_cols=status_cols, status_vals=status_vals, table_name="mld01_sandbox_de.ai_garage.email_communication_pipeline_dev", status="S")
        logger.info(f"Status updated in Databricks for customer {b_cust}")



if __name__ == "__main__":
    asyncio.run(main())
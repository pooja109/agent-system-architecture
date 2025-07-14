import os
import logging
import asyncio
import json
from typing import List
from dotenv import load_dotenv
from azure.core.exceptions import AzureError

from utils.azurequeuehelper import AzureQueueHelper
from utils.agentloghelper import AgentBatchRecord, createRecords, serializeRecords
from manager import LowTouchManager

# Load environment variables from .env file
load_dotenv()

# Configure logging (uncomment to enable debug output)
# logging.basicConfig(level=logging.INFO)

async def process_logic(data):
    """
    Handles the processing logic for each queue message.
    Logs success or failure, and handles exceptions.
    """
    logging.info(f"🔧 Processing: {data}")
    try:
        # Simulate processing logic; raise error if 'fail' key is present
        if data.get("fail"):
            raise ValueError("Simulated failure")
        else:
            mgr = LowTouchManager()
            await mgr.run(data)
            logging.info(f"✅ Successfully processed: {data}")
    except AzureError as ae:
        logging.error(f"Azure error occurred: {ae}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

async def main() -> None:
    """
    Main entry point for the queue processing script.
    Initializes the AzureQueueHelper, sends messages, and processes the queue in a loop.
    """
    # Initialize AzureQueueHelper with environment variables
    helper = AzureQueueHelper(
        connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        queue_name=os.getenv("AZURE_QUEUE_NAME"),
        dead_letter_queue=os.getenv("AZURE_DEAD_LETTER_QUEUE", None)
    )

    # Create and send agent records to the queue
    agentRecords = createRecords()
    for record in agentRecords:
        message = record.model_dump_json(indent=2)
        helper.send_message(message)
    logging.info(f"✅ {len(agentRecords)} messages sent to the queue.")

    # Continuously poll and process the queue
    while True:
        try:
            logging.info("🔄 Processing queue...")
            helper.process_queue(handler=process_logic, max_retry=3)
        except Exception as e:
            logging.error(f"Error processing queue: {e}")
        finally:
            logging.info("⏳ Waiting before next poll...")
            # Uncomment the following line to add a delay between polls
            # await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
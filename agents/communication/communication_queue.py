

import os
import logging
import asyncio
import json
from typing import List
from dotenv import load_dotenv
from azure.core.exceptions import AzureError

from agents.communication.config import LoggingConfig
from utils.azurequeuehelper import AzureQueueHelper
from utils.agentloghelper import AgentBatchRecord, createRecords, serializeRecords
from agents.communication.communication_manager import CommunicationManager

# Load environment variables from .env file
load_dotenv()
LoggingConfig.configure_logging()
# Configure logging (uncomment to enable debug output)
# logging.basicConfig(level=logging.INFO)

class CommunicationQueue:
    def __init__(self):
        self.mgr = CommunicationManager()
        # Initialize listener_queue from environment variables
        self.listener_queue = AzureQueueHelper(
            connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            queue_name=os.getenv("AZURE_COMMUNICATION_INPUT_QUEUE"),
            dead_letter_queue=os.getenv("AZURE_COMMUNICATION_INPUT_DLQ", None)
        )

    def send_test_message(self, payload: dict):
        # Create and send test agent records to the queue
        agentRecords = createRecords()
        for record in agentRecords:
            message = record.model_dump_json(indent=2)
            self.listener_queue.send_message(message)
        logging.info(f"✅ {len(agentRecords)} messages sent to the queue.")
    async def process_logic(self, data_list):
        """
        Handles the processing logic for a batch of queue messages.
        Logs success or failure, and handles exceptions.
        """
        logging.info(f"🔧 Processing batch of {len(data_list)} messages")
        try:
            await self.mgr.run(data_list)
            logging.info(f"✅ Successfully processed batch of {len(data_list)} messages")
        except AzureError as ae:
            logging.error(f"Azure error occurred: {ae}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")

    async def main(self):
        """
        Main entry point for the queue processing script.
        Initializes the AzureQueueHelper, sends messages, and processes the queue in a loop.
        """
        #self.send_test_message()

        # Continuously poll and process the queue
        while True:
            try:
                logging.info("🔄 Processing queue...")
                await self.listener_queue.process_queue(handler=self.process_logic, max_retry=20, batch_size=1)
            except Exception as e:
                logging.error(f"Error processing queue: {e}")
            finally:
                logging.info("⏳ Waiting before next poll...")
                await asyncio.sleep(2000)  # 2 seconds

if __name__ == "__main__":
    queue = CommunicationQueue()
    asyncio.run(queue.main())
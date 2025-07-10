# listener.py

import os
import time
import logging
from azure.storage.queue import QueueClient
from azure.core.exceptions import AzureError

logging.basicConfig(level=logging.INFO)

QUEUE_NAME = os.getenv("AZURE_QUEUE_NAME", "my-queue")
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))  # seconds

def process_message(message_text):
    # Replace with your actual processing logic
    logging.info(f"Processing message: {message_text}")

def main():
    try:
        queue_client = QueueClient.from_connection_string(
            conn_str=CONNECTION_STRING,
            queue_name=QUEUE_NAME
        )
        logging.info(f"Connected to Azure Queue: {QUEUE_NAME}")

        while True:
            messages = queue_client.receive_messages(messages_per_page=1, visibility_timeout=30)
            for msg_batch in messages.by_page():
                for msg in msg_batch:
                    try:
                        process_message(msg.content)
                        queue_client.delete_message(msg)
                    except Exception as e:
                        logging.error(f"Failed to process message: {e}")
            time.sleep(POLL_INTERVAL)

    except AzureError as ae:
        logging.error(f"Azure error occurred: {ae}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()

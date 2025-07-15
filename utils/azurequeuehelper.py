import asyncio
import os
import json
import logging
import inspect
from azure.storage.queue import QueueClient
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class AzureQueueHelper:
    def __init__(self, connection_string: str, queue_name: str, dead_letter_queue: str = None, storage_account: str = None):
        self.queue_name = queue_name
        self.dead_letter_client = None
        self.client = None

        # Try to use connection string if provided
        if connection_string:
            try:
                self.client = QueueClient.from_connection_string(connection_string, queue_name)
                # Test the client to see if key-based auth is permitted
                _ = self.client.get_queue_properties()
            except AzureError as e:
                if "Key based authentication is not permitted" in str(e):
                    logger.warning("Key-based authentication not permitted. Falling back to DefaultAzureCredential.")
                    self.client = None
                else:
                    raise

        # If client is still None, use DefaultAzureCredential
        if self.client is None:
            # storage_account param or env var required for URL
            if not storage_account:
                storage_account = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
            if not storage_account:
                raise ValueError("Storage account name must be provided via storage_account param or AZURE_STORAGE_ACCOUNT_NAME env var when using Azure AD authentication.")
            queue_url = f"https://{storage_account}.queue.core.windows.net"
            self.client = QueueClient(account_url=queue_url, queue_name=queue_name, credential=DefaultAzureCredential())

        # Dead letter queue
        if dead_letter_queue:
            if connection_string:
                try:
                    self.dead_letter_client = QueueClient.from_connection_string(connection_string, dead_letter_queue)
                    _ = self.dead_letter_client.get_queue_properties()
                except AzureError as e:
                    if "Key based authentication is not permitted" in str(e):
                        logger.warning("Key-based authentication not permitted for dead letter queue. Falling back to DefaultAzureCredential.")
                        self.dead_letter_client = None
                    else:
                        raise
            if self.dead_letter_client is None:
                if not storage_account:
                    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
                dead_letter_url = f"https://{storage_account}.queue.core.windows.net"
                self.dead_letter_client = QueueClient(account_url=dead_letter_url, queue_name=dead_letter_queue, credential=DefaultAzureCredential())

    def send_message(self, payload):
        try:
            if isinstance(payload, str):
                message_text = payload  # Already a string, use as-is
            else:
                message_text = json.dumps(payload)  # Serialize dict/list/etc
            
            self.client.send_message(message_text)
            logger.info(f"📤 Sent message to '{self.queue_name}': {payload}")
        except (TypeError, AzureError) as e:
            logger.error(f"❌ Failed to send message: {e}")
            raise

    def receive_messages(self, max_messages=16, visibility_timeout=30):
        try:
            return self.client.receive_messages(messages_per_page=max_messages, visibility_timeout=visibility_timeout)
        except AzureError as e:
            logger.error(f"❌ Failed to receive messages: {e}")
            return []

    async def process_queue(self, handler, max_retry=3, batch_size=8):
        messages = self.receive_messages(max_messages=batch_size)

        for msg_batch in messages.by_page():
            msg_list = []
            msg_objs = []
            for msg in msg_batch:
                try:
                    data = json.loads(msg.content)
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Invalid JSON, deleting: {msg.content}")
                    self.client.delete_message(msg)
                    continue

                if msg.dequeue_count > max_retry:
                    logger.warning(f"🚫 Max retries reached for message: {msg.content}")
                    if self.dead_letter_client:
                        self.dead_letter_client.send_message(msg.content)
                    self.client.delete_message(msg)
                    continue

                msg_list.append(data)
                msg_objs.append(msg)

            if msg_list:
                logger.info(f"Calling handler for batch of {len(msg_list)} messages.")
                try:
                    if inspect.iscoroutinefunction(handler):
                        await handler(msg_list)
                    else:
                        handler(msg_list)
                    # Only delete messages if handler succeeds
                    for msg in msg_objs:
                        self.client.delete_message(msg)
                except Exception as e:
                    logger.error(f"❌ Error in handler: {e}. Batch will retry.")


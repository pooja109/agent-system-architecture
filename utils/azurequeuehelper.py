import os
import json
import logging
from azure.storage.queue import QueueClient
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class AzureQueueHelper:
    def __init__(self, connection_string: str, queue_name: str, dead_letter_queue: str = None):
        self.queue_name = queue_name
        self.client = QueueClient.from_connection_string(connection_string, queue_name)
        self.dead_letter_client = None
        if not connection_string:
            self.client = QueueClient(
                f"https://{queue_name}.queue.core.windows.net",
                credential=DefaultAzureCredential()
            )
        if dead_letter_queue:
            self.dead_letter_client = QueueClient.from_connection_string(connection_string, dead_letter_queue)

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

    def process_queue(self, handler, max_retry=3):
        messages = self.receive_messages()

        for msg_batch in messages.by_page():
            for msg in msg_batch:
                try:
                    data = json.loads(msg.content)
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Invalid JSON, deleting: {msg.content}")
                    self.client.delete_message(msg)
                    continue

                try:
                    if msg.dequeue_count > max_retry:
                        logger.warning(f"🚫 Max retries reached for message: {msg.content}")
                        if self.dead_letter_client:
                            self.dead_letter_client.send_message(msg.content)
                        self.client.delete_message(msg)
                        continue

                    handler(data)
                    self.client.delete_message(msg)

                except Exception as e:
                    logger.error(f"❌ Error in handler: {e}. Message will retry.")


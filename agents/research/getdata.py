import os, sys, json, logging, asyncio
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from databricks import sql

##############      WIP         #################

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../utils')))
print("Utils Path: ",os.path.abspath(os.path.join(os.path.dirname(__file__), '../../utils')))


from utils import azureblobhelper, azurequeuehelper

from utils.azurequeuehelper import AzureQueueHelper
from utils.agentloghelper import AgentBatchRecord, createRecords, serializeRecords


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

    print("🔄 Processing queue...", os.getenv("AZURE_STORAGE_CONNECTION_STRING"), ", ", os.getenv("AZURE_QUEUE_NAME"), ", ", os.getenv("AZURE_DEAD_LETTER_QUEUE", None))


if __name__ == "__main__":
    asyncio.run(main())
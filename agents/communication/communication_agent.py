import asyncio
import logging
import traceback
import os
import sys
import time
import re
import json
from dotenv import load_dotenv
from colorama import Fore, Back, Style, init
from datetime import datetime


from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings, AzureAIAgentThread
from azure.ai.agents.models import (
    ResponseFormatJsonSchema,
    ResponseFormatJsonSchemaType,
)
import agents.sk_email_gen_agent as sk_email_gen_agent
import agents.sk_email_review_agent as sk_email_review_agent
import agents.sk_data_extractor_agent as sk_data_extractor_agent
import agents.sk_emailpercontact_gen_agent as sk_emailpercontact_gen_agent

from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.contents import ChatHistory
from semantic_kernel.agents.orchestration.group_chat import StringResult,MessageResult,GroupChatManager,BooleanResult
from semantic_kernel.agents.orchestration.tools import structured_outputs_transform

from azure.storage.blob.aio import BlobServiceClient
from azure.identity.aio import DefaultAzureCredential
from models import EvaluationFeedback
from pydantic import BaseModel, Field
from typing import Literal
from models import EmailTask, ResearchOutput, EmailDrafts,MultiContactEmailTask, ContactEmail



sys.stderr = open("error_log.txt", "w", encoding="utf-8")

# Add the parent directory to the Python path to find the agents module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)
# Remove per-module logger.setLevel, addHandler, and formatter setup
# Logging should be configured only in the __main__ block

def evaluate_score(feedback: EvaluationFeedback) -> Literal["pass", "fail"]:
        bool_fields = [
            feedback.profanity,
            feedback.bias,
            feedback.misleading_claims,
            feedback.aggressive_language,
            feedback.privacy_violation,
            feedback.tone_misalignment,
            feedback.sensitive_topics,
        ]
        # If all are False, then pass; else fail
        return "pass" if not any(bool_fields) else "fail"

load_dotenv()




def custom_input_transform(input_message: EmailTask) -> ChatMessageContent:
    return ChatMessageContent(role=AuthorRole.USER, content=input_message.model_dump_json())


# def read_from_source(filename: str) -> str:
#     filepath = os.path.join("source", filename)
#     with open(filepath, "r", encoding="utf-8") as f:
#         return f.read()
def read_from_source(folder: str, filename: str) -> str:
    filepath = os.path.join(folder, filename)
    if not os.path.exists(folder):
        logger.warning("Warning: Folder '%s' does not exist. Returning empty string.", folder)
        return ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("Warning: File '%s' not found. Returning empty string.", filepath)
        return ""
    except Exception as e:
        logger.error("Error reading file '%s': %s. Returning empty string.", filepath, e)
        return ""
# Initialize colorama for cross-platform colored terminal output
init(autoreset=True)



def save_string_to_file(folder: str, content, filename: str) -> None:
    filepath = os.path.join(folder, filename)
    if hasattr(content, "content"):
        content = content.content
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

async def save_string_to_blob(container_client, folder: str, blob_name: str, content) -> None:
    """Save a string as a blob in Azure Blob Storage, under a specified folder, and log the time taken."""
    start_time = time.time()
    if folder and not folder.endswith("/"):
        folder = folder + "/"
    full_blob_name = f"{folder}{blob_name}" if folder else blob_name
    try:
        # Ensure content is a string before uploading
        if not isinstance(content, str):
            # If it's a Pydantic model, use .model_dump() to get a dict
            if hasattr(content, 'model_dump'):
                content = json.dumps(content.model_dump(), ensure_ascii=False, indent=2)
            else:
                content = json.dumps(content, ensure_ascii=False, indent=2)
        blob_client = container_client.get_blob_client(full_blob_name)
        await blob_client.upload_blob(content, overwrite=True)
        elapsed = time.time() - start_time
        logger.info("Saved content to blob: %s in %.3f seconds", full_blob_name, elapsed)
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("Failed to save to blob %s after %.3f seconds: %s", full_blob_name, elapsed, e)

def parse_input(json_str, model_class):
    try:
        return model_class.model_validate_json(json_str)
    except Exception:
        return None

async def output_blob_exists(container_client, blob_name):
    blob_client = container_client.get_blob_client(blob_name)
    try:
        await blob_client.get_blob_properties()
        return True
    except Exception:
        return False

async def read_from_blob(container_client, blob_name):
    """
    Asynchronously read the content of a blob from Azure Blob Storage.
    
    """
    blob_client = container_client.get_blob_client(blob_name)
    stream = await blob_client.download_blob()
    file_content = await stream.readall()
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8")
    customer_research = file_content if file_content else ""
    return customer_research

def is_attribute_present(obj, attr_name, logger=logger):
    """
    Logs whether a given attribute exists and is non-empty on the provided object.
    Returns True if present and non-empty, else False.
    """
    if obj and hasattr(obj, attr_name):
        attr_value = getattr(obj, attr_name)
        if attr_value:
            logger.info("%s%s generated: value %s", Fore.CYAN, attr_name, Style.RESET_ALL)
            return True
        else:
            logger.info("%sNo %s generated for this task.%s", Fore.CYAN, attr_name, Style.RESET_ALL)
            return False
    else:
        logger.info("%sNo %s attribute found in response object.%s", Fore.CYAN, attr_name, Style.RESET_ALL)
        return False

async def main():
    """Main function to run the agents."""    
    total_start_time = time.time()
    ACCOUNT_URL = os.getenv("AZURE_STORAGE_ACCOUNT_URL")  # e.g. "https://<account>.blob.core.windows.net"
    CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    FOLDER_NAME = os.getenv("AZURE_STORAGE_INPUT_FOLDER_NAME", "")  # Optional default
    OUTPUT_FOLDER_NAME = os.getenv("AZURE_STORAGE_OUTPUT_FOLDER_NAME", "communication_output/")  # Optional default
    OUTPUT_CUSTOM_FOLDER = os.getenv("AZURE_STORAGE_OUTPUT_CUSTOM_FOLDER", "")
    AZURE_STORAGE_OUTPUT_OVERWRITE = os.getenv("AZURE_STORAGE_OUTPUT_OVERWRITE", "False").lower() == "true"

    OUTPUT_FOLDER_PREFIX = ""
    if(OUTPUT_CUSTOM_FOLDER):
        OUTPUT_FOLDER_PREFIX = OUTPUT_CUSTOM_FOLDER
    else:
        OUTPUT_FOLDER_PREFIX = datetime.now().strftime("%Y%m%d")
    
    # Initialize BlobServiceClient
    #blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    # Use DefaultAzureCredential for Entra ID auth
    credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(account_url=ACCOUNT_URL, credential=credential)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    prefix = FOLDER_NAME
    #customer_id = "1875782_2025-06-22_19-32-51"
    #customer_research = read_from_source("source",f"{customer_id}.md")
    sender_details = """Sender details : 
        Victoria Grant
        Manager, Account Expert Team
        On behalf of the Staples Expert Team
        Staplesexpertteam@staples.com
        """
    max_iterations = 2
    agent_creation_start_time = time.time()
    logger.info("%s🔄 Creating agents in parallel...%s", Fore.YELLOW, Style.RESET_ALL)
    # Create agents using the provided functions
    data_extractor_agent,email_generator_agent,email_review_agent,per_contact_email_agent = await asyncio.gather(
            sk_data_extractor_agent.get_data_agent(),
            sk_email_gen_agent.get_email_agent(),
            sk_email_review_agent.get_email_review_agent(),
            sk_emailpercontact_gen_agent.get_email_agent(),
        )
    agent_creation_duration = time.time() - agent_creation_start_time
    logger.info("%s✅ All agents created successfully!%s", Fore.GREEN, Style.RESET_ALL)
    logger.info("%s⏱️  Agent creation time: %.3f seconds%s", Fore.CYAN, agent_creation_duration, Style.RESET_ALL)
    #task = ChatMessageContent(role=AuthorRole.USER, content=input_obj.model_dump_json())
    # read from input folder and process all files and create a task for each file
    blob_list = container_client.list_blobs(name_starts_with=prefix)
    #async for blob in container_client.list_blobs(name_starts_with=FOLDER_NAME):
    try:
        async for blob in blob_list:
            filename = blob.name[len(prefix):] if blob.name.startswith(prefix) else blob.name
            blob_processing_start_time = time.time()
            if filename.endswith(".md"): 
                # For Azure Blob Storage, split on '/' to get the last part (the file name)
                base_filename = filename.split("/")[-1]
                # Remove the extension
                base_filename_no_ext = base_filename.rsplit(".", 1)[0]
                # Now split by '_' to get the customer_id
                customer_id = base_filename_no_ext.split("_")[0]
                customer_research = await read_from_blob(container_client, blob.name)
                if sender_details:
                    customer_research = customer_research + "\n\n" + sender_details
                output_folder_path = f"{OUTPUT_FOLDER_PREFIX}/{customer_id}/{OUTPUT_FOLDER_NAME}"
                output_blob_name = f"{output_folder_path}{customer_id}_feedback.json"
                if not AZURE_STORAGE_OUTPUT_OVERWRITE and await output_blob_exists(container_client, output_blob_name):
                    logger.info("%sSkipping %s as output already exists: %s%s", Fore.YELLOW, filename, output_blob_name, Style.RESET_ALL)
                    continue
                input_obj = EmailTask(
                    input="generate email for customer using the context data provided in instructions in the prompt",
                    draft_email="",
                    current_agent_name="User",
                    customer_id=customer_id,
                    customer_research=customer_research,  # Read customer research from file
                )
                task = ChatMessageContent(role=AuthorRole.USER, content=input_obj.model_dump_json())
                logger.info("%sProcessing file: %s%s", Fore.YELLOW, filename, Style.RESET_ALL)

                # Initialize lists to accumulate drafts and review comments for this file
                email_drafts = []
                review_comments_list = []

                try:
                    thread: AzureAIAgentThread | None = None
                    # Prepare KernelArguments to pass customer_research
                    #kernelargs = KernelArguments(customer_research=customer_research)
                    data_extractor_start = time.time()
                    response = await data_extractor_agent.get_response(messages=task, thread=thread)
                    data_extractor_duration = time.time() - data_extractor_start
                    logger.info("%sData extractor time: %.3f seconds%s", Fore.MAGENTA, data_extractor_duration, Style.RESET_ALL)
                    #logger.info("# %s: %s", response.name, response)
                    thread = response.thread
                    logger.info("%sStart Thread id: %s%s", Fore.GREEN, thread.id, Style.RESET_ALL)
                    research_output = parse_input(response.message.content, ResearchOutput)
                    customer_id = research_output.customer_id if research_output and hasattr(research_output, 'customer_id') else customer_id
                    review_value = None
                    email_drafts_obj = EmailDrafts(drafts=email_drafts, evaluations=review_comments_list)
                    review_iteration_start = time.time()
                    draft_email = ""  # Start with empty draft for the first iteration
                    review_comments = None
                    i = None
                    for i in range(max_iterations):  # review for max iterations
                        # Generate email draft
                        email_input_data = EmailTask(
                            input="Generate email with the context data provided",  # or the correct input string
                            draft_email=draft_email,
                            current_agent_name="Email_Assistant",  # or the correct agent name
                            customer_id=customer_id,
                            extracted_input=research_output,
                            review_comments=review_comments
                        )
                        email_input_task = ChatMessageContent(role=AuthorRole.USER, content=email_input_data.model_dump_json())
                        email_generation_start = time.time()
                        email_agent_response = await email_generator_agent.get_response(messages=email_input_task, thread=thread)
                        #logger.info("# %s: %s", email_agent_response.name, email_agent_response)
                        email_generation_duration = time.time() - email_generation_start
                        logger.info("%sEmail generation time: %.3f seconds%s", Fore.MAGENTA, email_generation_duration, Style.RESET_ALL)
                        # Parse the response to get the draft_email from EmailTask
                        email_agent_response_obj = parse_input(email_agent_response.message.content, EmailTask)
                        draft_email = email_agent_response_obj.draft_email if email_agent_response_obj else None
                        # Add new draft to the list
                        email_drafts.append(draft_email)
                        # Review the draft
                        email_input_data.input = "Review email using the context data provided"  # or the correct input string
                        email_input_data.draft_email = draft_email
                        review_start = time.time()
                        email_review_task = ChatMessageContent(role=AuthorRole.USER, content=email_input_data.model_dump_json())
                        email_review_response = await email_review_agent.get_response(messages=email_review_task, thread=thread)
                        #logger.info("# %s: %s", email_review_response.name, email_review_response)
                        review_duration = time.time() - review_start
                        logger.info("%sEmail review time: %.3f seconds%s", Fore.MAGENTA, review_duration, Style.RESET_ALL)
                        review_comments = parse_input(email_review_response.message.content, EvaluationFeedback)
                        email_input_data.review_comments = review_comments
                        review_comments_list.append(review_comments)
                        email_drafts_obj.add_draft(draft_email, review_comments)
                        review_value = review_comments.score if review_comments else None

                        logger.info("%s%s***** Review Iteration %d Result *****%s", Fore.GREEN, Style.BRIGHT, i+1, Style.RESET_ALL)
                        logger.info("%s%s%s", Fore.GREEN, review_value, Style.RESET_ALL)
                        if str(review_value).strip().upper() == "PASS":
                            logger.info("%sReview complete with YES. for customer_id: %s%s", Fore.CYAN, customer_id, Style.RESET_ALL)
                            await save_string_to_blob(container_client, output_folder_path, f"{customer_id}_email.html", draft_email)
                            await save_string_to_blob(container_client, output_folder_path, f"{customer_id}_research_output.json", email_input_data.extracted_input)
                            break
                        elif i == (max_iterations-1):
                            logger.info("%s Review complete with %s for customer_id:%s%s", Fore.CYAN,review_value, customer_id, Style.RESET_ALL)
                            await save_string_to_blob(container_client, output_folder_path, f"{customer_id}_email_{review_value}.html", draft_email)
                            await save_string_to_blob(container_client, output_folder_path, f"{customer_id}_research_output.json", email_input_data.extracted_input)
                            continue
                    review_iteration_duration = time.time() - review_iteration_start
                    logger.info("%s⏱️  Review loop completed after %d iteration(s) in %.3f seconds%s", Fore.MAGENTA, (i + 1) if i is not None else 0, review_iteration_duration, Style.RESET_ALL)
                    #START : generate follow up emails and contact specific emails
                    # Only generate contact-specific emails if input_email is present and non-empty
                    contact_list = getattr(research_output, 'contact_list', None)
                    if draft_email and contact_list and len(contact_list) > 1:
                        multi_contact_input = MultiContactEmailTask(
                            input="Generate contact-specific emails and follow-ups for each contact using the input email provided.",
                            input_email=draft_email,
                            customer_id=customer_id,
                            contact_emails=[],  # Let the agent populate this
                            contact_list=contact_list,
                            review_comments=review_comments,
                            customer_research=customer_research
                        )
                        per_contact_task = ChatMessageContent(role=AuthorRole.USER, content=multi_contact_input.model_dump_json())
                        per_contact_email_start = time.time()
                        per_contact_email_response = await per_contact_email_agent.get_response(messages=per_contact_task, thread=thread)
                        per_contact_email_duration = time.time() - per_contact_email_start
                        logger.info("%sContact-specific email generation time: %.3f seconds%s", Fore.MAGENTA, per_contact_email_duration, Style.RESET_ALL)
                        per_contact_email_obj = parse_input(per_contact_email_response.message.content, MultiContactEmailTask)
                        if is_attribute_present(per_contact_email_obj, 'contact_emails'):
                            for idx, contact_email in enumerate(per_contact_email_obj.contact_emails, 1):
                                await save_string_to_blob(
                                    container_client,
                                    output_folder_path,
                                    f"{customer_id}_contact_{idx}_email.html",
                                    contact_email.draft_email
                                )
                                for fidx, followup in enumerate(contact_email.follow_up_emails, 1):
                                    await save_string_to_blob(
                                        container_client,
                                        output_folder_path,
                                        f"{customer_id}_contact_{idx}_followup_{fidx}.html",
                                        followup
                                    )
                        else:
                            logger.info(
                                "%sSkipping contact-specific email generation for customer_id: %s. Reason: No contact_emails found in response.%s",
                                Fore.YELLOW, customer_id, Style.RESET_ALL
                            )
                    else:
                        logger.info(
                            "%sSkipping contact-specific email generation for customer_id: %s. Reason: Only one contact or draft_email missing. draft_email: %s%s",
                            Fore.YELLOW, customer_id, draft_email, Style.RESET_ALL
                        )
                    #END : generate follow up emails and contact specific emails

                    # start: generate contact specific emails:
                    

                    await save_string_to_blob(container_client, output_folder_path, customer_id+"_feedback.json", email_drafts_obj.model_dump())

                    logger.info("%sEnd Thread id: %s", Fore.GREEN, Style.RESET_ALL)
                except Exception as e:
                    error_time = time.time() - total_start_time
                    logger.exception("%s❌ Error in orchestrator after %.3fs: %s%s", Fore.RED, error_time, e, Style.RESET_ALL)
                    raise
            blob_processing_duration = time.time() - blob_processing_start_time
            logger.info("%s⏱️  Blob processing time: %.3f seconds%s", Fore.CYAN, blob_processing_duration, Style.RESET_ALL)
            # Print total execution time summary
            total_duration = time.time() - total_start_time
            logger.info("%s Total time taken so far:          %.3fs%s", Fore.WHITE, total_duration, Style.RESET_ALL)
    
    except Exception as e:
        logger.exception("%sError while iterating blobs: %s%s", Fore.RED, e, Style.RESET_ALL)
    finally:
        # Clean up resources to prevent unclosed client sessions
        try:
            await blob_service_client.close()
            await credential.close()
        except Exception as cleanup_error:
            logger.exception("%s⚠️  Error during cleanup: %s%s", Fore.RED, cleanup_error, Style.RESET_ALL)        
    total_duration = time.time() - total_start_time
    logger.info("%s Total time taken:          %.3fs%s", Fore.WHITE, total_duration, Style.RESET_ALL)
    
if __name__ == "__main__":
    # Configure root logger only once here
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            # Uncomment below for file logging in production
            #logging.FileHandler("app.log", encoding="utf-8"),
        ]
    )
    # Suppress Azure SDK info/debug logs
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    asyncio.run(main())
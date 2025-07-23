"""
Communication Manager for orchestrating the email generation workflow.
"""
import time
import logging
import sys
import os
from colorama import Fore, Style
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from config import CommunicationConfig
from blob_util import BlobUtil
from agent_manager import AgentManager


from typing import Optional, List
from models import (
    CommunicationOutput, Email, EmailTask, ResearchOutput, EvaluationFeedback, 
    EmailDrafts, MultiContactEmailTask, ContactEmail
)

from utils.azurequeuehelper import AzureQueueHelper
from utils.models import AgentBatchRecord


logger = logging.getLogger(__name__)

class CommunicationManager:

    
    
    
    def __init__(self):
        self.config = CommunicationConfig()
        self.blob_util = BlobUtil(self.config.account_url, self.config.container_name)
        self.agent_manager = AgentManager()
        self.agents_created = False
        self.queue_helper = AzureQueueHelper(self.config.connection_string, 
                                             self.config.queue_name, 
                                             self.config.dead_letter_queue)

    @property
    def queue_helper_instance(self):
        """Get the AzureQueueHelper instance for sending/receiving queue messages."""
        return self.queue_helper
    """Main manager class for the communication agent workflow."""

    @property
    def get_blob_util(self):
        """Get the BlobUtil instance for Azure Blob Storage operations."""
        return self.blob_util
    
    def send_communication_output_to_queue(self, customer_id, research_output, evaluation, contact_emails):
        """
        Create a CommunicationOutput object, serialize it to JSON, and send it to the Azure Storage Queue.
        Args:
            customer_id (str): The unique customer ID.
            research_output (ResearchOutput): The research output object.
            evaluation (EvaluationFeedback): The evaluation feedback object.
            contact_emails (List[ContactEmail]): List of ContactEmail objects.
        Returns:
            None
        """
        
        # Ensure contact_emails is always a list
        if contact_emails is None:
            contact_emails = []

        comm_output = CommunicationOutput(
            customer_id=customer_id,
            customer_name=research_output.customer_name,
            customer_zip=research_output.customer_zip,
            customer_state=research_output.customer_state,            
            final_evaluation=evaluation,
            contact_emails=contact_emails
        )

        message_json = comm_output.model_dump_json()
        #logger.info(f"📤 Sending message to queue for customer_id={customer_id}, message: {message_json} :END")
        self.queue_helper.send_message(message_json)
        logger.info(f"📤 CommunicationOutput sent to queue for customer_id={customer_id}")
        return comm_output
        
    def parse_input(self, input_data, model_class):
        """Parse input (dict or JSON string) to Pydantic model. Logs exception messages."""
        try:
            if isinstance(input_data, str):
                return model_class.model_validate_json(input_data)
            else:
                return model_class.model_validate(input_data)
        except Exception as e:
            logger.error(f"parse_input error: {e}")
            return None
    
    def is_attribute_present(self, obj, attr_name: str) -> bool:
        """Check if attribute exists and is non-empty on the provided object."""
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
    
    async def setup_agents(self):
        """Initialize all required agents."""
        if not self.agents_created:
            await self.agent_manager.create_agents()
            self.agents_created = True
    
    async def process_single_blob(self, blob, prefix: str) -> None:
        """Process a single blob file."""
        filename = blob.name[len(prefix):] if blob.name.startswith(prefix) else blob.name
        blob_processing_start_time = time.time()
        
        if not filename.endswith(".md"):
            return
        
        # Extract customer ID from filename
        base_filename = filename.split("/")[-1]
        base_filename_no_ext = base_filename.rsplit(".", 1)[0]
        customer_id = base_filename_no_ext.split("_")[0]
        
        # Read customer research from blob
        customer_research = await self.blob_util.read_from_blob(blob.name)
        if self.config.sender_details:
            customer_research = customer_research + "\n\n" + self.config.sender_details
        
        # Set up output paths
        output_folder_path = f"{self.config.output_folder_prefix}/{customer_id}/{self.config.output_folder_name}"
        output_blob_name = f"{output_folder_path}{customer_id}_feedback.json"
        
        # Check if output already exists
        logger.info("%sChecking if output exists: %s%s", Fore.YELLOW, output_blob_name, Style.RESET_ALL)
        if not self.config.output_overwrite and await self.blob_util.output_blob_exists(output_blob_name):
            logger.info("%sSkipping %s as output already exists: %s%s", Fore.YELLOW, filename, output_blob_name, Style.RESET_ALL)
            return
        
        # Create input object
        input_obj = EmailTask(
            input="generate email for customer using the context data provided in instructions in the prompt",
            draft_email=Email(subject="", body_html=""),
            current_agent_name="User",
            customer_id=customer_id,
            customer_research=customer_research,
        )
        
        logger.info("%sProcessing file: %s%s", Fore.YELLOW, filename, Style.RESET_ALL)
        
        # Process the email generation workflow
        await self._process_email_workflow(input_obj, customer_research, output_folder_path)
        
        blob_processing_duration = time.time() - blob_processing_start_time
        logger.info("%s⏱️  Blob processing time: %.3f seconds%s", Fore.CYAN, blob_processing_duration, Style.RESET_ALL)
    
    async def _process_email_workflow(self, input_obj: EmailTask, customer_research: str, output_folder_path: str):
        """Process the email generation workflow for a single customer."""
        agents = self.agent_manager.get_agents()
        data_extractor_agent, email_generator_agent, email_review_agent, per_contact_email_agent = agents
        
        email_drafts = []
        review_comments_list = []
        thread = None
        customer_id = input_obj.customer_id
        research_output=None
        
        try:
            # Data extraction
            task = ChatMessageContent(role=AuthorRole.USER, content=input_obj.model_dump_json())
            data_extractor_start = time.time()
            response = await data_extractor_agent.get_response(messages=task, thread=thread)
            data_extractor_duration = time.time() - data_extractor_start
            logger.info("%sData extractor time: %.3f seconds%s", Fore.MAGENTA, data_extractor_duration, Style.RESET_ALL)
            
            thread = response.thread
            logger.info("%sStart Thread id: %s%s", Fore.GREEN, thread.id, Style.RESET_ALL)
            research_output = self.parse_input(response.message.content, ResearchOutput)
            customer_id = research_output.customer_id if research_output and hasattr(research_output, 'customer_id') else customer_id
            
            # Email generation and review loop
            email_drafts_obj = EmailDrafts(drafts=email_drafts, evaluations=review_comments_list)
            review_iteration_start = time.time()
            draft_email = Email(subject="", body_html="")
            review_comments = None
            i = None
            
            for i in range(self.config.max_iterations):
                # Generate email draft
                email_input_data = EmailTask(
                    input="Generate email with the context data provided",
                    draft_email=draft_email,
                    current_agent_name="Email_Assistant",
                    customer_id=customer_id,
                    extracted_input=research_output,
                    review_comments=review_comments
                )

                email_input_task = ChatMessageContent(role=AuthorRole.USER, content=email_input_data.model_dump_json())
                email_generation_start = time.time()
                email_agent_response = await email_generator_agent.get_response(messages=email_input_task, thread=thread)
                email_generation_duration = time.time() - email_generation_start
                logger.info("%sEmail generation time: %.3f seconds%s", Fore.MAGENTA, email_generation_duration, Style.RESET_ALL)

                # Parse the response
                email_agent_response_obj = self.parse_input(email_agent_response.message.content, EmailTask)
                if email_agent_response_obj and email_agent_response_obj.draft_email:
                    draft_email = email_agent_response_obj.draft_email
                else:
                    draft_email = Email(subject="", body_html="")
                email_drafts.append(draft_email)

                # Review the draft
                email_input_data.input = "Review email using the context data provided"
                email_input_data.draft_email = draft_email
                review_start = time.time()
                email_review_task = ChatMessageContent(role=AuthorRole.USER, content=email_input_data.model_dump_json())
                email_review_response = await email_review_agent.get_response(messages=email_review_task, thread=thread)
                review_duration = time.time() - review_start
                logger.info("%sEmail review time: %.3f seconds%s", Fore.MAGENTA, review_duration, Style.RESET_ALL)

                review_comments = self.parse_input(email_review_response.message.content, EvaluationFeedback)
                email_input_data.review_comments = review_comments
                review_comments_list.append(review_comments)
                email_drafts_obj.add_draft(draft_email, review_comments)
                review_value = review_comments.score if review_comments else None

                logger.info("%s%s***** Review Iteration %d Result *****%s", Fore.GREEN, Style.BRIGHT, i+1, Style.RESET_ALL)
                logger.info("%s%s%s", Fore.GREEN, review_value, Style.RESET_ALL)

                if str(review_value).strip().upper() == "PASS":
                    logger.info("%sReview complete with %s. for customer_id: %s%s", Fore.CYAN,review_value, customer_id, Style.RESET_ALL)
                    await self.blob_util.save_string_to_blob(output_folder_path, f"{customer_id}_email.json", draft_email)
                    await self.blob_util.save_string_to_blob(output_folder_path, f"{customer_id}_email.html", "Subject: " + draft_email.subject + "<br>" + draft_email.body_html)
                    await self.blob_util.save_string_to_blob(output_folder_path, f"{customer_id}_research_output.json", email_input_data.extracted_input)
                    break
                elif i == (self.config.max_iterations-1):
                    logger.info("%s Review complete with %s for customer_id:%s%s", Fore.CYAN, review_value, customer_id, Style.RESET_ALL)
                    await self.blob_util.save_string_to_blob(output_folder_path, f"{customer_id}_email_{review_value}.html","Subject: " + draft_email.subject + "<br>" + draft_email.body_html)
                    await self.blob_util.save_string_to_blob(output_folder_path, f"{customer_id}_email_{review_value}.json", draft_email)
                    await self.blob_util.save_string_to_blob(output_folder_path, f"{customer_id}_research_output.json", email_input_data.extracted_input)
            
            review_iteration_duration = time.time() - review_iteration_start
            logger.info("%s⏱️  Review loop completed after %d iteration(s) in %.3f seconds%s", Fore.MAGENTA, (i + 1) if i is not None else 0, review_iteration_duration, Style.RESET_ALL)
            
            # Generate contact-specific emails
            contact_emails = await self._generate_contact_specific_emails(
                research_output=research_output,
                draft_email=draft_email,
                customer_id=customer_id,
                customer_research=customer_research,
                review_comments=review_comments,
                output_folder_path=output_folder_path,
                per_contact_email_agent=per_contact_email_agent,
                thread=thread
            )
            comm_output = self.send_communication_output_to_queue(
                customer_id=customer_id,
                research_output=research_output,
                evaluation=review_comments,
                contact_emails=contact_emails
            )
            
            # Save feedback
            await self.blob_util.save_string_to_blob(output_folder_path, customer_id+"_feedback.json", email_drafts_obj.model_dump())
            await self.blob_util.save_string_to_blob(output_folder_path, customer_id+"_comm_output.json", comm_output.model_dump())
            logger.info("%sEnd Thread id: %s", Fore.GREEN, Style.RESET_ALL)
            
        except Exception as e:
            logger.exception("%s❌ Error in email workflow: %s%s", Fore.RED, e, Style.RESET_ALL)
            raise
    
    async def _generate_contact_specific_emails(
        self,
        research_output,
        draft_email,
        customer_id,
        customer_research,
        review_comments,
        output_folder_path,
        per_contact_email_agent,
        thread
    ) -> Optional[List[ContactEmail]]:
        """Generate contact-specific emails if conditions are met."""
        contact_list = getattr(research_output, 'contact_list', None)
        if not draft_email:
            logger.info("%sSkipping contact-specific email generation for customer_id: %s. Reason: No draft_email provided.%s", Fore.YELLOW, customer_id, Style.RESET_ALL)
        elif contact_list and len(contact_list) >= 1:
            multi_contact_input = MultiContactEmailTask(
                input="Generate contact-specific emails and follow-ups for each contact using the input email provided.",
                input_email=draft_email,
                customer_id=customer_id,
                contact_emails=[],
                contact_list=contact_list,
                review_comments=review_comments
#                customer_research=customer_research
            )
            per_contact_task = ChatMessageContent(role=AuthorRole.USER, content=multi_contact_input.model_dump_json())
            per_contact_email_start = time.time()
            per_contact_email_response = await per_contact_email_agent.get_response(messages=per_contact_task, thread=thread)
            per_contact_email_duration = time.time() - per_contact_email_start
            logger.info("%sContact-specific email generation time: %.3f seconds%s", Fore.MAGENTA, per_contact_email_duration, Style.RESET_ALL)
            
            per_contact_email_obj = self.parse_input(per_contact_email_response.message.content, MultiContactEmailTask)
            if self.is_attribute_present(per_contact_email_obj, 'contact_emails'):
                for idx, contact_email in enumerate(per_contact_email_obj.contact_emails, 1):
    
                    subject = contact_email.email.subject if contact_email.email and hasattr(contact_email.email, 'subject') and contact_email.email.subject else ""
                    body_html = contact_email.email.body_html if contact_email.email and hasattr(contact_email.email, 'body_html') and contact_email.email.body_html else ""
                    html_content = f"Subject: {subject}<br>{body_html}"
                    await self.blob_util.save_string_to_blob(
                        output_folder_path,
                        f"{customer_id}_contact_{idx}_email.html",
                        html_content
                    )
                    for fidx, followup in enumerate(contact_email.follow_up_emails, 1):
                        subject = followup.subject if followup and hasattr(followup, 'subject') and followup.subject else ""
                        body_html = followup.body_html if followup and hasattr(followup, 'body_html') and followup.body_html else ""
                        html_content = f"Subject: {subject}<br>{body_html}"
                        await self.blob_util.save_string_to_blob(
                            output_folder_path,
                            f"{customer_id}_contact_{idx}_followup_{fidx}.html",
                            html_content
                        )
            else:
                logger.info(
                    "%sSkipping contact-specific email generation for customer_id: %s. Reason: No contact_emails found in response.%s",
                    Fore.YELLOW, customer_id, Style.RESET_ALL
                )
            return per_contact_email_obj.contact_emails
        else: #single contact # remove later
            logger.info(
                "%sSkipping contact-specific email generation for customer_id: %s. Reason: Only one contact or draft_email missing. draft_email: %s%s",
                Fore.YELLOW, customer_id, draft_email, Style.RESET_ALL
            )
            # get the contact_email from the draft_email if it exists
            contact = None
            if contact_list and isinstance(contact_list, list) and len(contact_list) > 0:
                contact = contact_list[0]

            contact_email = ContactEmail(
                contact_name=contact.full_name if contact else "Unknown",
                contact_email=contact.email if contact and hasattr(contact, 'email') else "Unknown",
                email=draft_email if draft_email else Email(subject="", body_html=""),
                follow_up_emails=[]
            )
            return [contact_email]

    async def run(self, data_list):
        """
        Main entry point to run the communication workflow for a batch of AgentBatchRecord objects.
        Each item in data_list is processed as a single customer.
        """
        total_start_time = time.time()
        try:
            await self.setup_agents()
            for data in data_list:
                try:
                    # Convert the data which is string to AgentBatchRecord
                    record = self.parse_input(data, AgentBatchRecord)
                    if record is None:
                        logger.error("%sInvalid AgentBatchRecord: %s%s", Fore.RED, data, Style.RESET_ALL)
                        continue
                    customer_id = record.cust_id
                    customer_research = record.agent_output
                    if self.config.sender_details:
                        customer_research = customer_research + "\n\n" + self.config.sender_details

                    output_folder_prefix = self.config.get_output_folder_prefix_from_run_date(record.run_date)
                    output_folder_path = f"{output_folder_prefix}/{customer_id}/{self.config.output_folder_name}"

                    # Create input object
                    input_obj = EmailTask(
                        input="generate email for customer using the context data provided in instructions in the prompt",
                        draft_email=Email(subject="", body_html=""),
                        current_agent_name="User",
                        customer_id=customer_id,
                        customer_research=customer_research,
                    )

                    logger.info("%sProcessing customer_id: %s%s", Fore.YELLOW, customer_id, Style.RESET_ALL)
                    # Check if output already exists
                    output_blob_name = f"{output_folder_path}{customer_id}_feedback.json"
                    logger.info("%sChecking if output exists: %s%s", Fore.YELLOW, output_blob_name, Style.RESET_ALL)
                    if not self.config.output_overwrite and await self.blob_util.output_blob_exists(output_blob_name):
                        logger.info("%sSkipping %s as output already exists: %s%s", Fore.YELLOW, customer_id, output_blob_name, Style.RESET_ALL)
                        continue
                    # Process the email generation workflow
                    await self._process_email_workflow(input_obj, customer_research, output_folder_path)
                except Exception as e:
                    logger.exception("%sError while processing customer_id %s: %s%s", Fore.RED, getattr(data, 'customer_id', 'unknown'), e, Style.RESET_ALL)
                    #TODO: add to dead letter queue or handle error
        finally:
            # Clean up resources
            await self.blob_util.close()
            pass

        total_duration = time.time() - total_start_time
        logger.info("%s Total time taken: %.3fs%s", Fore.WHITE, total_duration, Style.RESET_ALL)

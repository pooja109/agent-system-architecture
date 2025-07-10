from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence

from rich.console import Console

from agents import Runner, RunResult, TResponseInputItem, ItemHelpers, custom_span, gen_trace_id, trace

from .agents.emailoutline_agent import emailoutline_agent
from .agents.emailreviewer_agent import EvaluationFeedback, evaluate_score, emailreviewer_agent
from .agents.emailgenerator_agent import emailgenerator_agent
from .agents.structureresearchreport_agent import ContactDetails, ResearchReportInput, structuredresearchreport_agent
from .utils.azureblobhelper import AzureBlobHelper
#from .printer import Printer --> queueing / dbx mechanism not implemented yet

class LowTouchManager:
    """
    Orchestrates the low-touch email outreach flow:
    1. Structure research report
    2. Generate email outline
    3. Review email outline
    4. Generate final email
    """

    def __init__(self) -> None:
        self.console = Console()
        # self.printer = Printer(self.console)  # Uncomment when Printer is implemented
        self.blob_helper = AzureBlobHelper()
        self.input_prompt: str = ""
        self.input_items: list[TResponseInputItem] = []

    async def run(self, research_report: str) -> None:
        self.input_prompt = research_report
        self.input_items: list[TResponseInputItem] = [{"content": self.input_prompt, "role": "user"}]
        trace_id = gen_trace_id()
        feedback_iteration_count = 0
        with trace("Low-touch email outreach trace", trace_id=trace_id):
            self.console.print(f"Trace ID: {trace_id}")
            self.console.print("Starting low-touch email outreach...")

            # Step 1: Structure research report
            structured_report = await self._structure_report(self.input_prompt)
            
            structured_contacts: list[ContactDetails] = structured_report.final_output.contact_details
            self.console.print(f"Structured Contacts: {len(structured_contacts)} contacts found.")
            
            #todo - loop through each contact and generate emails
            if not structured_contacts:
                self.console.print("No contacts found in the research report. Exiting.")
                return
            
            while feedback_iteration_count < 3:
                 # Step 2: Generate email outline
                email_outline_result = await self._generate_email_outline()
                self.input_items = email_outline_result.to_input_list()
                latest_outline = ItemHelpers.text_message_outputs(email_outline_result.new_items)
                # Step 3: Review email outline
                evaluator_result = await self._review_email_outline()
                result = evaluator_result.final_output

                print(f"Evaluator score: {result.score}.....Evaluator feedback: {result.feedback}")

                print("Re-running with feedback")

                self.input_items.append({"content": f"Feedback: {result.feedback}", "role": "user"})
                feedback_iteration_count += 1

        # Optionally upload to Azure Blob Storage or handle further processing
        # await self.blob_helper.upload_blob("final_email.md", final_email.markdown_content.encode())

    async def _structure_report(self, query: str) -> ResearchReportInput:
        #self.printer.update_item("planning", "Planning searches...")
        structured_report = await Runner.run(
                structuredresearchreport_agent,
                self.input_items,
            )
        return structured_report.final_output_as(ResearchReportInput)
        # self.printer.update_item(
        #     "planning",
        #     f"Will perform {len(result.final_output.searches)} searches",
        #     is_done=True,
        # )
    
    async def _generate_email_outline(self) -> RunResult:
        # self.printer.update_item("generating_outline", "Generating email outline...")
        result = await Runner.run(
                emailoutline_agent,
                input_items=self.input_items,
            )
        # self.printer.update_item("generating_outline", "Email outline generated.", is_done=True)
        return result
    
    async def _review_email_outline(self, outline: str) -> EvaluationFeedback:
        # self.printer.update_item("reviewing_outline", "Reviewing email outline...")
       result = await Runner.run(emailreviewer_agent, self.input_items)
        # self.printer.update_item("reviewing_outline", "Email outline reviewed.", is_done=True)
       return result.final_output_as(EvaluationFeedback)
    
    async def _generate_final_email(self, outline: str) -> str:
        # self.printer.update_item("generating_email", "Generating final email...")
        result = await Runner.run(emailgenerator_agent, f"Outline: {outline}")
        # self.printer.update_item("generating_email", "Final email generated.", is_done=True)
        return result.final_output.markdown_content
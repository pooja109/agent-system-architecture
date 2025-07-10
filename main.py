from __future__ import annotations
import asyncio
from dataclasses import Field
import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI, AsyncOpenAI
from agents import Agent, Runner, trace, set_default_openai_client, set_tracing_disabled
from agents import Agent, ItemHelpers, Runner, TResponseInputItem, trace
from pydantic import BaseModel, Field
from typing import Literal
from utils.azureblobhelper import AzureBlobHelper

"""
This example shows the LLM as a judge pattern. The first agent generates an outline for a story.
The second agent judges the outline and provides feedback. We loop until the judge is satisfied
with the outline.
"""
load_dotenv()

azure_openai_client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
)

azure_responses_openai_client = AsyncOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    default_query={"api-version": "preview"},
    base_url=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

openai_client = azure_responses_openai_client # azure_openai_client
set_default_openai_client(openai_client)
set_tracing_disabled(True)

RESEARCH_REPORT_STRUCTURE_PROMPT = (
    "You are an expert B2B outreach agent. Your job is to analyze the provided research report and extract the following information:"
    "1. Contact details of all the contacts in the report (name, title, email)"
    "Return the extracted contact information in a structured format and also the entire report itself as-is in another field."
)

EMAIL_OUTLINE_PROMPT = (
    "You are an expert B2B outreach assistant. Your job is to draft hyper‑personalized emails using the provided customer data. Follow Maslow’s hierarchy:"
    "1. Physiological – address by name, reference title, company & industry."
    "2. Safety – mention timing or past engagement for relevance and trust."
    "3. Belonging – acknowledge industry challenges and align with their business environment."
    "4. Esteem – focus on the recipient’s role and how your solution supports their responsibilities and goals."
    "5. Self‑Actualization – share strategic insight that empowers their leadership and innovation."

    "Email requirements:"
    "- Max ~175 words"
    "- Professional yet friendly tone"
    "- Clear yet soft call-to-action (e.g., “Would you be open to a 15‑min chat next week?”)"

    "Use the research report given as inputs to build each layer of personalization. Generate only the email body as plain text. Select the first contact from the research report to send the email to."
)

REVIEW_PROMPT = (
    "You are a content safety reviewer for business communications. Evaluate the provided email for violations of content safety, brand compliance, or tone misalignment."
    "Return a structured safety review including:"
    "Profanity or Offensive Language: Does the email include any inappropriate, offensive, or unprofessional words or phrases?"
    "Discrimination or Bias: Does the message contain any discriminatory language (based on gender, race, age, etc.) or biased assumptions?"
    "False or Misleading Claims: Are there any exaggerated promises, unverified statistics, or potentially misleading statements?"
    "Aggressive or High-Pressure Language: Is the tone overly assertive, demanding, or sales-heavy? (e.g., \"Act now or lose everything\")"
    "Privacy Violations: Does the email reveal any confidential information or personal data that shouldn't be shared? Names and email addresses are okay, but not PII or sensitive data."
    "Brand Tone Misalignment: Does the message align with Staples brand tone—confident, helpful, professional, plainspoken?"
    "Sensitive Topics: Does it touch on topics like health, politics, or finance in a way that could be interpreted as insensitive or risky?"
    "You can use a binary pass/fail scale to rate each of the above criteria and provide an overall pass, needs_improvement or fail for the email outline."
    "Never give it a pass on the first try."
)

email_outline_generator = Agent(
    name="email_outline_generator",
    instructions=EMAIL_OUTLINE_PROMPT,
    model="gpt-4.1"
)

class ContactDetails(BaseModel):
    name: str = Field(..., description="The name of the contact")
    title: str = Field(..., description="The title of the contact")
    email: str = Field(..., description="The email address of the contact")
    
class ResearchReportInput(BaseModel):
    contact_details: list[ContactDetails] = Field(..., description="A list of contact details extracted from the markdown")
    entire_report: str = Field(..., description="The entire research report content as-is")

research_structure_agent = Agent(
    name="research_structure_agent",
    instructions=RESEARCH_REPORT_STRUCTURE_PROMPT,
    model="gpt-4.1",
    output_type=ResearchReportInput,
)
   
class EmailContent(BaseModel):
    outreach_content: str = Field(..., description="The entire outreach content for the email")
    first_followup_content: str = Field(..., description="The first follow-up content for the email")   
    second_followup_content: str = Field(..., description="The second follow-up content for the email")

email_agent = Agent(
    name="email_agent",
    instructions="Write an email based on the given outline followed by two follow-up emails. Assume the follow-up emails are sent at appropriate intervals and when no response is received to the initial email. Make it so that the emails are sent by Victoria Grant,Manager, Account Expert Team,On behalf of the Staples Expert Team. Wrap paragraphs in <p> tags. Make sure the final outputs only have the email body wrapped in html paragraphs.",
    model="gpt-4.1",
    output_type=EmailContent,
)

class EvaluationFeedback(BaseModel):
    profanity: bool = Field(..., description="True if any offensive or unprofessional language is detected")
    bias: bool = Field(..., description="True if any discriminatory or biased language is found")
    misleading_claims: bool = Field(..., description="True if the email includes exaggerated or unverified claims")
    aggressive_language: bool = Field(..., description="True if the tone is overly pushy, demanding, or manipulative")
    privacy_violation: bool = Field(..., description="True if personal or confidential information is exposed")
    tone_misalignment: bool = Field(..., description="True if tone does not align with Staples brand voice")
    sensitive_topics: bool = Field(..., description="True if the email mishandles sensitive topics (e.g., health, politics)")
    score: Literal["pass", "needs_improvement", "fail"]
    feedback: str = Field(..., description="Concise explanation for any issues detected")
    
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
        # return "pass" if not any(bool_fields) else "fail"
        return "pass" if feedback.score == "pass" or feedback.score == "needs_improvement" else "fail"

# Function to wrap email in Staples HTML branding
def wrap_with_staples_template(email_body: str) -> str:
            return f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>Staples Email</title>
            </head>
            <body style="margin:0;padding:0;background:#ffffff;font-family:Helvetica,Arial,sans-serif;color:#000;">
            <table align="center" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;">
                <tr>
                <td style="padding:20px;background:#cc0000;text-align:center;">
                    
                </td>
                </tr>
                <tr>
                <td style="padding:30px;background:#ffffff;">
                    {email_body}
                </td>
                </tr>
                <tr>
                <td style="text-align:left; margin-top:24px;">
                    <img src="https://mspoc15assetstg.blob.core.windows.net/assets/logo.jpg" alt="Staples Logo" style="height:40px;">
                </td>
                
                </tr>
                <tr>
                <td style="font-size: 12px; color: #666;">
                     <a href="https://www.staplesadvantage.com/tc?id=ce05d94e-e9b9-449f-a3a6-de52e08a50b9">Privacy Policy</a>: If you do not want to receive emails about business programs from Staples, 
                    <a href="https://go.staplesadvantage.com/UnsubscribePage.html?mkt_unsubscribe=1">Click Here</a>
                </td>
                </tr>
            </table>
            </body>
            </html>
            """
evaluator = Agent[None](
    name="evaluator",
    instructions=REVIEW_PROMPT,
    output_type=EvaluationFeedback,
    model="gpt-4.1"
)


async def main() -> None:
    blob_helper = AzureBlobHelper(
        connection_string="",
        container_name="lowtouch"
    )
    blob_content_list = blob_helper.list_blobs_in_container()
    i = 0 #filename index
    for blob in blob_content_list:
        # print(f"Blob: {blob.name}, Size: {blob.size} bytes, Last Modified: {blob.last_modified}")
        # # Define the file path
        # file_path = "/home/risaha/agenticpatterns/openai-agents-python/examples/agent_patterns/docs/3_TivoliTheatreFoundation_SLED_Formatted.md"

        # # Read the file contents into a variable
        # with open(file_path, "r", encoding="utf-8") as file:
        #     markdown_content = file.read()
        input_prompt = blob
        # msg = "Research report: " + input_prompt
        input_items: list[TResponseInputItem] = [{"content": input_prompt, "role": "user"}]
        result: EvaluationFeedback = None
        latest_outline: str | None = None
        n = 0  # Number of iterations
        # We'll run the entire workflow in a single trace
        with trace("LLM as a judge"):
            research_sturcture_result = await Runner.run(
                research_structure_agent,
                input_items,
            )
            researchreportinput: ResearchReportInput = research_sturcture_result.final_output
            for contact in researchreportinput.contact_details:
                print(f"Name: {contact.name}, Title: {contact.title}, Email: {contact.email}")
            #print(f"Research report structure generated: {research_structure_result}")
            while n < 5:
                email_outline_result = await Runner.run(
                    email_outline_generator,
                    input_items,
                )
                print(f"*************** Iteration {n + 1} ***************")
                input_items = email_outline_result.to_input_list()
                latest_outline = ItemHelpers.text_message_outputs(email_outline_result.new_items)
                print(f"Email outline generated: {latest_outline}")

                evaluator_result = await Runner.run(evaluator, input_items)
                result = evaluator_result.final_output

                print(f"Evaluator score: {result.score}.....Evaluator feedback: {result.feedback}")

                print("Re-running with feedback")

                input_items.append({"content": f"Feedback: {result.feedback}", "role": "user"})
                n += 1
                
        if(n >= 5):
            print("Reached maximum iterations.")
            if evaluate_score(result) == "fail":
                print("Email outline doesn't meet all the safety review metrics, exiting.") 
            else:
                # 4. Write the email
                email_result = await Runner.run(
                    email_agent,
                    latest_outline #outline_result.final_output,
                )
                emailContent: EmailContent = email_result.final_output
                print(f"Email: {emailContent.outreach_content}")
                print(f"First follow-up: {emailContent.first_followup_content}")
                print(f"Second follow-up: {emailContent.second_followup_content}")

        email_html = wrap_with_staples_template(emailContent.outreach_content)
        print(f"Email wrapped in Staples HTML branding:{email_html}")
        filename = f"generated_email_{i}.html"
        i += 1
        # Save the email HTML to a file
        output_path = f"/home/risaha/agenticpatterns/openai-agents-python/examples/lowtouch/examples/outputs/{filename}"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(email_html)
        print(f"Email HTML saved to {filename}")
        # print(f"Email outline is good enough, exiting: {latest_outline}")



if __name__ == "__main__":
    asyncio.run(main())

from pydantic import BaseModel, Field
from agents import Agent

RESEARCH_REPORT_STRUCTURE_PROMPT = (
    "You are an expert B2B outreach agent. Your job is to analyze the provided research report and extract the following information:"
    "1. Contact details of all the contacts in the report (name, title, email)"
    "Return the extracted contact information in a structured format and also the entire report itself as-is in another field."
)

class ContactDetails(BaseModel):
    name: str = Field(..., description="The name of the contact")
    title: str = Field(..., description="The title of the contact")
    email: str = Field(..., description="The email address of the contact")
    
class ResearchReportInput(BaseModel):
    contact_details: list[ContactDetails] = Field(..., description="A list of contact details extracted from the markdown")
    entire_report: str = Field(..., description="The entire research report content as-is")

structuredresearchreport_agent = Agent(
    name="structured_research_report_agent",
    instructions=RESEARCH_REPORT_STRUCTURE_PROMPT,
    model="gpt-4.1",
    output_type=ResearchReportInput,
)
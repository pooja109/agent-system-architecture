from pydantic import BaseModel, Field
from typing import Literal
from agents import Agent

class EmailContent(BaseModel):
    outreach_content: str = Field(..., description="The entire outreach content for the email")
    first_followup_content: str = Field(..., description="The first follow-up content for the email")   
    second_followup_content: str = Field(..., description="The second follow-up content for the email")

emailgenerator_agent = Agent(
    name="emailgenerator_agent",
    instructions="Write an email based on the given outline followed by two follow-up emails. Assume the follow-up emails are sent at appropriate intervals and when no response is received to the initial email. Make it so that the emails are sent by Victoria Grant,Manager, Account Expert Team,On behalf of the Staples Expert Team. Wrap paragraphs in <p> tags. Make sure the final outputs only have the email body wrapped in html paragraphs.",
    model="gpt-4.1",
    output_type=EmailContent,
)
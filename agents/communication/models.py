from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal

class Contact(BaseModel):
    first_name: str = Field(..., description="The contact's first name.")
    last_name: str = Field(..., description="The contact's last name.")
    full_name: Optional[str] = Field(None, description="The contact's full name, if available.")
    email: Optional[str] = Field(None, description="The contact's email address.")
    title: Optional[str] = Field(None, description="The contact's job title or role.")
    phone: Optional[str] = Field(None, description="The contact's phone number.")
    salesforce_account_id: Optional[str] = Field(None, description="Salesforce Account ID for the contact, if available.")
    salesforce_contact_id: Optional[str] = Field(None, description="Salesforce Contact ID for the contact, if available.")
    suggested_hooks: Optional[List[str]] = Field(None, description="Suggested hooks or talking points for the contact, if available.")
    

class SenderDetails(BaseModel):
    first_name: str = Field(..., description="The sender's first name.")
    last_name: str = Field(..., description="The sender's last name.")
    full_name: Optional[str] = Field(None, description="The sender's full name, if available.")
    email: Optional[str] = Field(None, description="The sender's email address.")
    title: Optional[str] = Field(None, description="The sender's job title or role.")
    phone: Optional[str] = Field(None, description="The sender's phone number.")
    team: Optional[str] = Field(None, description="The sender's team or department, if applicable.")

class Company(BaseModel):
    name: Optional[str] = Field(None, description="The company name.")

class Account(BaseModel):
    summary: Optional[str] = Field(None, description="Account summary.")
    observations: Optional[str] = Field(None, description="Account observations.")
    action_plan: Optional[str] = Field(None, description="Account action plan.")
    expected_upside: Optional[str] = Field(None, description="Expected upside for the account.")
    justification: Optional[str] = Field(None, description="Justification for recommendations.")
    citations: Optional[str] = Field(None, description="Citations or references for the account.")

class ResearchOutput(BaseModel):
    customer_name: Optional[str] = Field(None, description="The name of the customer.")
    customer_id: Optional[str] = Field(None, description="The unique customer ID.")
    customer_zip: Optional[str] = Field(None, description="The ZIP code of the customer.")
    customer_state: Optional[str] = Field(None, description="The state of the customer.")
    division: Optional[str] = Field(None, description="The division or region for the customer.")
    primary_reason_for_outreach: Optional[str] = Field(None, description="The main reason for contacting the customer.")
    issue: Optional[str] = Field(None, description="A brief description of the main issue or opportunity.")
    sender_details: Optional[SenderDetails] = Field(None, description="Details about the sender of the communication.")
    contact_list: Optional[List[Contact]] = Field(default_factory=list, description="A list of key contacts for the customer.")
    summary: Optional[str] = Field(None, description="A summary of the research or engagement.")
    recommendations: Optional[List[str]] = Field(None, description="List of recommendations or next steps.")
    sample_email_subject: Optional[str] = Field(None, description="A sample subject line for outreach.")
    sample_email_body: Optional[str] = Field(None, description="A sample email body for outreach.")
    citations: Optional[List[str]] = Field(None, description="List of citations or references.")
    url_citations: Optional[List[str]] = Field(None, description="List of URLs for external citations.")
    company: Optional[Company] = Field(None, description="Company information, if available.")
    account: Optional[Account] = Field(None, description="Account information, if available.")
    other_fields: Optional[Dict[str, Any]] = Field(None, description="Any additional fields or data.")

class EvaluationFeedback(BaseModel):
    profanity: bool = Field(..., description="True if any offensive or unprofessional language is detected")
    bias: bool = Field(..., description="True if any discriminatory or biased language is found")
    misleading_claims: bool = Field(..., description="True if the email includes exaggerated or unverified claims")
    aggressive_language: bool = Field(..., description="True if the tone is overly pushy, demanding, or manipulative")
    privacy_violation: bool = Field(..., description="True if personal or confidential information is exposed")
    tone_misalignment: bool = Field(..., description="True if tone does not align with Staples brand voice")
    sensitive_topics: bool = Field(..., description="True if the email mishandles sensitive topics (e.g., health, politics)")
    dashes_as_punctuation_violation: bool = Field(..., description="True if dashes (– or -) are used as punctuation instead of only in standard compound words")
    all_caps_violation: bool = Field(..., description="True if any content is in ALL CAPS")
    sender_not_team_violation: bool = Field(..., description="True if the sender is presented as a dedicated agent or individual, rather than as the Staples Expert Team")
    specific_times_dates_violation: bool = Field(..., description="True if specific times or dates are suggested for meetings, rather than open-ended CTAs")
    website_reference_violation: bool = Field(..., description="True if staplesbusiness.com is used incorrectly, or staples.com is used at all")
    signature_footer_violation: bool = Field(..., description="True if sender details are not included as a signature, or the required footer is not present verbatim")
    html_format_violation: bool = Field(..., description="True if the output is not valid HTML, or not all paragraphs are wrapped in <p> tags, or there is extra text or instructions")
    promotions_rebate_violation: bool = Field(...,description="True if the email contains any mention of promotions, discounts, rebates, special offers, dollar amounts, revenue, or incentives/offers")
    score: Literal["pass", "needs_improvement", "fail"]
    feedback: str = Field(..., description="Concise explanation for any issues detected")

class Email(BaseModel):
    subject: str = Field(..., description="The subject line of the email.")
    body_html: str = Field(..., description="The HTML body of the email.")

class ContactEmail(BaseModel):
    contact_name: str = Field(..., description="The name of the contact person for whom the email is generated.")
    contact_email: str = Field(..., description="The email address of the contact person.")
    email: Email = Field(..., description="The generated email object for this contact.")
    follow_up_emails: List[Email] = Field(..., description="A list of follow-up Email objects tailored to this contact.")

class MultiContactEmailTask(BaseModel):
    input: str = Field(..., description="The instruction or input for the contact-specific email generation task.")
    input_email: Optional[Email] = Field(None, description="The base email object to use for all contact-specific emails.")
    customer_id: str = Field(..., description="The unique customer ID for whom the emails are generated.")
    contact_emails: List[ContactEmail] = Field(..., description="A list of ContactEmail objects, one for each contact in contact_list, each containing the generated email and follow-up emails.")
    contact_list: Optional[List[Contact]] = Field(default_factory=list, description="A list of key contacts for the customer.")
    review_comments: Optional[EvaluationFeedback] = Field(None, description="Review feedback or comments for the generated emails, if any.")
    customer_research: Optional[str] = Field(None, description="Raw research or context data as a string, if available.")

class EmailTask(BaseModel):
    input: str = Field(..., description="The instruction or input for the email generation task.")
    draft_email: Email = Field(..., description="The generated email object, always present in the output.")
    current_agent_name: str = Field(..., description="The name of the agent generating the email.")
    customer_id: str = Field(..., description="The unique customer ID for whom the email is generated.")
    extracted_input: Optional[ResearchOutput] = Field(None, description="The extracted research/context data used for email generation.")
    review_comments: Optional[EvaluationFeedback] = Field(None, description="Review feedback or comments for the draft email, if any.")
    customer_research: Optional[str] = Field(None, description="Raw research or context data as a string, if available.")



# create an object which can hold a list of draft_email in html(str) format and corresponding EvaluationFeedback
class EmailDrafts(BaseModel):
    drafts: List[str] = Field(default_factory=list, description="List of draft emails in HTML format.")
    evaluations: List[EvaluationFeedback] = Field(default_factory=list, description="List of evaluations for each draft email.")
    
    def add_draft(self, draft: str, evaluation: EvaluationFeedback):
        self.drafts.append(draft)
        self.evaluations.append(evaluation)

class CommunicationOutput(BaseModel):
    """Model to hold the output of the communication agent."""
    customer_id: str = Field(..., description="The unique customer ID for whom the communication is generated.")
    customer_name: Optional[str] = Field(None, description="The name of the customer.")
    customer_id: Optional[str] = Field(None, description="The unique customer ID.")
    customer_zip: Optional[str] = Field(None, description="The ZIP code of the customer.")
    customer_state: Optional[str] = Field(None, description="The state of the customer.")
    final_evaluation: EvaluationFeedback = Field(None, description="Final evaluation for the communication.")
    contact_emails: List[ContactEmail] = Field(default_factory=list, description="List of emails generated for each contact.")


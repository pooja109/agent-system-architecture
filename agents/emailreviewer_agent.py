from pydantic import BaseModel, Field
from typing import Literal
from agents import Agent

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

emailreviewer_agent = Agent[None](
    name="emailreviewer_agent",
    instructions=REVIEW_PROMPT,
    output_type=EvaluationFeedback,
    model="gpt-4.1"
)
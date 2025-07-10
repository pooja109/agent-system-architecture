from datetime import date
from pydantic import BaseModel
from typing import Optional, List
import json

class AgentBatchRecord(BaseModel):
    batch_id: Optional[int]
    run_date: Optional[date]
    agent_name: str
    status: Optional[str]
    input_file: Optional[str]
    output_file: Optional[str]
    is_reviewed: Optional[bool]
    review_notes: Optional[str]
    is_approved: Optional[bool]
    approved_notes: Optional[str]
    is_email_sent: Optional[bool]
    customer_id: Optional[str]
    contact_id: Optional[str]
    customer_id_type: Optional[str]

def createRecords() -> List[AgentBatchRecord]:
    """
    Creates a list of AgentBatchRecord objects with sample data.
    """

    # Create a list of records
    records: List[AgentBatchRecord] = [
        AgentBatchRecord(
            batch_id=101,
            run_date=date(2025, 6, 24),
            agent_name="research",
            status="S - Success",
            input_file="input_research_0624.csv",
            output_file="output_research_0624.csv",
            is_reviewed=True,
            review_notes="Validated successfully",
            is_approved=True,
            approved_notes="Approved by QA",
            is_email_sent=True
        ),
        AgentBatchRecord(
            batch_id=101,
            run_date=date(2025, 6, 24),
            agent_name="communication",
            status="F - Failure",
            input_file="input_comm_0624.csv",
            output_file=None,
            is_reviewed=True,
            review_notes="File format error",
            is_approved=False,
            approved_notes="Needs correction",
            is_email_sent=False
        )
    ]

    return records

def serializeRecords(records: List[AgentBatchRecord]) -> str:
    """Serializes a list of AgentBatchRecord objects to a JSON string."""
    return json.dumps([record.model_dump() for record in records], indent=4)


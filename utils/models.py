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
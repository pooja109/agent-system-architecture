from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Literal
import json

class AgentBatchRecord(BaseModel):
    batch_id: str
    run_date: datetime
    cust_id: str
    contact_id: Optional[str] = None
    agent_name: str
    status: Literal["S", "F", "P", "IP"]
    agent_output: str
    agent_output_path: Optional[str] = None
    is_reviewed: Optional[bool] = None
    review_notes: Optional[str] = None
    is_approved: Optional[bool] = None
    approved_notes: Optional[str] = None
    is_email_sent: Optional[bool] = None
    customer_id_type: Optional[str] = None
from datetime import date
from pydantic import BaseModel
from typing import Optional, List
import json
from models import AgentBatchRecord


def createRecords() -> List[AgentBatchRecord]:
    """
    Creates a list of AgentBatchRecord objects with sample data.
    """

    # Read the markdown content for agent_output
    amazing_kidz_output = """# Priority Reason: **Growth**

---

## **Customer Overview**
**Amazing Kidz Academy LLC** operates multiple early-childhood education centers that collectively serve more than **450 children**. The organization partners with municipalities and educational programs to deliver bilingual, inclusive learning. Their continued expansion indicates sustained purchasing needs for classroom technology and related services.

---

## **Key Business Insights**

- **Rapid multi-location growth** signals an expanding footprint and rising demand for classroom essentials and technology infrastructure.

- The academy's partnerships with public agencies mean **consistent compliance and reporting needs**, placing high value on reliable suppliers that simplify procurement.

---

## **Spend Analysis & Target Categories**  
### Ranked by Importance

1. **Primary Category 3 – Technology** (Value: **$21K**)  
   - **Future Opportunity**: Upgrading tablets, laptops, projectors, and network accessories for new classrooms and administrative offices after **2025-07-14**.

2. **Secondary Category 3 – Computers, Mobile, and Services** (Value: **$59K**)
   - **Future Opportunity**: Device refresh cycles, IT support contracts, and mobile-device management for teachers and staff as locations scale.

---

## **Outreach Recommendations** *(after 2025-07-14)*

- **Position Staples Business** as a single source for technology procurement and device lifecycle services, emphasizing:
  - Easy online ordering.
  - Next-day delivery to any campus.
  - Asset tagging options.

- **Bundle classroom technology** with warranty extensions and recycling solutions to simplify refresh planning as enrollment grows.

- Share **case studies** featuring multi-site educational organizations that utilized Staples Business to:
  - Standardize purchasing.
  - Increase visibility.
  - Control costs."""

    electralloy_output = """# Electralloy Breakroom Expansion Opportunity

---

### **Priority Reason: Growth**

Electralloy (Cust ID: **1480156**) specializes in manufacturing specialty alloys for demanding sectors like **aerospace**. With a growing workforce, active participation in industry events, and a forward-thinking culture emphasizing intern-driven programs, they signal **continued expansion**. 

---

### **Account Overview**

- **Location**: Pennsylvania, Zip Code: 16301  
- **Industry**: Specialty Alloy Manufacturing  
- **Primary Categories**: 
  - **Office Supplies**, **Furniture**, **Breakroom**  
- **Secondary Categories**:  
  - Other Office Supplies, Chairs, Breakroom Supplies  

---

### **Spend & Category Insight**

- **Breakroom** Spending:
  - Historical Spend: **$214**
  - Breakroom Supplies Spend: **$197**

These are the only recorded categories, offering **an untapped opportunity to increase wallet share** by presenting Staples as a **single-source partner** for all breakroom requirements as Electralloy continues to scale.

---

### **Forward-Looking Opportunity (Post-July 14, 2025)**

1. **Scalable Solutions**: Align with Electralloy's expanded workforce and intern programs by introducing dynamic breakroom solutions that scale with their growth.  
2. **Procurement Support**: Offer scheduled restock options for breakroom supplies to free procurement bandwidth, enabling the team to stay focused on core alloy operations.  
3. **Sustainability Alignment**: Provide environmentally friendly breakroom products that reflect their aerospace clientele's **sustainability expectations**."""

    # Create a list of records
    records: List[AgentBatchRecord] = [
        AgentBatchRecord(
            batch_id=101,
            run_date=date(2025, 7, 14),
            customer_id="10250758",
            contact_id="0033t00004NKpTmAAL",
            agent_name="research_agent",
            status="success",
            agent_output=amazing_kidz_output,
            agent_output_path="/outputs/customer_10250758_research_output.md",
            is_reviewed=True,
            review_notes="Research report validated successfully",
            is_approved=True,
            approved_notes="Approved by QA team",
            is_email_sent=False,
            customer_id_type="internal"
        ),
        AgentBatchRecord(
            batch_id=102,
            run_date=date(2025, 7, 14),
            customer_id="1480156",
            contact_id="0013000005z3uPAAQ",
            agent_name="research_agent",
            status="success", 
            agent_output=electralloy_output,
            agent_output_path="/outputs/customer_1480156_research_output.md",
            is_reviewed=True,
            review_notes="Breakroom expansion opportunity identified",
            is_approved=True,
            approved_notes="Ready for outreach",
            is_email_sent=False,
            customer_id_type="internal"
        ),
        AgentBatchRecord(
            batch_id=103,
            run_date=date(2025, 7, 14),
            customer_id="10250758",
            contact_id="0033800002pAtHNAA0",
            agent_name="research_agent",
            status="pending",
            agent_output="Research in progress for Lisa Smith contact",
            agent_output_path=None,
            is_reviewed=False,
            review_notes=None,
            is_approved=False,
            approved_notes=None,
            is_email_sent=False,
            customer_id_type="internal"
        )
    ]

    return records

def serializeRecords(records: List[AgentBatchRecord]) -> str:
    """Serializes a list of AgentBatchRecord objects to a JSON string."""
    def serialize_record(record):
        record_dict = record.model_dump()
        # Convert date objects to string for JSON serialization
        if record_dict.get('run_date'):
            record_dict['run_date'] = record_dict['run_date'].isoformat()
        return record_dict
    
    return json.dumps([serialize_record(record) for record in records], indent=4)


from datetime import date
from pydantic import BaseModel
from typing import Optional, List
import json
from utils.models import AgentBatchRecord


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

- The academy’s partnerships with public agencies mean **consistent compliance and reporting needs**, placing high value on reliable suppliers that simplify procurement.

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
  - Control costs.

---

## **Contact-Wise Notes**

### 1. **Tawanna Bentley**
- Focus on centralized billing and recurring deliveries of laptops/tablets for each semester.

### 2. **Lisa Smith**
- Highlight Staples Business reporting dashboards that help meet quarterly compliance audits tied to city contracts.

### 3. **Destiny Gonzalez**
- Discuss tech-refresh timelines and trade-in programs for aging computers after **2025-07-14**.

### 4. **Lauren Merrell**
- Introduce remote-support service add-ons for troubleshooting staff devices across four locations.

### 5. **Dana Barnes**
- Emphasize sustainability initiatives, such as device recycling and e-waste certificates, aligning with community impact goals.

---

## **Next Steps**

1. **Send personalized emails** to each contact outlining the most relevant technology solutions.
2. **Schedule discovery calls** to map their upcoming classroom expansions and device needs.
3. Provide a **tailored Staples Business purchasing guide** focused on:
   - **Technology**
   - **Computers, Mobile & Services**

---

## **Customer Details**

- **State:** PA  
- **Zip Code:** 19126

### **Target Categories**:  
| **Primary Categories** | **Secondary Categories**                             |
| ----------------------- | --------------------------------------------------- |
| Furniture              | Desks                                              |
| Toner                  | OEM Toner and Other                                |
| **Technology**         | **Computers, Mobile, and Services**                |

---

## **Contacts**

| **SF Account ID**         | **SF Contact ID**         | **First Name** | **Last Name** | **Email**                          |
| -------------------------- | ------------------------- | -------------- | ------------- | ---------------------------------- |
| 0013800001KKTrJAAX         | 0033t00004NKpTmAAL        | Tawanna        | Bentley       | tbentley@amazingkidz123.com        |
| 0013800001KKTrJAAX         | 0033800002pAtHNAA0        | Lisa           | Smith         | amazing.lsmith@gmail.com           |
| 0013800001KKTrJAAX         | 0033t00004KQ3Z2AAL        | Destiny        | Gonzalez      | dgonz@amazingkidz123.com           |
| 0013800001KKTrJAAX         | 0033800002zyu13AAA        | Lauren         | Merrell       | lmerrell@amazingkidz123.com        |
| 0013800001KKTrJAAX         | 0033t00004eLIQNAA4        | Dana           | Barnes        | dbarnes@amazingkidz123.com         |

--- 

> **Why Staples Business?**  
Amazing Kidz Academy LLC’s growth trajectory demands scalable technology solutions, integration flexibility, and supplier reliability. Staples Business is positioned to be their trusted partner through tailored product offerings, sustainability initiatives, and optimized procurement strategies.


Justification : 
1. Selected “Growth” as priority because the customer’s category potential values are positive (Technology $21K; Computers, Mobile & Services $59K) and no retention flag was present.
2. Focused on Technology–related categories because they are the only categories listed in the dataset and have the highest potential revenue.
3. Incorporated public information from the websearch to validate the customer’s expansion trajectory, which supports a growth-oriented outreach.
4. Built contact-wise notes using the five contacts in the transactions dataset, aligning each outreach suggestion with their likely operational roles (no personal data beyond names used).
5. Ensured recommendations are forward-looking by stating actions to be taken after 2025-07-14 and referencing Staples Business instead of consumer channels.



Citation : 
[Citation(dataset_citation='customer dataset row 4: "PRIMARY_CAT_3 = Technology, PRIMARY_CAT_3_VALUE = 21, SECONDARY_CAT_3 = Computers, Mobile and Services, SECONDARY_CAT_3_VALUE = 59"', reason_for_citation='Shows the specific categories and potential revenue that should be prioritized in the outreach.'), Citation(dataset_citation='transactions dataset rows 1583-1587: list of contacts for SF_ACCOUNT_ID 0013800001KKTrJAAX (TAWANNA BENTLEY, LISA SMITH, DESTINY GONZALEZ, LAUREN MERRELL, DANA BARNES)', reason_for_citation='Provides the named contacts that will receive the recommendations and outreach.'), Citation(dataset_citation='websearch dataset: "Amazing Kidz Academy LLC … capacity for over 450 children … contracts with multiple organizations"', reason_for_citation='Gives current public information about the customer to add relevant context to the research report.')]



Bing Search Results and Citation : 

The most notable news from the past few months regarding Amazing Kidz Academy LLC is that it recently celebrated its 10th anniversary. Founded in 2014 in Philadelphia, the Academy serves at-risk youth to promote their academic success, providing bilingual and inclusive early childhood education. The academy has grown significantly, now operating across four locations with six buildings and a capacity for over 450 children. It has also expanded its services through contracts with multiple organizations, including the City of Philadelphia and Early Head Start【3:0†source】【3:2†source】.


URL Citation:
Amazing Kidz Academy Celebrates 10 Years in Business : https://pidcphila.com/blog/amazing-kidz-academy-celebrates-10-years-in-business/

"""

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

1. **Scalable Solutions**: Align with Electralloy’s expanded workforce and intern programs by introducing dynamic breakroom solutions that scale with their growth.  
2. **Procurement Support**: Offer scheduled restock options for breakroom supplies to free procurement bandwidth, enabling the team to stay focused on core alloy operations.  
3. **Sustainability Alignment**: Provide environmentally friendly breakroom products that reflect their aerospace clientele's **sustainability expectations**.  

---

### **Recommended Next Steps**

1. **Customized Proposal**:  
   - Share a tailored bundle showcasing tiered pricing and volume milestone incentives to sync with Electralloy's growth trajectory.  

2. **Q3 Virtual Review (2025)**:  
   - Schedule a **15-minute virtual session** to finalize delivery schedules aligned with their expanding workforce.  

3. **Insight via Dashboard**:  
   - Provide access to a dashboard on **StaplesBusiness.com** for easy **spend tracking** and **budget forecasting**.  

---

### **Contact-Level Outreach Suggestions**

| **Contact**       | **Title**                 | **Focus Areas**                                                             | **Email**              |
|--------------------|---------------------------|-----------------------------------------------------------------------------|------------------------|
| **Chelsey Flick** | Procurement Manager       | Automated ordering and streamlined procurement to save time.               | cflick@gocarlson.com  |
| **Michael Cusack**| Finance Analyst           | Cost-optimization analytics—highlight potential savings under new programs.| mcusack@gocarlson.com |
| **Jimmy Stewart** | Sustainability Lead       | Sustainable product certifications and environmental alignment.            | jstewart@gocarlson.com|  

---

### **Value Proposition**

For Electralloy, partnering now with Staples enables:  
- **Predictable Pricing**: Lock in competitive rates as they grow.  
- **Ease of Operations**: Reduce manual orders.  
- **Employee Satisfaction**: Ensure employees benefit from an optimized and well-stocked breakroom.  

---

### **Customer Snapshot**

| **Customer**           | **Spend Insight**                                      | **Location**                 |
|-------------------------|-------------------------------------------------------|-----------------------------|
| Electralloy (**#1480156**)| Breakroom Spend: Historical **$214** & Supplies - **$197** | PA, Zip: 16301             |

---

#### Be the **solution partner** Electralloy needs to achieve streamlined procurement, cost-effective growth, and sustainable alignment in its supply chain.


Justification : 
The customer dataset confirms Breakroom and Breakroom Supplies as the only categories with recorded spend, making them the clear focus for growth. Dollar values ($214 and $197) establish historical baseline spend. The websearch data shows Electralloy’s active expansion via industry events and intern programs, validating a growth-oriented outreach. The transactions file lists three contacts, enabling targeted messaging. All recommendations concentrate exclusively on the existing categories and reference future actions beyond 2025-07-14, in alignment with policy.



Citation : 
[Citation(dataset_citation='customer row shows PRIMARY_CAT_3 = "Breakroom" with PRIMARY_CAT_3_VALUE = 214 and SECONDARY_CAT_3 = "Breakroom Supplies" with SECONDARY_CAT_3_VALUE = 197', reason_for_citation='Supports the identification of target categories and historical dollar amounts.'), Citation(dataset_citation='transactions rows for SF_ACCOUNT_ID 00130000005z3uPAAQ list contacts CHELSEY FLICK, MICHAEL CUSACK, and JIMMY STEWART', reason_for_citation='Provides the list of active contacts for contact-level outreach.'), Citation(dataset_citation='websearch notes Electralloy’s participation in industry events and intern-driven initiatives in 2025', reason_for_citation='Gives current business context to tailor the outreach narrative.')]



Bing Search Results and Citation : 

Over the past three months, several updates concerning Electralloy, a company specializing in specialty alloys within industries like aerospace and other demanding sectors, have been covered. Notably:

1. In June 2025, Electralloy was to participate in the "Steel Identification, Classification, and Trade Law Seminar."
2. Electralloy is noted for engaging younger professionals, evidenced in their May 2025 intern-driven initiatives and their presence at major events like the Paris Air Show and Forge Fair earlier this year【3:0†source】. 

Would you like insights into specific events or broader industry activities related to their sector?


URL Citation:
Electralloy - News : https://electralloy.com/info-news/news

"""

    # Create a list of records
    records: List[AgentBatchRecord] = [
        AgentBatchRecord(
            batch_id=101,
            run_date=date(2025, 7, 1),
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
            run_date=date(2025, 7, 1),
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


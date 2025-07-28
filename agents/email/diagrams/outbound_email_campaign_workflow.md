# Outbound Email Campaign Processing Workflow

## Business Process Flow - Happy Path

```mermaid
graph TD
    A[Communication Agent<br/>Completes Research] --> B[Updates Pipeline Status<br/>to 'S' - Success]
    B --> C[Email Agent Monitors<br/>Databricks Pipeline Table]
    C --> D{New Records<br/>Found?}
    D -->|Yes| E[Query Pending Records<br/>agent_name='communication'<br/>status='S'<br/>is_email_sent IS NULL]
    D -->|No| F[Wait 5 Minutes]
    F --> C
    
    E --> G[Process Batch<br/>Default: 10 Records]
    G --> H[For Each Customer Record]
    H --> I[Load Research Output JSON<br/>from Blob Storage]
    I --> J[Extract Contact Information<br/>customer_name, email, subject]
    J --> K[Load Email HTML Content<br/>from Blob Storage]
    K --> L{Test Mode<br/>Enabled?}
    
    L -->|Yes| M[Apply Test Mode Override<br/>Redirect to Test Email<br/>Add Test Headers]
    L -->|No| N[Use Original Recipient]
    M --> O[Send Email via<br/>Azure Communication Services]
    N --> O
    
    O --> P{Email Send<br/>Successful?}
    P -->|Yes| Q[Update Database Record<br/>is_email_sent = true<br/>send_status = 'sent'<br/>acs_message_id = message_id<br/>send_timestamp = now()]
    P -->|No| R[Update Database Record<br/>is_email_sent = true<br/>send_status = 'failed'<br/>error_message = error_details]
    
    Q --> S[Log Success<br/>Customer ID, Recipient, Message ID]
    R --> T[Log Failure<br/>Customer ID, Error Details]
    S --> U{More Records<br/>in Batch?}
    T --> U
    U -->|Yes| H
    U -->|No| V[Complete Batch Processing<br/>Report Statistics]
    V --> C
    
    style A fill:#e1f5fe
    style B fill:#e8f5e8
    style O fill:#fff3e0
    style Q fill:#e8f5e8
    style R fill:#ffebee
```

## Key Data Flow Points

### 1. Trigger Conditions
- **Initiator**: Communication agent completes customer research
- **Database Trigger**: Records with `agent_name='communication'`, `status='S'`, `is_email_sent IS NULL`
- **Processing Interval**: Every 5 minutes (configurable)

### 2. Content Sources
- **Research Data**: `{customer_id}_research_output.json` contains:
  - Customer name and contact information
  - Email subject line (`sample_email_subject`)
  - Primary contact details (`contact_list[0].email`)
- **Email Content**: `{customer_id}_email.html` contains:
  - Personalized HTML email content
  - Ready-to-send formatted content

### 3. Processing Flow
- **Batch Processing**: Configurable batch size (default: 10 records)
- **Content Assembly**: Combines JSON metadata with HTML content
- **Test Mode**: Optional email redirection for safe testing
- **Delivery**: Azure Communication Services SMTP delivery
- **Audit Trail**: Complete database tracking of all operations

### 4. Business Outcomes
- **Success**: Customer receives personalized outreach email
- **Tracking**: Complete audit trail for campaign effectiveness
- **Scalability**: Batch processing enables high-volume campaigns
- **Safety**: Test mode prevents accidental customer contact
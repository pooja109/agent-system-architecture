# Inbox Monitor Email Scenarios Guide

Detailed explanation of AI email classification and automated business actions for intelligent email routing.

> **📚 Related Documentation:**
> - **Getting Started:** [Setup Guide](SETUP.md) - Install and configure the system
> - **Configuration:** [Configuration Guide](CONFIGURATION.md) - Authentication and service setup
> - **Operations:** [User Guide](USER_GUIDE.md) - Daily usage and monitoring
> - **Testing:** [Testing Guide](TESTING.md) - Test scenario processing
> - **Architecture:** [Services Overview](SERVICES-OVERVIEW.md) - Technical implementation details
> - **Need Help?** [Troubleshooting Guide](TROUBLESHOOTING.md) - Common scenario processing issues
> - **Back to Hub:** [Documentation Hub](README.md) - All available guides

## Overview

The Inbox Monitor uses Azure AI Foundry with advanced prompt engineering to classify customer email responses into six distinct business intents. Each classification triggers specific automated actions across multiple service integrations (Salesforce, Databricks, email forwarding) to ensure appropriate customer response handling.

**Business Value**: Automates customer response routing, expert assignment, and CRM updates, reducing manual processing time by 90% while ensuring consistent response handling.

## Email Classification Process

1. **Email Monitoring**: Microsoft Graph API continuously monitors designated inbox (default: every 5 minutes)
2. **AI Intent Classification**: Azure AI Foundry analyzes email content using Semantic Kernel with confidence scoring
3. **Business Action Routing**: Classified intent triggers appropriate automated actions across integrated services
4. **Multi-Service Automation**: Coordinated updates to Salesforce CRM, Databricks expert assignment, and email forwarding

## Detailed Scenario Breakdown

### Scenario 5: Positive Response

**Email Intent**: Customer shows interest and wants more engagement  
**AI Classification**: Customer expresses interest, requests follow-up, or asks for more information  
**Business Impact**: High-value lead requiring immediate expert assignment and CRM case creation

**Automated Actions**:
1. **Customer Lookup**: Query Databricks contact database for customer information and history
2. **Expert Assignment**: Apply round-robin algorithm to assign available expert representative
3. **Salesforce Case Creation**: Create new case record assigned to selected expert with customer context
4. **Assignment Tracking**: Update expert assignment count for balanced workload distribution

**Example Email Triggers**:
- "I'm very interested in learning more about your solutions. Could you please have someone call me?"
- "This looks promising. Can we schedule a demo next week?"
- "I'd like to discuss pricing options for my company."
- "Please have your sales team contact me - I have budget approved."

**Technical Implementation**:
- Uses Databricks `expert_lead_assignments` table for round-robin logic
- Creates Salesforce case with specific record type and queue assignment
- Updates assignment counters to maintain balanced expert workload

**Troubleshooting**: See [Positive Response Troubleshooting](TROUBLESHOOTING.md#positive-response-scenario-5-issues) for common expert assignment and case creation issues.

### Scenario 6: Negative Response

**Email Intent**: Customer wants to stop communication  
**AI Classification**: Customer requests removal from contact lists or expresses no interest  
**Business Impact**: Important compliance request requiring immediate attention and contact list management

**Automated Actions**:
1. **Email Forwarding**: Forward complete email to Victoria Grant for review and compliance handling
2. **Contact Logging**: Log customer request in system for audit trail and compliance tracking

**Example Email Triggers**:
- "Please remove me from your contact list immediately."
- "I'm not interested. Stop contacting me."
- "Unsubscribe me from all communications."
- "This is harassment. Remove my information from your database."

**Compliance Considerations**:
- Immediate forwarding ensures rapid compliance response
- Victoria Grant handles manual contact list updates and audit documentation
- System maintains complete audit trail of unsubscribe requests

**Related Actions**: Often followed by manual CRM updates to prevent future contact attempts.

### Scenario 7: Service Inquiry

**Email Intent**: Customer has questions about existing services  
**AI Classification**: Customer inquires about current orders, support issues, or service questions  
**Business Impact**: Existing customer requiring support team attention rather than new sales process

**Automated Actions**:
1. **Account Team Forwarding**: Route email to designated account team for existing customer support
2. **Service Context Preservation**: Maintain email thread and customer history for proper support context

**Example Email Triggers**:
- "I have a question about my recent order #12345."
- "There's an issue with my current service. Can someone help?"
- "How do I access the portal you set up for us?"
- "I need help with the implementation process."

**Service Differentiation**:
- Distinguishes existing customers from new prospects
- Routes to support rather than sales pipeline
- Preserves customer relationship continuity

**Support Integration**: Account team receives full email context and customer history for effective response.

### Scenario 8: Out of Office

**Email Intent**: Automated out-of-office response  
**AI Classification**: System-generated absence notification indicating temporary unavailability  
**Business Impact**: Temporary contact pause preventing wasted outreach attempts during customer absence

**Automated Actions**:
1. **Assignment Status Update**: Set customer status to "out_of_office" in tracking system
2. **Outreach Pause**: Temporarily suspend future email attempts until return date (if specified)

**Example Email Triggers**:
- "Thank you for your email. I am currently out of the office until..."
- "I will be unavailable from March 1-15. I will respond when I return."
- "Automatic reply: I'm currently on vacation and will return..."
- "Out of office: Please contact my assistant at..."

**Intelligent Pause Logic**:
- Automatically detects return dates when specified
- Prevents multiple out-of-office responses from triggering repeated actions
- Maintains customer relationship without intrusion during absence

**Resume Logic**: System can be configured to automatically resume contact attempts after specified return dates.

### Scenario 9: Invalid Email

**Email Intent**: Email delivery failure or bounce notification  
**AI Classification**: System-generated bounce messages indicating email delivery problems  
**Business Impact**: Critical CRM data quality update preventing future delivery failures and maintaining contact accuracy

**Automated Actions**:
1. **Salesforce Field Update**: Set contact's `Is_Email_Invalid__c` boolean field to `true`
2. **Assignment Status Update**: Change assignment status to "email_invalid" in tracking system
3. **Future Prevention**: Prevent all future email attempts to invalid address
4. **Data Quality Maintenance**: Flag contact for manual review and potential contact information update

**Example Email Triggers**:
- "Your message could not be delivered. The email address may be invalid..."
- "Delivery failed: User account does not exist"
- "550 5.1.1 The email account that you tried to reach does not exist"
- "Permanent failure: Invalid recipient address"

**CRM Integration Details**:
- Updates Salesforce Contact record with permanent invalid email flag
- Prevents future campaign inclusion for this email address
- Maintains data quality across all marketing and sales systems

**Data Quality Impact**: Critical for maintaining high deliverability rates and accurate contact database.

### Scenario 10: No Longer Works

**Email Intent**: Person no longer works at the company  
**AI Classification**: Notification that contact person has left the organization  
**Business Impact**: Important contact management update requiring manual review for relationship transfer or account update

**Automated Actions**:
1. **Victoria Grant Forwarding**: Forward email to Victoria Grant for manual review and relationship management
2. **Assignment Status Update**: Set status to "no_longer_works" to prevent future contact attempts
3. **Relationship Preservation**: Maintain opportunity for contact transfer or account relationship update

**Example Email Triggers**:
- "John no longer works at this company. He left last month..."
- "I'm no longer with XYZ Corporation. Please update your records."
- "This person is no longer employed here. Try contacting..."
- "Employee departed: Please remove from your contact list."

**Relationship Management**:
- Victoria Grant can identify replacement contacts or account managers
- Preserves business relationship opportunity despite personnel changes
- Enables proper account transition rather than lost opportunity

**Strategic Value**: Maintains business relationships even when primary contacts change roles.

## AI Classification Debugging

### Understanding Confidence Scores

The AI classification system provides confidence scores for each intent classification:

**High Confidence (>0.8)**: Clear intent classification with strong textual indicators  
**Medium Confidence (0.5-0.8)**: Probable classification requiring review  
**Low Confidence (<0.5)**: Uncertain classification requiring manual review

### Classification Review Process

**Debug Commands**:
```bash
# Enable detailed AI classification logging
export LOGGING_LEVEL=DEBUG
python main.py check

# Force specific scenario for testing
export TEST_FORCE_SCENARIO=5
python main.py check
```

**Common Edge Cases**:
- **Mixed Intent Emails**: Customer expresses both interest and concerns
- **Forwarded Messages**: Email chains with multiple intents
- **Language Variations**: Non-native English or informal language
- **Corporate Auto-Replies**: System messages that appear personal

### Manual Classification Override

For edge cases requiring manual intervention:

1. **Test Mode Override**: Use `TEST_FORCE_SCENARIO` to test specific routing
2. **Manual Review Process**: Victoria Grant reviews uncertain classifications
3. **System Learning**: Edge cases help improve future classification accuracy

## Business Logic Integration

### CRM Workflow Integration

**Salesforce Integration Points**:
- Case creation for positive responses with proper record type and queue
- Contact field updates for email validity and status tracking
- Assignment tracking for expert workload management

**Expert Assignment Algorithm**:
- Round-robin distribution ensures balanced expert workload
- Databricks tracking maintains assignment history and performance metrics
- Automatic expert pool management for availability and capacity

### Contact Lifecycle Management

**Status Progression**:
1. **Active**: Contact available and responsive
2. **Out of Office**: Temporarily unavailable (auto-resume possible)
3. **Email Invalid**: Permanent email delivery failure
4. **No Longer Works**: Personnel change requiring relationship management
5. **Unsubscribed**: Compliance-based contact cessation

**Lifecycle Actions**:
- Automatic status updates based on email classification
- Prevention of inappropriate contact attempts based on status
- Audit trail maintenance for compliance and relationship management

## Performance and Monitoring

### Classification Metrics

**Daily Metrics Tracked**:
- Total emails processed and classification distribution
- Expert assignment balance and case creation success rate
- Email forwarding delivery and response times
- Data quality updates and invalid email detection rate

### Business Impact Measurement

**Key Performance Indicators**:
- Response time reduction for customer inquiries
- Expert workload distribution balance
- CRM data quality improvement metrics
- Compliance request handling efficiency

## Related Documentation

**Email Agent Integration**:
- [Email Agent Campaign Processing](../../email/docs/TROUBLESHOOTING.md) - How outbound campaigns are generated
- [Email Agent Configuration](../../email/docs/CONFIGURATION.md) - Understanding the campaigns customers are responding to
- [Campaign Content Debugging](../../email/README.md#troubleshooting) - Understanding what customers are responding to

**Complete System Documentation**:
- [Email Agent Main Documentation](../../email/README.md) - Comprehensive outbound campaign processing reference
- **[Setup Guide](SETUP.md)** - Getting the AI classification system running with all service integrations
- **[Configuration Guide](CONFIGURATION.md)** - Service authentication configuration for scenario processing
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Scenario-specific debugging and service integration issues
- **[Main README](README.md)** - Complete system documentation and architecture overview

## Advanced Scenario Customization

### Adding New Scenarios

To extend the system with additional email intents:

1. **AI Model Training**: Update Azure AI Foundry prompts with new intent examples
2. **Business Logic Implementation**: Add new automated actions in scenario processor
3. **Service Integration**: Configure appropriate CRM, database, and email actions
4. **Testing and Validation**: Comprehensive testing with representative email samples

### Scenario Configuration

Each scenario can be customized through environment variables and service configuration:

```bash
# Scenario-specific email routing
SCENARIO_VICTORIA_GRANT_EMAIL=victoria.grant@yourcompany.com
SCENARIO_ACCOUNT_TEAM_EMAIL=support@yourcompany.com

# Expert assignment customization
EXPERT_ASSIGNMENT_ALGORITHM=round_robin  # Future: weighted, skill-based, etc.
EXPERT_POOL_REFRESH_INTERVAL=3600       # Refresh expert availability hourly
```
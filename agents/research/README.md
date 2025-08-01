# Research Agent

## Overview

The Research Agent is a sophisticated AI-powered service that conducts comprehensive research and analysis on low-touch customers for Staples B2B operations. It integrates multiple data sources, performs web searches, and generates detailed research reports with personalized recommendations for customer outreach.

## Purpose

This agent is designed to:
- Analyze low-touch customer accounts that lack dedicated sales representatives
- Conduct web research using Bing Search to gather current company information
- Generate comprehensive research reports with growth and retention recommendations
- Create hyper-personalized outreach strategies based on customer data and market intelligence
- Process customer data from Azure queues and deliver formatted reports to downstream agents

## Key Features

### Multi-Source Data Integration
- **Customer Data (I2A)**: Account information, primary/secondary categories, potential revenue
- **Transaction Data**: Sales history, contact information, purchase patterns
- **DNB Data**: Business information, company websites, industry details
- **Marketing Data**: Category hierarchies and product mapping
- **Web Search**: Real-time company news and market intelligence via Bing Search

### AI-Powered Analysis
- **O3 Reasoning Model**: Advanced reasoning for complex customer analysis
- **Research Review**: AI-powered relevance filtering of web search results
- **Multi-Agent Architecture**: Specialized agents for search, formatting, and JSON processing
- **Structured Output**: Pydantic models ensure consistent data formatting

### Report Generation
- **Markdown Formatting**: Executive-ready presentation formatting
- **Comprehensive Citations**: Traceable data sources and justifications
- **Contact-Specific Reports**: Personalized recommendations for each customer contact
- **Azure Blob Storage**: Automated report storage and retrieval

## Architecture

```
Azure Queue → Research Agent → [Bing Search + O3 Analysis] → Formatted Report → Azure Blob + Queue
     ↓
Status Tracking (Databricks)
```

### Agent Components
1. **Bing Search Assistant**: Web research and current information gathering
2. **Research Reviewer**: AI-powered relevance filtering of search results
3. **O3 Reasoning Agent**: Advanced customer analysis and recommendations
4. **Markdown Formatter**: Executive presentation formatting
5. **JSON Processor**: Structured data formatting

## File Structure

```
research/
├── __init__.py              # Package initialization
├── research_agent.py        # Main research agent logic
├── researchreviewer.py      # AI-powered search result filtering
├── requirements.txt         # Python dependencies
├── sample.env              # Environment variables template
├── .env                    # Environment variables (not in repo)
├── Dockerfile              # Container configuration
└── README.md               # This documentation
```

## Core Functions

### `get_bing_search_results(CUSTOMER_PROFILE, query)`
- Performs web searches using Azure AI Foundry Bing Grounding Tool
- Integrates with research reviewer for relevance filtering
- Returns search results, citations, and filtered content

### `format_response_message_as_json(response_message)`
- Converts agent responses to structured JSON format
- Handles fallback scenarios for robust processing
- Ensures compatibility with downstream processing

### `o3call(prompt, reasoning_effort, tools, response_format)`
- Interfaces with O3 reasoning model for advanced analysis
- Supports tool calling and structured output
- Provides detailed reasoning and justification

### `format_content(content)`
- Formats research reports for executive presentation
- Maintains data integrity while improving readability
- Creates professional markdown output

### `save_research_report(container_name, blob_name, file_content)`
- Stores research reports in Azure Blob Storage
- Organizes files by date and customer ID
- Provides URL access for downstream consumption

## Data Flow

1. **Queue Processing**: Receives customer data from GetData Agent via Azure Queue
2. **Data Preparation**: Converts JSON data to structured DataFrames
3. **Web Research**: Conducts Bing searches for current company information
4. **AI Analysis**: Processes data through O3 reasoning model for insights
5. **Report Generation**: Creates formatted markdown reports with recommendations
6. **Storage & Distribution**: Saves reports to Azure Blob and queues for Communication Agent
7. **Status Tracking**: Updates Databricks with processing status

## Environment Variables

### Required Configuration

```bash
# Azure AI Services
ST_AI_FOUNDRY_ENDPOINT=your_foundry_endpoint
ST_AZURE_OPENAI_ENDPOINT=your_openai_endpoint
ST_AZURE_OPENAI_API_KEY=your_openai_key
ST_API_VERSION=2024-05-01-preview
ST_MODEL_DEPLOYMENT_NAME=your_model_name
REASONING_MODEL_NAME=o3

# Bing Search
ST_BING_CONNECTION_NAME=your_bing_connection

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=your_storage_string
AZURE_CONTAINER_NAME=your_container_name

# Azure Queues
AZURE_QUEUE_CONNECTION_STRING=your_queue_string
AZURE_SRC_QUEUE_NAME=source_queue_name
AZURE_TGT_QUEUE_NAME=target_queue_name
MAX_MESSAGES=5

# Databricks Configuration
DATABRICKS_SERVER_HOSTNAME=your_databricks_hostname
DATABRICKS_HTTP_PATH=your_http_path
DATABRICKS_TOKEN=your_databricks_token

DATABRICKS_STATUS_CATALOG_NAME=status_catalog
DATABRICKS_STATUS_SCHEMA_NAME=status_schema
DATABRICKS_STATUS_TABLE_NAME=status_table
```

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp sample.env .env
   # Edit .env with your actual values
   ```

3. **Set up Azure Resources**:
   - Configure Azure AI Foundry project
   - Set up Bing Search connection
   - Create Azure Storage containers and queues
   - Configure Databricks workspace

## Usage

### Running the Agent

```bash
python research_agent.py
```

### Docker Deployment

```bash
# Build container
docker build -t research-agent .

# Run container
docker run --env-file .env research-agent
```

### Expected Output

The agent processes customer data and generates:

1. **Comprehensive Research Reports** including:
   - Customer analysis and business intelligence
   - Primary/secondary category recommendations
   - Growth vs. retention strategy guidance
   - Contact-specific outreach suggestions
   - Current market intelligence from web research

2. **Structured Data Output**:
   ```json
   {
     "batch_id": "20250801120000",
     "run_date": "2025-08-01 12:00:00",
     "agent_name": "Research_Agent",
     "status": "S",
     "cust_id": "12345",
     "agent_output": "formatted_research_content",
     "agent_output_path": "20250801/12345/research_output/..."
   }
   ```

## Research Report Structure

### Report Components
- **Executive Summary**: Business overview and key findings
- **Customer Profile**: Industry, location, and business intelligence
- **Category Analysis**: Primary/secondary category breakdown with revenue potential
- **Market Intelligence**: Current news and business developments
- **Recommendations**: Prioritized outreach strategies
- **Contact Information**: Specific contact details and personalization data
- **Citations**: Data sources and justification for recommendations

### Output Format
- **Markdown**: Executive-ready presentation format
- **Structured Data**: JSON format for downstream processing
- **Citations**: Traceable references to source data
- **Metadata**: Processing timestamps and batch information

## AI Models and Tools

### O3 Reasoning Model
- **High Reasoning Effort**: Complex analysis and decision-making
- **Structured Output**: Pydantic model validation
- **Tool Integration**: Access to additional data sources when needed

### Bing Search Integration
- **Real-time Information**: Current company news and developments
- **Citation Tracking**: Source URLs and titles
- **Relevance Filtering**: AI-powered result filtering

### Multi-Agent Architecture
- **Specialized Agents**: Each agent optimized for specific tasks
- **Agent Reuse**: Efficient agent lifecycle management
- **Error Handling**: Robust fallback mechanisms

## Error Handling

### Robust Processing
- **Queue Management**: Automatic retry and dead letter handling
- **Data Validation**: Type checking and format validation
- **Fallback Mechanisms**: Alternative processing paths
- **Status Tracking**: Comprehensive logging and monitoring

### Common Error Scenarios
- **Search API Failures**: Graceful degradation with cached data
- **Model Timeouts**: Retry logic with exponential backoff
- **Data Format Issues**: Automatic data cleaning and validation
- **Storage Failures**: Local caching and retry mechanisms

## Performance Considerations

### Optimization Strategies
- **Batch Processing**: Configurable message batch sizes
- **Agent Reuse**: Minimize agent creation overhead
- **Concurrent Processing**: Parallel web searches when possible
- **Caching**: Result caching for repeated queries

### Monitoring Metrics
- **Processing Time**: Customer analysis duration
- **Success Rate**: Successful report generation percentage
- **Queue Depth**: Backlog monitoring
- **Error Rates**: Failure tracking and alerting

## Integration Points

### Upstream Dependencies
- **GetData Agent**: Customer data preparation and queuing
- **Databricks**: Source data tables and status tracking
- **Azure AI Foundry**: Model deployment and Bing Search

### Downstream Consumers
- **Communication Agent**: Report consumption for email generation
- **Azure Blob Storage**: Report storage and archival
- **Databricks**: Status and audit logging

## Business Rules

### Customer Analysis Guidelines
- **Growth vs. Retention**: Strategic classification based on data analysis
- **Category Prioritization**: Primary categories take precedence
- **Revenue Focus**: Emphasis on high-value opportunities
- **B2B Context**: Staples Business branding and messaging

### Data Integrity
- **Source Validation**: All recommendations must be data-backed
- **Citation Requirements**: Traceable sources for all claims
- **No Fabrication**: Only existing categories and data points
- **Future-Focused**: Recommendations for post-current date

## Troubleshooting

### Common Issues

1. **Bing Search Connection Errors**
   - Verify ST_BING_CONNECTION_NAME configuration
   - Check Azure AI Foundry project permissions
   - Validate connection setup in Azure portal

2. **O3 Model Timeout**
   - Reduce reasoning effort level
   - Simplify prompt complexity
   - Check model deployment status

3. **Queue Processing Failures**
   - Verify queue connection strings
   - Check Azure Storage permissions
   - Monitor queue visibility timeouts

4. **Report Storage Issues**
   - Validate storage connection strings
   - Check container permissions
   - Verify blob naming conventions

### Debug Logging

The agent provides comprehensive logging:
- **File Logging**: Daily log files with detailed processing information
- **Console Logging**: Real-time processing status
- **Error Tracking**: Detailed error messages and stack traces
- **Performance Metrics**: Processing times and throughput

## Security Considerations

### Data Protection
- **Credential Management**: Environment variable-based configuration
- **Azure Authentication**: Managed identity and service principal support
- **Data Encryption**: In-transit and at-rest encryption
- **Access Control**: Role-based access to Azure resources

### Compliance
- **Audit Logging**: Comprehensive processing trails
- **Data Retention**: Configurable retention policies
- **Privacy Controls**: Customer data handling compliance
- **Security Scanning**: Regular dependency and vulnerability checks

## Contributing

When modifying the Research Agent:
1. Test with small customer datasets first
2. Validate all AI model integrations
3. Ensure report quality and format consistency
4. Update documentation for any new environment variables
5. Add appropriate error handling and logging
6. Test integration with upstream and downstream agents


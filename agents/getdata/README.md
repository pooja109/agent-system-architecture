# GetData Agent

## Overview

The GetData Agent is a data extraction and processing service that fetches B2B Customer data from multiple Databricks sources, processes it, and queues it for downstream analysis by the Research Agent. This agent serves as the initial data pipeline component for the low-touch customer analysis system.

## Purpose

This agent is designed to:
- Extract customer data from multiple Databricks tables (I2A, Transactions, DNB, Marketing) for different verticals (Commercial, Healthcare, SLED)
- Process and merge data across different datasets
- Filter customers based on whether there is Contact information available (for outreach)
- Queue processed customer data only for those customers where contact information is available, for research analysis
- Track processing status in Databricks status tables (S - Success ; N - Not Processed)

## Key Features

### Data Sources
- **I2A Data**: Insights-To-Action - B2B Customer account information with prioritized primary/secondary categories for outreach
- **Transaction Data**: Sales contact and transaction history
- **DNB Data**: Business information and website details
- **Marketing Data**: Marketing Category hierarchy and its mapping to I2A Categories

### Processing Logic
- Extracts customers from 3 verticals: Commercial, Healthcare, SLED 
- Merges I2A categories with marketing category mappings
- Filters out customers without contact details. These records are not processed. Status updated as 'N' in the databricks execution status table
- Creates consolidated customer profiles for downstream processing for customers with contact details

### Queue Management
- Publishes processed customer data to Azure Storage Queue
- Handles queue creation and connection management
- Implements error handling for queue operations

## Architecture

```
Databricks Tables → GetData Agent → Azure Queue → Research Agent
     ↓
Status Tracking Table
```

## File Structure

```
getdata/
├── __init__.py          # Package initialization
├── getdata.py           # Main data processing logic
├── requirements.txt     # Python dependencies
├── sample.env           # Environment variables template
├── .env                 # Environment variables (not in repo)
└── README.md            # This documentation
```

## Core Functions

### `get_data_from_databricks(query: str)`
- Executes SQL queries against Databricks
- Returns pandas DataFrame with results
- Handles connection management and error handling

### `update_status_in_databricks(status_cols, status_vals, table_name, status)`
- Updates processing status in Databricks status table
- Tracks batch processing and agent execution
- Provides audit trail for data processing

### `main()`
- Orchestrates the entire data extraction and processing workflow
- Manages customer data processing loop
- Handles queue operations and status updates

## Data Flow

1. **Data Extraction**: Fetches data from multiple Databricks tables
2. **Data Processing**: 
   - Merges I2A data with marketing categories
   - Filters customers by vertical and contact availability
   - Drops unused category columns (PRIMARY_CAT_3, SECONDARY_CAT_3)
3. **Queue Publishing**: Sends processed customer data to Azure Queue
4. **Status Tracking**: Updates Databricks with processing status

## Environment Variables

### Required Environment Variables

```bash
# Databricks Connection
DATABRICKS_SERVER_HOSTNAME=your_databricks_hostname
DATABRICKS_HTTP_PATH=your_http_path
DATABRICKS_TOKEN=your_databricks_token

# Database Table Configuration
DATABRICKS_STATUS_CATALOG_NAME=status_catalog
DATABRICKS_STATUS_SCHEMA_NAME=status_schema  
DATABRICKS_STATUS_TABLE_NAME=status_table

DATABRICKS_I2A_CATALOG_NAME=i2a_catalog
DATABRICKS_I2A_SCHEMA_NAME=i2a_schema
DATABRICKS_I2A_TABLE_NAME=i2a_table

DATABRICKS_TXN_CATALOG_NAME=txn_catalog
DATABRICKS_TXN_SCHEMA_NAME=txn_schema
DATABRICKS_TXN_TABLE_NAME=txn_table

DATABRICKS_DNB_CATALOG_NAME=dnb_catalog
DATABRICKS_DNB_SCHEMA_NAME=dnb_schema
DATABRICKS_DNB_TABLE_NAME=dnb_table

DATABRICKS_MKT_CATALOG_NAME=mkt_catalog
DATABRICKS_MKT_SCHEMA_NAME=mkt_schema
DATABRICKS_MKT_TABLE_NAME=mkt_table

DATABRICKS_I2A_MKT_CATALOG_NAME=i2a_mkt_catalog
DATABRICKS_I2A_MKT_SCHEMA_NAME=i2a_mkt_schema
DATABRICKS_I2A_MKT_TABLE_NAME=i2a_mkt_table

# Azure Queue Configuration
AZURE_QUEUE_CONNECTION_STRING=your_queue_connection_string
AZURE_TGT_QUEUE_NAME=your_target_queue_name
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

3. **Set up Azure Authentication**:
   - Ensure Azure CLI is installed and authenticated
   - Or configure service principal credentials

## Usage

### Running the Agent

```bash
python getdata.py
```

### Expected Output

The agent will:
1. Connect to Databricks and fetch customer data
2. Process and merge data from multiple sources
3. Send customer data to Azure Queue for research processing
4. Update status in Databricks tracking table
5. Log processing results and any errors

### Output Data Structure

Each customer message sent to the queue contains:

```json
{
  "batch_id": "20250130120000",
  "run_date": "2025-01-30 12:00:00", 
  "agent_name": "db_Data_Agent",
  "status": "S",
  "customer_id": "12345",
  "i2a_data": "[{customer account data}]",
  "transactions_data": "[{transaction data}]", 
  "dnb_data": "[{business data}]",
  "marketing_data": "[{marketing category data}]"
}
```

## Error Handling

- **Database Connection Errors**: Logged and execution stops
- **Queue Connection Errors**: Attempts to create queue if not found
- **Data Processing Errors**: Individual customer errors logged, processing continues
- **Status Update Errors**: Logged but don't halt processing

## Logging

The agent uses Python's logging module with:
- INFO level logging to console
- Detailed logging of data extraction steps
- Customer processing progress tracking
- Error logging with stack traces

## Customer Filtering Logic

### Included Customers
- Commercial vertical: Customers with contact details belonging to the Commercial Vertical
- Healthcare vertical: Customers with contact details belonging to the Healthcare Vertical 
- SLED vertical: Customers with contact details belonging to the SLED Vertical
- Must have corresponding contact details in the transaction data

### Excluded Customers
- Customers without contact/transaction details
- Marked with status "N" in tracking table

## Dependencies

Key Python packages:
- `pandas`: Data manipulation and analysis
- `databricks-sql-connector`: Databricks connectivity
- `azure-storage-queue`: Azure Queue operations
- `azure-identity`: Azure authentication
- `python-dotenv`: Environment variable management

## Monitoring

### Success Indicators
- Messages successfully queued for research processing
- Status records created in Databricks tracking table
- No unhandled exceptions in logs

### Failure Indicators  
- Database connection failures
- Queue publishing failures
- Missing environment variables
- Data extraction errors

## Next Steps

After successful execution, customer data flows to:
1. **Research Agent**: Performs detailed customer analysis
2. **Communication Agent**: Generates personalized outreach content
3. **Email Agent**: Delivers final communications

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check Databricks credentials and network access
   - Verify hostname and HTTP path configuration

2. **Queue Not Found**
   - Ensure queue connection string is correct
   - Check Azure permissions for queue operations

3. **No Customer Data**
   - Verify table names and schema configuration
   - Check if source tables contain expected data

4. **Environment Variable Errors**
   - Ensure all required variables are set in .env file
   - Check for typos in variable names

## Contributing

When modifying this agent:
1. Test with small customer datasets first
2. Verify data quality and completeness
3. Check downstream agent compatibility
4. Update documentation for any new environment variables
5. Add appropriate error handling and logging

#!/usr/bin/env python3
"""
Pipeline Data Population Script
===============================

This script populates the email_communication_pipeline table with historical data
from the blob storage account. It processes research and communication files to
create the necessary database records.

Usage:
    python scripts/populate_pipeline_data.py --date-folder 20250707 [--dry-run]
"""

import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from services.blob_service import BlobStorageService
from database.databricks_client import DatabricksClient
from database.models import EmailRecord

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class FileInfo:
    """Information about a file in blob storage."""
    blob_name: str
    full_path: str
    last_modified: datetime
    size: int
    customer_id: str

@dataclass
class CustomerData:
    """Data for a single customer."""
    customer_id: str
    research_file: Optional[FileInfo] = None
    communication_files: List[FileInfo] = None
    
    def __post_init__(self):
        if self.communication_files is None:
            self.communication_files = []

class PipelineDataPopulator:
    """Populates pipeline data from blob storage."""
    
    def __init__(self, settings):
        """Initialize the populator."""
        self.settings = settings
        self.blob_service = BlobStorageService(settings.azure_storage)
        self.databricks_client = DatabricksClient(settings.databricks)
        self.batch_id = None
        self.processed_count = 0
        self.error_count = 0
        self.warnings = []
        
    def _get_next_batch_id(self) -> int:
        """Get the next batch ID by finding the max existing batch_id."""
        try:
            query = f"""
            SELECT COALESCE(MAX(batch_id), 0) + 1 as next_batch_id 
            FROM {self.databricks_client._table_name}
            """
            
            results = self.databricks_client.execute_query(query)
            if results and len(results) > 0:
                return results[0]['next_batch_id']
            else:
                return 1
                
        except Exception as e:
            logger.warning(f"Could not get next batch ID, defaulting to 1: {e}")
            return 1
    
    def delete_existing_records(self, dry_run: bool = False) -> bool:
        """Delete all existing records from the pipeline table."""
        try:
            if dry_run:
                # Count records that would be deleted
                count_query = f"SELECT COUNT(*) as record_count FROM {self.databricks_client._table_name}"
                results = self.databricks_client.execute_query(count_query)
                count = results[0]['record_count'] if results else 0
                logger.info(f"DRY RUN: Would delete {count} existing records")
                return True
            
            # Delete all records
            delete_query = f"DELETE FROM {self.databricks_client._table_name}"
            
            logger.info("Deleting existing records from pipeline table...")
            affected_rows = self.databricks_client.execute_update(delete_query)
            
            logger.info(f"Successfully deleted {affected_rows} existing records")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting existing records: {e}")
            return False
    
    def _get_blob_path(self, blob_name: str) -> str:
        """Get blob path for database storage (without SAS token)."""
        return blob_name
    
    def _get_file_info(self, blob_name: str) -> Optional[FileInfo]:
        """Get file information from blob storage."""
        try:
            blob_client = self.blob_service.container_client.get_blob_client(blob_name)
            properties = blob_client.get_blob_properties()
            
            # Extract customer_id from blob name
            path_parts = blob_name.split('/')
            if len(path_parts) >= 2:
                customer_id = path_parts[1]
            else:
                customer_id = "unknown"
            
            return FileInfo(
                blob_name=blob_name,
                full_path=self._get_blob_path(blob_name),
                last_modified=properties.last_modified,
                size=properties.size,
                customer_id=customer_id
            )
            
        except Exception as e:
            logger.error(f"Error getting file info for {blob_name}: {e}")
            return None
    
    def scan_date_folder(self, date_folder: str) -> List[CustomerData]:
        """Scan a date folder and collect customer data."""
        logger.info(f"Scanning date folder: {date_folder}")
        
        customer_data = {}
        
        try:
            # List all blobs in the date folder
            blobs = self.blob_service.container_client.list_blobs(name_starts_with=f"{date_folder}/")
            
            for blob in blobs:
                blob_name = blob.name
                path_parts = blob_name.split('/')
                
                # Expected structure: 20250707/10016125/research_output/file.md
                if len(path_parts) < 4:
                    continue
                    
                date_part = path_parts[0]
                customer_id = path_parts[1]
                folder_type = path_parts[2]
                file_name = path_parts[3]
                
                # Initialize customer data if not exists
                if customer_id not in customer_data:
                    customer_data[customer_id] = CustomerData(customer_id=customer_id)
                
                # Get file info
                file_info = self._get_file_info(blob_name)
                if not file_info:
                    continue
                
                # Process based on folder type
                if folder_type == "research_output" and file_name.endswith('.md'):
                    customer_data[customer_id].research_file = file_info
                    logger.debug(f"Found research file for {customer_id}: {file_name}")
                    
                elif folder_type == "communication_output":
                    # Check for expected communication files
                    expected_files = [
                        f"{customer_id}_email.html",
                        f"{customer_id}_feedback.json", 
                        f"{customer_id}_research_output.json"
                    ]
                    
                    if file_name in expected_files:
                        customer_data[customer_id].communication_files.append(file_info)
                        logger.debug(f"Found communication file for {customer_id}: {file_name}")
                    else:
                        logger.warning(f"Unexpected communication file for {customer_id}: {file_name}")
            
            logger.info(f"Found {len(customer_data)} customers in {date_folder}")
            return list(customer_data.values())
            
        except Exception as e:
            logger.error(f"Error scanning date folder {date_folder}: {e}")
            return []
    
    def validate_customer_data(self, customer_data: List[CustomerData]) -> List[CustomerData]:
        """Validate customer data and log any issues."""
        valid_customers = []
        
        for customer in customer_data:
            issues = []
            
            # Check for research file
            if not customer.research_file:
                issues.append("Missing research .md file")
            
            # Check for communication files
            expected_comm_files = 3
            if len(customer.communication_files) != expected_comm_files:
                issues.append(f"Expected {expected_comm_files} communication files, found {len(customer.communication_files)}")
            
            # Check for specific communication files
            comm_file_names = [os.path.basename(f.blob_name) for f in customer.communication_files]
            expected_patterns = ['_email.html', '_feedback.json', '_research_output.json']
            
            for pattern in expected_patterns:
                if not any(pattern in name for name in comm_file_names):
                    issues.append(f"Missing communication file with pattern: {pattern}")
            
            if issues:
                self.warnings.append(f"Customer {customer.customer_id}: {'; '.join(issues)}")
                logger.warning(f"Customer {customer.customer_id} has issues: {'; '.join(issues)}")
                self.error_count += 1
            else:
                valid_customers.append(customer)
        
        logger.info(f"Validated {len(valid_customers)} customers out of {len(customer_data)}")
        return valid_customers
    
    def create_database_records(self, customer_data: List[CustomerData], dry_run: bool = False) -> List[EmailRecord]:
        """Create database records for the customer data."""
        records = []
        
        for customer in customer_data:
            # Create research record
            if customer.research_file:
                research_record = EmailRecord(
                    batch_id=self.batch_id,
                    run_date=customer.research_file.last_modified.strftime('%Y-%m-%d'),
                    agent_name='research',
                    status='S',
                    customer_id=customer.customer_id,
                    input_file=None,  # NULL for research records
                    output_file=customer.research_file.full_path,
                    is_reviewed=None,
                    is_approved=None,
                    is_email_sent=None,
                    blob_date_folder=customer.research_file.blob_name.split('/')[0],
                    json_file_path=None,
                    html_file_path=None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                records.append(research_record)
            
            # Create communication records (one for each file)
            for comm_file in customer.communication_files:
                # Determine file type and set appropriate paths
                file_name = os.path.basename(comm_file.blob_name)
                json_file_path = None
                html_file_path = None
                
                if file_name.endswith('.html'):
                    html_file_path = comm_file.full_path
                elif file_name.endswith('.json'):
                    json_file_path = comm_file.full_path
                
                comm_record = EmailRecord(
                    batch_id=self.batch_id,
                    run_date=comm_file.last_modified.strftime('%Y-%m-%d'),
                    agent_name='communication',
                    status='S',
                    customer_id=customer.customer_id,
                    input_file=customer.research_file.full_path if customer.research_file else None,
                    output_file=comm_file.full_path,
                    is_reviewed=None,
                    is_approved=True,
                    is_email_sent=False,
                    blob_date_folder=comm_file.blob_name.split('/')[0],
                    json_file_path=json_file_path,
                    html_file_path=html_file_path,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                records.append(comm_record)
        
        logger.info(f"Created {len(records)} database records")
        return records
    
    def insert_records(self, records: List[EmailRecord], dry_run: bool = False) -> bool:
        """Insert records into the database."""
        if dry_run:
            logger.info(f"DRY RUN: Would insert {len(records)} records")
            for record in records[:5]:  # Show first 5 as example
                logger.info(f"  - {record.agent_name} record for customer {record.customer_id}")
            if len(records) > 5:
                logger.info(f"  ... and {len(records) - 5} more records")
            return True
        
        try:
            for record in records:
                # Insert the record
                query = f"""
                INSERT INTO {self.databricks_client._table_name} (
                    batch_id, run_date, agent_name, status, customer_id,
                    input_file, output_file, is_reviewed, is_approved, is_email_sent,
                    blob_date_folder, json_file_path, html_file_path,
                    created_at, updated_at, processed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                parameters = [
                    record.batch_id,
                    record.run_date,
                    record.agent_name,
                    record.status,
                    record.customer_id,
                    record.input_file,
                    record.output_file,
                    record.is_reviewed,
                    record.is_approved,
                    record.is_email_sent,
                    record.blob_date_folder,
                    record.json_file_path,
                    record.html_file_path,
                    record.created_at,
                    record.updated_at,
                    record.processed_by
                ]
                
                self.databricks_client.execute_update(query, parameters)
                self.processed_count += 1
            
            logger.info(f"Successfully inserted {len(records)} records")
            return True
            
        except Exception as e:
            logger.error(f"Error inserting records: {e}")
            return False
    
    async def populate_data(self, date_folder: str, dry_run: bool = False) -> bool:
        """Main method to populate pipeline data."""
        logger.info(f"Starting pipeline data population for {date_folder}")
        
        try:
            # Connect to Databricks
            if not self.databricks_client.connect():
                logger.error("Failed to connect to Databricks")
                return False
            
            # Delete existing records first
            if not self.delete_existing_records(dry_run):
                logger.error("Failed to delete existing records")
                return False
            
            # Get batch ID (should be 1 after deletion)
            self.batch_id = 1 if not dry_run else self._get_next_batch_id()
            logger.info(f"Using batch_id: {self.batch_id}")
            
            # Scan blob storage
            customer_data = self.scan_date_folder(date_folder)
            if not customer_data:
                logger.error("No customer data found")
                return False
            
            # Validate data
            valid_customers = self.validate_customer_data(customer_data)
            if not valid_customers:
                logger.error("No valid customers found")
                return False
            
            # Create database records
            records = self.create_database_records(valid_customers, dry_run)
            
            # Insert records
            success = self.insert_records(records, dry_run)
            
            # Print summary
            self.print_summary(valid_customers, records)
            
            return success
            
        except Exception as e:
            logger.error(f"Error in populate_data: {e}")
            return False
        finally:
            self.databricks_client.disconnect()
    
    def print_summary(self, customers: List[CustomerData], records: List[EmailRecord]):
        """Print a summary of the population process."""
        print("\n" + "="*80)
        print("PIPELINE DATA POPULATION SUMMARY")
        print("="*80)
        print(f"Batch ID: {self.batch_id}")
        print(f"Customers processed: {len(customers)}")
        print(f"Records created: {len(records)}")
        print(f"Successful inserts: {self.processed_count}")
        print(f"Errors encountered: {self.error_count}")
        
        # Count by agent type
        research_count = sum(1 for r in records if r.agent_name == 'research')
        comm_count = sum(1 for r in records if r.agent_name == 'communication')
        
        print(f"\nRecord breakdown:")
        print(f"  Research records: {research_count}")
        print(f"  Communication records: {comm_count}")
        
        # Show warnings
        if self.warnings:
            print(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings[:10]:  # Show first 10
                print(f"  ⚠️  {warning}")
            if len(self.warnings) > 10:
                print(f"  ... and {len(self.warnings) - 10} more warnings")
        
        print("="*80)

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Populate pipeline data from blob storage",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--date-folder',
        required=True,
        help='Date folder to process (e.g., 20250707)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually inserting records'
    )
    
    args = parser.parse_args()
    
    try:
        # Load settings
        settings = get_settings()
        
        # Create populator
        populator = PipelineDataPopulator(settings)
        
        # Run population
        success = await populator.populate_data(args.date_folder, args.dry_run)
        
        if success:
            print("\n✅ Pipeline data population completed successfully!")
            return 0
        else:
            print("\n❌ Pipeline data population failed!")
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
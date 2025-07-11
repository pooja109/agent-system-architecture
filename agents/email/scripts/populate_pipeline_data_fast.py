#!/usr/bin/env python3
"""
Fast Pipeline Data Population Script
====================================

A more efficient version that processes customers in smaller batches.
"""

import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from services.blob_service import BlobStorageService
from database.databricks_client import DatabricksClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FastPipelinePopulator:
    """Fast pipeline data populator."""
    
    def __init__(self, settings):
        self.settings = settings
        self.blob_service = BlobStorageService(settings.azure_storage)
        self.databricks_client = DatabricksClient(settings.databricks)
        self.batch_id = None
        
    def get_next_batch_id(self) -> int:
        """Get next batch ID."""
        try:
            query = f"""
            SELECT COALESCE(MAX(batch_id), 0) + 1 as next_batch_id 
            FROM {self.databricks_client._table_name}
            """
            results = self.databricks_client.execute_query(query)
            return results[0]['next_batch_id'] if results else 1
        except:
            return 1
    
    def construct_blob_url(self, blob_name: str) -> str:
        """Construct blob URL."""
        if self.settings.azure_storage.account_name:
            base_url = f"https://{self.settings.azure_storage.account_name}.blob.core.windows.net/{self.settings.azure_storage.container_name}/{blob_name}"
            if self.settings.azure_storage.sas_token:
                sas_token = self.settings.azure_storage.sas_token.lstrip('?')
                return f"{base_url}?{sas_token}"
            return base_url
        return f"https://storage.blob.core.windows.net/{self.settings.azure_storage.container_name}/{blob_name}"
    
    def scan_customers_quick(self, date_folder: str) -> Dict[str, Dict]:
        """Quick scan to find customers and their files."""
        print(f"🔍 Scanning {date_folder} folder...")
        
        customers = defaultdict(lambda: {
            'research_files': [],
            'communication_files': []
        })
        
        try:
            blobs = self.blob_service.container_client.list_blobs(name_starts_with=f"{date_folder}/")
            
            count = 0
            for blob in blobs:
                count += 1
                if count % 100 == 0:
                    print(f"   Processed {count} files...")
                
                parts = blob.name.split('/')
                if len(parts) >= 4:
                    customer_id = parts[1]
                    folder_type = parts[2]
                    file_name = parts[3]
                    
                    if folder_type == "research_output" and file_name.endswith('.md'):
                        customers[customer_id]['research_files'].append({
                            'blob_name': blob.name,
                            'url': self.construct_blob_url(blob.name),
                            'last_modified': blob.last_modified.strftime('%Y-%m-%d')
                        })
                    elif folder_type == "communication_output":
                        customers[customer_id]['communication_files'].append({
                            'blob_name': blob.name,
                            'url': self.construct_blob_url(blob.name),
                            'last_modified': blob.last_modified.strftime('%Y-%m-%d'),
                            'file_name': file_name
                        })
            
            print(f"✅ Found {len(customers)} customers, {count} total files")
            return dict(customers)
            
        except Exception as e:
            print(f"❌ Error scanning: {e}")
            return {}
    
    def validate_and_insert(self, customers: Dict, dry_run: bool = False) -> bool:
        """Validate customer data and insert records."""
        print(f"🔧 Processing {len(customers)} customers...")
        
        valid_customers = 0
        total_records = 0
        warnings = []
        
        for customer_id, data in customers.items():
            # Validate customer data
            issues = []
            
            if not data['research_files']:
                issues.append("No research .md file")
            elif len(data['research_files']) > 1:
                issues.append(f"Multiple research files: {len(data['research_files'])}")
            
            if len(data['communication_files']) != 3:
                issues.append(f"Expected 3 communication files, found {len(data['communication_files'])}")
            
            if issues:
                warnings.append(f"Customer {customer_id}: {'; '.join(issues)}")
                continue
                
            valid_customers += 1
            
            # Create records for this customer
            records = []
            current_time = datetime.now(timezone.utc).isoformat()
            
            # Research record
            research_file = data['research_files'][0]
            records.append({
                'batch_id': self.batch_id,
                'run_date': research_file['last_modified'],
                'agent_name': 'research',
                'status': 'S',
                'customer_id': customer_id,
                'input_file': None,
                'output_file': research_file['url'],
                'is_reviewed': None,
                'is_approved': None,
                'is_email_sent': None,
                'blob_date_folder': research_file['blob_name'].split('/')[0],
                'json_file_path': None,
                'html_file_path': None,
                'created_at': current_time,
                'updated_at': current_time,
                'processed_by': 'populate_pipeline_data'
            })
            
            # Communication records
            for comm_file in data['communication_files']:
                json_file_path = comm_file['url'] if comm_file['file_name'].endswith('.json') else None
                html_file_path = comm_file['url'] if comm_file['file_name'].endswith('.html') else None
                
                records.append({
                    'batch_id': self.batch_id,
                    'run_date': comm_file['last_modified'],
                    'agent_name': 'communication',
                    'status': 'S',
                    'customer_id': customer_id,
                    'input_file': research_file['url'],
                    'output_file': comm_file['url'],
                    'is_reviewed': None,
                    'is_approved': True,
                    'is_email_sent': False,
                    'blob_date_folder': comm_file['blob_name'].split('/')[0],
                    'json_file_path': json_file_path,
                    'html_file_path': html_file_path,
                    'created_at': current_time,
                    'updated_at': current_time,
                    'processed_by': 'populate_pipeline_data'
                })
            
            total_records += len(records)
            
            # Insert records
            if not dry_run:
                try:
                    for record in records:
                        query = f"""
                        INSERT INTO {self.databricks_client._table_name} (
                            batch_id, run_date, agent_name, status, customer_id,
                            input_file, output_file, is_reviewed, is_approved, is_email_sent,
                            blob_date_folder, json_file_path, html_file_path,
                            created_at, updated_at, processed_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        
                        self.databricks_client.execute_update(query, [
                            record['batch_id'], record['run_date'], record['agent_name'],
                            record['status'], record['customer_id'], record['input_file'],
                            record['output_file'], record['is_reviewed'], record['is_approved'],
                            record['is_email_sent'], record['blob_date_folder'],
                            record['json_file_path'], record['html_file_path'],
                            record['created_at'], record['updated_at'], record['processed_by']
                        ])
                        
                except Exception as e:
                    print(f"❌ Error inserting records for customer {customer_id}: {e}")
                    continue
            
            if valid_customers % 10 == 0:
                print(f"   Processed {valid_customers} customers...")
        
        # Print results
        print(f"\n{'='*60}")
        print(f"POPULATION SUMMARY - Batch ID: {self.batch_id}")
        print(f"{'='*60}")
        print(f"Valid customers: {valid_customers}")
        print(f"Total records: {total_records}")
        print(f"Warnings: {len(warnings)}")
        
        if warnings:
            print(f"\nWarnings:")
            for warning in warnings[:10]:
                print(f"  ⚠️  {warning}")
            if len(warnings) > 10:
                print(f"  ... and {len(warnings) - 10} more")
        
        if dry_run:
            print(f"\n🔍 DRY RUN: No records were actually inserted")
        else:
            print(f"\n✅ Records inserted into database")
        
        return True
    
    async def populate(self, date_folder: str, dry_run: bool = False) -> bool:
        """Main population method."""
        try:
            # Connect to Databricks
            if not self.databricks_client.connect():
                print("❌ Failed to connect to Databricks")
                return False
            
            # Get batch ID
            self.batch_id = self.get_next_batch_id()
            print(f"📋 Using batch ID: {self.batch_id}")
            
            # Scan customers
            customers = self.scan_customers_quick(date_folder)
            if not customers:
                print("❌ No customers found")
                return False
            
            # Process customers
            return self.validate_and_insert(customers, dry_run)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
        finally:
            self.databricks_client.disconnect()

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fast pipeline data population")
    parser.add_argument('--date-folder', required=True, help='Date folder (e.g., 20250707)')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    
    args = parser.parse_args()
    
    settings = get_settings()
    populator = FastPipelinePopulator(settings)
    
    success = await populator.populate(args.date_folder, args.dry_run)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
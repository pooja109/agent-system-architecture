#!/usr/bin/env python3
"""
Simple Pipeline Data Population
===============================
"""

import sys
import os
from datetime import datetime, timezone
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from services.blob_service import BlobStorageService
from database.databricks_client import DatabricksClient

def main():
    print("🚀 Starting pipeline data population for 20250707")
    
    # Load settings and initialize services
    settings = get_settings()
    blob_service = BlobStorageService(settings.azure_storage)
    databricks_client = DatabricksClient(settings.databricks)
    
    # Connect to Databricks
    if not databricks_client.connect():
        print("❌ Failed to connect to Databricks")
        return 1
    
    # Get next batch ID
    try:
        query = f"SELECT COALESCE(MAX(batch_id), 0) + 1 as next_batch_id FROM {databricks_client._table_name}"
        result = databricks_client.execute_query(query)
        batch_id = result[0]['next_batch_id'] if result else 1
    except:
        batch_id = 1
    
    print(f"📋 Using batch ID: {batch_id}")
    
    # Scan blob storage
    print("🔍 Scanning blob storage...")
    customers = defaultdict(lambda: {'research': [], 'communication': []})
    
    try:
        blobs = blob_service.container_client.list_blobs(name_starts_with="20250707/")
        file_count = 0
        
        for blob in blobs:
            file_count += 1
            if file_count % 50 == 0:
                print(f"   Processed {file_count} files...")
            
            parts = blob.name.split('/')
            if len(parts) >= 4:
                customer_id = parts[1]
                folder_type = parts[2]
                file_name = parts[3]
                
                # Construct blob URL
                if settings.azure_storage.account_name:
                    base_url = f"https://{settings.azure_storage.account_name}.blob.core.windows.net/{settings.azure_storage.container_name}/{blob.name}"
                    if settings.azure_storage.sas_token:
                        sas_token = settings.azure_storage.sas_token.lstrip('?')
                        blob_url = f"{base_url}?{sas_token}"
                    else:
                        blob_url = base_url
                else:
                    blob_url = f"https://storage.blob.core.windows.net/{settings.azure_storage.container_name}/{blob.name}"
                
                file_info = {
                    'blob_name': blob.name,
                    'url': blob_url,
                    'last_modified': blob.last_modified.strftime('%Y-%m-%d'),
                    'file_name': file_name
                }
                
                if folder_type == "research_output" and file_name.endswith('.md'):
                    customers[customer_id]['research'].append(file_info)
                elif folder_type == "communication_output":
                    customers[customer_id]['communication'].append(file_info)
        
        print(f"✅ Found {len(customers)} customers, {file_count} total files")
        
    except Exception as e:
        print(f"❌ Error scanning blob storage: {e}")
        return 1
    
    # Process customers and insert records
    print(f"🔧 Processing customers...")
    
    valid_customers = 0
    total_records = 0
    warnings = []
    
    for customer_id, data in customers.items():
        # Validate customer data
        issues = []
        
        if not data['research']:
            issues.append("No research .md file")
        elif len(data['research']) > 1:
            issues.append(f"Multiple research files: {len(data['research'])}")
        
        if len(data['communication']) != 3:
            issues.append(f"Expected 3 communication files, found {len(data['communication'])}")
        
        if issues:
            warnings.append(f"Customer {customer_id}: {'; '.join(issues)}")
            continue
        
        valid_customers += 1
        
        # Insert research record
        research_file = data['research'][0]
        current_time = datetime.now(timezone.utc).isoformat()
        
        try:
            query = f"""
            INSERT INTO {databricks_client._table_name} (
                batch_id, run_date, agent_name, status, customer_id,
                input_file, output_file, is_reviewed, is_approved, is_email_sent,
                blob_date_folder, created_at, updated_at, processed_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            databricks_client.execute_update(query, [
                batch_id,
                research_file['last_modified'],
                'research',
                'S',
                customer_id,
                None,  # input_file is NULL for research
                research_file['url'],
                None,  # is_reviewed
                None,  # is_approved
                None,  # is_email_sent
                '20250707',
                current_time,
                current_time,
                'populate_simple'
            ])
            
            total_records += 1
            
        except Exception as e:
            print(f"❌ Error inserting research record for {customer_id}: {e}")
            continue
        
        # Insert communication records
        for comm_file in data['communication']:
            try:
                json_file_path = comm_file['url'] if comm_file['file_name'].endswith('.json') else None
                html_file_path = comm_file['url'] if comm_file['file_name'].endswith('.html') else None
                
                query = f"""
                INSERT INTO {databricks_client._table_name} (
                    batch_id, run_date, agent_name, status, customer_id,
                    input_file, output_file, is_reviewed, is_approved, is_email_sent,
                    blob_date_folder, json_file_path, html_file_path,
                    created_at, updated_at, processed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                databricks_client.execute_update(query, [
                    batch_id,
                    comm_file['last_modified'],
                    'communication',
                    'S',
                    customer_id,
                    research_file['url'],  # input_file points to research
                    comm_file['url'],
                    None,  # is_reviewed
                    True,  # is_approved
                    False,  # is_email_sent
                    '20250707',
                    json_file_path,
                    html_file_path,
                    current_time,
                    current_time,
                    'populate_simple'
                ])
                
                total_records += 1
                
            except Exception as e:
                print(f"❌ Error inserting communication record for {customer_id}: {e}")
                continue
        
        if valid_customers % 10 == 0:
            print(f"   Processed {valid_customers} customers...")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"POPULATION SUMMARY - Batch ID: {batch_id}")
    print(f"{'='*60}")
    print(f"Valid customers: {valid_customers}")
    print(f"Total records inserted: {total_records}")
    print(f"Warnings: {len(warnings)}")
    
    if warnings:
        print(f"\nWarnings:")
        for warning in warnings[:10]:
            print(f"  ⚠️  {warning}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")
    
    print(f"\n✅ Population completed successfully!")
    
    databricks_client.disconnect()
    return 0

if __name__ == "__main__":
    sys.exit(main())
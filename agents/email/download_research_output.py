#!/usr/bin/env python3
"""
Download Research Output for Customer
=====================================

Downloads the research output JSON for customer 10223539.
"""

import sys
import os
import json

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config.settings import get_settings, validate_settings
from services.blob_service import BlobStorageService

def download_research_output():
    """Download and display the research output JSON."""
    print("🔍 Downloading research output for customer 10223539...")
    
    # Initialize settings
    settings = get_settings()
    validate_settings(settings)
    
    # Create blob service
    blob_service = BlobStorageService(settings.azure_storage)
    
    # Test connection
    if not blob_service.test_connection():
        print("❌ Failed to connect to blob storage")
        return
    
    # Download the research output JSON
    blob_name = "20250707/10223539/communication_output/10223539_research_output.json"
    
    try:
        json_content = blob_service.download_blob_content(blob_name)
        if json_content:
            # Parse and display the JSON
            data = json.loads(json_content)
            
            # Save to file
            output_file = "customer_10223539_research_output.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ Downloaded research output ({len(json_content)} characters)")
            print(f"💾 Saved to: {os.path.abspath(output_file)}")
            
            # Display key information
            print("\n📊 Key Information:")
            print(f"   Customer Name: {data.get('customer_name', 'Unknown')}")
            print(f"   Customer ID: {data.get('customer_id', 'Unknown')}")
            print(f"   Email Subject: {data.get('sample_email_subject', 'Unknown')}")
            
            # Display contact information
            contact_list = data.get('contact_list', [])
            print(f"   Contacts: {len(contact_list)}")
            for i, contact in enumerate(contact_list):
                print(f"     {i+1}. {contact.get('full_name', 'Unknown')} ({contact.get('email', 'No email')})")
            
            print(f"\n📄 Full JSON content saved to: {output_file}")
            
        else:
            print("❌ Failed to download research output")
            
    except Exception as e:
        print(f"❌ Error downloading research output: {e}")

if __name__ == "__main__":
    download_research_output()
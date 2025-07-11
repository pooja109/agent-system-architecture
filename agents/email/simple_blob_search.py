#!/usr/bin/env python3
"""
Simple Blob Search
==================

This script directly searches blob storage for customer files using a simpler approach.
"""

import sys
import os
from typing import List

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config.settings import get_settings, validate_settings
from services.blob_service import BlobStorageService

def search_blob_directly(customer_id: str):
    """Search blob storage directly for customer files."""
    print(f"🔍 Searching blob storage for customer {customer_id}...")
    
    # Initialize settings
    settings = get_settings()
    validate_settings(settings)
    
    # Create blob service
    blob_service = BlobStorageService(settings.azure_storage)
    
    # Test connection
    if not blob_service.test_connection():
        print("❌ Failed to connect to blob storage")
        return
    
    print("✅ Connected to blob storage")
    
    # List all blobs that contain the customer ID
    try:
        # Try listing blobs with customer ID prefix
        print(f"🔍 Searching for blobs containing customer ID {customer_id}...")
        
        # Search for blobs with customer ID in the path
        found_blobs = []
        
        # Try different date patterns (recent dates)
        date_patterns = [
            "20250707", "20250708", "20250709", "20250710",  # Recent dates
            "20250701", "20250702", "20250703", "20250704", "20250705", "20250706",  # July 2025
            "20250630", "20250629", "20250628",  # End of June 2025
        ]
        
        for date_pattern in date_patterns:
            prefix = f"{date_pattern}/{customer_id}/"
            print(f"   Checking: {prefix}")
            
            try:
                blobs = blob_service.container_client.list_blobs(name_starts_with=prefix)
                blob_list = list(blobs)
                
                if blob_list:
                    print(f"   ✅ Found {len(blob_list)} blobs in {date_pattern}")
                    for blob in blob_list:
                        found_blobs.append({
                            'name': blob.name,
                            'size': blob.size,
                            'last_modified': blob.last_modified
                        })
                        print(f"      📄 {blob.name}")
                        
                        # If this is an HTML email file, download and examine it
                        if blob.name.endswith('_email.html'):
                            print(f"      📧 Found HTML email file!")
                            try:
                                html_content = blob_service.download_blob_content(blob.name)
                                if html_content:
                                    print(f"      📥 Downloaded HTML content ({len(html_content)} characters)")
                                    
                                    # Save to a local file for examination
                                    output_file = f"customer_{customer_id}_email.html"
                                    with open(output_file, 'w', encoding='utf-8') as f:
                                        f.write(html_content)
                                    
                                    print(f"      💾 Saved to: {os.path.abspath(output_file)}")
                                    
                                    # Show preview
                                    preview = html_content[:500] + "..." if len(html_content) > 500 else html_content
                                    print(f"      👀 Preview:")
                                    print("-" * 40)
                                    print(preview)
                                    print("-" * 40)
                                else:
                                    print(f"      ❌ Failed to download HTML content")
                            except Exception as e:
                                print(f"      ❌ Error downloading HTML: {e}")
                else:
                    print(f"   ❌ No blobs found in {date_pattern}")
                    
            except Exception as e:
                print(f"   ❌ Error searching {date_pattern}: {e}")
        
        if not found_blobs:
            print(f"❌ No blobs found for customer {customer_id}")
            print("   Trying broader search...")
            
            # Try searching all blobs (limited to first 1000)
            try:
                print("🔍 Searching first 1000 blobs for customer ID...")
                all_blobs = blob_service.container_client.list_blobs()
                count = 0
                
                for blob in all_blobs:
                    count += 1
                    if count > 1000:
                        break
                    
                    if customer_id in blob.name:
                        print(f"   ✅ Found: {blob.name}")
                        found_blobs.append({
                            'name': blob.name,
                            'size': blob.size,
                            'last_modified': blob.last_modified
                        })
                        
                        # If this is an HTML email file, download it
                        if blob.name.endswith('_email.html'):
                            print(f"      📧 Found HTML email file!")
                            try:
                                html_content = blob_service.download_blob_content(blob.name)
                                if html_content:
                                    print(f"      📥 Downloaded HTML content ({len(html_content)} characters)")
                                    
                                    # Save to a local file for examination
                                    output_file = f"customer_{customer_id}_email.html"
                                    with open(output_file, 'w', encoding='utf-8') as f:
                                        f.write(html_content)
                                    
                                    print(f"      💾 Saved to: {os.path.abspath(output_file)}")
                                    
                                    # Show preview
                                    preview = html_content[:500] + "..." if len(html_content) > 500 else html_content
                                    print(f"      👀 Preview:")
                                    print("-" * 40)
                                    print(preview)
                                    print("-" * 40)
                            except Exception as e:
                                print(f"      ❌ Error downloading HTML: {e}")
                
                print(f"🔍 Searched {count} blobs")
                
            except Exception as e:
                print(f"❌ Error in broader search: {e}")
        
        if found_blobs:
            print(f"\n📊 Summary: Found {len(found_blobs)} files for customer {customer_id}")
            for blob_info in found_blobs:
                print(f"   📄 {blob_info['name']} ({blob_info['size']} bytes)")
        else:
            print(f"\n❌ No files found for customer {customer_id}")
            
    except Exception as e:
        print(f"❌ Error searching blob storage: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple blob storage search for customer files")
    parser.add_argument('--customer', '-c', required=True, help='Customer ID to search for')
    
    args = parser.parse_args()
    
    search_blob_directly(args.customer)
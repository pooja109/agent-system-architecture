#!/usr/bin/env python3
"""
Query Salesforce Record Types for Case object.
This script will help find the correct Record Type ID for Support Request cases.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the path so we can import modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def get_salesforce_record_types():
    """Query Salesforce for available Case Record Types."""
    try:
        from config.settings import get_settings
        from services.salesforce_client import SalesforceClient
        from utils.custom_logging import initialize_logging, LoggingConfig
        
        # Initialize logging
        logging_config = LoggingConfig()
        initialize_logging(logging_config)
        
        print("🔍 Querying Salesforce Record Types...")
        
        # Get settings - use test mode to get proper credentials
        settings = await get_settings(test_mode=False)
        
        print(f"📍 Salesforce Base URL: {settings.salesforce.base_url}")
        print(f"📍 API Version: {settings.salesforce.api_version}")
        
        # Create Salesforce client
        async with SalesforceClient(settings.salesforce) as sf_client:
            # Get access token first to test connection
            print("🔗 Authenticating with Salesforce...")
            access_token = await sf_client._get_access_token()
            print("✅ Successfully authenticated with Salesforce")
            
            # Query Case object metadata to get Record Types
            print("📋 Querying Case Record Types...")
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }
            
            # Query the Case object describe to get Record Types
            describe_url = f"{settings.salesforce.base_url}/services/data/{settings.salesforce.api_version}/sobjects/Case/describe/"
            
            response = await sf_client.client.get(describe_url, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ Failed to describe Case object: {response.status_code} - {response.text}")
                return
                
            describe_data = response.json()
            record_types = describe_data.get('recordTypeInfos', [])
            
            print(f"\\n📊 Found {len(record_types)} Record Type(s) for Case object:")
            print("=" * 80)
            
            for rt in record_types:
                record_type_id = rt.get('recordTypeId')
                name = rt.get('name')
                developer_name = rt.get('developerName')
                is_active = rt.get('active')
                is_available = rt.get('available')
                is_default = rt.get('defaultRecordTypeMapping')
                
                status_indicators = []
                if is_active:
                    status_indicators.append("✅ Active")
                else:
                    status_indicators.append("❌ Inactive")
                    
                if is_available:
                    status_indicators.append("🟢 Available")
                else:
                    status_indicators.append("🔴 Not Available")
                    
                if is_default:
                    status_indicators.append("⭐ Default")
                
                print(f"🏷️  Record Type: {name}")
                print(f"   📋 ID: {record_type_id}")
                print(f"   🔧 Developer Name: {developer_name}")
                print(f"   📊 Status: {' | '.join(status_indicators)}")
                print()
            
            # Check current configured Record Type ID
            current_rt_id = settings.salesforce.case_record_type_id
            print(f"🔍 Current Configured Record Type ID: {current_rt_id}")
            
            # Find if current ID matches any available Record Type
            matching_rt = None
            for rt in record_types:
                if rt.get('recordTypeId') == current_rt_id:
                    matching_rt = rt
                    break
            
            if matching_rt:
                print(f"✅ Current ID matches: {matching_rt['name']} ({matching_rt['developerName']})")
                if not matching_rt.get('available'):
                    print("⚠️  WARNING: This Record Type is not available for the current user!")
            else:
                print("❌ Current ID does not match any available Record Types")
            
            # Suggest the best Record Type for Support Requests
            print("\\n💡 Recommendations for Support Request Record Type:")
            print("=" * 60)
            
            support_candidates = []
            for rt in record_types:
                name = rt.get('name', '').lower()
                dev_name = rt.get('developerName', '').lower()
                if rt.get('active') and rt.get('available'):
                    if any(keyword in name or keyword in dev_name for keyword in ['support', 'request', 'case', 'inquiry']):
                        support_candidates.append(rt)
            
            if support_candidates:
                print("🎯 Best candidates for Support Request:")
                for rt in support_candidates:
                    print(f"   📋 {rt['name']} | ID: {rt['recordTypeId']} | Dev: {rt['developerName']}")
            else:
                print("🔍 No obvious Support Request Record Types found. Consider using the default Record Type.")
                
                # Show available active Record Types
                active_rts = [rt for rt in record_types if rt.get('active') and rt.get('available')]
                if active_rts:
                    print("\\n📋 Available Active Record Types:")
                    for rt in active_rts:
                        print(f"   📋 {rt['name']} | ID: {rt['recordTypeId']}")
            
    except Exception as e:
        print(f"❌ Error querying Salesforce Record Types: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(get_salesforce_record_types())
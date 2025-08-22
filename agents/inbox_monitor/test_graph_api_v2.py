#!/usr/bin/env python3
"""
Test script to validate Graph API call for email_payload and email_headers fields.
This script tests the actual API endpoint used in the inbox monitor system.
Version 2: Shows full, untruncated results and optionally saves to file.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from msal import ConfidentialClientApplication
import httpx

# Load environment variables from local .env file
load_dotenv(Path(__file__).parent / '.env')

class GraphAPITester:
    """Test Graph API calls for inbox monitor"""
    
    def __init__(self):
        # Get credentials from environment or Key Vault
        self.tenant_id = os.getenv('GRAPH_API_TENANT_ID')
        self.client_id = os.getenv('GRAPH_API_CLIENT_ID')
        self.client_secret = os.getenv('GRAPH_API_CLIENT_SECRET')
        self.monitored_email = os.getenv('GRAPH_API_MONITORED_EMAIL', 'Victoria_Grant@staples.com')
        
        # If credentials not in env, try to get from Key Vault
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            print("Graph API credentials not found in .env, attempting to retrieve from Key Vault...")
            self._load_from_key_vault()
        
        self.graph_api_endpoint = "https://graph.microsoft.com/v1.0"
        self.authority_url = "https://login.microsoftonline.com"
        self.scopes = ["https://graph.microsoft.com/.default"]
        
        # Initialize MSAL app
        self.msal_app = ConfidentialClientApplication(
            self.client_id,
            authority=f"{self.authority_url}/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        
    def _load_from_key_vault(self):
        """Load Graph API credentials from Azure Key Vault"""
        try:
            from azure.identity import ClientSecretCredential
            from azure.keyvault.secrets import SecretClient
            
            # Get Key Vault credentials from environment
            kv_tenant_id = os.getenv('AZURE_TENANT_ID')
            kv_client_id = os.getenv('AZURE_CLIENT_ID')
            kv_client_secret = os.getenv('AZURE_CLIENT_SECRET')
            kv_url = os.getenv('AZURE_KEY_VAULT_URL')
            
            if not all([kv_tenant_id, kv_client_id, kv_client_secret, kv_url]):
                raise ValueError("Key Vault credentials not found in environment")
            
            # Create Key Vault client
            credential = ClientSecretCredential(
                tenant_id=kv_tenant_id,
                client_id=kv_client_id,
                client_secret=kv_client_secret
            )
            
            client = SecretClient(vault_url=kv_url, credential=credential)
            
            # Retrieve Graph API secrets
            self.tenant_id = client.get_secret("graph-api-tenant-id").value
            self.client_id = client.get_secret("graph-api-client-id").value
            self.client_secret = client.get_secret("graph-api-client-secret").value
            
            print("✅ Successfully loaded Graph API credentials from Key Vault")
            
        except Exception as e:
            print(f"❌ Failed to load from Key Vault: {e}")
            print("Please ensure Graph API credentials are set in .env or Key Vault")
            sys.exit(1)
    
    def get_access_token(self):
        """Get access token using MSAL"""
        result = self.msal_app.acquire_token_for_client(scopes=self.scopes)
        
        if "access_token" not in result:
            error_msg = result.get("error_description", "Unknown error acquiring token")
            raise Exception(f"Failed to acquire token: {error_msg}")
        
        return result["access_token"]
    
    async def test_graph_api_call(self, save_to_file=True):
        """Test the actual Graph API call used in inbox monitor
        
        Args:
            save_to_file: If True, saves full output to JSON files
        """
        print("\n" + "="*80)
        print("GRAPH API EMAIL RETRIEVAL TEST - V2 (Full Output)")
        print("="*80)
        
        print(f"\n📧 Monitored Email: {self.monitored_email}")
        print(f"🔑 Tenant ID: {self.tenant_id}")
        print(f"🔑 Client ID: {self.client_id}")
        
        # Get access token
        print("\n🔐 Acquiring access token...")
        try:
            token = self.get_access_token()
            print("✅ Access token acquired successfully")
        except Exception as e:
            print(f"❌ Failed to get access token: {e}")
            return
        
        # Prepare the API call
        endpoint = f"/users/{self.monitored_email}/mailFolders/Inbox/messages"
        url = f"{self.graph_api_endpoint}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        # These are the exact parameters used in graph_api_client.py
        params = {
            "$top": 3,  # Get only 3 messages for testing
            "$orderby": "receivedDateTime desc",
            "$select": "id,conversationId,subject,bodyPreview,body,from,toRecipients,ccRecipients,bccRecipients,receivedDateTime,sentDateTime,hasAttachments,importance,categories,isRead,isDraft,internetMessageHeaders",
        }
        
        print(f"\n🌐 API Endpoint: {url}")
        print(f"📋 Query Parameters: {json.dumps(params, indent=2)}")
        
        # Make the API call
        async with httpx.AsyncClient() as client:
            print("\n📡 Making API request...")
            try:
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    messages = data.get("value", [])
                    
                    print(f"\n✅ API Call Successful!")
                    print(f"📬 Retrieved {len(messages)} message(s)")
                    
                    # Save full response to file if requested
                    if save_to_file and messages:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        
                        # Save complete API response
                        full_output_file = f"graph_api_full_response_{timestamp}.json"
                        with open(full_output_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        print(f"\n💾 Full API response saved to: {full_output_file}")
                        
                        # Save individual message files
                        for i, msg in enumerate(messages, 1):
                            msg_file = f"graph_api_message_{i}_{timestamp}.json"
                            with open(msg_file, 'w', encoding='utf-8') as f:
                                json.dump(msg, f, indent=2, ensure_ascii=False)
                            print(f"💾 Message {i} saved to: {msg_file}")
                    
                    if messages:
                        print("\n" + "-"*60)
                        print("SAMPLE MESSAGE DATA STRUCTURE")
                        print("-"*60)
                        
                        # Show first message structure
                        first_msg = messages[0]
                        
                        print(f"\n📧 Message 1 of {len(messages)}:")
                        print(f"  ID: {first_msg.get('id', 'N/A')}")  # Full ID, not truncated
                        print(f"  Subject: {first_msg.get('subject', 'N/A')}")
                        print(f"  From: {first_msg.get('from', {}).get('emailAddress', {}).get('address', 'N/A')}")
                        print(f"  Received: {first_msg.get('receivedDateTime', 'N/A')}")
                        
                        # Check for internetMessageHeaders
                        headers_data = first_msg.get('internetMessageHeaders', [])
                        print(f"\n📋 Internet Message Headers: {len(headers_data)} headers found")
                        if headers_data:
                            print("\n  ALL HEADERS:")
                            print("  " + "="*50)
                            for i, header in enumerate(headers_data, 1):  # Show ALL headers
                                print(f"  [{i:3d}] {header.get('name', 'N/A')}:")
                                print(f"        {header.get('value', 'N/A')}")  # Full value, not truncated
                                print()
                        
                        # Show how email_payload would be stored
                        print("\n" + "-"*60)
                        print("DATABASE FIELD MAPPING")
                        print("-"*60)
                        
                        # email_payload - complete message as JSON
                        email_payload = json.dumps(first_msg, ensure_ascii=False, separators=(',', ':'))
                        print(f"\n1️⃣ email_payload (complete Graph API response as JSON):")
                        print(f"   Size: {len(email_payload)} characters")
                        
                        # Option to show full or formatted JSON
                        show_full = input("\n   Show full email_payload? (y/n/f for formatted): ").lower()
                        if show_full == 'y':
                            print(f"   Full content (raw JSON):")
                            print(email_payload)
                        elif show_full == 'f':
                            print(f"   Full content (formatted JSON):")
                            print(json.dumps(first_msg, indent=2, ensure_ascii=False))
                        
                        # email_headers - just the internetMessageHeaders as JSON
                        email_headers = json.dumps(headers_data, ensure_ascii=False, separators=(',', ':'))
                        print(f"\n2️⃣ email_headers (internetMessageHeaders array as JSON):")
                        print(f"   Size: {len(email_headers)} characters")
                        
                        show_headers = input("\n   Show full email_headers? (y/n/f for formatted): ").lower()
                        if show_headers == 'y':
                            print(f"   Full content (raw JSON):")
                            print(email_headers)
                        elif show_headers == 'f':
                            print(f"   Full content (formatted JSON):")
                            print(json.dumps(headers_data, indent=2, ensure_ascii=False))
                        
                        # Verify fields are present
                        print("\n" + "-"*60)
                        print("FIELD AVAILABILITY CHECK")
                        print("-"*60)
                        
                        required_fields = [
                            'id', 'conversationId', 'subject', 'body', 'from',
                            'toRecipients', 'receivedDateTime', 'internetMessageHeaders'
                        ]
                        
                        for field in required_fields:
                            status = "✅" if field in first_msg else "❌"
                            print(f"  {status} {field}")
                        
                        # Show body content details
                        print("\n" + "-"*60)
                        print("BODY CONTENT DETAILS")
                        print("-"*60)
                        body_data = first_msg.get('body', {})
                        print(f"  Content Type: {body_data.get('contentType', 'N/A')}")
                        print(f"  Content Size: {len(body_data.get('content', ''))} characters")
                        
                        show_body = input("\n  Show full body content? (y/n): ").lower()
                        if show_body == 'y':
                            print("\n  Full Body Content:")
                            print("  " + "="*50)
                            print(body_data.get('content', 'No content'))
                        
                    else:
                        print("\n⚠️ No messages found in inbox")
                        
                elif response.status_code == 401:
                    print(f"\n❌ Authentication failed (401)")
                    print("Please check your Graph API credentials")
                elif response.status_code == 404:
                    print(f"\n❌ User/mailbox not found (404)")
                    print(f"Please verify the email address: {self.monitored_email}")
                else:
                    print(f"\n❌ API call failed with status: {response.status_code}")
                    print(f"Response: {response.text}")
                    
            except Exception as e:
                print(f"\n❌ Error making API request: {e}")

async def main():
    """Main test function"""
    tester = GraphAPITester()
    
    print("\n🔧 Graph API Test v2 - Full Output Mode")
    print("This version shows complete, untruncated results")
    print("Output files will be saved in the current directory")
    
    await tester.test_graph_api_call(save_to_file=True)
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\n📁 Check the current directory for saved JSON files with full output")

if __name__ == "__main__":
    asyncio.run(main())
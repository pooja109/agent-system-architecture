#!/usr/bin/env python3
"""
Test Email Loading Process
==========================

This script tests the email loading and processing for customer 10223539
to understand how the HTML content is being processed by the email service.
"""

import sys
import os
import json

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config.settings import get_settings, validate_settings
from services.blob_service import BlobStorageService
from database.models import ResearchOutput, EmailContent

def test_email_loading():
    """Test the email loading process step by step."""
    print("🧪 Testing email loading process for customer 10223539...")
    
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
    
    # Test loading research output JSON
    json_blob_name = "20250707/10223539/communication_output/10223539_research_output.json"
    print(f"\n📥 Loading research output JSON: {json_blob_name}")
    
    try:
        research_output = blob_service.load_research_output(json_blob_name)
        if research_output:
            print("✅ Successfully loaded research output")
            print(f"   Customer: {research_output.customer_name}")
            print(f"   Subject: {research_output.sample_email_subject}")
            
            primary_contact = research_output.get_primary_contact()
            if primary_contact:
                print(f"   Primary Contact: {primary_contact.full_name} ({primary_contact.email})")
            else:
                print("❌ No primary contact found")
        else:
            print("❌ Failed to load research output")
            return
    except Exception as e:
        print(f"❌ Error loading research output: {e}")
        return
    
    # Test loading HTML email
    html_blob_name = "20250707/10223539/communication_output/10223539_email.html"
    print(f"\n📥 Loading HTML email: {html_blob_name}")
    
    try:
        # First, test raw download
        raw_html = blob_service.download_blob_content(html_blob_name)
        if raw_html:
            print(f"✅ Raw HTML downloaded ({len(raw_html)} characters)")
            print("📄 Raw HTML preview:")
            print("-" * 40)
            print(raw_html[:200] + "..." if len(raw_html) > 200 else raw_html)
            print("-" * 40)
        else:
            print("❌ Failed to download raw HTML")
            return
        
        # Now test processed HTML
        processed_html = blob_service.load_email_html(html_blob_name)
        if processed_html:
            print(f"✅ Processed HTML loaded ({len(processed_html)} characters)")
            print("📄 Processed HTML preview:")
            print("-" * 40)
            print(processed_html[:500] + "..." if len(processed_html) > 500 else processed_html)
            print("-" * 40)
            
            # Save processed HTML for comparison
            with open("processed_email.html", 'w', encoding='utf-8') as f:
                f.write(processed_html)
            print(f"💾 Saved processed HTML to: {os.path.abspath('processed_email.html')}")
            
        else:
            print("❌ Failed to load processed HTML")
            return
    except Exception as e:
        print(f"❌ Error loading HTML: {e}")
        return
    
    # Test creating EmailContent object
    print(f"\n📧 Creating EmailContent object...")
    
    try:
        primary_contact = research_output.get_primary_contact()
        if not primary_contact:
            print("❌ No primary contact available")
            return
        
        email_content = EmailContent(
            subject=research_output.sample_email_subject,
            body_html=processed_html,
            recipient_email=primary_contact.email,
            customer_id=research_output.customer_id,
            customer_name=research_output.customer_name,
            contact_name=primary_contact.full_name
        )
        
        print("✅ EmailContent object created successfully")
        print(f"   Subject: {email_content.subject}")
        print(f"   Recipient: {email_content.recipient_email}")
        print(f"   HTML Length: {len(email_content.body_html)} characters")
        print(f"   Customer: {email_content.customer_name}")
        print(f"   Contact: {email_content.contact_name}")
        
        # Check if HTML contains the expected content
        if "Victoria Grant" in email_content.body_html:
            print("✅ HTML contains expected sender name")
        else:
            print("❌ HTML missing expected sender name")
        
        if "Kristin" in email_content.body_html:
            print("✅ HTML contains expected recipient name")
        else:
            print("❌ HTML missing expected recipient name")
        
        if "Auto-Restock Tool" in email_content.body_html:
            print("✅ HTML contains expected product mentions")
        else:
            print("❌ HTML missing expected product mentions")
        
        # Save final email content for review
        final_email = f"""
Subject: {email_content.subject}
To: {email_content.recipient_email}
From: {research_output.sender_details.get('email', 'Unknown')}

{email_content.body_html}
"""
        
        with open("final_email_content.txt", 'w', encoding='utf-8') as f:
            f.write(final_email)
        print(f"💾 Saved final email content to: {os.path.abspath('final_email_content.txt')}")
        
        return email_content
        
    except Exception as e:
        print(f"❌ Error creating EmailContent: {e}")
        return None

def main():
    """Main function."""
    email_content = test_email_loading()
    
    if email_content:
        print("\n🎉 Email loading test completed successfully!")
        print("\nFiles created for review:")
        print("   📄 customer_10223539_email.html - Original downloaded HTML")
        print("   📄 processed_email.html - HTML after blob service processing")
        print("   📄 final_email_content.txt - Complete final email as it would be sent")
    else:
        print("\n❌ Email loading test failed!")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Find Customer Email File
========================

This script searches for and retrieves the HTML email file for a specific customer
from Azure blob storage.

Usage:
    python find_customer_email.py --customer 10223539
"""

import asyncio
import argparse
import logging
import sys
import os
from typing import Optional, List

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config.settings import get_settings, validate_settings
from services.blob_service import BlobStorageService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CustomerEmailFinder:
    """Finds and retrieves email files for specific customers."""
    
    def __init__(self, settings):
        """Initialize the finder."""
        self.settings = settings
        self.blob_service = BlobStorageService(settings.azure_storage)
        
    def find_customer_in_date_folders(self, customer_id: str, max_folders: int = 20) -> List[str]:
        """Find which date folders contain data for the specified customer."""
        logger.info(f"Searching for customer {customer_id} across date folders...")
        
        # Get available date folders (most recent first)
        date_folders = self.blob_service.list_date_folders(limit=max_folders)
        logger.info(f"Found {len(date_folders)} date folders to search")
        
        matching_folders = []
        
        for date_folder in date_folders:
            logger.info(f"Checking date folder: {date_folder}")
            
            # List customer folders in this date folder
            customer_folders = self.blob_service.list_customer_folders(date_folder, limit=5000)
            
            if customer_id in customer_folders:
                logger.info(f"✅ Found customer {customer_id} in date folder {date_folder}")
                matching_folders.append(date_folder)
            else:
                logger.debug(f"❌ Customer {customer_id} not found in date folder {date_folder}")
        
        return matching_folders
    
    def find_email_files_for_customer(self, customer_id: str, date_folder: str) -> dict:
        """Find email files for a customer in a specific date folder."""
        logger.info(f"Looking for email files for customer {customer_id} in {date_folder}")
        
        # Use the blob service method to find files
        files = self.blob_service.find_email_files(date_folder, customer_id)
        
        result = {
            'date_folder': date_folder,
            'customer_id': customer_id,
            'json_file': files.get('json'),
            'html_file': files.get('html'),
            'files_found': []
        }
        
        if files.get('json'):
            result['files_found'].append('JSON research output')
            logger.info(f"Found JSON file: {files['json'].blob_name}")
        
        if files.get('html'):
            result['files_found'].append('HTML email')
            logger.info(f"Found HTML file: {files['html'].blob_name}")
        
        return result
    
    def get_html_content(self, html_blob_name: str) -> Optional[str]:
        """Download and return the HTML content."""
        logger.info(f"Downloading HTML content from: {html_blob_name}")
        
        html_content = self.blob_service.load_email_html(html_blob_name)
        if html_content:
            logger.info(f"Successfully downloaded HTML content ({len(html_content)} characters)")
            return html_content
        else:
            logger.error(f"Failed to download HTML content from {html_blob_name}")
            return None
    
    def search_customer(self, customer_id: str) -> dict:
        """Comprehensive search for a customer's email files."""
        logger.info(f"Starting comprehensive search for customer {customer_id}")
        
        # Test blob storage connection
        if not self.blob_service.test_connection():
            logger.error("Failed to connect to blob storage")
            return {'error': 'Failed to connect to blob storage'}
        
        # Find date folders containing this customer
        matching_folders = self.find_customer_in_date_folders(customer_id)
        
        if not matching_folders:
            logger.warning(f"Customer {customer_id} not found in any date folders")
            return {
                'customer_id': customer_id,
                'found': False,
                'message': 'Customer not found in any date folders'
            }
        
        # Check each matching folder for email files
        results = []
        
        for date_folder in matching_folders:
            file_result = self.find_email_files_for_customer(customer_id, date_folder)
            results.append(file_result)
        
        return {
            'customer_id': customer_id,
            'found': True,
            'date_folders': matching_folders,
            'results': results
        }

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Find and retrieve HTML email files for a specific customer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python find_customer_email.py --customer 10223539
  python find_customer_email.py --customer 10223539 --show-content
  python find_customer_email.py --customer 10223539 --save-to email_content.html
        """
    )
    
    parser.add_argument('--customer', '-c', required=True,
                       help='Customer ID to search for')
    parser.add_argument('--show-content', action='store_true',
                       help='Display the HTML content to console')
    parser.add_argument('--save-to', '-o',
                       help='Save HTML content to specified file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize settings
        print("🔧 Initializing settings...")
        settings = get_settings()
        validate_settings(settings)
        
        # Create finder
        finder = CustomerEmailFinder(settings)
        
        # Search for customer
        print(f"🔍 Searching for customer {args.customer}...")
        print("=" * 60)
        
        search_results = finder.search_customer(args.customer)
        
        if 'error' in search_results:
            print(f"❌ Error: {search_results['error']}")
            return False
        
        if not search_results['found']:
            print(f"❌ {search_results['message']}")
            return False
        
        print(f"✅ Found customer {args.customer} in {len(search_results['date_folders'])} date folder(s):")
        for folder in search_results['date_folders']:
            print(f"   📅 {folder}")
        print()
        
        # Display results for each date folder
        html_content = None
        latest_html_file = None
        
        for result in search_results['results']:
            print(f"📁 Date Folder: {result['date_folder']}")
            print(f"   Files found: {', '.join(result['files_found']) if result['files_found'] else 'None'}")
            
            if result['json_file']:
                print(f"   📄 JSON: {result['json_file'].blob_name}")
            
            if result['html_file']:
                print(f"   📧 HTML: {result['html_file'].blob_name}")
                latest_html_file = result['html_file']
            
            print()
        
        # If we found HTML files and user wants to see content or save it
        if latest_html_file and (args.show_content or args.save_to):
            print(f"📥 Downloading HTML content from: {latest_html_file.blob_name}")
            html_content = finder.get_html_content(latest_html_file.blob_name)
            
            if html_content:
                print(f"✅ Downloaded {len(html_content)} characters of HTML content")
                
                if args.show_content:
                    print("\n" + "="*60)
                    print("HTML CONTENT:")
                    print("="*60)
                    print(html_content)
                    print("="*60)
                
                if args.save_to:
                    try:
                        save_path = os.path.abspath(args.save_to)
                        with open(save_path, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        print(f"💾 Saved HTML content to: {save_path}")
                    except Exception as e:
                        print(f"❌ Failed to save file: {e}")
            else:
                print("❌ Failed to download HTML content")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
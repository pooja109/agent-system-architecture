#!/usr/bin/env python3
"""
Debug HTML Processing
====================

This script debugs the HTML processing issue by stepping through
the _clean_html_content method.
"""

import sys
import os
import re

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def debug_clean_html_content(html_content: str) -> str:
    """Debug version of the _clean_html_content method with detailed logging."""
    print(f"🔍 Input HTML content ({len(html_content)} chars):")
    print("=" * 60)
    print(html_content[:500] + "..." if len(html_content) > 500 else html_content)
    print("=" * 60)
    
    original_content = html_content
    
    try:
        # Step 1: Remove YAML frontmatter if present
        print("\n📋 Step 1: Checking for YAML frontmatter...")
        if html_content.startswith('---'):
            print("✅ Found YAML frontmatter, removing...")
            parts = html_content.split('---', 2)
            print(f"   Split into {len(parts)} parts")
            
            for i, part in enumerate(parts):
                print(f"   Part {i} ({len(part)} chars): {repr(part[:100])}")
            
            if len(parts) >= 3:
                html_content = parts[2].strip()
                print(f"   Using part 2 after stripping: ({len(html_content)} chars)")
                print(f"   Content: {repr(html_content[:200])}")
            else:
                print("   Not enough parts, keeping original")
        else:
            print("❌ No YAML frontmatter found")
        
        # Step 2: Check if it's a complete HTML document
        print(f"\n📋 Step 2: Checking if content is complete HTML document...")
        print(f"   Starts with DOCTYPE: {html_content.strip().startswith('<!DOCTYPE')}")
        print(f"   Starts with <html: {html_content.strip().startswith('<html')}")
        
        if not html_content.strip().startswith('<!DOCTYPE') and not html_content.strip().startswith('<html'):
            print("✅ Content is a fragment, needs wrapping")
            
            # Step 2a: Look for subject paragraph
            print("\n📋 Step 2a: Looking for subject paragraph...")
            subject_match = re.search(r'<p><strong>Subject:</strong>\s*(.*?)</p>', html_content, re.IGNORECASE)
            if subject_match:
                print(f"   Found subject: {subject_match.group(1)}")
                # Remove the subject paragraph from the body
                html_content = re.sub(r'<p><strong>Subject:</strong>.*?</p>\s*', '', html_content, flags=re.IGNORECASE)
                print(f"   Content after subject removal ({len(html_content)} chars): {repr(html_content[:200])}")
            else:
                print("   No subject paragraph found")
            
            # Step 2b: Wrap in complete HTML document
            print("\n📋 Step 2b: Wrapping in complete HTML document...")
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #ffffff;
        }}
        p {{
            margin: 15px 0;
            line-height: 1.6;
        }}
        ul {{
            margin: 15px 0;
            padding-left: 20px;
        }}
        li {{
            margin: 8px 0;
        }}
        a {{
            color: #0066cc;
            text-decoration: underline;
        }}
        a:hover {{
            color: #004499;
        }}
        hr {{
            border: none;
            border-top: 1px solid #ddd;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
{html_content.strip()}
</body>
</html>"""
            print(f"   Final wrapped content ({len(html_content)} chars)")
        else:
            print("❌ Content is already a complete HTML document")
        
        print(f"\n🔍 Final HTML content ({len(html_content)} chars):")
        print("=" * 60)
        print(html_content[:1000] + "..." if len(html_content) > 1000 else html_content)
        print("=" * 60)
        
        return html_content.strip()
        
    except Exception as e:
        print(f"❌ Error cleaning HTML content: {e}")
        return original_content

def main():
    """Test the HTML processing with the actual customer content."""
    # Load the original HTML content
    try:
        with open('customer_10223539_email.html', 'r', encoding='utf-8') as f:
            original_html = f.read()
        
        print("🧪 Testing HTML processing with customer 10223539 content...")
        print("=" * 80)
        
        processed_html = debug_clean_html_content(original_html)
        
        # Save the debug output
        with open('debug_processed_email.html', 'w', encoding='utf-8') as f:
            f.write(processed_html)
        
        print(f"\n💾 Saved debug processed HTML to: {os.path.abspath('debug_processed_email.html')}")
        
        # Check for expected content
        print(f"\n📊 Content Analysis:")
        print(f"   Original length: {len(original_html)} chars")
        print(f"   Processed length: {len(processed_html)} chars")
        print(f"   Contains 'Victoria Grant': {'Victoria Grant' in processed_html}")
        print(f"   Contains 'Kristin': {'Kristin' in processed_html}")
        print(f"   Contains 'Auto-Restock': {'Auto-Restock' in processed_html}")
        
    except FileNotFoundError:
        print("❌ customer_10223539_email.html not found. Run simple_blob_search.py first.")

if __name__ == "__main__":
    main()
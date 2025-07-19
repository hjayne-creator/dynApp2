#!/usr/bin/env python3
"""
Test script for the improved text processing and ranking functionality
"""

import sys
import os
sys.path.append('.')

from app import clean_html, tokenize_text, filter_ecommerce_keywords, find_common_keywords

def test_text_processing():
    """Test the improved text processing"""
    print("Testing Improved Text Processing...")
    print("=" * 50)
    
    # Sample HTML content
    html_content = """
    <html>
    <body>
        <h1>Best Laptop Guide</h1>
        <p>This is the best laptop for your needs. The quality is excellent and the price is affordable.</p>
        <p>You can buy this laptop online with free shipping and secure payment options.</p>
        <p>This premium laptop offers reliable performance and durable construction.</p>
    </body>
    </html>
    """
    
    # Test HTML cleaning
    print("1. Testing HTML cleaning...")
    clean_text = clean_html(html_content)
    print(f"   Clean text: {clean_text[:100]}...")
    
    # Test tokenization
    print("\n2. Testing tokenization...")
    tokens = tokenize_text(clean_text)
    print(f"   Total tokens: {len(tokens)}")
    print("   Sample tokens:")
    for i, token in enumerate(sorted(tokens)[:10]):
        print(f"     {i+1}. {token}")
    
    # Test keyword filtering
    print("\n3. Testing keyword filtering...")
    filtered = filter_ecommerce_keywords(tokens)
    print(f"   Filtered keywords: {len(filtered)}")
    print("   Sample filtered keywords:")
    for i, keyword in enumerate(sorted(filtered)[:10]):
        print(f"     {i+1}. {keyword}")
    
    # Test with multiple files
    print("\n4. Testing common keyword finding...")
    file1_tokens = {"best", "laptop", "quality", "price", "buy", "shipping"}
    file2_tokens = {"best", "laptop", "quality", "performance", "buy", "payment"}
    file3_tokens = {"best", "laptop", "quality", "durable", "buy", "secure"}
    
    common = find_common_keywords([file1_tokens, file2_tokens, file3_tokens])
    print(f"   Common keywords: {len(common)}")
    print("   Ranked results:")
    for i, (keyword, freq) in enumerate(common):
        print(f"     {i+1}. {keyword} (frequency: {freq})")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    test_text_processing() 
#!/usr/bin/env python3
"""
Simple test script for the Ecommerce Guide Analyzer
"""

import requests
import json
import os
from bs4 import BeautifulSoup

def test_app():
    """Test the Flask application"""
    base_url = "http://localhost:5000"
    
    print("Testing Ecommerce Guide Analyzer...")
    print("=" * 50)
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    # Test 1: Check if app is running using health endpoint
    try:
        response = session.get(f"{base_url}/health")
        if response.status_code == 200:
            health_data = response.json()
            print(f"✓ Application is running - {health_data.get('message', 'OK')}")
        else:
            print(f"✗ Health check failed with status: {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("✗ Application is not running. Please start it with: python app.py")
        return
    
    # Test 1b: Check main page and CSRF token
    try:
        response = session.get(base_url)
        if response.status_code == 200:
            print("✓ Main page accessible")
            
            # Parse the page to get CSRF token
            soup = BeautifulSoup(response.text, 'html.parser')
            csrf_token = soup.find('input', {'name': 'csrf_token'})
            if csrf_token:
                print("✓ CSRF protection is active")
            else:
                print("⚠ CSRF token not found (may not be needed for GET requests)")
        else:
            print(f"✗ Main page failed with status: {response.status_code}")
    except Exception as e:
        print(f"✗ Main page test failed: {e}")
    
    # Test 2: Check API endpoints (these don't need CSRF tokens)
    try:
        response = session.get(f"{base_url}/api/keywords")
        if response.status_code == 200:
            keywords = response.json()
            print(f"✓ API endpoint working - Found {len(keywords)} keyword categories")
            for category, words in keywords.items():
                print(f"  - {category}: {len(words)} keywords")
        else:
            print(f"✗ API endpoint failed with status: {response.status_code}")
    except Exception as e:
        print(f"✗ API test failed: {e}")
    
    # Test 3: Check upload page
    try:
        response = session.get(f"{base_url}/upload")
        if response.status_code == 200:
            print("✓ Upload page accessible")
        else:
            print(f"✗ Upload page failed with status: {response.status_code}")
    except Exception as e:
        print(f"✗ Upload page test failed: {e}")
    
    # Test 4: Check if sample files exist
    sample_files = [
        "samples/sample_guide_1.html",
        "samples/sample_guide_2.html", 
        "samples/sample_guide_3.html"
    ]
    
    print("\nSample files:")
    for file_path in sample_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"✓ {file_path} ({size} bytes)")
        else:
            print(f"✗ {file_path} not found")
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("\nTo use the application:")
    print("1. Open http://localhost:5000 in your browser")
    print("2. Upload the sample HTML files from the samples/ directory")
    print("3. View the analysis results")
    print("\nNote: The 403 error you saw earlier was likely due to CSRF protection.")
    print("The web interface handles CSRF tokens automatically.")

if __name__ == "__main__":
    test_app() 
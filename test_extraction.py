#!/usr/bin/env python3
"""Test improved extraction on existing HTML files"""

from bs4 import BeautifulSoup
from scraper import PNGworkforceScraper
import json

scraper = PNGworkforceScraper()

# Test on first job
test_html = "html_output/job_25045.html"
with open(test_html, 'r') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')
url = "https://www.pngworkforce.com/jobs/view/people-culture-safeguarding-coordinator/25045"

data = scraper.extract_structured_data(soup, url)

print("Improved extraction results:")
print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
print("\n\nKey fields:")
print(f"Title: {data.get('title', 'N/A')}")
print(f"Location: {data.get('location', 'N/A')}")
print(f"Date Posted: {data.get('date_posted', 'N/A')}")
print(f"Industry: {data.get('industry', 'N/A')}")
print(f"Employer: {data.get('employer', 'N/A')}")


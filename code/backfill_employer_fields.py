#!/usr/bin/env python3
"""
Backfill script to extract employer profile URL, external website, phone, and address
from existing job HTML files and update their JSON files.

This is a one-time script to add the new employer fields to jobs that were scraped
before these fields were added to the scraper.
"""

import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup
import re

# Add code directory to path to import scraper
sys.path.insert(0, str(Path(__file__).parent))
from scraper import PNGworkforceScraper, format_date_dd_mm_yyyy

def extract_employer_fields_from_html(soup, base_url):
    """
    Extract employer profile URL, external website, phone, and address from HTML.
    Returns dict with the new fields.
    """
    fields = {
        'employer_profile_url': '',
        'employer_external_website': '',
        'employer_phone': '',
        'employer_address': ''
    }
    
    # Look for hiringOrganization div first (most reliable)
    hiring_org = soup.find('div', itemprop='hiringOrganization')
    if hiring_org:
        # Extract employer profile URL
        profile_link = hiring_org.find('a', href=re.compile(r'/jobs/view-company/'))
        if profile_link:
            profile_href = profile_link.get('href', '')
            if profile_href:
                if profile_href.startswith('/'):
                    fields['employer_profile_url'] = f"{base_url}{profile_href}"
                else:
                    fields['employer_profile_url'] = profile_href
        
        # Extract employer phone number
        phone_elem = hiring_org.find('span', {'id': 'comp_phone'}) or hiring_org.find('span', itemprop='telephone')
        if phone_elem:
            phone_text = phone_elem.get_text(strip=True)
            if phone_text:
                fields['employer_phone'] = phone_text
        
        # Extract employer address
        addr_elem = hiring_org.find('span', {'id': 'comp_addr'}) or hiring_org.find('span', itemprop='streetAddress')
        if addr_elem:
            addr_text = addr_elem.get_text(strip=True)
            if addr_text:
                fields['employer_address'] = addr_text
        
        # Extract employer external website
        external_link = hiring_org.find('a', {'target': '_blank'})
        if external_link:
            external_href = external_link.get('href', '')
            if external_href and 'pngworkforce.com' not in external_href.lower():
                fields['employer_external_website'] = external_href
        else:
            # Alternative: look for link in "Website:" label
            website_label = hiring_org.find('label', string=re.compile(r'Website:', re.I))
            if website_label:
                website_parent = website_label.find_parent('p')
                if website_parent:
                    website_link = website_parent.find('a')
                    if website_link:
                        website_href = website_link.get('href', '')
                        if website_href and 'pngworkforce.com' not in website_href.lower():
                            fields['employer_external_website'] = website_href
    
    # If not found, try COMPANY INFO section
    if not any(fields.values()):
        company_info_heading = soup.find(['h3', 'h4'], string=re.compile(r'COMPANY INFO', re.I))
        if company_info_heading:
            company_section = company_info_heading.find_parent(['div', 'section'])
            if company_section:
                if not fields['employer_profile_url']:
                    profile_link = company_section.find('a', href=re.compile(r'/jobs/view-company/'))
                    if profile_link:
                        profile_href = profile_link.get('href', '')
                        if profile_href:
                            if profile_href.startswith('/'):
                                fields['employer_profile_url'] = f"{base_url}{profile_href}"
                            else:
                                fields['employer_profile_url'] = profile_href
                
                if not fields['employer_phone']:
                    phone_elem = company_section.find('span', {'id': 'comp_phone'}) or company_section.find('span', itemprop='telephone')
                    if phone_elem:
                        phone_text = phone_elem.get_text(strip=True)
                        if phone_text:
                            fields['employer_phone'] = phone_text
                
                if not fields['employer_address']:
                    addr_elem = company_section.find('span', {'id': 'comp_addr'}) or company_section.find('span', itemprop='streetAddress')
                    if addr_elem:
                        addr_text = addr_elem.get_text(strip=True)
                        if addr_text:
                            fields['employer_address'] = addr_text
                
                if not fields['employer_external_website']:
                    external_link = company_section.find('a', {'target': '_blank'})
                    if external_link:
                        external_href = external_link.get('href', '')
                        if external_href and 'pngworkforce.com' not in external_href.lower():
                            fields['employer_external_website'] = external_href
    
    return fields

def backfill_employer_fields():
    """Main backfill function"""
    # Initialize paths relative to project root (parent of code directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    json_dir = project_root / 'json_output'
    html_dir = project_root / 'html_output'
    all_jobs_path = json_dir / 'all_jobs.json'
    
    if not all_jobs_path.exists():
        print(f"Error: {all_jobs_path} not found. Run the scraper first.")
        return
    
    # Load existing jobs
    print(f"Loading existing jobs from {all_jobs_path}...")
    with open(all_jobs_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    jobs = data.get('jobs', [])
    print(f"Found {len(jobs)} jobs to process")
    
    # Initialize scraper for base URL
    scraper = PNGworkforceScraper()
    
    updated_count = 0
    missing_html_count = 0
    error_count = 0
    
    for i, job in enumerate(jobs, 1):
        job_id = job.get('job_id')
        if not job_id:
            continue
        
        # Check if already has the fields (skip if already updated)
        if (job.get('employer_profile_url') or job.get('employer_external_website') or 
            job.get('employer_phone') or job.get('employer_address')):
            continue
        
        html_file = html_dir / f"job_{job_id}.html"
        json_file = json_dir / f"job_{job_id}.json"
        
        if not html_file.exists():
            print(f"[{i}/{len(jobs)}] ⚠️  Job {job_id}: HTML file not found, skipping")
            missing_html_count += 1
            continue
        
        try:
            # Load and parse HTML
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract new fields
            new_fields = extract_employer_fields_from_html(soup, scraper.base_url)
            
            # Update job dict
            job.update(new_fields)
            
            # Update individual JSON file
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    individual_data = json.load(f)
                individual_data.update(new_fields)
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(individual_data, f, indent=2, ensure_ascii=False)
            
            updated_count += 1
            
            # Show progress
            if updated_count % 10 == 0:
                found_fields = [k for k, v in new_fields.items() if v]
                print(f"[{i}/{len(jobs)}] ✅ Updated {updated_count} jobs (Job {job_id}: found {len(found_fields)} fields)")
        
        except Exception as e:
            print(f"[{i}/{len(jobs)}] ❌ Error processing job {job_id}: {e}")
            error_count += 1
    
    # Save updated consolidated file
    print(f"\nSaving updated consolidated files...")
    with open(all_jobs_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Regenerate CSV using scraper's method
    print(f"Regenerating CSV file...")
    scraper.save_consolidated_files(jobs, data.get('failed_jobs', []))
    
    print(f"\n=== Backfill Complete ===")
    print(f"Total jobs processed: {len(jobs)}")
    print(f"Jobs updated: {updated_count}")
    print(f"Jobs with missing HTML: {missing_html_count}")
    print(f"Errors: {error_count}")
    print(f"\nUpdated files:")
    print(f"  - {all_jobs_path}")
    print(f"  - {json_dir / 'all_jobs.csv'}")

if __name__ == "__main__":
    backfill_employer_fields()

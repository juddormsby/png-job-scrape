#!/usr/bin/env python3
"""
PNGworkforce.com Job Scraper

Scrapes job listings from PNGworkforce.com:
1. Extracts job listings from the main page
2. Downloads detail pages and saves as HTML
3. Extracts structured data from each job posting

IMPORTANT: Run this script using the virtual environment:
    source venv/bin/activate
    python scraper.py

Or use the run script:
    ./run_scraper.sh
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
import csv
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime


class PNGworkforceScraper:
    def __init__(self, base_url="https://www.pngworkforce.com", delay=1):
        """
        Initialize the scraper
        
        Args:
            base_url: Base URL for the website
            delay: Delay between requests in seconds (to be respectful)
        """
        self.base_url = base_url
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create output directories (relative to project root, not code/ directory)
        # If running from code/, go up one level
        base_dir = Path(__file__).parent.parent if Path(__file__).parent.name == 'code' else Path(__file__).parent
        self.html_dir = base_dir / "html_output"
        self.json_dir = base_dir / "json_output"
        self.html_dir.mkdir(exist_ok=True)
        self.json_dir.mkdir(exist_ok=True)
        
    def fetch_page(self, url):
        """Fetch a page and return BeautifulSoup object"""
        try:
            print(f"Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
        
    def fetch_page_with_error(self, url):
        """Fetch a page and return (soup, error) tuple"""
        try:
            print(f"Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser'), None
        except requests.RequestException as e:
            error_msg = str(e)
            print(f"Error fetching {url}: {error_msg}")
            return None, error_msg
    
    def extract_job_listings(self, soup):
        """
        Extract job listings from the main page
        
        Returns list of dicts with: title, url, date_advertised, location, employer
        """
        jobs = []
        
        # Based on the website structure:
        # - Job titles are in h4 headings with links
        # - Date advertised appears as "Date advertised: **DD MMM YYYY**"
        # - Employer appears as "Company Name - Location"
        # - Links follow pattern /jobs/view/job-title-slug/ID
        
        # Find all headings that contain job titles
        headings = soup.find_all(['h2', 'h3', 'h4', 'h5', 'h6'])
        
        for heading in headings:
            link = heading.find('a')
            if not link:
                continue
                
            href = link.get('href', '')
            
            # Check if this looks like a job listing link
            if '/jobs/view/' in href or '/job/' in href or ('job' in href.lower() and any(char.isdigit() for char in href)):
                job_data = {
                    'title': heading.get_text(strip=True),
                    'url': urljoin(self.base_url, href)
                }
                
                # Find the parent container for this job listing
                # Walk up the DOM to find a container that has the date info
                parent = heading.parent
                max_depth = 5
                depth = 0
                
                while parent and depth < max_depth:
                    # Check if this container has "Date advertised" text
                    parent_text = parent.get_text()
                    
                    if "Date advertised" in parent_text or "Date Posted" in parent_text:
                        # Extract date - try multiple patterns
                        date_elem = parent.find(string=re.compile(r'Date (?:advertised|Posted)', re.I))
                        if date_elem:
                            date_parent = date_elem.find_parent()
                            if date_parent:
                                # Look for bold/strong tag with date
                                bold = date_parent.find(['strong', 'b'])
                                if bold:
                                    date_text = bold.get_text(strip=True)
                                    if re.match(r'\d{1,2}\s+\w+\s+\d{4}', date_text):
                                        job_data['date_advertised'] = date_text
                                        job_data['date_posted'] = date_text  # Also set date_posted for consistency
                                else:
                                    # Try regex extraction
                                    date_match = re.search(r'Date (?:advertised|Posted)[:\s]+(?:\*\*)?(\d{1,2}\s+\w+\s+\d{4})', parent_text, re.I)
                                    if date_match:
                                        date_text = date_match.group(1)
                                        job_data['date_advertised'] = date_text
                                        job_data['date_posted'] = date_text
                        
                        # Extract location - look for patterns like "Company - Location"
                        # Or location appears near the date
                        location_pattern = r'(?:National Capital District|Morobe|Autonomous Region of Bougainville|East Sepik|East New Britain|Eastern Highlands|Enga|Gulf|Hela|Jiwaka|Madang|Manus|Milne Bay|New Ireland|Oro|Northern|Sandaun|West Sepik|Simbu|Chimbu|Southern Highlands|West New Britain|Western|Fly|Western Highlands|Solomon Islands|South Pacific|Vanuatu|Papua New Guinea|Port Moresby|Lae)'
                        location_match = re.search(location_pattern, parent_text, re.I)
                        if location_match:
                            job_data['location'] = location_match.group()
                        
                        # Extract employer - often appears before the dash
                        # Pattern: "Company Name - Location" or "Company Name logo"
                        employer_match = re.search(r'^([^-]+?)\s*-\s*(?:National Capital District|Morobe)', parent_text)
                        if employer_match:
                            job_data['employer'] = employer_match.group(1).strip()
                        else:
                            # Try finding logo alt text or title
                            logo = parent.find('img', alt=True)
                            if logo and logo.get('alt'):
                                job_data['employer'] = logo['alt'].replace(' logo', '').strip()
                            else:
                                # Look for text pattern before location
                                lines = parent_text.split('\n')
                                for line in lines[:5]:  # Check first few lines
                                    if ' - ' in line and any(loc in line for loc in ['District', 'Province', 'Highlands', 'Papua']):
                                        parts = line.split(' - ')
                                        if len(parts) >= 2:
                                            job_data['employer'] = parts[0].strip()
                                            break
                        
                        break
                    
                    parent = parent.parent
                    depth += 1
                
                jobs.append(job_data)
        
        # Also look for links directly in the page that match job URL patterns
        all_links = soup.find_all('a', href=True)
        seen_urls = {job['url'] for job in jobs}
        
        for link in all_links:
            href = link.get('href', '')
            if '/jobs/view/' in href:
                full_url = urljoin(self.base_url, href)
                if full_url not in seen_urls:
                    # Try to find associated heading or title
                    title = link.get_text(strip=True)
                    if title and len(title) > 10:  # Likely a job title
                        parent = link.find_parent(['div', 'article', 'section', 'li'])
                        if parent:
                            job_data = {
                                'title': title,
                                'url': full_url
                            }
                            
                            # Extract date and other info from parent
                            parent_text = parent.get_text()
                            if "Date advertised" in parent_text:
                                date_match = re.search(r'Date advertised[:\s]+(?:\*\*)?(\d{1,2}\s+\w+\s+\d{4})', parent_text, re.I)
                                if date_match:
                                    job_data['date_advertised'] = date_match.group(1)
                            
                            jobs.append(job_data)
                            seen_urls.add(full_url)
        
        # Remove duplicates based on URL
        unique_jobs = []
        seen = set()
        for job in jobs:
            if job['url'] not in seen:
                seen.add(job['url'])
                unique_jobs.append(job)
        
        return unique_jobs
    
    def extract_job_id_from_url(self, url):
        """Extract job ID from URL (e.g., /jobs/view/title/25045 -> 25045)"""
        match = re.search(r'/(\d+)/?$', url)
        return match.group(1) if match else None
    
    def save_html(self, url, html_content):
        """Save HTML content to file"""
        job_id = self.extract_job_id_from_url(url)
        if job_id:
            filename = f"job_{job_id}.html"
        else:
            # Use a sanitized version of the URL
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]
            filename = f"job_{'_'.join(path_parts[-2:])}.html"
        
        filepath = self.html_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return filepath
    
    def extract_structured_data(self, soup, url):
        """
        Extract structured data from a job detail page using proper HTML selectors
        
        Returns dict with: title, date_advertised, location, employer, description, etc.
        Note: Fields are ordered with most important first (job_id, title, date_posted, etc.)
        """
        job_id = self.extract_job_id_from_url(url)
        
        # Order fields logically: ID, title, date, location, etc. (most important first)
        data = {
            'job_id': job_id,
        }
        
        # Extract title - use title tag first, then h1 in job content
        title_elem = soup.find('title')
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            # Remove trailing location from title if present (common pattern: "Title - Location")
            if ' - ' in title_text:
                title_text = title_text.split(' - ')[0]
            data['title'] = title_text
        else:
            # Fallback to h1 in job content area
            h1_elem = soup.find('div', class_='jobadvert').find('h1') if soup.find('div', class_='jobadvert') else None
            if h1_elem:
                data['title'] = h1_elem.get_text(strip=True)
        
        # Extract location using structured data - itemprop="addressRegion"
        location_elem = soup.find('span', itemprop='addressRegion')
        if location_elem:
            data['location'] = location_elem.get_text(strip=True)
        else:
            # Fallback: look for "Location:" label
            location_label = soup.find('label', string=re.compile(r'Location:', re.I))
            if location_label:
                location_parent = location_label.find_parent()
                if location_parent:
                    # Get text after "Location:" but before next label
                    location_text = location_parent.get_text()
                    location_match = re.search(r'Location:\s*([^,\n]+)', location_text, re.I)
                    if location_match:
                        data['location'] = location_match.group(1).strip()
        
        # Extract date posted - prefer human-readable format over ISO
        # First try label approach (human-readable format)
        date_label = soup.find('label', string=re.compile(r'Date Posted:', re.I))
        if date_label:
            date_parent = date_label.find_parent('p')
            if date_parent:
                date_span = date_parent.find('span')
                if date_span:
                    data['date_posted'] = date_span.get_text(strip=True)
                else:
                    # Try regex extraction from parent text
                    date_match = re.search(r'Date Posted:\s*([^\n<]+)', date_parent.get_text(), re.I)
                    if date_match:
                        data['date_posted'] = date_match.group(1).strip()
        
        # Fallback to structured data (ISO format)
        if 'date_posted' not in data:
            date_meta = soup.find('meta', {'itemprop': 'datePosted'})
            if date_meta and date_meta.get('content'):
                data['date_posted'] = date_meta.get('content')
                data['date_posted_iso'] = date_meta.get('content')  # Keep ISO format too
        
        # Also check for "Date advertised" pattern (sometimes used on main page)
        if 'date_posted' not in data:
            date_elem = soup.find(string=re.compile(r'Date advertised', re.I))
            if date_elem:
                date_parent = date_elem.find_parent()
                if date_parent:
                    bold = date_parent.find(['strong', 'b'])
                    if bold:
                        data['date_posted'] = bold.get_text(strip=True)
                    else:
                        date_match = re.search(r'Date advertised[:\s]+([^\n<]+)', date_parent.get_text(), re.I)
                        if date_match:
                            data['date_posted'] = date_match.group(1).strip()
        
        # Extract industry - try structured data first
        industry_elem = soup.find('span', itemprop='industry')
        if industry_elem:
            data['industry'] = industry_elem.get_text(strip=True)
        else:
            # Try label approach
            industry_label = soup.find('label', string=re.compile(r'Industry:', re.I))
            if industry_label:
                industry_parent = industry_label.find_parent('p')
                if industry_parent:
                    industry_span = industry_parent.find('span', itemprop='industry')
                    if industry_span:
                        data['industry'] = industry_span.get_text(strip=True)
                    else:
                        # Fallback: find any span in the parent
                        industry_span = industry_parent.find('span')
                        if industry_span:
                            data['industry'] = industry_span.get_text(strip=True)
                        else:
                            # Regex fallback
                            industry_match = re.search(r'Industry:\s*([^\n<]+)', industry_parent.get_text(), re.I)
                            if industry_match:
                                data['industry'] = industry_match.group(1).strip()
        
        # Extract employer/company - look for company info section
        # Often appears as logo alt text or in company info section
        company_logo = soup.find('img', alt=re.compile(r'logo', re.I))
        if company_logo and company_logo.get('alt'):
            data['employer'] = company_logo['alt'].replace(' logo', '').replace('Logo', '').strip()
        
        # Also check for company name in structured data or company info section
        if 'employer' not in data:
            company_info = soup.find('div', class_=re.compile(r'company|employer', re.I))
            if company_info:
                # Look for company name heading or link
                company_name = company_info.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'company|employer', re.I))
                if company_name:
                    data['employer'] = company_name.get_text(strip=True)
        
        # Extract job ID from structured element
        job_id_elem = soup.find('span', class_='jobid')
        if job_id_elem:
            data['job_id_display'] = job_id_elem.get_text(strip=True)
        
        # Extract description - use itemprop="description"
        desc_elem = soup.find('div', itemprop='description')
        if desc_elem:
            # Clean up description - remove extra whitespace but keep structure
            desc_text = desc_elem.get_text(separator='\n', strip=True)
            # Limit to reasonable length but keep more than before
            data['description'] = desc_text[:10000] if len(desc_text) > 10000 else desc_text
        else:
            # Fallback: get from jobadvert div
            job_advert = soup.find('div', class_='jobadvert')
            if job_advert:
                desc_text = job_advert.get_text(separator='\n', strip=True)
                data['description'] = desc_text[:10000] if len(desc_text) > 10000 else desc_text
        
        # Extract employment type
        employment_types = ['Full-Time', 'Part-Time', 'Contract', 'Permanent', 'Temporary']
        text = soup.get_text()
        for emp_type in employment_types:
            if re.search(r'\b' + re.escape(emp_type) + r'\b', text, re.I):
                data['employment_type'] = emp_type
                break
        
        # Extract salary (if mentioned)
        salary_patterns = [
            r'(?:Salary|Remuneration)[:\s]+([\d,]+(?:\s*(?:PGK|K|thousand))?)',
            r'([\d,]+(?:\s*PGK)?(?:\s*per\s*(?:annum|month|year))?)',
        ]
        for pattern in salary_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                data['salary'] = match.group(1) if match.groups() else match.group(0)
                break
        
        # Add metadata fields
        data['url'] = url
        data['scraped_at'] = datetime.now().isoformat()
        
        # Return data (will be reordered in scrape_job_detail after adding file paths)
        return data
    
    def scrape_job_detail(self, job_url, main_page_data=None):
        """
        Scrape a single job detail page, returns (data_dict, error_string)
        
        Args:
            job_url: URL of the job detail page
            main_page_data: Optional dict with data extracted from main page (title, date, location, employer, etc.)
        """
        soup, error = self.fetch_page_with_error(job_url)
        if not soup:
            return None, error
        
        # Get raw HTML
        html_content = str(soup)
        
        # Save HTML
        html_path = self.save_html(job_url, html_content)
        
        # Extract structured data from detail page
        structured_data = self.extract_structured_data(soup, job_url)
        
        # Merge with main page data (main page data as fallback if detail page extraction failed)
        if main_page_data:
            # Use main page title if detail page title extraction failed or is generic
            if not structured_data.get('title') or structured_data.get('title') in ['TITLE', '']:
                if main_page_data.get('title'):
                    structured_data['title'] = main_page_data['title']
            
            # Use main page date if detail page doesn't have it
            if not structured_data.get('date_posted'):
                if main_page_data.get('date_posted'):
                    structured_data['date_posted'] = main_page_data['date_posted']
                elif main_page_data.get('date_advertised'):
                    structured_data['date_posted'] = main_page_data['date_advertised']
            
            # Use main page location if detail page doesn't have it
            if not structured_data.get('location'):
                if main_page_data.get('location'):
                    structured_data['location'] = main_page_data['location']
            
            # Use main page employer if detail page doesn't have it
            if not structured_data.get('employer') or structured_data.get('employer') in ['Employers / Agents', '']:
                if main_page_data.get('employer'):
                    structured_data['employer'] = main_page_data['employer']
        
        # Add file paths and reorder to maintain logical field order
        job_id = structured_data.get('job_id') or 'unknown'
        json_path = self.json_dir / f"job_{job_id}.json"
        
        # Build final ordered dict with file paths in correct position
        final_ordered_data = {
            'job_id': structured_data.get('job_id'),
            'title': structured_data.get('title'),
            'date_posted': structured_data.get('date_posted'),
            'location': structured_data.get('location'),
            'industry': structured_data.get('industry'),
            'employer': structured_data.get('employer'),
            'employment_type': structured_data.get('employment_type'),
            'salary': structured_data.get('salary'),
            'description': structured_data.get('description'),
            'url': structured_data.get('url'),
            'html_file': str(html_path),
            'html_file_rel': f"html_output/job_{job_id}.html",
            'json_file': str(json_path),
            'json_file_rel': f"json_output/job_{job_id}.json",
            'scraped_at': structured_data.get('scraped_at'),
            'job_id_display': structured_data.get('job_id_display'),
        }
        
        # Remove None values but keep job_id and title even if None
        final_ordered_data = {k: v for k, v in final_ordered_data.items() if v is not None or k in ['job_id', 'title']}
        
        # Save structured data with proper ordering
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(final_ordered_data, f, indent=2, ensure_ascii=False)
        
        return final_ordered_data, None
    
    def load_existing_summary(self):
        """Load existing scrape summary if it exists"""
        summary_path = self.json_dir / 'all_jobs.json'
        if summary_path.exists():
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return None
    
    def is_job_already_scraped(self, job_id):
        """
        Check if a job has already been successfully scraped.
        Returns True if both HTML and JSON files exist and are valid.
        
        Args:
            job_id: Job ID to check
            
        Returns:
            bool: True if job is already successfully scraped
        """
        if not job_id:
            return False
        
        html_file = self.html_dir / f"job_{job_id}.html"
        json_file = self.json_dir / f"job_{job_id}.json"
        
        # Both files must exist
        if not (html_file.exists() and json_file.exists()):
            return False
        
        # Check if JSON is valid and has required fields
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                job_data = json.load(f)
                # Consider it successfully scraped if it has title and description
                if job_data.get('title') and job_data.get('title') not in ['TITLE', '']:
                    return True
        except:
            pass
        
        return False
    
    def get_failed_job_ids(self):
        """Get set of job IDs that previously failed"""
        existing_data = self.load_existing_summary()
        if existing_data:
            failed = existing_data.get('failed_jobs', [])
            return {fj.get('job_id') for fj in failed if fj.get('job_id')}
        return set()
    
    def save_consolidated_files(self, all_jobs_data, failed_jobs):
        """Save consolidated JSON and CSV files"""
        # Prepare data for CSV (flatten some fields)
        csv_data = []
        
        # Add successful jobs
        for job in all_jobs_data:
            csv_row = {
                'job_id': job.get('job_id', ''),
                'title': job.get('title', ''),
                'url': job.get('url', ''),
                'date_posted': job.get('date_posted', job.get('date_advertised', '')),  # Fallback to old field name
                'location': job.get('location', ''),
                'industry': job.get('industry', ''),
                'employer': job.get('employer', ''),
                'employment_type': job.get('employment_type', ''),
                'salary': job.get('salary', ''),
                'scraped_at': job.get('scraped_at', ''),
                'html_file': job.get('html_file_rel', job.get('html_file', '')),
                'json_file': job.get('json_file_rel', job.get('json_file', '')),
                'description_length': len(job.get('description', '')),
                'status': 'success'
            }
            csv_data.append(csv_row)
        
        # Add failed jobs
        for failed_job in failed_jobs:
            csv_row = {
                'job_id': failed_job.get('job_id', ''),
                'title': failed_job.get('title', ''),
                'url': failed_job.get('url', ''),
                'date_posted': '',
                'location': '',
                'industry': '',
                'employer': '',
                'employment_type': '',
                'salary': '',
                'scraped_at': '',
                'html_file': '',
                'json_file': '',
                'description_length': 0,
                'status': 'failed',
                'error': failed_job.get('error', ''),
                'failed_at': failed_job.get('failed_at', '')
            }
            csv_data.append(csv_row)
        
        # Save CSV with logical column order (not alphabetical!)
        csv_path = self.json_dir / 'all_jobs.csv'
        if csv_data:
            # Define logical column order: most important fields first
            primary_fields = [
                'job_id', 'title', 'date_posted', 'location', 'industry', 
                'employer', 'employment_type', 'salary', 'url'
            ]
            secondary_fields = ['html_file', 'json_file', 'description_length']
            metadata_fields = ['scraped_at', 'status', 'error', 'failed_at']
            
            # Get all unique fieldnames
            all_fieldnames = set()
            for row in csv_data:
                all_fieldnames.update(row.keys())
            
            # Build ordered fieldnames list (primary -> secondary -> metadata -> any extras)
            ordered_fieldnames = []
            for field in primary_fields + secondary_fields + metadata_fields:
                if field in all_fieldnames:
                    ordered_fieldnames.append(field)
            
            # Add any remaining fields that weren't in our order (shouldn't happen, but safe)
            for field in sorted(all_fieldnames):
                if field not in ordered_fieldnames:
                    ordered_fieldnames.append(field)
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=ordered_fieldnames)
                writer.writeheader()
                writer.writerows(csv_data)
            print(f"CSV file saved to: {csv_path} ({len(csv_data)} rows)")
        
        # Save consolidated JSON
        consolidated = {
            'last_updated': datetime.now().isoformat(),
            'total_jobs': len(all_jobs_data),
            'total_failed': len(failed_jobs),
            'jobs': all_jobs_data,
            'failed_jobs': failed_jobs
        }
        
        json_path = self.json_dir / 'all_jobs.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(consolidated, f, indent=2, ensure_ascii=False)
        print(f"Consolidated JSON saved to: {json_path}")
        
        return json_path, csv_path
    
    def scrape_all(self, start_url=None, update_existing=True):
        """
        Main method to scrape all jobs
        
        Args:
            start_url: URL of the page with job listings (defaults to latest jobs page)
            update_existing: If True, update existing summary rather than overwrite
        """
        if start_url is None:
            start_url = f"{self.base_url}/jobs/view-latest-jobs"
        
        print(f"Starting scrape from: {start_url}")
        
        # Load existing data if updating
        existing_data = None
        existing_job_ids = set()
        existing_jobs_map = {}
        failed_job_ids = set()
        
        if update_existing:
            existing_data = self.load_existing_summary()
            if existing_data:
                existing_jobs_list = existing_data.get('jobs', [])
                existing_job_ids = {job.get('job_id') for job in existing_jobs_list if job.get('job_id')}
                existing_jobs_map = {job.get('job_id'): job for job in existing_jobs_list if job.get('job_id')}
                print(f"Found {len(existing_job_ids)} existing jobs in database")
            
            # Get list of previously failed jobs to re-attempt
            failed_job_ids = self.get_failed_job_ids()
            if failed_job_ids:
                print(f"Found {len(failed_job_ids)} previously failed jobs (will re-attempt)")
        
        # Fetch main page
        soup = self.fetch_page(start_url)
        if not soup:
            print("Failed to fetch main page")
            return
        
        # Extract job listings
        jobs = self.extract_job_listings(soup)
        print(f"Found {len(jobs)} job listings on page")
        
        if not jobs:
            print("No jobs found. The HTML structure might have changed.")
            print("Saving the main page HTML for inspection...")
            self.save_html(start_url, str(soup))
            return
        
        # Filter jobs to scrape:
        # 1. New jobs (not in database)
        # 2. Previously failed jobs (re-attempt)
        # 3. Jobs where files are missing (re-scrape)
        jobs_to_scrape = []
        jobs_to_skip = []
        
        for job in jobs:
            job_id = self.extract_job_id_from_url(job['url'])
            
            if not job_id:
                # Can't extract ID, scrape it
                jobs_to_scrape.append((job, 'new'))
                continue
            
            # Always re-attempt failed jobs
            if job_id in failed_job_ids:
                jobs_to_scrape.append((job, 'retry_failed'))
                continue
            
            # Check if already successfully scraped
            if self.is_job_already_scraped(job_id):
                jobs_to_skip.append((job, job_id))
                continue
            
            # New job or missing files - scrape it
            jobs_to_scrape.append((job, 'new'))
        
        print(f"\nJobs to scrape: {len(jobs_to_scrape)}")
        print(f"Jobs to skip (already scraped): {len(jobs_to_skip)}")
        
        # Scrape each job detail page
        results = []
        failed_jobs = []
        new_count = 0
        updated_count = 0
        retry_count = 0
        skipped_count = 0
        
        # First, add all skipped jobs back to results (they're already in database)
        for job, job_id in jobs_to_skip:
            if job_id in existing_jobs_map:
                results.append(existing_jobs_map[job_id])
                skipped_count += 1
        
        # Now scrape new/failed jobs
        for i, (job, reason) in enumerate(jobs_to_scrape, 1):
            job_id = self.extract_job_id_from_url(job['url'])
            
            reason_str = {
                'new': 'NEW',
                'retry_failed': 'RETRY (prev failed)',
                'missing_files': 'RE-SCRAPE (missing files)'
            }.get(reason, 'PROCESSING')
            
            print(f"\n[{i}/{len(jobs_to_scrape)}] [{reason_str}] {job.get('title', 'Unknown')[:50]}...")
            result, error = self.scrape_job_detail(job['url'], main_page_data=job)
            
            if result:
                results.append(result)
                if reason == 'retry_failed':
                    retry_count += 1
                elif update_existing and job_id in existing_job_ids:
                    updated_count += 1
                else:
                    new_count += 1
            else:
                failed_jobs.append({
                    'url': job['url'],
                    'job_id': job_id,
                    'title': job.get('title', 'Unknown'),
                    'error': error,
                    'failed_at': datetime.now().isoformat()
                })
            
            # Be respectful - delay between requests
            if i < len(jobs_to_scrape):
                time.sleep(self.delay)
        
        # Merge with existing data (results already includes skipped jobs)
        if update_existing and existing_data:
            # Create final jobs map from results (which includes skipped + new/updated)
            final_jobs_map = {}
            
            # Add all results (includes skipped jobs + newly scraped)
            for job in results:
                job_id = job.get('job_id')
                if job_id:
                    final_jobs_map[job_id] = job
            
            # Add any existing jobs that weren't in results (edge case)
            for job_id, job in existing_jobs_map.items():
                if job_id not in final_jobs_map:
                    final_jobs_map[job_id] = job
            
            all_jobs_data = list(final_jobs_map.values())
            
            # Merge failed jobs (update existing failed with new failures)
            existing_failed = {fj.get('job_id'): fj for fj in existing_data.get('failed_jobs', []) if fj.get('job_id')}
            for fj in failed_jobs:
                job_id = fj.get('job_id')
                if job_id:
                    # Update if this job was previously successful (now failed) or update existing failure
                    existing_failed[job_id] = fj
            
            # Remove from failed if now successful
            successful_ids = {job.get('job_id') for job in results if job.get('job_id')}
            failed_jobs = [fj for fj_id, fj in existing_failed.items() if fj_id not in successful_ids]
        else:
            all_jobs_data = results
        
        # Save consolidated files
        json_path, csv_path = self.save_consolidated_files(all_jobs_data, failed_jobs)
        
        # Save summary with this scrape's details
        summary = {
            'scrape_date': datetime.now().isoformat(),
            'total_jobs_found_on_page': len(jobs),
            'new_jobs_scraped': new_count,
            'jobs_retried': retry_count,
            'jobs_skipped': skipped_count,
            'jobs_updated': updated_count,
            'jobs_failed': len(failed_jobs),
            'total_jobs_in_database': len(all_jobs_data),
            'failed_jobs': failed_jobs[:10]  # Save first 10 failed for reference
        }
        
        summary_path = self.json_dir / 'scrape_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n\nScraping complete!")
        print(f"New jobs scraped: {new_count}")
        print(f"Jobs retried (prev failed): {retry_count}")
        print(f"Jobs skipped (already scraped): {skipped_count}")
        print(f"Jobs updated: {updated_count}")
        print(f"Failed: {len(failed_jobs)}")
        print(f"Total jobs in database: {len(all_jobs_data)}")
        print(f"HTML files saved to: {self.html_dir}")
        print(f"JSON files saved to: {self.json_dir}")
        print(f"Consolidated files: {json_path}, {csv_path}")
        print(f"Summary saved to: {summary_path}")
        
        if failed_jobs:
            print(f"\nFailed jobs (showing first 5):")
            for fj in failed_jobs[:5]:
                print(f"  - {fj.get('title', 'Unknown')}: {fj.get('error', 'Unknown error')}")
        
        return all_jobs_data


if __name__ == "__main__":
    scraper = PNGworkforceScraper(delay=2)  # 2 second delay between requests
    scraper.scrape_all()


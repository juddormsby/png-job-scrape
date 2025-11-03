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
from urllib.parse import urljoin, urlparse, unquote, parse_qs
from datetime import datetime


def format_date_dd_mm_yyyy(date_str):
    """
    Convert date string to DD/MM/YYYY format.
    Handles various input formats:
    - "1st October 2025" -> "01/10/2025"
    - "30th October 2025" -> "30/10/2025"
    - "2025-10-01" -> "01/10/2025"
    - "October 1, 2025" -> "01/10/2025"
    Returns original string if parsing fails.
    """
    if not date_str or not isinstance(date_str, str):
        return date_str
    
    date_str = date_str.strip()
    if not date_str:
        return date_str
    
    # Try parsing common formats
    date_formats = [
        "%Y-%m-%d",           # ISO format: 2025-10-01
        "%d %B %Y",           # 1 October 2025
        "%dth %B %Y",         # 1st October 2025
        "%dst %B %Y",         # 1st October 2025
        "%dnd %B %Y",         # 2nd October 2025
        "%drd %B %Y",         # 3rd October 2025
        "%B %d, %Y",          # October 1, 2025
        "%d/%m/%Y",           # Already DD/MM/YYYY
        "%m/%d/%Y",           # MM/DD/YYYY format
        "%Y/%m/%d",           # YYYY/MM/DD format
    ]
    
    # Try each format
    for fmt in date_formats:
        try:
            # Handle ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
            date_str_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
            parsed_date = datetime.strptime(date_str_clean, fmt.replace('%dth ', '%d ').replace('%dst ', '%d ').replace('%dnd ', '%d ').replace('%drd ', '%d '))
            # Format as DD/MM/YYYY
            return parsed_date.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            continue
    
    # If all parsing fails, return original string
    return date_str


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
                                        formatted_date = format_date_dd_mm_yyyy(date_text)
                                        job_data['date_advertised'] = formatted_date
                                        job_data['date_posted'] = formatted_date  # Also set date_posted for consistency
                                else:
                                    # Try regex extraction
                                    date_match = re.search(r'Date (?:advertised|Posted)[:\s]+(?:\*\*)?(\d{1,2}\s+\w+\s+\d{4})', parent_text, re.I)
                                    if date_match:
                                        date_text = date_match.group(1)
                                        formatted_date = format_date_dd_mm_yyyy(date_text)
                                        job_data['date_advertised'] = formatted_date
                                        job_data['date_posted'] = formatted_date
                        
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
    
    def extract_job_url_from_redirect(self, redirect_url):
        """
        Extract the actual job URL from a redirect URL.
        
        Handles URLs like: https://www.pngworkforce.com/s/redirect?url=https%3A%2F%2Fwww.pngworkforce.com%2Fjobs%2Fview%2F...
        Returns the decoded job URL, or None if extraction fails.
        """
        try:
            # Parse the redirect URL
            parsed = urlparse(redirect_url)
            query_params = parse_qs(parsed.query)
            
            # Get the 'url' parameter
            if 'url' in query_params:
                encoded_url = query_params['url'][0]
                # URL decode
                decoded_url = unquote(encoded_url)
                return decoded_url
            
            # Also try direct extraction from query string
            if '?' in redirect_url:
                # Extract everything after url=
                match = re.search(r'url=([^&]+)', redirect_url)
                if match:
                    encoded_url = match.group(1)
                    decoded_url = unquote(encoded_url)
                    return decoded_url
            
            return None
        except Exception:
            return None
    
    def extract_homepage_jobs(self, soup):
        """
        Extract job listings from the homepage format.
        
        Handles jobs in <div class="job-result-featured"> with redirect links.
        Returns list of dicts with: title, url, date_advertised, location, employer
        """
        jobs = []
        
        # Find all job result divs
        job_divs = soup.find_all('div', class_='job-result-featured')
        
        for job_div in job_divs:
            job_data = {}
            
            # Extract title - usually in h4 with class t2
            title_elem = job_div.find('h4', class_='t2')
            if title_elem:
                title_link = title_elem.find('a')
                if title_link:
                    job_data['title'] = title_link.get_text(strip=True)
                    
                    # Extract URL - could be redirect or direct
                    href = title_link.get('href', '')
                    if href:
                        if '/s/redirect' in href:
                            # Extract actual URL from redirect
                            actual_url = self.extract_job_url_from_redirect(href)
                            if actual_url:
                                job_data['url'] = actual_url
                            else:
                                # Fallback: use redirect URL as-is
                                job_data['url'] = urljoin(self.base_url, href)
                        else:
                            # Direct link
                            job_data['url'] = urljoin(self.base_url, href)
            
            # Extract date advertised - look for "Date advertised: **DD MMM YYYY**"
            date_elem = job_div.find(string=re.compile(r'Date advertised', re.I))
            if date_elem:
                date_parent = date_elem.find_parent()
                if date_parent:
                    # Look for strong/bold tag with date
                    bold = date_parent.find(['strong', 'b'])
                    if bold:
                        date_text = bold.get_text(strip=True)
                        # Remove "*NEW*" if present
                        date_text = re.sub(r'\*NEW\*', '', date_text).strip()
                        if re.match(r'\d{1,2}\s+\w+\s+\d{4}', date_text):
                            job_data['date_advertised'] = format_date_dd_mm_yyyy(date_text)
                            job_data['date_posted'] = job_data['date_advertised']
                    else:
                        # Try regex extraction
                        date_match = re.search(r'Date advertised:\s*\*\*?([^*]+)\*\*?', date_parent.get_text(), re.I)
                        if date_match:
                            date_text = date_match.group(1).strip()
                            # Remove "*NEW*" if present
                            date_text = re.sub(r'\*NEW\*', '', date_text).strip()
                            job_data['date_advertised'] = format_date_dd_mm_yyyy(date_text)
                            job_data['date_posted'] = job_data['date_advertised']
            
            # Extract employer - look for strong tags, but skip date ones
            # Usually appears in paragraph after date line
            all_strong = job_div.find_all('strong')
            for strong_elem in all_strong:
                employer_text = strong_elem.get_text(strip=True)
                # Skip if it's "*NEW*", empty, or looks like a date
                if employer_text and '*' not in employer_text and not re.match(r'\d{1,2}\s+\w+\s+\d{4}', employer_text) and len(employer_text) > 2:
                    # Check if parent is not the date parent
                    parent = strong_elem.find_parent()
                    if parent and 'Date advertised' not in parent.get_text():
                        job_data['employer'] = employer_text
                        break
            
            # Extract location - look for links with location names
            location_pattern = r'(?:National Capital District|Morobe|Autonomous Region of Bougainville|East Sepik|East New Britain|Eastern Highlands|Enga|Gulf|Hela|Jiwaka|Madang|Manus|Milne Bay|New Ireland|Oro|Northern|Sandaun|West Sepik|Simbu|Chimbu|Southern Highlands|West New Britain|Western|Fly|Western Highlands|Solomon Islands|South Pacific|Vanuatu|Papua New Guinea|Port Moresby|Lae)'
            location_link = job_div.find('a', href=re.compile(r'meta_R=', re.I))
            if location_link:
                location_text = location_link.get_text(strip=True)
                if re.match(location_pattern, location_text, re.I):
                    job_data['location'] = location_text
            else:
                # Fallback: search in text
                location_match = re.search(location_pattern, job_div.get_text(), re.I)
                if location_match:
                    job_data['location'] = location_match.group()
            
            # Extract industry - look for links with industry
            industry_link = job_div.find('a', href=re.compile(r'meta_C=', re.I))
            if industry_link and 'meta_R=' not in industry_link.get('href', ''):
                industry_text = industry_link.get_text(strip=True)
                if industry_text:
                    job_data['industry'] = industry_text
            
            # Only add if we have at least a URL
            if 'url' in job_data:
                jobs.append(job_data)
        
        return jobs
    
    def get_homepage_pagination_links(self, soup):
        """
        Extract pagination links from homepage.
        
        Returns list of URLs for all pages (including current page).
        """
        pagination_urls = []
        
        # Find pagination div
        pager_div = soup.find('div', class_=re.compile(r'pager|pagination', re.I))
        if not pager_div:
            return pagination_urls
        
        # Get base URL (current page URL or homepage)
        base_url = self.base_url
        
        # Find all page links
        page_links = pager_div.find_all('a', href=True)
        seen_urls = set()
        
        for link in page_links:
            href = link.get('href', '')
            if not href or href.startswith('javascript:'):
                continue
            
            # Build full URL
            if href.startswith('/'):
                full_url = urljoin(self.base_url, href)
            elif href.startswith('?'):
                # Relative query string
                full_url = f"{self.base_url}{href}"
            elif '://' in href:
                full_url = href
            else:
                full_url = urljoin(self.base_url, href)
            
            if full_url not in seen_urls:
                pagination_urls.append(full_url)
                seen_urls.add(full_url)
        
        return pagination_urls
    
    def fetch_homepage_ajax_page(self, start_rank=1):
        """
        Fetch a page of jobs from the homepage AJAX endpoint.
        
        Args:
            start_rank: Starting rank for pagination (1, 11, 21, 31, etc.)
        
        Returns:
            BeautifulSoup object or None if fetch fails
        """
        ajax_url = f"{self.base_url}/ajax/get-search-page-home"
        params = {
            'collection': 'pngwf_live',
            'query': '!nojobs',
            'form': 'jobs',
            'num_ranks': '10',
            'sort': 'dmeta8',
            'start_rank': str(start_rank)
        }
        
        try:
            # Use AJAX headers (important - site requires X-Requested-With header)
            headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': '*/*',
                'Referer': f'{self.base_url}/',
                'User-Agent': self.session.headers.get('User-Agent', 'Mozilla/5.0')
            }
            
            response = self.session.get(ajax_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            print(f"Error fetching AJAX page (start_rank={start_rank}): {e}")
            return None
    
    def scrape_homepage_jobs(self):
        """
        Scrape all jobs from homepage using the AJAX endpoint.
        
        Returns list of all job dicts found across all pages.
        """
        all_jobs = []
        seen_urls = set()
        start_rank = 1
        max_pages = 500  # Safety limit (10 jobs per page = max 5000 jobs)
        page_count = 0
        
        print(f"Starting homepage scraping via AJAX endpoint")
        
        while start_rank <= max_pages * 10:
            print(f"  Fetching page {page_count + 1} (start_rank={start_rank})")
            soup = self.fetch_homepage_ajax_page(start_rank)
            
            if not soup:
                print(f"  Failed to fetch page, stopping")
                break
            
            page_count += 1
            
            # Extract jobs from this page
            page_jobs = self.extract_homepage_jobs(soup)
            
            if not page_jobs:
                print(f"  No jobs found on page {page_count}, stopping")
                break
            
            # Add jobs (deduplicate by URL)
            jobs_added = 0
            for job in page_jobs:
                job_url = job.get('url')
                if job_url:
                    # Normalize URL for deduplication
                    normalized_url = job_url.rstrip('/')
                    if normalized_url not in seen_urls:
                        all_jobs.append(job)
                        seen_urls.add(normalized_url)
                        jobs_added += 1
            
            print(f"  Found {len(page_jobs)} jobs on page, {jobs_added} new")
            
            # If we got fewer than expected jobs, we might be at the end
            if len(page_jobs) < 10:
                print(f"  Got fewer than 10 jobs, likely at end of results")
                break
            
            # Move to next page (10 jobs per page)
            start_rank += 10
            
            # Be respectful - delay between requests
            time.sleep(self.delay)
        
        print(f"Homepage scraping complete: found {len(all_jobs)} unique jobs across {page_count} pages")
        return all_jobs
    
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
                    raw_date = date_span.get_text(strip=True)
                    data['date_posted'] = format_date_dd_mm_yyyy(raw_date)
                else:
                    # Try regex extraction from parent text
                    date_match = re.search(r'Date Posted:\s*([^\n<]+)', date_parent.get_text(), re.I)
                    if date_match:
                        raw_date = date_match.group(1).strip()
                        data['date_posted'] = format_date_dd_mm_yyyy(raw_date)
        
        # Fallback to structured data (ISO format)
        if 'date_posted' not in data:
            date_meta = soup.find('meta', {'itemprop': 'datePosted'})
            if date_meta and date_meta.get('content'):
                raw_date = date_meta.get('content')
                data['date_posted'] = format_date_dd_mm_yyyy(raw_date)
                data['date_posted_iso'] = raw_date  # Keep ISO format too
        
        # Also check for "Date advertised" pattern (sometimes used on main page)
        if 'date_posted' not in data:
            date_elem = soup.find(string=re.compile(r'Date advertised', re.I))
            if date_elem:
                date_parent = date_elem.find_parent()
                if date_parent:
                    bold = date_parent.find(['strong', 'b'])
                    if bold:
                        raw_date = bold.get_text(strip=True)
                        data['date_posted'] = format_date_dd_mm_yyyy(raw_date)
                    else:
                        date_match = re.search(r'Date advertised[:\s]+([^\n<]+)', date_parent.get_text(), re.I)
                        if date_match:
                            raw_date = date_match.group(1).strip()
                            data['date_posted'] = format_date_dd_mm_yyyy(raw_date)
        
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
        
        # Extract employer/company - use structured data first (most reliable)
        # Look for itemprop="hiringOrganization" -> itemprop="name"
        hiring_org = soup.find('div', itemprop='hiringOrganization')
        if hiring_org:
            # First try to get the name from structured data
            org_name_elem = hiring_org.find('span', itemprop='name')
            if org_name_elem:
                name_text = org_name_elem.get_text(strip=True)
                # Make sure it's not empty and not the site name
                if name_text and 'pngworkforce' not in name_text.lower():
                    data['employer'] = name_text
            else:
                # Fallback: look for company name in h4 or link within hiringOrganization
                company_name = hiring_org.find(['h4', 'a'])
                if company_name:
                    name_text = company_name.get_text(strip=True)
                    if name_text and 'pngworkforce' not in name_text.lower() and len(name_text) > 2:
                        data['employer'] = name_text
        
        # If not found, look for "COMPANY INFO" section specifically
        if 'employer' not in data or not data.get('employer'):
            company_info_heading = soup.find(['h3', 'h4'], string=re.compile(r'COMPANY INFO', re.I))
            if company_info_heading:
                company_section = company_info_heading.find_parent(['div', 'section'])
                if company_section:
                    # Look for h4 with company name
                    company_h4 = company_section.find('h4')
                    if company_h4:
                        name_text = company_h4.get_text(strip=True)
                        if name_text and 'pngworkforce' not in name_text.lower():
                            data['employer'] = name_text
        
        # Last resort: look for company logo in COMPANY INFO section (not site header)
        if 'employer' not in data or not data.get('employer'):
            # Only look for logos within hiringOrganization div (not site-wide)
            hiring_org = soup.find('div', itemprop='hiringOrganization')
            if hiring_org:
                company_logo = hiring_org.find('img', alt=re.compile(r'logo', re.I))
                if company_logo and company_logo.get('alt'):
                    alt_text = company_logo.get('alt', '')
                    # Skip PNGworkForce.com logos
                    if 'pngworkforce' not in alt_text.lower():
                        data['employer'] = alt_text.replace(' logo', '').replace('Logo', '').strip()
        
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
                    structured_data['date_posted'] = format_date_dd_mm_yyyy(main_page_data['date_posted'])
                elif main_page_data.get('date_advertised'):
                    structured_data['date_posted'] = format_date_dd_mm_yyyy(main_page_data['date_advertised'])
            
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
        current_time = datetime.now().isoformat()
        
        # Build final ordered dict with file paths in correct position
        final_ordered_data = {
            'job_id': structured_data.get('job_id'),
            'title': structured_data.get('title'),
            'date_posted': structured_data.get('date_posted'),
            'first_seen': current_time,  # Will be updated if job exists in scrape_all
            'last_seen': current_time,   # Always update to current time
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
    
    def get_failed_jobs_info(self):
        """
        Get comprehensive failed jobs info: by job_id and by URL.
        Returns (by_id_dict, by_url_dict) for tracking jobs without extractable IDs.
        """
        existing_data = self.load_existing_summary()
        if existing_data:
            failed = existing_data.get('failed_jobs', [])
            by_id = {fj.get('job_id'): fj for fj in failed if fj.get('job_id')}
            by_url = {}
            for fj in failed:
                url = fj.get('url')
                if url:
                    normalized_url = url.rstrip('/')
                    by_url[normalized_url] = fj
            return by_id, by_url
        return {}, {}
    
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
                'date_posted': format_date_dd_mm_yyyy(job.get('date_posted', job.get('date_advertised', ''))),  # Fallback to old field name and format
                'first_seen': job.get('first_seen', ''),
                'last_seen': job.get('last_seen', ''),
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
        
        # Add failed jobs (include all available info for manual review)
        for failed_job in failed_jobs:
            csv_row = {
                'job_id': failed_job.get('job_id', ''),
                'title': failed_job.get('title', ''),
                'url': failed_job.get('url', ''),
                'date_posted': failed_job.get('date_posted', ''),
                'location': failed_job.get('location', ''),
                'industry': failed_job.get('industry', ''),
                'employer': failed_job.get('employer', ''),
                'employment_type': '',
                'salary': '',
                'scraped_at': '',
                'html_file': '',
                'json_file': '',
                'description_length': 0,
                'status': 'failed',
                'error': failed_job.get('error', ''),
                'failure_type': failed_job.get('failure_type', 'unknown'),
                'retry_count': failed_job.get('retry_count', 0),
                'failed_at': failed_job.get('failed_at', ''),
                'last_attempted': failed_job.get('last_attempted', '')
            }
            csv_data.append(csv_row)
        
        # Save CSV with logical column order (not alphabetical!)
        csv_path = self.json_dir / 'all_jobs.csv'
        if csv_data:
            # Define logical column order: most important fields first
            primary_fields = [
                'job_id', 'title', 'date_posted', 'first_seen', 'last_seen', 'location', 'industry', 
                'employer', 'employment_type', 'salary', 'url'
            ]
            secondary_fields = ['html_file', 'json_file', 'description_length']
            metadata_fields = ['scraped_at', 'status', 'error', 'failure_type', 'retry_count', 'failed_at', 'last_attempted']
            
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
        existing_failed_by_id = {}
        existing_failed_by_url = {}
        
        if update_existing:
            existing_data = self.load_existing_summary()
            if existing_data:
                existing_jobs_list = existing_data.get('jobs', [])
                existing_job_ids = {job.get('job_id') for job in existing_jobs_list if job.get('job_id')}
                existing_jobs_map = {job.get('job_id'): job for job in existing_jobs_list if job.get('job_id')}
                print(f"Found {len(existing_job_ids)} existing jobs in database")
            
            # Get comprehensive failed jobs info (by ID and by URL)
            existing_failed_by_id, existing_failed_by_url = self.get_failed_jobs_info()
            failed_job_ids = set(existing_failed_by_id.keys())
            
            # Log failed jobs stats
            failed_with_id = len([fj for fj in existing_data.get('failed_jobs', []) if fj.get('job_id')])
            failed_without_id = len([fj for fj in existing_data.get('failed_jobs', []) if not fj.get('job_id')])
            if failed_job_ids:
                print(f"Found {failed_with_id} previously failed jobs with ID (will re-attempt)")
            if failed_without_id > 0:
                print(f"Found {failed_without_id} previously failed jobs without extractable ID (will re-attempt)")
        
        # Scrape from homepage (with pagination) to discover all jobs
        print("\n=== Scraping homepage (all pages) ===")
        homepage_jobs = self.scrape_homepage_jobs()
        
        # Also scrape from latest jobs page (backward compatibility, may have some jobs not on homepage)
        print(f"\n=== Scraping latest jobs page ===")
        soup = self.fetch_page(start_url)
        if not soup:
            print("Failed to fetch latest jobs page")
            latest_jobs = []
        else:
            latest_jobs = self.extract_job_listings(soup)
        
        # Merge both sources and deduplicate by URL
        print(f"\n=== Merging job sources ===")
        print(f"Homepage jobs: {len(homepage_jobs)}")
        print(f"Latest jobs page: {len(latest_jobs)}")
        
        # Create a map by URL for deduplication
        jobs_by_url = {}
        jobs_without_id_preliminary = []
        
        # Add homepage jobs first
        for job in homepage_jobs:
            url = job.get('url')
            if url:
                # Normalize URL (remove trailing slashes, etc.)
                normalized_url = url.rstrip('/')
                job_id = self.extract_job_id_from_url(url)
                if not job_id:
                    # Track jobs without extractable ID for logging
                    jobs_without_id_preliminary.append({
                        'url': normalized_url,
                        'title': job.get('title', 'Unknown'),
                        'employer': job.get('employer', ''),
                        'location': job.get('location', ''),
                        'date_posted': job.get('date_posted', ''),
                        'source': 'homepage'
                    })
                jobs_by_url[normalized_url] = job
        
        # Add latest jobs (may override if same URL, but that's fine)
        for job in latest_jobs:
            url = job.get('url')
            if url:
                normalized_url = url.rstrip('/')
                job_id = self.extract_job_id_from_url(url)
                if not job_id:
                    # Track jobs without extractable ID for logging (if not already tracked)
                    if normalized_url not in jobs_by_url:
                        jobs_without_id_preliminary.append({
                            'url': normalized_url,
                            'title': job.get('title', 'Unknown'),
                            'employer': job.get('employer', ''),
                            'location': job.get('location', ''),
                            'date_posted': job.get('date_posted', ''),
                            'source': 'latest_jobs'
                        })
                jobs_by_url[normalized_url] = job
        
        # Convert back to list
        jobs = list(jobs_by_url.values())
        print(f"Total unique jobs after merge: {len(jobs)}")
        
        # Log jobs without extractable IDs
        if jobs_without_id_preliminary:
            print(f"\n⚠️  Found {len(jobs_without_id_preliminary)} jobs without extractable job_id (will attempt to scrape and extract):")
            for job_info in jobs_without_id_preliminary[:5]:  # Show first 5
                print(f"  - {job_info['title'][:50]}: {job_info['url'][:80]}")
            if len(jobs_without_id_preliminary) > 5:
                print(f"  ... and {len(jobs_without_id_preliminary) - 5} more")
        
        print(f"Found {len(jobs)} job listings on page")
        
        if not jobs:
            print("No jobs found. The HTML structure might have changed.")
            print("Saving the main page HTML for inspection...")
            self.save_html(start_url, str(soup))
            return
        
        # Filter jobs to scrape:
        # 1. New jobs (not in database)
        # 2. Previously failed jobs (re-attempt, with retry limit)
        # 3. Jobs where files are missing (re-scrape)
        # 4. Jobs without extractable job_id (track separately, retry limit)
        max_retries = 3  # Maximum retry attempts before giving up
        jobs_to_scrape = []
        jobs_to_skip = []
        jobs_without_id_skipped = []
        
        for job in jobs:
            job_url = job.get('url', '')
            normalized_url = job_url.rstrip('/') if job_url else ''
            job_id = self.extract_job_id_from_url(job_url)
            
            if not job_id:
                # Can't extract ID from URL - check if we've seen this URL before
                existing_failed = existing_failed_by_url.get(normalized_url) if normalized_url else None
                
                if existing_failed:
                    retry_count = existing_failed.get('retry_count', 0)
                    if retry_count >= max_retries:
                        # Exceeded retry limit - skip but track it
                        jobs_without_id_skipped.append({
                            'url': normalized_url,
                            'title': job.get('title', 'Unknown'),
                            'employer': job.get('employer', ''),
                            'location': job.get('location', ''),
                            'date_posted': job.get('date_posted', ''),
                            'retry_count': retry_count,
                            'reason': 'max_retries_exceeded'
                        })
                        continue
                    else:
                        # Retry it (increment count will happen during scrape)
                        jobs_to_scrape.append((job, 'retry_no_job_id'))
                else:
                    # First time seeing this URL without job_id - try to scrape
                    jobs_to_scrape.append((job, 'no_job_id'))
                continue
            
            # Job has extractable ID - use existing logic
            # Always re-attempt failed jobs (with retry limit)
            if job_id in failed_job_ids:
                existing_failed = existing_failed_by_id.get(job_id)
                if existing_failed:
                    retry_count = existing_failed.get('retry_count', 0)
                    if retry_count >= max_retries:
                        # Skip but still track in failed_jobs
                        jobs_without_id_skipped.append({
                            'url': normalized_url,
                            'job_id': job_id,
                            'title': job.get('title', 'Unknown'),
                            'employer': job.get('employer', ''),
                            'location': job.get('location', ''),
                            'date_posted': job.get('date_posted', ''),
                            'retry_count': retry_count,
                            'reason': 'max_retries_exceeded'
                        })
                        continue
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
        if jobs_without_id_skipped:
            print(f"Jobs skipped (max retries exceeded): {len(jobs_without_id_skipped)}")
            print(f"  (These jobs cannot extract job_id or exceeded {max_retries} retry attempts)")
            print(f"  Sample: {jobs_without_id_skipped[0].get('title', 'Unknown')[:50]}")
        
        # Scrape each job detail page
        # Use a single timestamp for this entire scrape session
        scrape_timestamp = datetime.now().isoformat()
        results = []
        failed_jobs = []
        new_count = 0
        updated_count = 0
        retry_count = 0
        skipped_count = 0
        
        # First, add all skipped jobs back to results (they're already in database)
        # Update their last_seen since we encountered them on this scrape
        for job, job_id in jobs_to_skip:
            if job_id in existing_jobs_map:
                existing_job = existing_jobs_map[job_id].copy()
                existing_job['last_seen'] = scrape_timestamp  # Update last_seen since we saw it
                # Preserve first_seen if it exists, otherwise use scrape timestamp (backfill)
                if not existing_job.get('first_seen'):
                    existing_job['first_seen'] = scrape_timestamp
                results.append(existing_job)
                skipped_count += 1
        
        # Now scrape new/failed jobs
        for i, (job, reason) in enumerate(jobs_to_scrape, 1):
            job_id = self.extract_job_id_from_url(job['url'])
            
            reason_str = {
                'new': 'NEW',
                'retry_failed': 'RETRY (prev failed)',
                'retry_no_job_id': 'RETRY (no ID, prev failed)',
                'no_job_id': 'NO_ID (trying to extract from page)',
                'missing_files': 'RE-SCRAPE (missing files)'
            }.get(reason, 'PROCESSING')
            
            print(f"\n[{i}/{len(jobs_to_scrape)}] [{reason_str}] {job.get('title', 'Unknown')[:50]}...")
            result, error = self.scrape_job_detail(job['url'], main_page_data=job)
            
            if result:
                # Check if we successfully extracted job_id from detail page
                extracted_job_id = result.get('job_id')
                if not extracted_job_id:
                    # Still no job_id after scraping detail page - track as failed
                    normalized_url = job['url'].rstrip('/')
                    existing_failed = existing_failed_by_url.get(normalized_url) if normalized_url else None
                    retry_count = (existing_failed.get('retry_count', 0) + 1) if existing_failed else 1
                    
                    failed_jobs.append({
                        'url': normalized_url,
                        'job_id': None,
                        'title': result.get('title') or job.get('title', 'Unknown'),
                        'employer': result.get('employer') or job.get('employer', ''),
                        'location': result.get('location') or job.get('location', ''),
                        'date_posted': result.get('date_posted') or job.get('date_posted', ''),
                        'industry': result.get('industry') or job.get('industry', ''),
                        'error': 'no_job_id_extractable',
                        'retry_count': retry_count,
                        'failure_type': 'no_job_id',
                        'failed_at': datetime.now().isoformat(),
                        'last_attempted': datetime.now().isoformat()
                    })
                    print(f"  ⚠️  Warning: Could not extract job_id from detail page (attempt {retry_count})")
                else:
                    # Success! Job has ID now
                    results.append(result)
                    if reason == 'retry_failed':
                        retry_count += 1
                    elif reason in ['retry_no_job_id', 'no_job_id']:
                        retry_count += 1
                        print(f"  ✅ Successfully extracted job_id: {extracted_job_id}")
                    elif update_existing and extracted_job_id in existing_job_ids:
                        updated_count += 1
                    else:
                        new_count += 1
            else:
                # Scraping failed - track with retry count
                normalized_url = job['url'].rstrip('/')
                existing_failed = existing_failed_by_id.get(job_id) if job_id else existing_failed_by_url.get(normalized_url) if normalized_url else None
                retry_count = (existing_failed.get('retry_count', 0) + 1) if existing_failed else 1
                
                failed_job_entry = {
                    'url': normalized_url,
                    'job_id': job_id,
                    'title': job.get('title', 'Unknown'),
                    'employer': job.get('employer', ''),
                    'location': job.get('location', ''),
                    'date_posted': job.get('date_posted', ''),
                    'industry': job.get('industry', ''),
                    'error': error,
                    'retry_count': retry_count,
                    'failure_type': 'fetch_error' if not job_id else 'unknown',
                    'failed_at': datetime.now().isoformat(),
                    'last_attempted': datetime.now().isoformat()
                }
                failed_jobs.append(failed_job_entry)
            
            # Be respectful - delay between requests
            if i < len(jobs_to_scrape):
                time.sleep(self.delay)
        
        # Merge with existing data (results already includes skipped jobs)
        # scrape_timestamp was set at the start of the scrape session
        
        if update_existing and existing_data:
            # Create final jobs map from results (which includes skipped + new/updated)
            final_jobs_map = {}
            
            # Add all results (includes skipped jobs + newly scraped)
            jobs_without_id_count = 0
            jobs_without_id_details = []
            for job in results:
                job_id = job.get('job_id')
                if job_id:
                    # Update last_seen to scrape timestamp for all jobs we encountered
                    job['last_seen'] = scrape_timestamp
                    
                    # If job exists in existing data, preserve first_seen
                    if job_id in existing_jobs_map:
                        existing_job = existing_jobs_map[job_id]
                        if existing_job.get('first_seen'):
                            job['first_seen'] = existing_job['first_seen']
                        else:
                            # If existing job doesn't have first_seen, use scrape timestamp (backfill)
                            job['first_seen'] = scrape_timestamp
                    else:
                        # New job - set first_seen to scrape timestamp if not already set
                        if not job.get('first_seen'):
                            job['first_seen'] = scrape_timestamp
                    
                    final_jobs_map[job_id] = job
                else:
                    # Job without extractable ID - log but don't add to final map
                    jobs_without_id_count += 1
                    jobs_without_id_details.append({
                        'title': job.get('title', 'Unknown'),
                        'url': job.get('url', 'No URL'),
                        'has_stored_id': bool(job.get('job_id'))
                    })
                    print(f"  ⚠️  Warning: Job without extractable ID excluded from final database: {job.get('title', 'Unknown')[:50]} (URL: {job.get('url', 'No URL')[:70]})")
            
            if jobs_without_id_count > 0:
                print(f"\n  ⚠️  Excluded {jobs_without_id_count} jobs without extractable job_id from final database (see failed_jobs for details):")
                for detail in jobs_without_id_details[:10]:
                    print(f"     - {detail['title'][:50]}: {detail['url'][:70]}")
                if len(jobs_without_id_details) > 10:
                    print(f"     ... and {len(jobs_without_id_details) - 10} more")
            
            # Add any existing jobs that weren't in results (edge case - jobs not on main page anymore)
            for job_id, job in existing_jobs_map.items():
                if job_id not in final_jobs_map:
                    # Preserve existing first_seen and last_seen for jobs not seen this scrape
                    final_jobs_map[job_id] = job
            
            all_jobs_data = list(final_jobs_map.values())
            
            # Debug: Check for counting discrepancies
            print(f"\n=== Merge Debug Info ===")
            print(f"Results list length: {len(results)}")
            print(f"Final jobs map length: {len(final_jobs_map)}")
            print(f"Existing jobs in map: {len(existing_jobs_map)}")
            print(f"Jobs preserved (not in results): {len([j for j in final_jobs_map.values() if j.get('job_id') not in {r.get('job_id') for r in results if r.get('job_id')}])}")
            
            # Merge failed jobs (update existing failed with new failures)
            # Track by both job_id and URL for jobs without extractable IDs
            existing_failed_by_id_final = {fj.get('job_id'): fj for fj in existing_data.get('failed_jobs', []) if fj.get('job_id')}
            existing_failed_by_url_final = {}
            for fj in existing_data.get('failed_jobs', []):
                url = fj.get('url')
                if url:
                    normalized_url = url.rstrip('/')
                    existing_failed_by_url_final[normalized_url] = fj
            
            # Add new failures, updating retry counts
            for fj in failed_jobs:
                job_id = fj.get('job_id')
                url = fj.get('url', '').rstrip('/') if fj.get('url') else ''
                
                if job_id:
                    # Track by job_id
                    existing_failed_by_id_final[job_id] = fj
                
                if url:
                    # Also track by URL (for jobs without job_id)
                    existing_failed_by_url_final[url] = fj
            
            # Remove from failed if now successful
            successful_ids = {job.get('job_id') for job in results if job.get('job_id')}
            successful_urls = {job.get('url', '').rstrip('/') for job in results if job.get('url')}
            
            # Build final failed_jobs list, excluding successful ones
            final_failed_jobs = []
            seen_urls = set()
            
            # Add failed jobs with job_id (if not successful)
            for job_id, fj in existing_failed_by_id_final.items():
                if job_id not in successful_ids:
                    url = fj.get('url', '').rstrip('/')
                    if url and url not in seen_urls:
                        final_failed_jobs.append(fj)
                        seen_urls.add(url)
            
            # Add failed jobs without job_id (if not successful)
            for url, fj in existing_failed_by_url_final.items():
                if url not in seen_urls and url not in successful_urls:
                    final_failed_jobs.append(fj)
                    seen_urls.add(url)
            
            failed_jobs = final_failed_jobs
        else:
            # No existing data - all jobs are new, ensure first_seen and last_seen are set
            scrape_timestamp = datetime.now().isoformat()
            for job in results:
                if not job.get('first_seen'):
                    job['first_seen'] = scrape_timestamp
                if not job.get('last_seen'):
                    job['last_seen'] = scrape_timestamp
            all_jobs_data = results
        
        # Save consolidated files
        json_path, csv_path = self.save_consolidated_files(all_jobs_data, failed_jobs)
        
        # Save summary with this scrape's details
        failed_with_id_count = len([fj for fj in failed_jobs if fj.get('job_id')])
        failed_without_id_count = len([fj for fj in failed_jobs if not fj.get('job_id')])
        
        summary = {
            'scrape_date': datetime.now().isoformat(),
            'total_jobs_found_on_page': len(jobs),
            'new_jobs_scraped': new_count,
            'jobs_retried': retry_count,
            'jobs_skipped': skipped_count,
            'jobs_updated': updated_count,
            'jobs_failed': len(failed_jobs),
            'failed_with_job_id': failed_with_id_count,
            'failed_without_job_id': failed_without_id_count,
            'total_jobs_in_database': len(all_jobs_data),
            'failed_jobs': failed_jobs[:50]  # Save first 50 failed for reference (increased for manual review)
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
            # Categorize failed jobs
            failed_with_id = [fj for fj in failed_jobs if fj.get('job_id')]
            failed_without_id = [fj for fj in failed_jobs if not fj.get('job_id')]
            
            print(f"\n=== Failed Jobs Summary ===")
            print(f"Total failed: {len(failed_jobs)}")
            print(f"  - With job_id: {len(failed_with_id)}")
            print(f"  - Without extractable job_id: {len(failed_without_id)}")
            
            if failed_without_id:
                print(f"\nJobs without extractable job_id (for manual review):")
                for fj in failed_without_id[:10]:
                    retry_info = f" (retry {fj.get('retry_count', 0)}/{max_retries})" if fj.get('retry_count', 0) > 0 else ""
                    print(f"  - {fj.get('title', 'Unknown')[:50]}: {fj.get('url', 'No URL')[:70]}{retry_info}")
                if len(failed_without_id) > 10:
                    print(f"  ... and {len(failed_without_id) - 10} more (see all_jobs.json/all_jobs.csv)")
            
            if failed_with_id:
                print(f"\nFailed jobs with job_id (showing first 5):")
                for fj in failed_with_id[:5]:
                    retry_info = f" (retry {fj.get('retry_count', 0)}/{max_retries})" if fj.get('retry_count', 0) > 0 else ""
                    failure_type = fj.get('failure_type', 'unknown')
                    print(f"  - {fj.get('title', 'Unknown')[:50]} (ID: {fj.get('job_id')}): {fj.get('error', 'Unknown error')} [{failure_type}]{retry_info}")
        
        return all_jobs_data


if __name__ == "__main__":
    scraper = PNGworkforceScraper(delay=2)  # 2 second delay between requests
    scraper.scrape_all()


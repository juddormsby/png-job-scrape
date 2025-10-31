# PNGworkforce.com Job Scraper

A Python scraper for extracting job listings from PNGworkforce.com with improved data extraction and incremental updates.

## Features

- **Main Page Scraping**: Extracts all job listings from the latest jobs page
- **Detail Page Scraping**: Downloads complete HTML for each job detail page
- **Improved Structured Data Extraction**: Uses proper HTML selectors to extract:
  - Job title (from `<title>` tag)
  - Location (from structured data `itemprop="addressRegion"`)
  - Date posted (from "Date Posted:" label)
  - Industry (from structured data `itemprop="industry"`)
  - Employer/company name
  - Full job description
  - Employment type, salary (when available)
- **HTML Archival**: Saves raw HTML files for later processing (e.g., LLM analysis)
- **Consolidated Output**: Creates `all_jobs.json` and `all_jobs.csv` with all jobs in one file
- **Incremental Updates**: Updates existing database instead of recreating each time
- **Failed Job Tracking**: Tracks and documents jobs that fail to scrape (404s, etc.)
- **Respectful Scraping**: Includes delays between requests to avoid overloading the server

## Installation

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

**IMPORTANT:** You must activate the virtual environment first!

### Method 1: Activate venv manually (Recommended)

```bash
# Activate the virtual environment
source venv/bin/activate

# Run the scraper
python scraper.py

# When done, deactivate (optional)
deactivate
```

### Method 2: Use the helper script (Easiest)

```bash
./run_scraper.sh
```

This automatically activates the venv and runs the scraper.

### Method 3: Run directly with venv Python

```bash
venv/bin/python scraper.py
```

### Troubleshooting

If you get `ModuleNotFoundError: No module named 'requests'`:
- You're not using the virtual environment
- Activate it first: `source venv/bin/activate`
- Or use one of the methods above

The scraper will:
1. Check for existing `all_jobs.json` and load it if found (incremental mode)
2. Fetch the latest jobs page from PNGworkforce.com
3. Extract all job listings and their detail page URLs
4. Download each job detail page and save as HTML in `html_output/`
5. Extract structured data using improved HTML selectors
6. Save individual JSON files in `json_output/`
7. Update/create consolidated files:
   - `all_jobs.json` - All jobs in one JSON file
   - `all_jobs.csv` - All jobs in CSV format for easy analysis
   - `scrape_summary.json` - Summary of the latest scrape

## Output Structure

```
pngworkforce-scrape/
├── html_output/          # Individual job HTML files
│   ├── job_25045.html
│   ├── job_25046.html
│   └── ...
├── json_output/          # Structured data JSON files
│   ├── job_25045.json    # Individual job data
│   ├── job_25046.json
│   ├── all_jobs.json     # ⭐ Consolidated JSON with all jobs
│   ├── all_jobs.csv      # ⭐ Consolidated CSV with all jobs
│   └── scrape_summary.json  # Latest scrape summary
└── scraper.py
```

## Output Format

### Individual Job JSON (`job_XXXXX.json`)
Each job JSON file contains:
- `job_id`: Unique job ID from URL
- `url`: Job detail page URL
- `title`: Job title (extracted from `<title>` tag)
- `date_posted`: Date the job was posted (from "Date Posted:" label)
- `location`: Job location (from structured data)
- `industry`: Industry category
- `employer`: Employer/company name
- `description`: Full job description text (up to 10,000 chars)
- `employment_type`: Full-Time, Part-Time, Contract, etc. (when available)
- `salary`: Salary information (when available)
- `html_file`: Absolute path to saved HTML file
- `html_file_rel`: Relative path to HTML file (for easy access)
- `json_file`: Absolute path to JSON file
- `json_file_rel`: Relative path to JSON file
- `scraped_at`: Timestamp of when the job was scraped

### Consolidated Files

**`all_jobs.json`**: 
- Main database file containing all scraped jobs
- Structure: `{ "last_updated": "...", "total_jobs": N, "jobs": [...], "failed_jobs": [...] }`
- Each job includes all fields from individual JSON files
- Use `job_id` to loop over jobs and access HTML files via `html_file_rel`

**`all_jobs.csv`**:
- Flattened CSV format for easy analysis in Excel/Python/R
- Includes: job_id, title, url, date_posted, location, industry, employer, etc.
- Perfect for filtering, sorting, and basic analysis

**`scrape_summary.json`**:
- Summary of the latest scrape session
- Shows: new jobs scraped, jobs updated, failed jobs, etc.

## Incremental Updates

The scraper supports incremental updates by default:
- On first run: Creates new `all_jobs.json` and `all_jobs.csv`
- On subsequent runs: 
  - Loads existing `all_jobs.json`
  - Only scrapes new jobs (not in existing database)
  - Updates existing jobs if they're found again
  - Merges everything into updated consolidated files
  - Tracks failed jobs separately

This means you can run the scraper daily/weekly and it will maintain a growing database without re-scraping everything.

## Failed Jobs

Failed jobs (typically 404 errors for expired/removed listings) are tracked in:
- `all_jobs.json` → `failed_jobs` array
- `scrape_summary.json` → `failed_jobs` array (first 10)

Each failed job entry includes:
- `url`: The job URL that failed
- `job_id`: Job ID if extractable
- `title`: Job title if known
- `error`: Error message (e.g., "404 Client Error: Not Found")
- `failed_at`: Timestamp of failure

## Customization

You can modify the scraper behavior by editing `scraper.py`:

- Change `delay` parameter in `PNGworkforceScraper()` to adjust time between requests (default: 2 seconds)
- Set `update_existing=False` in `scrape_all()` to force full re-scrape
- Modify `extract_structured_data()` to extract additional fields
- Adjust selectors in `extract_job_listings()` if the website structure changes

## Processing Existing Data

If you have existing scraped data and want to generate consolidated files:

```bash
python process_existing.py
```

This will create `all_jobs.json` and `all_jobs.csv` from existing individual JSON files.

## Notes

- The scraper includes a User-Agent header to identify itself as a browser
- A delay is included between requests to be respectful to the server
- HTML files are saved for later processing (e.g., with an LLM for more advanced extraction)
- The improved extraction uses proper HTML selectors and structured data (itemprop attributes)
- If the website structure changes, you may need to update the extraction logic
- Failed jobs (404s) are normal - some jobs get removed/expired


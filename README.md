# PNGworkforce.com Job Scraper

A Python scraper for extracting job listings from PNGworkforce.com.

**If you just want to view the main .csv output from scarping see:

```
├── json_output/          # Structured data JSON files
│   ├── all_jobs.json     # ⭐ Consolidated JSON with all jobs
│   ├── all_jobs.csv      # ⭐ Consolidated CSV with all jobs
```

If you want to understand the rest ... read on!

## Features

- **Main Page Scraping**: Extracts all job listings checking both the latest jobs page (https://www.pngworkforce.com/jobs/view-latest-jobs) and iterating through each set of 10 page listing on the main page (https://www.pngworkforce.com/)
- **Detail Page Scraping**: From the jobs scraped in the "Main Page Scrapng" the scraper then visits the indidual adds and downloads complete HTML for each job detail page
- **Improved Structured Data Extraction**: Uses proper HTML selectors to extract:
  - Job title (from `<title>` tag)
  - Location (from structured data `itemprop="addressRegion"`)
  - Date posted (from "Date Posted:" label)
  - Industry (from structured data `itemprop="industry"`)
  - Employer/company name (as well as employer profile page link, employer external website link, phone number and address).
  - Full job description
  - Employment type, salary (when available)
  - Various logging files (date first and last seen by scraper).
- **HTML Archival**: Saves raw HTML files for later processing (e.g., LLM analysis)
- **Consolidated Output**: Creates `all_jobs.json` and `all_jobs.csv` with all jobs in one file
- **Incremental Updates**: Updates existing database instead of recreating each time
- **Failed Job Tracking**: Tracks and documents jobs that fail to scrape (404s, etc.)
- **Respectful Scraping**: Includes delays between requests to avoid overloading the server

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

The scraper is designed to be run daily (using git actions).
- On first EVER run: Creates new `all_jobs.json` and `all_jobs.csv`
- On subsequent runs: 
  - **Skips already-scraped jobs**: If HTML and JSON files exist and are valid, skips scraping
  - **Only scrapes new jobs**: Only downloads detail pages for jobs not yet scraped
  - **Re-attempts failed jobs**: Automatically retries previously failed jobs
  - **Updates existing jobs**: If a job is found again but data changed, updates it
  - **Merges everything**: Combines all jobs into updated consolidated files

## Failed Jobs & Retries

Failed jobs (typically 404 errors for expired/removed listings) are:
- **Tracked separately** in `all_jobs.json` → `failed_jobs` array
- **Automatically re-attempted** on each run (maybe the page came back)
- **Removed from failed list** if they succeed on retry

Each failed job entry includes:
- `url`: The job URL that failed
- `job_id`: Job ID if extractable
- `title`: Job title if known
- `error`: Error message (e.g., "404 Client Error: Not Found")
- `failed_at`: Timestamp of failure

**Why retry failed jobs?**
- Sometimes jobs temporarily return 404 but come back
- Network issues might cause false failures
- Jobs might be temporarily removed then reposted

## Customization

You can modify the scraper behavior by editing `scraper.py`:

- Change `delay` parameter in `PNGworkforceScraper()` to adjust time between requests (default: 2 seconds)
- Set `update_existing=False` in `scrape_all()` to force full re-scrape (not recommended for daily runs)
- Modify `extract_structured_data()` to extract additional fields
- Adjust selectors in `extract_job_listings()` if the website structure changes

**For daily runs**: Leave `update_existing=True` (default) to use incremental updates.

## Processing Existing Data

If you have existing scraped data and want to generate consolidated files:

```bash
python process_existing.py
```

This will create `all_jobs.json` and `all_jobs.csv` from existing individual JSON files.

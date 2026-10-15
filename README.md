# PNGworkforce.com Job Scraper

A Python scraper for extracting job listings from PNGworkforce.com.

## Operational history and data quality

See the [15 October 2026 scraper audit](docs/SCRAPER_AUDIT_2026-10-15.md) for verified workflow history, live HTML comparisons, extraction defects and recommended repairs. In particular, **1–19 September 2026 is an observation gap caused by a GitHub billing lock**; scraping resumed on 20 September. Current title and salary extraction errors and description truncation should be considered before refreshing classifications or using the data analytically.

The [detailed September gap estimate](docs/SEPTEMBER_2026_GAP_ESTIMATE.md) suggests **about 75 lost advert IDs**, with a **40–90 sensitivity range**; most of the affected cohort was recovered after resumption. The [improvement plan](docs/SCRAPER_IMPROVEMENT_PLAN.md) explains the remaining focused repairs and retrospective salary recovery.

**HTML preservation is enabled.** All 26 retained workflow archives were saved before expiry, preserving HTML for 678 distinct IDs. Future runs commit compressed first/changed source versions and observation manifests to GitHub, including error pages and source captured before extraction. See the [archive operation and recovery guide](docs/HTML_ARCHIVE.md) for storage, provenance, recovery commands and test evidence. Historical field backfilling remains separate.

**If you just want to view the main .csv output from scraping see**:

```
├── json_output/          # Structured data JSON files
│   ├── all_jobs.json     # ⭐ Consolidated JSON with all jobs
│   ├── all_jobs.csv      # ⭐ Consolidated CSV with all jobs
```

If you want to understand the rest ... read on!

- **Main Page Scraping**: Extracts all job listings (urls), checking both the latest jobs page (https://www.pngworkforce.com/jobs/view-latest-jobs) and iterating through each set of 10 page listing on the main page (https://www.pngworkforce.com/).
- **Detail Page Scraping**: From the list of jobs scraped in the "Main Page Scraping" the scraper visits the individual job ads and downloads complete HTMLs for each job detail page
- **Structured Data Extraction**: Uses proper HTML selectors to extract:
  - Job title (from `<title>` tag)
  - Location (from structured data `itemprop="addressRegion"`)
  - Date posted (from "Date Posted:" label)
  - Industry (from structured data `itemprop="industry"`)
  - Employer/company name (as well as employer profile page link, employer external website link, phone number and address).
  - Full job description
  - Employment type, salary (when available)
  - Various logging files (date first and last seen by scraper).
- **HTML Archival**: Saves immutable compressed source versions and observation manifests in `archive/`, plus convenience HTML files in `html_output/`
- **Consolidated Output**: Creates `all_jobs.json` and `all_jobs.csv` with all jobs in one file
- **Incremental Updates**: Updates existing database instead of recreating each time
- **Failed Job Tracking**: Tracks and documents jobs that fail to scrape (404s, etc.)
- **Respectful Scraping**: Includes delays between requests to avoid overloading the server

## Output Structure

```
pngworkforce-scrape/
├── archive/              # Git-tracked source versions, manifests and inventory
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
└── code/scraper.py
```

## Output Format

### Individual Job JSON (`job_XXXXX.json`)
Each job JSON file contains:

**Core Fields:**
- `job_id`: Unique job ID from URL
- `date_posted`: Date the job was posted (formatted as DD/MM/YYYY)
- `title`: Job title (extracted from `<title>` tag)
- `industry`: Industry category
- `employer`: Employer/company name

**Employer Details:**
- `employer_profile_url`: Link to employer's profile page on PNGworkforce.com
- `employer_external_website`: Employer's external website URL
- `employer_phone`: Employer's phone number
- `employer_address`: Employer's address

**Job Details:**
- `employment_type`: Full-Time, Part-Time, Contract, etc. (when available)
- `salary`: Salary information (typically missing)
- `url`: Job detail page URL
- `description`: Full job description text (up to 10,000 chars)

**File References:**
- `html_file`: Absolute path to saved HTML file
- `html_file_rel`: Relative path to HTML file (for easy access)
- `json_file`: Absolute path to JSON file
- `json_file_rel`: Relative path to JSON file
- `source_archive_file`: Repository-relative path to immutable compressed source (newly fetched records)
- `source_archive_sha256`: SHA-256 of the decompressed archived source
- `source_archive_run_id`: Observation run that supplied this source reference

**Tracking Fields:**
- `first_seen`: Timestamp of when the job was first discovered by the scraper
- `last_seen`: Timestamp of when the job was most recently seen by the scraper
- `scraped_at`: Timestamp of when the job was last scraped/updated

**Additional Fields:**
- `location`: Job location (from structured data)
- `job_id_display`: Display version of job ID (when available)

### Consolidated Files

**`all_jobs.json`**: 
- Main database file containing all scraped jobs
- Structure: `{ "last_updated": "...", "total_jobs": N, "jobs": [...], "failed_jobs": [...] }`
- Each job includes all fields from individual JSON files
- Use `job_id` to loop over jobs and access HTML files via `html_file_rel`

**`all_jobs.csv`**:
- Flattened CSV format for easy analysis in Excel/Python/R
- Column order: `job_id`, `date_posted`, `title`, `industry`, `employer`, `employer_profile_url`, `employer_external_website`, `employer_phone`, `employer_address`, `employment_type`, `salary`, `url`, `html_file`, `json_file`, `description_length`, `first_seen`, `last_seen`, `scraped_at`, `status`, and any other fields
- Includes all fields from JSON files plus:
  - `description_length`: Character count of description (calculated field, not in JSON)
  - `status`: "success" for successfully scraped jobs, "failed" for failed jobs
- Perfect for filtering, sorting, and basic analysis

**`scrape_summary.json`**:
- Summary of the latest scrape session
- Shows: new jobs scraped, jobs updated, failed jobs, etc.

## Daily updates

The scraper runs daily at 02:00 UTC in GitHub Actions. It refreshes discovered live pages, archives first/changed source evidence, updates existing records and combines them with preserved historical jobs in the consolidated files. Having a local HTML/JSON file no longer prevents a live refresh. Failed jobs remain tracked separately. Each workflow verifies and publishes the source archive and uploads a temporary recovery artifact. See the archive guide above for manual checks and recovery.

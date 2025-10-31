# File Structure & Column Ordering

## Directory Structure

```
pngworkforce-scrape/
├── code/                    # Source code directory
│   ├── scraper.py          # Main scraper
│   ├── process_existing.py # Utility to process existing data
│   ├── test_extraction.py  # Test extraction improvements
│   ├── run_scraper.sh      # Helper script to run scraper
│   └── config.yaml         # Configuration template
├── html_output/            # Scraped HTML files (gitignored)
├── json_output/            # JSON/CSV output files (gitignored)
├── venv/                   # Virtual environment (gitignored)
├── requirements.txt        # Python dependencies
├── README.md               # Main documentation
└── .github/
    └── workflows/
        └── scrape.yml      # GitHub Actions workflow
```

## Column Ordering

### JSON Files (`job_XXXXX.json` & `all_jobs.json`)

Fields are ordered logically with **most important information first**:

**Primary Information:**
1. `job_id` - Unique identifier
2. `title` - Job title
3. `date_posted` - Date the job was posted
4. `location` - Job location
5. `industry` - Industry category
6. `employer` - Employer/company name
7. `employment_type` - Full-Time, Part-Time, etc.
8. `salary` - Salary information (if available)
9. `description` - Full job description

**Reference Information:**
10. `url` - Job detail page URL
11. `html_file` - Path to HTML file
12. `html_file_rel` - Relative path to HTML file
13. `json_file` - Path to JSON file
14. `json_file_rel` - Relative path to JSON file

**Metadata:**
15. `scraped_at` - When the job was scraped
16. `job_id_display` - Display version of job ID

### CSV File (`all_jobs.csv`)

Columns follow the same logical order:

**Primary Columns:**
1. `job_id`
2. `title`
3. `date_posted`
4. `location`
5. `industry`
6. `employer`
7. `employment_type`
8. `salary`
9. `url`

**File References:**
10. `html_file`
11. `json_file`
12. `description_length` - Length of description (useful for filtering)

**Metadata:**
13. `scraped_at`
14. `status` - 'success' or 'failed'
15. `error` - Error message (if failed)
16. `failed_at` - Timestamp of failure (if failed)

## Path Handling

All code in `code/` directory automatically detects if it's in a subdirectory and adjusts paths:

- Code detects `Path(__file__).parent.name == 'code'`
- If true, goes up one level to project root
- Output directories (`html_output/`, `json_output/`) are always in project root
- This ensures consistency whether running from `code/` or project root

## Running the Scraper

**From project root:**
```bash
cd code
python scraper.py
```

**Using helper script:**
```bash
cd code
./run_scraper.sh
```

**From project root:**
```bash
./code/run_scraper.sh
```

The script automatically handles path detection and runs from the correct location.


#!/usr/bin/env python3
"""
Process existing scraped data to create consolidated files
"""

import json
import csv
from pathlib import Path
from datetime import datetime

# Handle paths - if running from code/, go up one level
base_dir = Path(__file__).parent.parent if Path(__file__).parent.name == 'code' else Path(__file__).parent
json_dir = base_dir / "json_output"
html_dir = base_dir / "html_output"

# Load existing summary
summary_path = json_dir / 'scrape_summary.json'
if summary_path.exists():
    with open(summary_path, 'r') as f:
        summary = json.load(f)
    jobs_data = summary.get('jobs', [])
else:
    # Load from individual JSON files
    jobs_data = []
    for json_file in json_dir.glob('job_*.json'):
        try:
            with open(json_file, 'r') as f:
                job = json.load(f)
                # Add relative paths
                job_id = job.get('job_id', 'unknown')
                job['html_file_rel'] = f"html_output/job_{job_id}.html"
                job['json_file_rel'] = f"json_output/job_{job_id}.json"
                jobs_data.append(job)
        except:
            pass

# Create CSV
csv_data = []
for job in jobs_data:
    csv_row = {
        'job_id': job.get('job_id', ''),
        'title': job.get('title', ''),
        'url': job.get('url', ''),
        'date_posted': job.get('date_posted', job.get('date_advertised', '')),
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

# Add failed jobs if they exist in summary
if summary_path.exists():
    summary = json.load(open(summary_path, 'r'))
    failed_jobs = summary.get('failed_jobs', [])
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

# Save CSV
if csv_data:
    csv_path = json_dir / 'all_jobs.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
        writer.writeheader()
        writer.writerows(csv_data)
    print(f"CSV file saved: {csv_path}")

# Save consolidated JSON
consolidated = {
    'last_updated': datetime.now().isoformat(),
    'total_jobs': len(jobs_data),
    'jobs': jobs_data
}

json_path = json_dir / 'all_jobs.json'
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(consolidated, f, indent=2, ensure_ascii=False)
print(f"Consolidated JSON saved: {json_path}")
print(f"Total jobs: {len(jobs_data)}")


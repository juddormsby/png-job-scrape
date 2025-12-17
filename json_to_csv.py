import json
import csv

# Load JSON
with open('json_output/LLM_processed_jobs.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Flatten nested structure
rows = []
for job in data:
    row = {'job_id': job.get('job_id', '')}
    
    # Flatten industry classification
    ind = job.get('industry_classification', {})
    for key, value in ind.items():
        row[key] = value
    
    # Flatten occupation classification
    occ = job.get('occupation_classification', {})
    for key, value in occ.items():
        row[key] = value
    
    row['classification_summary'] = job.get('classification_summary', '')
    if 'error' in job:
        row['error'] = job.get('error', '')
    rows.append(row)

# Write CSV
with open('json_output/LLM_processed_jobs.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
    writer.writeheader()
    writer.writerows(rows)

print(f"Converted {len(rows)} records to CSV")

import json
import os
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from openai import OpenAI
from pydantic import BaseModel

# ============================================================================
# CONFIGURATION
# ============================================================================
DEMO_MODE = False  # Set to False to process all jobs
DEMO_NUM_JOBS = 100  # Number of jobs to process in demo mode
PARALLEL_WORKERS = 500  # Number of parallel workers for processing jobs
# ============================================================================


class IndustryClassification(BaseModel):
    """ISIC Rev.4 classification at different digit levels"""
    isic_1digit: Optional[str] = None  # Section (1 digit)
    isic_2digit: Optional[str] = None  # Division (2 digits)
    isic_3digit: Optional[str] = None  # Group (3 digits)
    isic_4digit: Optional[str] = None  # Class (4 digits)
    isic_1digit_confidence: float
    isic_2digit_confidence: float
    isic_3digit_confidence: float
    isic_4digit_confidence: float


class OccupationClassification(BaseModel):
    """ISCO-08 classification at different digit levels"""
    isco_1digit: Optional[str] = None  # Major group (1 digit)
    isco_2digit: Optional[str] = None  # Sub-major group (2 digits)
    isco_3digit: Optional[str] = None  # Minor group (3 digits)
    isco_4digit: Optional[str] = None  # Unit group (4 digits)
    isco_1digit_confidence: float
    isco_2digit_confidence: float
    isco_3digit_confidence: float
    isco_4digit_confidence: float


class JobClassification(BaseModel):
    """Complete classification result for a job posting (without job_id, added separately)"""
    industry_classification: IndustryClassification
    occupation_classification: OccupationClassification
    classification_summary: str  # Two-sentence summary of classification quality


def load_api_key(file_path: str) -> str:
    """Load OpenAI API key from text file"""
    with open(file_path, 'r') as f:
        return f.read().strip()


def load_jobs(file_path: str) -> list:
    """Load jobs from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('jobs', [])


# Lock for thread-safe file writing
file_lock = Lock()

def save_results(results: list, file_path: str):
    """Save classification results to JSON file (thread-safe)"""
    with file_lock:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)


def load_existing_results(file_path: str) -> dict:
    """Load existing results to avoid reprocessing"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return {item['job_id']: item for item in json.load(f)}
    return {}


def classify_job(api_key: str, job: dict) -> dict:
    """Classify a single job posting using OpenAI"""
    
    # Extract relevant fields
    title = job.get('title', '')
    description = job.get('description', '')
    employer = job.get('employer', '')
    employer_external_url = job.get('employer_external_website', '')
    location = job.get('location', '')
    industry = job.get('industry', '')
    
    # Create prompt
    prompt = f"""Analyze the following job posting (scraped from online) and classify it according to ISIC Rev.4 (Economic Activity) and ISCO-08 (Occupation) standards.

Job Title: {title}
Employer: {employer}
Location: {location}
Industry (note this is as described informally in online posting - not official information): {industry}
Employer Website: {employer_external_url}

Job Description:
{description}

Please provide:
1. ISIC Rev.4 classification at 1-digit (Section), 2-digit (Division), 3-digit (Group), and 4-digit (Class) levels
2. ISCO-08 classification at 1-digit (Major Group), 2-digit (Sub-major Group), 3-digit (Minor Group), and 4-digit (Unit Group) levels
3. Confidence scores (0.0 to 1.0) for each classification level
4. A two-sentence summary evaluating how well this job posting can be classified

If a classification cannot be determined at a specific digit level, use null for that field but still provide a confidence score (which should be low if uncertain).
Use standard ISIC Rev.4 and ISCO-08 code formats.
Note that you should provide them in the digit description format: 
E.g. for ISIC 1 Digit.
A - Agriculture, forestry and fishing
B - Mining and quarrying
C - Manufacturing
D - Electricity, gas, steam and air conditioning supply
E - Water supply; sewerage, waste management and remediation activities
F - Construction
G - Wholesale and retail trade; repair of motor vehicles and motorcycles
H - Transportation and storage
I - Accommodation and food service activities
J - Information and communication
K - Financial and insurance activities
L - Real estate activities
M - Professional, scientific and technical activities
N - Administrative and support service activities
O - Public administration and defence; compulsory social security
P - Education
Q - Human health and social work activities
R - Arts, entertainment and recreation
S - Other service activities
T - Activities of households as employers; undifferentiated goods- and services-producing activities of households for own use
U - Activities of extraterritorial organisations and bodies

And for ISCO 1 digit:
0 - Armed forces occupations
1 - Managers
2 - Professionals
3 - Technicians and associate professionals
4 - Clerical support workers
5 - Service and sales workers
6 - Skilled agricultural, forestry and fishery workers
7 - Craft and related trades workers
8 - Plant and machine operators and assemblers
9 - Elementary occupations



"""

    # Create client for this thread (OpenAI client is not thread-safe)
    client = OpenAI(api_key=api_key)
    
    try:
        response = client.responses.parse(
            model="gpt-5-mini",
            input=[
                {
                    "role": "system",
                    "content": "You are an expert in labor market classification systems. You classify job postings according to ISIC Rev.4 (economic activity) and ISCO-08 (occupation) standards with high accuracy."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            text_format=JobClassification
        )
        
        # Extract parsed result
        classification = response.output_parsed
        
        # Convert to dictionary (job_id comes from input job, not LLM)
        result = {
            "job_id": job.get('job_id', 'unknown'),
            "industry_classification": {
                "isic_1digit": classification.industry_classification.isic_1digit,
                "isic_2digit": classification.industry_classification.isic_2digit,
                "isic_3digit": classification.industry_classification.isic_3digit,
                "isic_4digit": classification.industry_classification.isic_4digit,
                "isic_1digit_confidence": classification.industry_classification.isic_1digit_confidence,
                "isic_2digit_confidence": classification.industry_classification.isic_2digit_confidence,
                "isic_3digit_confidence": classification.industry_classification.isic_3digit_confidence,
                "isic_4digit_confidence": classification.industry_classification.isic_4digit_confidence,
            },
            "occupation_classification": {
                "isco_1digit": classification.occupation_classification.isco_1digit,
                "isco_2digit": classification.occupation_classification.isco_2digit,
                "isco_3digit": classification.occupation_classification.isco_3digit,
                "isco_4digit": classification.occupation_classification.isco_4digit,
                "isco_1digit_confidence": classification.occupation_classification.isco_1digit_confidence,
                "isco_2digit_confidence": classification.occupation_classification.isco_2digit_confidence,
                "isco_3digit_confidence": classification.occupation_classification.isco_3digit_confidence,
                "isco_4digit_confidence": classification.occupation_classification.isco_4digit_confidence,
            },
            "classification_summary": classification.classification_summary
        }
        
        return result
        
    except Exception as e:
        print(f"Error classifying job {job.get('job_id', 'unknown')}: {str(e)}")
        return {
            "job_id": job.get('job_id', 'unknown'),
            "error": str(e)
        }


def process_job_batch(api_key: str, jobs_batch: list, existing_results: dict, output_file: str, batch_num: int, total_batches: int) -> list:
    """Process a batch of jobs in parallel"""
    results = []
    
    def process_single_job(job):
        """Process a single job and return result"""
        job_id = job.get('job_id', 'unknown')
        title = job.get('title', 'N/A')
        
        # Skip if already processed
        if job_id in existing_results:
            return None
        
        print(f"[Batch {batch_num}/{total_batches}] Processing job {job_id}: {title}")
        
        # Classify job
        result = classify_job(api_key, job)
        
        print(f"  ✓ Completed job {job_id}")
        return result
    
    # Process batch in parallel
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        future_to_job = {executor.submit(process_single_job, job): job for job in jobs_batch}
        
        for future in as_completed(future_to_job):
            result = future.result()
            if result is not None:
                results.append(result)
    
    return results


def main():
    # File paths
    api_key_file = "png-jobscraper.txt"
    jobs_file = "json_output/all_jobs.json"
    output_file = "json_output/LLM_processed_jobs.json"
    
    # Load API key
    print("Loading API key...")
    api_key = load_api_key(api_key_file)
    
    # Load jobs
    print("Loading jobs...")
    jobs = load_jobs(jobs_file)
    print(f"Found {len(jobs)} jobs to process")
    
    # Load existing results
    existing_results = load_existing_results(output_file)
    print(f"Found {len(existing_results)} existing classifications")
    
    # Apply demo mode limit
    if DEMO_MODE:
        print(f"\n{'='*60}")
        print(f"DEMO MODE ENABLED - Processing only first {DEMO_NUM_JOBS} jobs")
        print(f"{'='*60}\n")
        jobs = jobs[:DEMO_NUM_JOBS]
    
    # Filter out already processed jobs
    jobs_to_process = [job for job in jobs if job.get('job_id') not in existing_results]
    print(f"Jobs to process: {len(jobs_to_process)} (skipping {len(jobs) - len(jobs_to_process)} already processed)")
    
    if not jobs_to_process:
        print("No new jobs to process!")
        return
    
    # Initialize results with existing ones
    results = list(existing_results.values())
    processed_count = len(results)
    
    # Process jobs in batches
    batch_size = PARALLEL_WORKERS
    total_batches = (len(jobs_to_process) + batch_size - 1) // batch_size
    
    print(f"\n{'='*60}")
    print(f"Processing {len(jobs_to_process)} jobs in {total_batches} batch(es)")
    print(f"Using {PARALLEL_WORKERS} parallel workers per batch")
    print(f"{'='*60}\n")
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(jobs_to_process))
        batch = jobs_to_process[start_idx:end_idx]
        
        print(f"\n--- Processing Batch {batch_num + 1}/{total_batches} ({len(batch)} jobs) ---")
        
        # Process batch
        batch_results = process_job_batch(
            api_key, batch, existing_results, output_file, 
            batch_num + 1, total_batches
        )
        
        # Add batch results
        results.extend(batch_results)
        processed_count += len(batch_results)
        
        # Update existing results to avoid duplicates in next batch
        for result in batch_results:
            existing_results[result['job_id']] = result
        
        # Save after each batch
        save_results(results, output_file)
        print(f"  ✓ Batch {batch_num + 1} complete. Saved {len(batch_results)} new results ({processed_count} total)")
    
    print(f"\n{'='*60}")
    print(f"Completed! Processed {processed_count} jobs total ({len(jobs_to_process)} new).")
    if DEMO_MODE:
        print(f"Demo mode: Limited to first {DEMO_NUM_JOBS} jobs from the list.")
    print(f"Results saved to {output_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()


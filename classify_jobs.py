import json
import os
from typing import Optional
from openai import OpenAI
from pydantic import BaseModel

# ============================================================================
# DEMO MODE CONFIGURATION
# ============================================================================
DEMO_MODE = True  # Set to False to process all jobs
DEMO_NUM_JOBS = 10  # Number of jobs to process in demo mode
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


def save_results(results: list, file_path: str):
    """Save classification results to JSON file"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def load_existing_results(file_path: str) -> dict:
    """Load existing results to avoid reprocessing"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return {item['job_id']: item for item in json.load(f)}
    return {}


def classify_job(client: OpenAI, job: dict) -> dict:
    """Classify a single job posting using OpenAI"""
    
    # Extract relevant fields
    title = job.get('title', '')
    description = job.get('description', '')
    employer = job.get('employer', '')
    employer_external_url = job.get('employer_external_website', '')
    location = job.get('location', '')
    industry = job.get('industry', '')
    
    # Create prompt
    prompt = f"""Analyze the following job posting and classify it according to ISIC Rev.4 (Economic Activity) and ISCO-08 (Occupation) standards.

Job Title: {title}
Employer: {employer}
Location: {location}
Industry: {industry}
Employer Website: {employer_external_url}

Job Description:
{description}

Please provide:
1. ISIC Rev.4 classification at 1-digit (Section), 2-digit (Division), 3-digit (Group), and 4-digit (Class) levels
2. ISCO-08 classification at 1-digit (Major Group), 2-digit (Sub-major Group), 3-digit (Minor Group), and 4-digit (Unit Group) levels
3. Confidence scores (0.0 to 1.0) for each classification level
4. A two-sentence summary evaluating how well this job posting can be classified

If a classification cannot be determined at a specific digit level, use null for that field but still provide a confidence score (which should be low if uncertain).
Use standard ISIC Rev.4 and ISCO-08 code formats."""

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


def main():
    # File paths
    api_key_file = "png-jobscraper.txt"
    jobs_file = "json_output/all_jobs.json"
    output_file = "json_output/LLM_processed_jobs.json"
    
    # Load API key
    print("Loading API key...")
    api_key = load_api_key(api_key_file)
    client = OpenAI(api_key=api_key)
    
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
    
    # Process each job
    results = list(existing_results.values())
    processed_count = len(results)
    new_jobs_processed = 0
    
    for i, job in enumerate(jobs, 1):
        job_id = job.get('job_id', 'unknown')
        
        # Skip if already processed
        if job_id in existing_results:
            print(f"[{i}/{len(jobs)}] Skipping job {job_id} (already processed)")
            continue
        
        print(f"[{i}/{len(jobs)}] Processing job {job_id}: {job.get('title', 'N/A')}")
        
        # Classify job
        result = classify_job(client, job)
        
        # Add to results
        results.append(result)
        
        # Save after each job
        save_results(results, output_file)
        processed_count += 1
        new_jobs_processed += 1
        
        print(f"  ✓ Saved result for job {job_id} ({processed_count} total)")
    
    print(f"\nCompleted! Processed {processed_count} jobs total ({new_jobs_processed} new).")
    if DEMO_MODE:
        print(f"Demo mode: Limited to first {DEMO_NUM_JOBS} jobs from the list.")
    print(f"Results saved to {output_file}")


if __name__ == "__main__":
    main()


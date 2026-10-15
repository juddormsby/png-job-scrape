#!/usr/bin/env python3
"""Read-only investigation of exact description repeats in the 15 Oct snapshot."""
import hashlib
import json
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

from summarize_dataset import parse_date

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/2026-10-15/duplicates'


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def duplicate_table(rows, fields):
    counts = Counter(tuple(row.get(field, '') for field in fields) for row in rows)
    distribution = Counter(counts.values())
    return [{'copies': size, 'observations': size*distribution[size],
             'surplus': (size-1)*distribution[size], 'groups': distribution[size]}
            for size in sorted(distribution)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'json_output/all_jobs.json'
    jobs = json.loads(source.read_text())['jobs']
    by_text = defaultdict(list)
    for job in jobs:
        by_text[job['description']].append(job)
    repeated = sorted([v for v in by_text.values() if len(v)>1],
                      key=lambda v: min(int(j['job_id']) for j in v))
    rows, groups = [], []
    group_ids = {v[0]['description']: index+1 for index,v in enumerate(repeated)}
    keys_to_text = {}
    for job in jobs:
        text = job['description']
        key = digest(text)
        assert keys_to_text.setdefault(key, text) == text, 'Hash collision'
        group = by_text[text]
        first_days = [date.fromisoformat(j['first_seen'][:10]) for j in group]
        row = {field: job.get(field, '') or '' for field in
               ['title','employer','date_posted','first_seen','last_seen','url','description']}
        row.update({'job_id': int(job['job_id']), 'description_key': key,
                    'employer_key': digest(job['employer']), 'title_key': digest(job['title']),
                    'first_day': job['first_seen'][:10],
                    'posted_day': parse_date(job['date_posted']).strftime('%Y-%m-%d'),
                    'description_chars': len(text), 'description_utf8_bytes': len(text.encode()),
                    'copy_count': len(group), 'repeat_group': group_ids.get(text, 0),
                    'group_first_span_days': (max(first_days)-min(first_days)).days})
        rows.append(row)
    for index, members in enumerate(repeated, 1):
        days = sorted({j['first_seen'][:10] for j in members})
        core = members[0]['description'].split('\nEmail job to a friend', 1)[0].strip()
        groups.append({'repeat_group': index, 'description_key': digest(members[0]['description']),
                       'copies': len(members), 'description_chars': len(members[0]['description']),
                       'characters_before_share_controls': len(core),
                       'first_seen_min': days[0], 'first_seen_max': days[-1],
                       'first_seen_span_days': (date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days,
                       'distinct_first_seen_days': len(days),
                       'distinct_employers': sorted({j['employer'] for j in members}),
                       'distinct_titles': sorted({j['title'] for j in members}),
                       'has_same_day_companions': len(members)>len(days),
                       'at_description_cap': len(members[0]['description'])==10000,
                       'members': [{k:j.get(k) for k in ['job_id','title','employer','date_posted','first_seen','last_seen','url']}
                                   for j in sorted(members,key=lambda j:(j['first_seen'],int(j['job_id'])))]})
    employer_total = Counter(j['employer'] for j in jobs)
    employer_repeat = Counter(j['employer'] for group in repeated for j in group)
    summary = {
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'records': len(jobs), 'unique_ids': len({j['job_id'] for j in jobs}),
        'duplicate_definition': 'Exact entire stored description string; no whitespace normalization or truncation for the hash.',
        'description_report': duplicate_table(jobs,['description']),
        'job_id_report': duplicate_table(jobs,['job_id']),
        'employer_description_report': duplicate_table(jobs,['employer','description']),
        'employer_title_description_report': duplicate_table(jobs,['employer','title','description']),
        'employer_title_posted_description_report': duplicate_table(jobs,['employer','title','date_posted','description']),
        'normalized_posted_report': duplicate_table(rows,['employer_key','title_key','posted_day','description_key']),
        'repeated_groups': len(repeated), 'repeated_records': sum(map(len,repeated)),
        'surplus': sum(len(group)-1 for group in repeated),
        'distinct_description_strings': len(by_text),
        'same_first_day_groups': sum(g['distinct_first_seen_days']==1 for g in groups),
        'different_first_days_groups': sum(g['distinct_first_seen_days']>1 for g in groups),
        'groups_with_any_same_first_day_companions': sum(g['has_same_day_companions'] for g in groups),
        'groups_spanning_at_least_30_days': sum(g['first_seen_span_days']>=30 for g in groups),
        'median_first_seen_span_days': statistics.median(g['first_seen_span_days'] for g in groups),
        'max_first_seen_span_days': max(g['first_seen_span_days'] for g in groups),
        'single_employer_groups': sum(len(g['distinct_employers'])==1 for g in groups),
        'cross_employer_groups': [g['repeat_group'] for g in groups if len(g['distinct_employers'])>1],
        'minimum_repeated_description_chars': min(g['description_chars'] for g in groups),
        'minimum_repeated_chars_before_share_controls': min(g['characters_before_share_controls'] for g in groups),
        'capped_groups': [g['repeat_group'] for g in groups if g['at_description_cap']],
        'employers': [{'employer':employer, 'repeated_records':count,
                      'all_records':employer_total[employer],
                      'share_of_all_repeated_records':count/sum(map(len,repeated))}
                     for employer,count in employer_repeat.most_common()],
        'interpretation': 'First-seen spans are observation spans, not proven vacancy durations. Same first day may include startup stock. Date_posted is mutable. No rows are dropped.',
    }
    # Full Unicode, long-text review file for Stata 14+.
    frame = pd.DataFrame(rows).sort_values(['repeat_group','first_day','job_id'])
    frame.to_stata(OUT/'duplicate_review.dta',write_index=False,version=118,
                   convert_strl=['description'],data_label='PNGworkforce exact-description duplicate review')
    restored = pd.read_stata(OUT/'duplicate_review.dta',convert_categoricals=False)
    assert all(digest(text)==key for text,key in zip(restored['description'],restored['description_key']))
    # Installed Stata is 13.1: ASCII display labels; exact hashes retain original
    # Unicode equality. This smaller file omits full descriptions, not hash input.
    legacy = frame.drop(columns=['description']).copy()
    for column in legacy.select_dtypes(include=['object']).columns:
        legacy[column] = legacy[column].map(lambda value: value.encode('ascii','backslashreplace').decode('ascii'))
    legacy.to_stata(OUT/'duplicate_keys_stata13.dta',write_index=False,version=117,
                    data_label='Exact hashes of original Unicode text; ASCII display labels')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    (OUT/'groups.json').write_text(json.dumps(groups,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['employers','normalized_posted_report']},indent=2))


if __name__=='__main__':
    main()

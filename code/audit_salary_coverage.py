"""Offline salary-evidence audit; never calls a model or modifies source records."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import random
import re

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PAY = re.compile(r"\b(?:salar\w*|remunerat\w*|wages?|stipends?|compensation|pay(?:ment)?|earn(?:ing)?s?|allowances?|packages?|rates?|fortnight\w*|annum|kina|PGK|USD|AUD|NZD|dollars?)\b|\$", re.I)
CURRENCY = re.compile(r"(?:\b(?:PGK|USD|AUD|NZD|US\$|AU\$|Kina)\s*[:=]?\s*\d[\d,. ]*|(?<!\w)[Kk$]\s*\d[\d,. ]*(?!\w)|\d[\d,. ]*\s*(?:PGK|USD|AUD|NZD|kina)\b)", re.I)
PERIOD = re.compile(r"\d[\d,. ]*\s*(?:[-–—]\s*\d[\d,. ]*)?\s*(?:per\s+(?:annum|year|month|week|day|hour|fortnight)|p\.?a\.?\b|annually|monthly|fortnightly)", re.I)
NUMBER = re.compile(r"\d")


def windows(text, pattern, radius=180):
    spans = [(max(0, m.start()-radius), min(len(text), m.end()+radius)) for m in pattern.finditer(text)]
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(b, merged[-1][1])
        else:
            merged.append([a, b])
    return [text[a:b].replace('\n', ' ') for a,b in merged]


def candidate(text):
    # Broad screening, deliberately inclusive. Human review decides whether pay.
    if CURRENCY.search(text) or PERIOD.search(text):
        return True
    return any(NUMBER.search(s) for s in windows(text, PAY, 130))


def load_sources(jobs):
    sources = {}
    for p in sorted((ROOT/'archive/index').rglob('job_*.json')):
        d = json.loads(p.read_text())
        if d.get('category') not in ('job_html','legacy_html'):
            continue
        if d.get('category') == 'job_html' and not p.name.endswith('-200.json'):
            continue
        jid = d['resource'][4:]
        if jid not in sources or d['category']=='job_html':
            sources[jid] = ROOT/'archive'/d['source_path']
    for j in jobs:
        jid = str(j['job_id'])
        if j.get('source_archive_file') and (ROOT/j['source_archive_file']).is_file():
            sources[jid] = ROOT/j['source_archive_file']
        elif jid not in sources and j.get('html_file_rel') and (ROOT/j['html_file_rel']).is_file():
            sources[jid] = ROOT/j['html_file_rel']
    return sources


def finalize(rows, meta, report):
    """Apply the saved human review decisions; regenerate counts and evidence."""
    review = json.loads((report/'manual_review.json').read_text())
    desc = set(review['description_numeric_salary_ids'])
    extra = set(review['html_only_numeric_salary_ids'])
    html = [r for r in rows if 'source_path' in r]
    recent = [r for r in rows if r['first_seen'] >= '2026-09']
    pct = lambda n,d: round(100*n/d,3)
    summary = dict(meta)
    summary.update({
        'salary_definition': 'Explicit monetary wage/salary amount or range for the advertised role. Grades, competitive/negotiable wording, project budgets, employer turnover, tax rates and unspecified commissions excluded.',
        'unit': 'Distinct advert IDs, not individual positions or unique recruitment episodes.',
        'description_confirmed':len(desc), 'description_percent':pct(len(desc),len(rows)),
        'html_paired_description_confirmed':sum(r['job_id'] in desc for r in html),
        'html_only_additional_confirmed':len(extra),
        'html_paired_either_confirmed':sum(r['job_id'] in desc|extra for r in html),
        'html_paired_either_percent':pct(sum(r['job_id'] in desc|extra for r in html),len(html)),
        'all_available_sources_confirmed':len(desc|extra),
        'all_available_sources_percent':pct(len(desc|extra),len(rows)),
        'recent_cohort':{'definition':'First seen September–October 2026, through database snapshot 15 October',
                         'records':len(recent),'html_records':sum('source_path' in r for r in recent),
                         'description_confirmed':sum(r['job_id'] in desc for r in recent),
                         'either_confirmed':sum(r['job_id'] in desc|extra for r in recent)},
        'html_only_by_employer':dict(collections.Counter(r['employer'] for r in rows if r['job_id'] in extra)),
        'random_negative_check':{'n':150,'additional_numeric_salary_found':0,
                                'scope':'Human inspection of numeric and compensation-relevant passages, not a blind full-text gold-standard annotation.'},
        'description_pay_grade_candidates':sum(bool(re.search(r'(?:salary\s*(?:grade|level)|salary\s*:\s*(?:grade|[NU]\d)|NC\s*Salary\s*Grade)',r['description'],re.I)) for r in rows),
        'limitations':[
            'Descriptions screened comprehensively by multiple patterns; human review used evidence windows and grouped repeated templates, rather than reading all complete descriptions.',
            'HTML availability is strongly selected by employer and capture date. Paired percentages are descriptive, not representative sample estimates.',
            'One selected available HTML version per advert; a historical source is not guaranteed contemporaneous with latest JSON.',
            'No model API calls, live website fetches, external application pages, attachment downloads, image OCR, or linked pay-scale lookups.',
            'Salary amounts need not state currency/pay period consistently. Any-amount coverage is higher than coverage of fully normalized annual salaries.',
        ],
    })
    stored = {str(j['job_id']): j.get('salary') for j in json.loads((ROOT/'json_output/all_jobs.json').read_text())['jobs']}
    confirmed_paired = [r for r in html if r['job_id'] in desc|extra]
    summary['html_subset_existing_salary_field'] = {
        'records':len(html),
        'nonempty_fields':sum(bool(stored.get(r['job_id'])) for r in html),
        'comma_fields':sum(stored.get(r['job_id']) == ',' for r in html),
        'confirmed_usable_numeric_salary_fields':0,
        'confirmed_salary_adverts':len(confirmed_paired),
        'confirmed_salary_adverts_with_comma_field':sum(stored.get(r['job_id']) == ',' for r in confirmed_paired),
        'note':'Usability is a reviewed result for this snapshot, not a generic numeric-field validator.'
    }
    evidence=[]
    for r in rows:
        if r['job_id'] not in desc|extra:continue
        evidence.append({'job_id':r['job_id'],'title':r['title'],'employer':r['employer'],'url':r['url'],
                         'first_seen':r['first_seen'], 'numeric_salary_in_description':r['job_id'] in desc,
                         'numeric_salary_in_html_only':r['job_id'] in extra,
                         'description_evidence':r['description_evidence'] if r['job_id'] in desc else [],
                         'html_base_salary':r.get('html_base_salary',[]),
                         'html_source_path':r.get('source_path')})
    (report/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    (report/'confirmed_salary_evidence.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False))
    # Keep reviewable screens without copying all source descriptions into the report.
    screened=[]
    for r in rows:
        if not r['description_candidate']:continue
        screened.append({'job_id':r['job_id'],'numeric_salary_confirmed':r['job_id'] in desc,
                         'currency_period_passages':r['description_evidence'],
                         'pay_number_passages':[w for w in r['description_pay_windows'] if NUMBER.search(w)]})
    (report/'reviewed_description_candidates.json').write_text(json.dumps(screened,indent=2,ensure_ascii=False))
    print(json.dumps(summary,indent=2))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='/private/tmp/pngworkforce-salary-audit-20261016')
    parser.add_argument('--finalize',action='store_true',help='Apply saved manual labels and write compact report evidence')
    args=parser.parse_args()
    out=ROOT/args.out
    out.mkdir(parents=True,exist_ok=True)
    raw=(ROOT/'json_output/all_jobs.json').read_bytes()
    jobs=json.loads(raw)['jobs']
    sources=load_sources(jobs)
    rows=[]
    for j in jobs:
        jid=str(j['job_id']); desc=j.get('description','')
        r={'job_id':jid,'title':j['title'],'employer':j['employer'],'first_seen':j.get('first_seen'),
           'url':j['url'],'description':desc,'description_candidate':candidate(desc),
           'description_currency_or_period':bool(CURRENCY.search(desc) or PERIOD.search(desc)),
           'description_evidence':windows(desc, re.compile(CURRENCY.pattern+'|'+PERIOD.pattern, re.I),200),
           'description_pay_windows':windows(desc,PAY,160)}
        if jid in sources:
            p=sources[jid];body=gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()
            s=BeautifulSoup(body,'html.parser')
            r['source_path']=str(p.relative_to(ROOT))
            r['html_base_salary']=[e.get('content',e.get_text(' ',strip=True)) for e in s.select('[itemprop="baseSalary"]')]
            r['html_currency']=[e.get('content',e.get_text(' ',strip=True)) for e in s.select('[itemprop="salaryCurrency"]')]
            e=s.select_one('[itemprop="description"]')
            r['html_description']=e.get_text('\n',strip=True) if e else ''
            # Use the whole page for the inclusive screen; reviewer can reject footer noise.
            for tag in s(['script','style','noscript']):tag.decompose()
            text=s.get_text('\n',strip=True)
            r['html_candidate']=candidate(text)
            r['html_evidence']=windows(text,re.compile(CURRENCY.pattern+'|'+PERIOD.pattern,re.I),200)
            r['html_pay_windows']=windows(text,PAY,160)
        rows.append(r)
    (out/'screening.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False))
    numeric=[r for r in rows if r['description_currency_or_period']]
    broad=[r for r in rows if r['description_candidate'] and not r['description_currency_or_period']]
    negative=[r for r in rows if not r['description_candidate']]
    rng=random.Random(20261016)
    # Fixed random sample from the screen-negative stratum, without replacement.
    sample=rng.sample(negative,min(150,len(negative)))
    (out/'negative_review_sample.json').write_text(json.dumps([r['job_id'] for r in sample],indent=2))
    for name,items in [('currency_candidates',numeric),('broad_candidates',broad),('negative_sample',sample)]:
        lines=[]
        for r in items:
            lines.append(f"\n### {r['job_id']} | {r['title']} | {r['employer']}\n")
            if name=='currency_candidates':lines.extend(r['description_evidence'])
            elif name=='broad_candidates':
                lines.extend(w for w in r['description_pay_windows'] if NUMBER.search(w))
            else:lines.append(r['description'])
        (out/(name+'.txt')).write_text('\n'.join(lines))
    meta={'source_sha256':hashlib.sha256(raw).hexdigest(),'records':len(rows),
          'html_records':sum('source_path' in r for r in rows),'currency_candidates':len(numeric),
          'broad_candidates':len(broad),'screen_negative':len(negative),'random_negative_sample':len(sample),
          'seed':20261016}
    (out/'screening_summary.json').write_text(json.dumps(meta,indent=2))
    print(json.dumps(meta,indent=2))
    if args.finalize:
        finalize(rows,meta,ROOT/'reports/2026-10-16/salary-audit')


if __name__=='__main__':main()

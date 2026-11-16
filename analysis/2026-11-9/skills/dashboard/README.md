# PNG skills dashboard

Run locally, from this folder:

```sh
python3 serve.py
```

Open **http://127.0.0.1:8765**. Use `--port 8766` if the default port is occupied.
The server listens only on this computer. Stop it with Ctrl+C. Python's standard
library is sufficient. There is no npm build step, CDN, external font, telemetry,
model call, or API key. Directly opening `index.html` will not load the JSON files.

## Netlify hosting

The repository is `juddormsby/png-job-scrape`, production branch `main`.
Set the Netlify **base directory** to
`analysis/2026-11-9/skills/dashboard`. Its `netlify.toml` runs
`python3 build_site.py` and publishes `public`, relative to that base directory.
The Edge Function requires `DASHBOARD_PASSWORD` and `DASHBOARD_SESSION_SECRET`
in Netlify environment settings, with Functions scope. No model API key is used.

The build copies only the four browser assets and prepared display JSON. Local
classification caches, source-preparation scripts, tests and QA files are excluded
from the website. `.netlify/`, the generated `public/` folder, classification
refresh outputs and QA files are ignored by Git in this directory.

Push dashboard changes to `main` to redeploy. This is the frozen 9 November skills
snapshot; daily scraper updates do not automatically run AI classification or
refresh this dashboard. Prepare updated display JSON locally before committing a
later data snapshot. The hosting build performs no paid model calls.

```sh
python3 build_site.py
```

## Views

- Ranked prevalence of all 74 categories or eight ESCO skill families. Every
  percentage includes adverts with no assigned skill in its denominator.
- Research shortlist (47 categories coloured in the supplied Word document) and
  original-study selection (24 categories from the emailed Indeed prompt).
  These change the skills shown, not the advert sample.
- Explicit-only sensitivity view, alongside explicit plus strongly implied skills.
- Industry and occupation profiles at classification levels 1–4, plus a family
  matrix. Minimum group size is adjustable. Unclassified records remain visible.
- Geography starts with skill-prevalence bars for the four major regions, with
  sample sizes in parentheses. Switch to 22 provinces or the interactive map.
  The map includes a Highlands enlargement and province profiles. Small samples
  are labelled on bars and hatched on the map. Counts remain available in the table.
- Companion skills, conditional prevalence and relative frequency. Pairs require
  at least ten shared adverts. Monthly counts and skill shares use first-seen dates.
- Advert browser with full available descriptions, source quotes, motivations,
  evidence type and source-length flags. Text layout is cleaned deterministically.
- CSV downloads for the current skill table and advert selection. Cohort filters,
  hierarchy, skill selection, evidence setting and skill focus persist in the URL.

Each analytical section has its own skill/family, evidence and research-selection
controls, plus optional industry, occupation, province, employer, education and
date filters. These controls affect only that section. The main sample filters
at the top still apply across the dashboard; section filters further narrow that
sample. Skill controls do not change the denominator. Local settings persist in
the URL. “Read matching adverts” copies the selected skill into the advert browser.
The opening findings section has been removed.

## Data and reproducibility

```sh
python3 build_data.py
node --test tests/stats.test.mjs
```

`build_data.py` reads the frozen skills v1 run, the completed classification
refresh in this folder (falling back to the parent classification file when absent), the supplied ESCO Word document, and existing province boundaries.
It writes only inside this dashboard folder. It validates unique advert IDs,
input hashes, category codes and evidence quotes, and records source SHA-256 hashes
in `data/provenance.json`. No classifications are rerun.

The index (`data/dashboard.json`, about 2 MB) contains each job once. Descriptions
and evidence are split into 100-advert files and loaded on demand. The server
compresses JSON responses. The display map simplifies the existing province
geometry without using external map tiles.

The current snapshot contains:

| Measure | Count |
| --- | ---: |
| Records processed by skills run | 3,964 |
| Job adverts included | 3,955 |
| Non-job notices excluded | 9 |
| Advert/category selections | 38,447 |
| Adverts with no assigned category | 59 |
| Categories observed | 72 of 74 |
| Exact matches to usable classifications | 3,954 |
| Usable industry at level 1 | 3,208 |
| Usable occupation at level 1 | 3,902 |
| At least one named PNG province | 3,904 |
| Included adverts with unrecovered source-length caps | 49 |

On 10 November, the existing classification pipeline reused all **3,775** unchanged
responses and classified **172 new adverts and 17 with changed text**. All 3,964
records completed successfully. The original v3 prompt, schema, gpt-6-luna model
and low reasoning setting were retained. Cached records are verified unchanged,
including existing null/unclassified answers. One advert still has conflicting
job-advert flags across the skills and general-classification runs; its general
classifications are withheld. All other missing codes are unclassified answers.

The refresh and its provenance are in `classification_refresh/`. The parent
classification run and original skills outputs are preserved. To inspect or
resume the usual pipeline:

```sh
python3 refresh_classifications.py           # Preview only
python3 refresh_classifications.py --execute # Only pending/failed records call the API
python3 build_data.py
```

The wrapper seeds matching cached records once, then invokes the existing root
`classify_jobs.py`. It verifies that preparation matches the frozen skills
snapshot and that the model/prompt/schema match the earlier run. The existing API
key is read by that pipeline only during execution; no credential is copied here.
Spelling variants in ISIC/ISCO labels are consolidated by code, using the most
common supplied label at each level. No new codes are inferred by the dashboard.

Families count the union of included child categories, including .0 general
categories. At family level, any explicit child gives the advert an explicit
match; only adverts with no explicit child appear in the implied-only segment.
Adverts count once per named province and once per region. Multiple provinces
in one region do not duplicate an advert in the regional chart. PNG-wide flags are not
expanded to all provinces. Within-province skill percentages use that province's
adverts as the denominator. Province shares of the selection use the entire
selected sample, including records without a province.

These are online advert counts, not numbers of positions or a representative
measure of PNG employment. Reposts with different IDs remain separate. The skills
run's semantic QA limitations still apply. October 2025 and November 2026 are
partial first-seen months; the scraper pause on 1–19 September 2026 affects coverage.

## Files

- `index.html`, `styles.css`, `app.mjs`: local interface and ADB-inspired design.
- `stats.mjs`: shared, testable counting rules.
- `build_data.py`: deterministic preparation from the saved project files.
- `serve.py`: standard-library local server.
- `refresh_classifications.py`, `classification_refresh/`: cached classification refresh.
- `data/`: prepared index, evidence, geometry and provenance.
- `tests/`: numerical and browser checks.
- `qa/`: screenshots and validation results.

Browser QA is optional and requires Playwright (or playwright-core) and Chrome:

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright-core/index.mjs node tests/browser.mjs
```

Set `CHROME_PATH` to override the default macOS Chrome executable. Start the server
first. The browser check uses an isolated, temporary headless session.

The design takes its colours and editorial treatment from the project mood board
and `analysis/2026-11-9/overview of data2.pptx`: navy `#002569`, blue `#007DB7`, cyan
`#00B6C9`, orange `#E9532B`, lime `#8DC63F`, and Arial. It is a research dashboard,
not an official ADB publication template.

## Password gate

`netlify/edge-functions/password-gate.js` protects every path before static files
are served. Visitors enter a shared password, with no username. Successful login
sets a signed, Secure, HttpOnly, SameSite cookie for eight hours. Direct JSON and
asset requests also need that cookie. Responses disable browser and CDN caching.
The footer includes Sign out on HTTPS. Changing the password invalidates sessions
after the new deployment. Missing configuration fails closed.

Set `DASHBOARD_PASSWORD` and a random, independent `DASHBOARD_SESSION_SECRET` of at
least 32 characters in Netlify's environment settings. Both must be available to
Functions in every deploy context. Redeploy after changing them. Neither value
belongs in Git, the static publish folder or client JavaScript. The ordinary
Python server remains a local-only preview and does not execute Edge Functions.

Run the authentication checks with:

```sh
node --test tests/password-gate.test.mjs
```

# Repeated descriptions: investigation and actual Stata report

Snapshot: 15 October 2026, 13:28 UTC; 3,712 successful advert IDs. Analysis is read-only. No records were dropped, merged or rewritten. The three direct website checks were made later on 15 October; exact times are in the evidence file.

## What the 433 figure means

There are **169 groups of exactly identical entire stored descriptions**, involving **433 advert IDs**. They contain **264 surplus records** beyond one per group. There are **3,448 distinct description strings** and **3,279 records whose description occurs only once**. These are different quantities. The database has **zero duplicate job IDs**.

The equality test includes the full stored text, not just a common company introduction or sharing form. The shortest repeated description is 1,301 characters; it still has 1,215 characters before the trailing sharing controls. All but one repeated group are below the known 10,000-character cap. Near-matches with edited wording are outside this exact-match screen.

## Patterns in the repeated groups

- **116/169 groups (68.6%)** span different first-observation dates. **104** span at least 30 calendar days. The median first-observation span is **45 days**, and the largest is **301 days**. This is consistent with repeated recruitment or reposting, but does not establish why an employer re-advertised.
- **53 groups** were entirely first captured on the same date. Across all groups, **80** have at least one same-day pair; some of those groups also have later reposts. These categories therefore overlap. Startup observations can include stock already on the site.
- **166 groups** have the same raw employer name throughout; **three groups** span different employer labels/accounts.
- **266/433 repeated-text records (61.4%)** are from **K92 Mining**. PeopleConnexion contributes 58, Express Freight Management 32, and Newmont 16. The concentration means that treating every repeated description as redundant would disproportionately reduce mining adverts.

| Employer | All its adverts | Adverts belonging to repeated-text groups |
|---|---:|---:|
| K92 Mining Inc. | 428 | 266 |
| PeopleConnexion | 292 | 58 |
| Express Freight Management | 117 | 32 |
| Newmont | 176 | 16 |
| CHM & Sons Limited | 20 | 11 |
| Able Computing (PNG) Ltd | 50 | 7 |
| KTF | 15 | 6 |
| Telemu No.16 Limited | 19 | 4 |

## Examples

### 1. Same campaign on two separate source pages: Boiler Operator

WR Carpenter (PNG) Limited adverts [28894](https://www.pngworkforce.com/jobs/view/boiler-operator/28894) and [28895](https://www.pngworkforce.com/jobs/view/boiler-operator/28895) were both first captured on **15 October 2026**. Both advertise Boiler Operator, Madang, Globe division, with a 30 October 2026 closing date. Both full on-site descriptions are **3,966 characters** and exactly identical.

Both URLs returned HTTP 200 in the new live check. Their raw HTML hashes differ, but their description-container hashes are identical, and both match the saved records. The archived source HTML gives the same result. This is source-level duplication, not the scraper copying one ID twice. It is a strong candidate for one recruitment campaign, although we cannot infer the number of underlying positions or the publisher’s intent from text alone.

### 2. Repeated over seven months: K92 Maintenance Planner

| Advert ID | First captured | Latest saved advertised date |
|---|---|---|
| [26460](https://www.pngworkforce.com/jobs/view/maintenance-planner/26460) | 2026-03-15 | 31/03/2026 |
| [26461](https://www.pngworkforce.com/jobs/view/maintenance-planner/26461) | 2026-03-15 | 30/03/2026 |
| [28060](https://www.pngworkforce.com/jobs/view/maintenance-planner-site-services/28060) | 2026-08-07 | 12/08/2026 |
| [28893](https://www.pngworkforce.com/jobs/view/maintenance-planner/28893) | 2026-10-15 | 15/10/2026 |

All four stored descriptions are exactly the same **5,056-character** text. The March pair was captured together, with later copies first captured in August and October. That is a mixture of same-period duplication and later repeated recruitment. The October page returned HTTP 200 and matches the stored text; HTML for the three older IDs is not in the preserved archive, so their evidence is the stored descriptions.

Notice that the latest advertised dates can be later than the first observation: the site can refresh or edit its displayed date. Use first-observation dates to describe collection timing; do not interpret the current displayed date as an unchanging original publication date.

### 3. Largest group: ten K92 fitter adverts over 301 days

The identical **4,167-character** heavy-equipment-fitter text occurs under ten IDs, from 31 October 2025 through 28 August 2026, on nine different first-observation dates:

| Advert ID | Saved title | First captured |
|---|---|---|
| [24646](https://www.pngworkforce.com/jobs/view/technician-fitter-hef/24646) | Technician | 2025-10-31 |
| [25864](https://www.pngworkforce.com/jobs/view/technician-fitter-hef-/25864) | Technician | 2026-02-01 |
| [26283](https://www.pngworkforce.com/jobs/view/technician-fitter-hef-/26283) | Technician | 2026-02-28 |
| [26445](https://www.pngworkforce.com/jobs/view/technician-fitter-hef-/26445) | Technician | 2026-03-13 |
| [26444](https://www.pngworkforce.com/jobs/view/technician-fitter-hef-/26444) | Technician | 2026-03-13 |
| [26613](https://www.pngworkforce.com/jobs/view/technician-heavy-equipment-fitter-underground-/26613) | Technician | 2026-03-28 |
| [27421](https://www.pngworkforce.com/jobs/view/technician-heavy-vehicle-fitter/27421) | Technician | 2026-06-16 |
| [28140](https://www.pngworkforce.com/jobs/view/heavy-vehicle-fitter/28140) | Heavy Vehicle Fitter | 2026-08-14 |
| [28240](https://www.pngworkforce.com/jobs/view/technician-hef-ug-/28240) | Technician | 2026-08-23 |
| [28311](https://www.pngworkforce.com/jobs/view/technician-heavy-equipment-fitter-underground-/28311) | Technician | 2026-08-28 |

This is not merely a matching company introduction: the substantive duties and qualifications also match. The old archived HTML for 24646 confirms the full title **Technician - Fitter (HEF)** and exactly matches its stored description. The saved title is only “Technician” because of the known title-cutting bug. Other IDs have different fitter-related URL slugs or saved titles. The data support reuse of the same role specification over time, not a conclusion that ten independently advertised vacancies are the same underlying position.

### 4. Same advert under different organization accounts

**Marine Livelihoods Officer:** [28715](https://www.pngworkforce.com/jobs/view/marine-livelihoods-officer/28715) was first captured on **30 September 2026** under Tree Kangaroo Conservation Program; [28730](https://www.pngworkforce.com/jobs/view/marine-livelihoods-officer/28730) was first captured on **1 October** under Wildlife Conservation Papua New Guinea (WCS PNG). The descriptions are exactly the same **6,157-character** WCS role specification. Archived HTML confirms both the identical full descriptions and the different organization labels. This is consistent with cross-posting or use of another organization’s account; it is not explained by identical scraper IDs.

The other two cross-employer groups are [25376](https://www.pngworkforce.com/jobs/view/assistant-lecturer-accounting/25376) / [25747](https://www.pngworkforce.com/jobs/view/assistant-lecturer-accounting/25747) (IBSUniversity versus IBS University, Assistant/Lecturer - Accounting) and [25420](https://www.pngworkforce.com/jobs/view/secondary-school-teacher/25420) / [25443](https://www.pngworkforce.com/jobs/view/secondary-school-teacher/25443) (KTF versus SDP-KTF, Secondary School Teacher). These illustrate employer naming/account differences. Historical HTML for those four IDs is unavailable here; their matching stored text is the evidence. Requiring an exact employer string would miss these cases.

### 5. One group needs extra caution because of truncation

Principal, Balimo College School of Nursing: [24967](https://www.pngworkforce.com/jobs/view/principal-balimo-college-school-of-nursing/24967) (first captured **31 October 2025**) and [25328](https://www.pngworkforce.com/jobs/view/principal-balimo-college-school-of-nursing/25328) (**3 December 2025**) have the same **10,000-character stored prefix**. The archived original for 24967 has **13,916 characters** of description; no preserved source for 25328 is available. Their missing tails could differ, so equality of the complete source descriptions is unproven. This affects **one group / two records**, not the bulk of the repeated-text result.

## Actual Stata output

The installed Stata 13.1 was executed in batch mode. Its counts agree with an independent Python grouping. Since descriptions are long strings, `description_key` is a SHA-256 digest of the **entire original Unicode string**, generated before export. Every hash group was checked for exact source-string equality; the Stata 14+ full-text review file was also round-tripped and rehashed. No 2,045-character conversion or prefix comparison was used.

```stata
. duplicates report description_key

   copies | observations       surplus
----------+---------------------------
        1 |         3279             0
        2 |          236           118
        3 |           93            62
        4 |           36            27
        5 |           25            20
        6 |           24            20
        9 |            9             8
       10 |           10             9
```

“Copies = 2, observations = 236” means **118 pairs**, not 236 pairs. The surplus column sums to **264**, so keeping one row per exact description would leave **3,448 records**. The 433 count includes every member of a repeated group; it is not the number of rows to discard.

| Duplicate key | Repeated groups | Records in those groups | Surplus |
|---|---:|---:|---:|
| Job ID | 0 | 0 | 0 |
| Description | 169 | 433 | 264 |
| Employer + description | 166 | 427 | 261 |
| Employer + title + description | 164 | 406 | 242 |
| Employer + title + advertised date + description | 49 | 102 | 53 |

The strict last definition finds **49 groups / 102 records / 53 surplus**. This is a useful candidate screen, not 53 confirmed redundant vacancies: displayed dates are mutable, titles have known truncation, and one recruitment campaign can cover multiple positions. Normalizing the advertised dates to ISO format gives the same counts in this snapshot.

## Using the saved review in Stata

```stata
use "reports/2026-10-15/duplicates/duplicates_tagged.dta", clear
duplicates report job_id
duplicates report description_key
duplicates report employer_key title_key posted_day description_key
count if dup_description > 0  // 433: every member of repeated groups
count if !first_text         // 264: surplus beyond one per text
sort repeat_group first_day job_id
list repeat_group job_id employer title first_day if dup_description > 0, sepby(repeat_group)
```

`dup_description` equals the group size minus one on **every** member of the group. Dropping all tagged observations would remove all copies, including the representative row. The review performs no drops. `first_text` simply marks the earliest first-observed row in each exact-text group; it is a bookkeeping marker, not a validated choice of which vacancy to keep.

- [duplicates_review.do](duplicates_review.do): rerunnable reports, tags, examples and assertions. Run from the repository root, or pass its absolute path as the first argument.
- [duplicates_stata.log](duplicates_stata.log): actual successful Stata output.
- [duplicates_tagged.dta](duplicates_tagged.dta): all 3,712 records with tags and metadata, readable by installed Stata 13. Display labels use ASCII escapes for non-ASCII characters; matching keys always use original text. This compatibility file does not include the full descriptions.
- [duplicate_review.dta](duplicate_review.dta): all 3,712 records with full Unicode descriptions (`strL`), for Stata 14+.
- [GROUP_INDEX.md](GROUP_INDEX.md): human-readable index of all 169 repeated-text groups.
- [groups.json](groups.json): complete group memberships, dates and source URLs.
- [live-source-check.json](live-source-check.json) and [archived-source-check.json](archived-source-check.json): source validation evidence.

## How I would handle this in analysis

Keep the original **3,712 advert-ID records** and add these flags to a derived analysis dataset. They are a valid count of collected adverts, not a deduplicated count of unique positions. Review same-campaign pairs and overlapping postings first; distinguish those from later re-advertising.

For industry or occupation shares, report a sensitivity using one record per exact employer-description specification alongside the advert-level result, with the changed unit clearly labelled. A blind year-wide text deduplication would reduce K92 from **428 adverts to 258 text specifications**, while PeopleConnexion falls from 292 to 261. That could materially change sector shares simply because employers differ in how they reuse wording. The **3,448 distinct descriptions are not an established estimate of unique vacancies**.

The current monthly chart remains a count of newly captured IDs. A deduplicated recruitment-episode series would be a separate derived result requiring an explicit episode definition and review, not a silent correction to those totals.

Source SHA-256: `7b0b330f6d999c29de5ddf3d6ce57e46e138944b5c871bb9d2f5c4f6314d5285`. Counts and original files were unchanged by this work.

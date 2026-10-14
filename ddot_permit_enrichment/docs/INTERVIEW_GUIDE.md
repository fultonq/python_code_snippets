# Interview Guide — DDOT CS-12 Data Scientist Skill Test

Interview questions grounded in the Public Space Occupancy Permit enrichment application. Use these for hiring panels or candidate self-prep.

Suggested scoring per question: **1** incomplete · **2** partial · **3** solid · **4** strong · **5** expert (trade-offs + DDOT context).

---

## Section A — Problem understanding (business context)

### A1. Why does FHWA functional class matter for public-space permits?
**Look for:** Functional class drives allowable time-of-day work windows; higher-class roads typically need stricter off-peak / night constraints to protect mobility and safety.

**Strong answer:** Associate Director needs both location-level class (for each occupied roadway) and the highest class on a multi-location permit (governing the most restrictive work window for the application as a whole).

### A2. Why one row per location instead of one row per permit?
**Look for:** Permits can span multiple roadways/addresses; collapsing early loses the ability to inspect each site’s class while still rolling up a permit-level maximum.

### A3. Which filters did the AD request, and how did you operationalize them without a data dictionary?
**Look for:**

- Date: application **or** issue ≥ 2026-01-01
- Types: Construction Staging Area; Mobile Crane Work Zone
- Utilities: DC Water, PEPCO, Washington Gas
- Method: explore REST fields / distinct values / name variants (`DCWater/CIP`, `Potomac Electric Power Company`, `Wash Gas & Light Co.`)

---

## Section B — Data engineering & GIS

### B1. Walk through your enrichment architecture.
**Expected flow:**

1. Query Occupancy Permits layer 24 with server-side filters  
2. LRS `getPointOnSubBlock` for nearest roadway  
3. Exclude alleys  
4. Join SubBlock `FHWAFUNCTIONALCLASS` by `SubBlockKey`  
5. Aggregate highest class by `TrackingNumber`  
6. Emit CSV

### B2. LRS vs MAR + SubBlock — when would you choose each?
**Look for:**

- **LRS:** best when you have reliable XY; returns nearest roadway measure/offset and keys in one call  
- **MAR:** useful when starting from addresses / needing authoritative address-level SubBlockKey  
- Hybrid: LRS primary, MAR fallback for geocode misses

### B3. Why filter alleys?
**Look for:** LRS includes alleys; alleys lack FHWA functional class and produce blank enrichment. Filtering avoids false nulls that look like data defects.

### B4. What does “highest functional class” mean numerically?
**Look for:** FHWA codes 1–7 where **1 (Interstate) is highest significance**. Highest class = **minimum** code among a permit’s locations—not the maximum integer.

### B5. How did you handle ArcGIS date filtering quirks?
**Look for:** REST returns epoch ms, but where-clause numeric comparisons failed; `DATE '2026-01-01'` (or timestamp literal) worked.

---

## Section C — Code & software practice

### C1. Why use `pathlib` and avoid hard-coded separators?
**Look for:** Windows 11 deliverable requirement; `Path` keeps joins portable across `C:\...` and `/...`.

### C2. How do you make a long LRS run resumable and polite to the service?
**Look for:** coordinate cache (`lrs_cache.csv`), retries/backoff, bounded worker pool, optional `MAX_FEATURES` for dry runs, periodic cache flush.

### C3. Why group on `TrackingNumber` rather than `PermitNumber`?
**Look for:** Many in-process applications have null `PermitNumber` until issuance; `TrackingNumber` remains stable across locations.

### C4. What would you put in unit tests for this script?
**Look for:**

- Utility classifier fixtures for name variants  
- Highest-class aggregation edge cases (nulls, single location, mixed classes)  
- Alley exclusion logic  
- Recorded JSON fixtures for LRS / permit pages (no live network in CI)

### C5. Dependencies are minimal (`requests` only). Why?
**Look for:** Easier Windows setup for reviewers; stdlib `csv` is enough; reduce install friction for the zip submission.

---

## Section D — Data quality & edge cases

### D1. A permit location returns only an alley match. What do you output?
**Look for:** `LRSStatus=alley_only` (or equivalent), blank FHWA, still keep the row so AD can see the gap; optionally retry with larger radius / MAR.

### D2. Coordinates are missing or zero. How do you handle it?
**Look for:** Fall back to returned geometry; if still missing, mark `missing_coordinates`, do not call LRS, leave FHWA blank.

### D3. Two locations on the same permit are FHWA 3 and 7. What is the highest class?
**Answer:** **3** (Principal Arterial - Other).

### D4. How would you QA the CSV before sending to the Associate Director?
**Look for:**

- Counts by utility / permit type / ward  
- % FHWA matched  
- Spot-check map of unmatched points  
- Confirm multi-location permits show consistent `HighestFHWAFunctionalClass`  
- Compare a sample against known arterials (e.g., major avenues)

---

## Section E — Product / stakeholder communication

### E1. The AD asks for “all individual permit locations.” What clarifying questions would you ask in a real intake?
**Examples:** Preferred key fields; include pending vs issued only; utility matching rules; whether alleys should be dropped or flagged; delivery SLA / refresh cadence.

### E2. Explain your CSV to a non-GIS director in 60 seconds.
**Look for:** Plain language: each row is a worksite; columns show which utility, which road class is next to that worksite, and the most important road class touched by the whole permit (drives work-hour rules).

### E3. Partial delivery under time pressure — what ships first?
**Look for:** Working filtered extract + documented enrichment plan beats silence; cache/test-mode outputs; narrative of remaining MAR fallback / QA (matches the brief’s guidance).

---

## Section F — Live technical prompts (whiteboard / pair)

### F1. Write the SQL/where logic for the three business filters.
Evaluate correctness of date OR logic, exact type list, and utility LIKE coverage.

### F2. Given this LRS JSON snippet, extract the fields needed for FHWA join.
Candidate should pull `subBlockKey`, ignore alley `routeType`, and not mistake DC `functionalClassCode` for FHWA.

### F3. Pseudocode the highest-class rollup.
Expect a map/reduce keyed by permit id with `min(code)` ignoring nulls.

### F4. Estimate runtime for ~5,000 locations at 8 parallel LRS workers averaging 0.4s each.
Rough math: 5000/8 × 0.4 ≈ **250 seconds** plus SubBlock batch lookups — discuss caching impact on re-runs.

---

## Section G — Behavioral / role fit for DDOT Analytics

### G1. Describe a time you delivered analysis without a complete data dictionary.
Map to this project’s REST exploration approach.

### G2. How do you balance speed vs. correctness for an executive data request?
Look for phased delivery, explicit assumptions, QA metrics, and clear caveats on unmatched rows.

### G3. How would you productionize this for weekly refresh?
Scheduler, incremental dates, cache invalidation, monitoring of match rate, automated QA email to Public Space AD.

---

## Candidate scorecard (panel use)

| Area | Weight | Notes |
|---|---|---|
| Business framing (work windows / AD needs) | 15% | |
| GIS enrichment correctness (LRS, alleys, FHWA) | 25% | |
| Data wrangling (filters, variants, grain) | 20% | |
| Engineering quality (paths, cache, errors) | 20% | |
| Communication / QA mindset | 20% | |

**Hire signal:** Candidate correctly distinguishes DC vs FHWA class, excludes alleys, and explains why highest class uses the minimum FHWA code for multi-location permits.

---

## Quick reference — application facts

| Item | Value |
|---|---|
| Permit layer | DDOT_TOPS MapServer /24 |
| Enrichment | LRS getPointOnSubBlock → SubBlock /162 |
| Output grain | One CSV row per location |
| Permit rollup key | TrackingNumber |
| FHWA range | 1–7 |
| Highest class | min(FHWA) |
| Script | `enrich_permits.py` |
| Output | `output/enriched_permits_2026.csv` |

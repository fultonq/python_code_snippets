# Development Log — DDOT CS-12 Permit Enrichment

Complete record of steps taken while building this application from the Public Space Division data request.

## 1. Problem framing

**Requestor:** Associate Director, Public Space Division (via Analytics, Assets, and Performance Branch)  
**Goal:** Enrich CY2026 occupancy permits with FHWA functional class so time-of-day work rules can be evaluated by roadway class.

**Required outputs:**

1. Python scripts + supporting files
2. CSV with one row per permit location, location FHWA class, and highest FHWA class per permit
3. README with run instructions
4. Self-contained zip (`FirstName_MiddleInitial_LastName_Python.zip`)
5. Windows 11 path-safe script

## 2. Source material review

Reviewed the skill-test brief and extracted hard requirements:

| Requirement | Interpretation used in code |
|---|---|
| Applications or issued permits ≥ 2026-01-01 | `ApplicationDate >= DATE '2026-01-01' OR IssueDate >= DATE '2026-01-01'` |
| Permit types | Exact `EventTypeDescription` values: `Construction Staging Area`, `Mobile Crane Work Zone` |
| Utilities | DC Water, PEPCO, Washington Gas (name variants discovered in live data) |
| One row per location | Occupancy layer already stores multiple locations per TrackingNumber |
| Highest functional class per permit | Minimum FHWA code (1 most significant … 7 local) grouped by TrackingNumber |
| Avoid blank alley results | Skip LRS matches where `routeType == Alley`; SubBlock lookup excludes `ROADTYPE = '4'` |

## 3. API / schema exploration (no data dictionary)

### 3.1 Occupancy Permits layer

Endpoint: `DDOT_TOPS/MapServer/24`

Steps:

1. Pulled layer metadata (`?f=pjson`) and listed all fields.
2. Confirmed geometry is point (`esriGeometryPoint`), Web Mercator source with Lon/Lat attributes.
3. Identified key business fields:
   - Dates: `ApplicationDate`, `IssueDate` (epoch milliseconds over REST)
   - Type: `EventTypeDescription`
   - Parties: `ApplicantCompany`, `OwnerName`, `PermitteeName`
   - Location grain: `LocationID`, `WorkLocationFullAddress`, `TrackingNumber`, `PermitNumber`
4. Queried distinct `EventTypeDescription` values (27 types) and confirmed exact staging/crane labels.
5. Tested date filter syntax. Numeric epoch predicates failed; ArcGIS SQL `DATE '2026-01-01'` succeeded.

### 3.2 Utility name discovery

Initial exact searches for `"DC Water"`, `"PEPCO"`, `"Washington Gas"` in `ApplicantCompany` returned zero or incomplete matches.

Follow-up exploration found real name variants:

| Utility | Observed spellings |
|---|---|
| DC Water | `DCWater/CIP`, `DCWater/OPS`, `DC Water` |
| PEPCO | `Potomac Electric Power Company`, `Pepco`, `Pepco holdings inc` |
| Washington Gas | `Wash Gas & Light Co.`, `Washington Gas` |

Decision: classify utility with case-insensitive LIKE patterns across company/owner/permittee fields.

### 3.3 LRS enrichment tool

Endpoint: `.../DdotLrsExtensions/getPointOnSubBlock`

Discovery sequence:

1. Missing params returned actionable validation errors.
2. Required parameters identified: `x`, `y`, `inSR`, `outSR`, `searchRadius` (0–200 meters).
3. Successful calls return `pointOnSubBlocks[]` with `subBlockKey`, `routeType`, and roadway attributes.
4. LRS `functionalClassCode` aligns with **DC** functional class, not FHWA.
5. `routeType` includes `Alley`; alleys must be filtered out.

### 3.4 Roadway SubBlock (FHWA)

Endpoint: `Transportation_WebMercator/MapServer/162`

- Field `FHWAFUNCTIONALCLASS` contains integers 1–7.
- Field `ROADTYPE` coded values include `4` = Alley.
- Joining LRS `subBlockKey` → SubBlock `SUBBLOCKKEY` yields authoritative FHWA class.

Validation example (Scott Circle NW):

- LRS DC class code: `14` (Principal Arterial)
- SubBlock FHWA class: `3` (Principal Arterial - Other)

## 4. Design decisions

1. **LRS first, SubBlock for FHWA** — matches the brief’s primary enrichment path and corrects for LRS returning DC class rather than FHWA.
2. **TrackingNumber as permit key** — many 2026 applications have null `PermitNumber` until issuance.
3. **Coordinate cache** (`output/lrs_cache.csv`) — LRS is per-point and rate-sensitive; cache enables resume and re-runs.
4. **Thread pool** (`LRS_WORKERS=8`) — balances throughput vs. service politeness.
5. **pathlib paths** — Windows-safe defaults; no hard-coded `/` or `\`.
6. **Stdlib CSV** — avoids pandas dependency for easier Windows setup.

## 5. Implementation sequence

1. Created project folder `ddot_permit_enrichment/`.
2. Added `requirements.txt` (`requests`).
3. Implemented `enrich_permits.py` modules:
   - configuration
   - permit query + pagination
   - utility classification
   - LRS nearest-road enrichment with alley exclusion
   - SubBlock FHWA batch lookup
   - highest-class rollup
   - CSV + logging
4. Wrote `README.md` with run/config guidance.
5. Documented development and interview materials under `docs/`.
6. Executed test run with `MAX_FEATURES`, then full enrichment run.
7. Verified CSV schema and sample rows.
8. Packaged repository for PR / zip submission.

## 6. Pipeline flowchart

```text
Occupancy Permits (Layer 24)
        │
        │  date + type + utility filters
        ▼
Permit location rows (TrackingNumber × LocationID)
        │
        │  lon/lat → getPointOnSubBlock
        ▼
Nearest non-alley SubBlockKey (+ route diagnostics)
        │
        │  SUBBLOCKKEY lookup on Layer 162
        ▼
FHWAFunctionalClass at location
        │
        │  min(FHWA) by TrackingNumber
        ▼
CSV: location class + highest class per permit
```

## 7. Issues encountered and resolutions

| Issue | Resolution |
|---|---|
| No data dictionary | Explored live REST metadata and sample features |
| Epoch date SQL errors | Switched to `DATE '2026-01-01'` |
| Utility names inconsistent | Broad LIKE patterns + explicit `Utility` classifier |
| LRS returns DC class, not FHWA | Secondary SubBlock FHWA lookup by key |
| Alleys lack FHWA | Filter alley route types / ROADTYPE 4 |
| `routeType=All` rejected by LRS | Omit `routeType` (default candidates) and rank Street/Service/Ramp client-side |
| Long LRS runtime | Cache + workers + optional `MAX_FEATURES` |
| Null PermitNumber on applications | Group/report on TrackingNumber |

## 8. Validation checklist

- [x] Layer field discovery completed
- [x] Filters produce non-zero utility staging/crane records for 2026
- [x] LRS call succeeds with documented parameters
- [x] SubBlock FHWA lookup succeeds for matched keys
- [x] CSV contains location-level and permit-level FHWA columns
- [x] README documents Windows run steps
- [x] Script uses pathlib for cross-platform paths

## 9. Future improvements (if more time)

- Add MAR address → SubBlockKey fallback for points that miss LRS.
- Write unit tests with recorded JSON fixtures (offline CI).
- Add a small summary report (counts by utility / FHWA / ward).
- Expose CLI flags (`--max-features`, `--workers`) instead of in-file config.
- Spatial QA map of unmatched points.

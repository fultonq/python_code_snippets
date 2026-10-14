# DDOT Public Space Occupancy Permit Enrichment

Python enrichment tool for the Washington, DC DDOT Analytics, Assets, and Performance Branch skill assessment (CS-12 Data Scientist).

It filters calendar-year **2026** Public Space Occupancy Permits for public utilities, resolves the nearest non-alley roadway for each permit location, attaches **FHWA functional class**, and writes a CSV with:

- one row per permit application **location**
- FHWA functional class at that location
- the **highest** FHWA functional class for the overall permit application

## Requirements

- Windows 11 (also runs on macOS / Linux)
- Python 3.10+
- Internet access to DC GIS REST services

```text
pip install -r requirements.txt
```

## Configuration

Open `enrich_permits.py` and edit the configuration block near the top if needed:

| Variable | Purpose | Default |
|---|---|---|
| `OUTPUT_CSV` | Final enriched CSV path | `output/enriched_permits_2026.csv` |
| `MAX_FEATURES` | Limit rows for testing (`None` = all) | `None` |
| `LRS_SEARCH_RADIUS_METERS` | Nearest-road search radius (0–200) | `100` |
| `LRS_WORKERS` | Parallel LRS request workers | `20` |

Paths use `pathlib.Path`, so the script is safe on Windows (`C:\...`) and Unix (`/...`).

## How to run

From the project directory:

```bat
cd ddot_permit_enrichment
python enrich_permits.py
```

On PowerShell:

```powershell
cd ddot_permit_enrichment
python .\enrich_permits.py
```

Optional quick test (edit the script first):

```python
MAX_FEATURES = 25
```

## Filters applied

1. **Date:** `ApplicationDate >= 2026-01-01` **OR** `IssueDate >= 2026-01-01`
2. **Permit types:** `Construction Staging Area`, `Mobile Crane Work Zone`
3. **Utilities:** DC Water, PEPCO, Washington Gas  
   Matched against `ApplicantCompany`, `OwnerName`, and `PermitteeName` using observed name variants such as:
   - `DCWater/CIP`, `DC Water`
   - `Potomac Electric Power Company`, `Pepco`
   - `Wash Gas & Light Co.`, `Washington Gas`

## Enrichment method

**Primary approach: DDOT Linear Referencing System (LRS)**

1. Call `getPointOnSubBlock` with WGS84 coordinates.
2. Skip **Alley** matches (alleys have no FHWA class).
3. Use returned `subBlockKey` to look up `FHWAFUNCTIONALCLASS` on Roadway SubBlock (layer 162).
4. For each `TrackingNumber`, compute the highest FHWA class as the **lowest numeric code** (1 Interstate … 7 Local).

LRS responses are cached in `output/lrs_cache.csv` so interrupted runs can resume.

### Data sources

| Source | URL |
|---|---|
| Occupancy Permits | https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/24 |
| LRS getPointOnSubBlock | https://rh.dcgis.dc.gov/dcgis/rest/services/DDOT/RoadwayBlocks/MapServer/exts/DdotLrsExtensions/getPointOnSubBlock |
| Roadway SubBlock | https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Transportation_WebMercator/MapServer/162 |

## Output columns

Key columns in `output/enriched_permits_2026.csv`:

- Permit identifiers: `TrackingNumber`, `PermitNumber`, `LocationID`
- Business attributes: `EventTypeDescription`, `Utility`, company/owner fields, dates, address, ward
- Location enrichment: `NearestRouteName`, `SubBlockKey`, `FHWAFunctionalClass`, `FHWAFunctionalClassLabel`
- Permit-level rollup: `HighestFHWAFunctionalClass`, `HighestFHWAFunctionalClassLabel`
- Diagnostics: `LRSStatus`, `LRSOffsetMeters`, DC functional class fields from LRS

## Package / zip naming

For the DDOT submission package, zip this folder as:

```text
FirstName_MiddleInitial_LastName_Python.zip
```

Example:

```text
Jane_Q_Doe_Python.zip
```

## Project layout

```text
ddot_permit_enrichment/
  enrich_permits.py
  requirements.txt
  README.md
  docs/
    DEVELOPMENT_LOG.md
    INTERVIEW_GUIDE.md
  output/
    enriched_permits_2026.csv   (generated)
    lrs_cache.csv               (generated)
    enrichment.log              (generated)
```

## Notes / assumptions

- There is no official data dictionary; field meanings were inferred by exploring the live REST layer.
- `TrackingNumber` is used as the permit-application key because `PermitNumber` can be null for applications that are not yet issued.
- “Highest” FHWA class means **most significant roadway**, i.e. smallest FHWA code.
- Partial runs are supported via `MAX_FEATURES` and the LRS cache.
- A full run against the live feed during development produced **4,983** rows (DC Water / PEPCO / Washington Gas). Mobile Crane Work Zone had **0** matching utility records at that time; the filter still includes it for future data.
- Package a submission zip with:

```bat
python package_submission.py FirstName MiddleInitial LastName
```

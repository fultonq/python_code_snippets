# DDOT CS-12 Data Scientist — Public Space Permit Enrichment

Technical skill-test application for a Data Scientist (CS-12) role supporting the Washington, DC District Department of Transportation (DDOT).

## What’s in this repo

| Path | Description |
|---|---|
| `ddot_permit_enrichment/` | Self-contained enrichment tool (submit this folder as the zip) |
| `ddot_permit_enrichment/enrich_permits.py` | Main Python script |
| `ddot_permit_enrichment/README.md` | How to configure and run |
| `ddot_permit_enrichment/docs/DEVELOPMENT_LOG.md` | Complete development steps |
| `ddot_permit_enrichment/docs/INTERVIEW_GUIDE.md` | Interview questions around the application |

## Quick start

```bat
cd ddot_permit_enrichment
pip install -r requirements.txt
python enrich_permits.py
```

Output: `ddot_permit_enrichment/output/enriched_permits_2026.csv`

## Zip naming (DDOT submission)

```text
FirstName_MiddleInitial_LastName_Python.zip
```

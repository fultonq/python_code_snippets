"""
DDOT Public Space Occupancy Permit enrichment
==============================================

Enriches calendar-year 2026 Construction Staging Area and Mobile Crane Work Zone
permits for DC Water, PEPCO, and Washington Gas with FHWA functional class at
each permit location, plus the highest (most significant) FHWA class per permit.

Approach
--------
1. Query Occupancy Permits (DDOT_TOPS MapServer layer 24) with server-side filters.
2. Resolve nearest non-alley roadway via DDOT LRS getPointOnSubBlock.
3. Look up FHWAFUNCTIONALCLASS on Roadway SubBlock using SubBlockKey.
4. Compute highest FHWA class per TrackingNumber (lower numeric code = higher class).
5. Write one CSV row per permit application location.

Windows 11 compatible: all paths use pathlib.Path.
"""

from __future__ import annotations

import csv
import logging
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# Configuration — edit these before running
# ---------------------------------------------------------------------------

# Project root (script directory). Works on Windows and Linux/macOS.
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_CSV = OUTPUT_DIR / "enriched_permits_2026.csv"
CACHE_CSV = OUTPUT_DIR / "lrs_cache.csv"
LOG_FILE = OUTPUT_DIR / "enrichment.log"

# Set to an integer (e.g. 50) to limit records during testing; None = all.
MAX_FEATURES: Optional[int] = None

# LRS nearest-road search
LRS_SEARCH_RADIUS_METERS = 100  # must be 0–200
LRS_WORKERS = 8
LRS_RETRY_COUNT = 3
LRS_RETRY_SLEEP_SECONDS = 1.5

# HTTP
HTTP_TIMEOUT_SECONDS = 60
USER_AGENT = "DDOT-CS12-PermitEnrichment/1.0"

# Data sources
PERMITS_QUERY_URL = (
    "https://maps2.dcgis.dc.gov/dcgis/rest/services/"
    "DCGIS_APPS/DDOT_TOPS/MapServer/24/query"
)
LRS_URL = (
    "https://rh.dcgis.dc.gov/dcgis/rest/services/DDOT/"
    "RoadwayBlocks/MapServer/exts/DdotLrsExtensions/getPointOnSubBlock"
)
SUBBLOCK_QUERY_URL = (
    "https://maps2.dcgis.dc.gov/dcgis/rest/services/"
    "DCGIS_DATA/Transportation_WebMercator/MapServer/162/query"
)

PERMIT_TYPES = (
    "Construction Staging Area",
    "Mobile Crane Work Zone",
)

# FHWA functional class labels (1 = highest significance, 7 = local)
FHWA_LABELS = {
    1: "Interstate",
    2: "Principal Arterial - Other Freeways and Expressways",
    3: "Principal Arterial - Other",
    4: "Minor Arterial",
    5: "Major Collector",
    6: "Minor Collector",
    7: "Local",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


def get_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """GET JSON with basic retries."""
    last_error: Optional[Exception] = None
    for attempt in range(1, LRS_RETRY_COUNT + 1):
        try:
            resp = SESSION.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("error"):
                raise RuntimeError(data["error"])
            return data
        except Exception as exc:  # noqa: BLE001 - surface and retry network/API issues
            last_error = exc
            logging.warning("Request failed (%s/%s) %s: %s", attempt, LRS_RETRY_COUNT, url, exc)
            time.sleep(LRS_RETRY_SLEEP_SECONDS * attempt)
    raise RuntimeError(f"Failed after retries: {url} -> {last_error}")


# ---------------------------------------------------------------------------
# Permit query
# ---------------------------------------------------------------------------

def build_permit_where() -> str:
    """
    Server-side filter matching the Public Space AD request.

    - Application or issued date on/after 2026-01-01
    - Permit types: Construction Staging Area, Mobile Crane Work Zone
    - Public utilities: DC Water, PEPCO, Washington Gas (name variants explored in data)
    """
    type_list = ", ".join(f"'{t}'" for t in PERMIT_TYPES)
    # LIKE patterns cover observed ApplicantCompany / OwnerName / PermitteeName values.
    utility_clauses = [
        "UPPER(ApplicantCompany) LIKE '%DCWATER%'",
        "UPPER(ApplicantCompany) LIKE '%DC WATER%'",
        "UPPER(ApplicantCompany) LIKE '%PEPCO%'",
        "UPPER(ApplicantCompany) LIKE '%POTOMAC ELECTRIC%'",
        "UPPER(ApplicantCompany) LIKE '%WASH GAS%'",
        "UPPER(ApplicantCompany) LIKE '%WASHINGTON GAS%'",
        "UPPER(OwnerName) LIKE '%DCWATER%'",
        "UPPER(OwnerName) LIKE '%DC WATER%'",
        "UPPER(OwnerName) LIKE '%PEPCO%'",
        "UPPER(OwnerName) LIKE '%POTOMAC ELECTRIC%'",
        "UPPER(OwnerName) LIKE '%WASH GAS%'",
        "UPPER(OwnerName) LIKE '%WASHINGTON GAS%'",
        "UPPER(PermitteeName) LIKE '%DCWATER%'",
        "UPPER(PermitteeName) LIKE '%DC WATER%'",
        "UPPER(PermitteeName) LIKE '%PEPCO%'",
        "UPPER(PermitteeName) LIKE '%POTOMAC ELECTRIC%'",
        "UPPER(PermitteeName) LIKE '%WASH GAS%'",
        "UPPER(PermitteeName) LIKE '%WASHINGTON GAS%'",
    ]
    return (
        "(ApplicationDate >= DATE '2026-01-01' OR IssueDate >= DATE '2026-01-01') "
        f"AND EventTypeDescription IN ({type_list}) "
        f"AND ({' OR '.join(utility_clauses)})"
    )


OUT_FIELDS = [
    "OBJECTID",
    "TrackingNumber",
    "PermitNumber",
    "StatusDescription",
    "EventTypeDescription",
    "ApplicationDate",
    "IssueDate",
    "EffectiveDate",
    "ExpirationDate",
    "ApplicantCompany",
    "OwnerName",
    "PermitteeName",
    "WorkLocationFullAddress",
    "LocationID",
    "WorkLocationWard",
    "WorkLocationANC",
    "Longitude",
    "Latitude",
    "XCoord",
    "YCoord",
]


def epoch_ms_to_iso(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return str(value)


def classify_utility(row: Dict[str, Any]) -> str:
    blob = " ".join(
        str(row.get(k) or "").upper()
        for k in ("ApplicantCompany", "OwnerName", "PermitteeName")
    )
    if "WASH GAS" in blob or "WASHINGTON GAS" in blob:
        return "Washington Gas"
    if "PEPCO" in blob or "POTOMAC ELECTRIC" in blob:
        return "PEPCO"
    if "DCWATER" in blob or "DC WATER" in blob:
        return "DC Water"
    return "Unknown"


def fetch_permits() -> List[Dict[str, Any]]:
    where = build_permit_where()
    logging.info("Permit where clause:\n%s", where)

    count_data = get_json(
        PERMITS_QUERY_URL,
        {"where": where, "returnCountOnly": "true", "f": "json"},
    )
    total = int(count_data.get("count", 0))
    logging.info("Server matched %s permit location features", total)

    features: List[Dict[str, Any]] = []
    offset = 0
    page_size = 1000
    while True:
        if MAX_FEATURES is not None and len(features) >= MAX_FEATURES:
            break
        params = {
            "where": where,
            "outFields": ",".join(OUT_FIELDS),
            "returnGeometry": "true",
            "outSR": 4326,
            "orderByFields": "TrackingNumber ASC, LocationID ASC, OBJECTID ASC",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "f": "json",
        }
        page = get_json(PERMITS_QUERY_URL, params)
        batch = page.get("features") or []
        if not batch:
            break
        for feat in batch:
            attrs = dict(feat.get("attributes") or {})
            geom = feat.get("geometry") or {}
            # Prefer explicit lon/lat fields; fall back to returned geometry (outSR=4326).
            lon = attrs.get("Longitude")
            lat = attrs.get("Latitude")
            if lon in (None, 0, 0.0) or lat in (None, 0, 0.0):
                lon = geom.get("x")
                lat = geom.get("y")
            attrs["_lon"] = lon
            attrs["_lat"] = lat
            attrs["Utility"] = classify_utility(attrs)
            attrs["ApplicationDateISO"] = epoch_ms_to_iso(attrs.get("ApplicationDate"))
            attrs["IssueDateISO"] = epoch_ms_to_iso(attrs.get("IssueDate"))
            attrs["EffectiveDateISO"] = epoch_ms_to_iso(attrs.get("EffectiveDate"))
            attrs["ExpirationDateISO"] = epoch_ms_to_iso(attrs.get("ExpirationDate"))
            features.append(attrs)
            if MAX_FEATURES is not None and len(features) >= MAX_FEATURES:
                break
        logging.info("Fetched %s / %s features", len(features), total)
        if not page.get("exceededTransferLimit"):
            break
        offset += len(batch)

    if MAX_FEATURES is not None:
        features = features[:MAX_FEATURES]
        logging.info("Truncated to MAX_FEATURES=%s", MAX_FEATURES)
    return features


# ---------------------------------------------------------------------------
# LRS enrichment
# ---------------------------------------------------------------------------

def _coord_key(lon: Any, lat: Any) -> Optional[Tuple[float, float]]:
    try:
        if lon is None or lat is None:
            return None
        # Round to ~1 meter precision to improve cache hits.
        return (round(float(lon), 6), round(float(lat), 6))
    except (TypeError, ValueError):
        return None


def _parse_lrs_match(match: Dict[str, Any], status: str = "matched") -> Dict[str, Any]:
    other = (
        ((match.get("roadData") or {}).get("roadwayAttributes") or {}).get("other") or {}
    )
    return {
        "subblock_key": match.get("subBlockKey") or "",
        "route_name": match.get("routeName") or "",
        "route_type": match.get("routeType") or "",
        "offset_meters": match.get("offsetInMeters"),
        "dc_functional_class_code": other.get("functionalClassCode"),
        "dc_functional_class": other.get("functionalClass"),
        "lrs_status": status,
    }


def query_lrs(lon: float, lat: float) -> Dict[str, Any]:
    """
    Return nearest non-alley roadway match from LRS.

    Omit routeType so the service returns nearby candidates (default behavior).
    Explicit routeType=\"All\" is rejected by the API. Prefer Street, then Service,
    then Ramp. Skip Alley / Driveway / Trail (no usable FHWA class).
    """
    empty = {
        "subblock_key": "",
        "route_name": "",
        "route_type": "",
        "offset_meters": None,
        "dc_functional_class_code": None,
        "dc_functional_class": None,
        "lrs_status": "no_match",
    }
    params = {
        "x": lon,
        "y": lat,
        "inSR": 4326,
        "outSR": 4326,
        "searchRadius": LRS_SEARCH_RADIUS_METERS,
        "returnNearestMatchOnly": "false",
        "f": "json",
    }
    data = get_json(LRS_URL, params)
    matches = data.get("pointOnSubBlocks") or []
    if not matches:
        return empty

    rank = {"street": 0, "service": 1, "ramp": 2}
    usable = []
    for match in matches:
        route_type = str(match.get("routeType") or "").lower()
        if route_type in {"alley", "driveway", "trail"}:
            continue
        if route_type not in rank:
            continue
        offset = match.get("offsetInMeters")
        try:
            offset_val = float(offset) if offset is not None else 9999.0
        except (TypeError, ValueError):
            offset_val = 9999.0
        usable.append((rank[route_type], offset_val, match))

    if usable:
        usable.sort(key=lambda item: (item[0], item[1]))
        best = usable[0][2]
        return _parse_lrs_match(best, status="matched")

    # Only non-FHWA road types nearby.
    result = _parse_lrs_match(matches[0], status="alley_only")
    result["subblock_key"] = ""
    result["dc_functional_class_code"] = None
    result["dc_functional_class"] = None
    return result


def load_lrs_cache() -> Dict[Tuple[float, float], Dict[str, Any]]:
    cache: Dict[Tuple[float, float], Dict[str, Any]] = {}
    if not CACHE_CSV.exists():
        return cache
    with CACHE_CSV.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                key = (float(row["lon"]), float(row["lat"]))
            except (KeyError, TypeError, ValueError):
                continue
            cache[key] = {
                "subblock_key": row.get("subblock_key") or "",
                "route_name": row.get("route_name") or "",
                "route_type": row.get("route_type") or "",
                "offset_meters": row.get("offset_meters") or None,
                "dc_functional_class_code": row.get("dc_functional_class_code") or None,
                "dc_functional_class": row.get("dc_functional_class") or None,
                "lrs_status": row.get("lrs_status") or "",
            }
    logging.info("Loaded %s LRS cache entries from %s", len(cache), CACHE_CSV)
    return cache


def save_lrs_cache(cache: Dict[Tuple[float, float], Dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "lon",
        "lat",
        "subblock_key",
        "route_name",
        "route_type",
        "offset_meters",
        "dc_functional_class_code",
        "dc_functional_class",
        "lrs_status",
    ]
    with CACHE_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for (lon, lat), value in sorted(cache.items()):
            row = {"lon": lon, "lat": lat, **value}
            writer.writerow(row)


def enrich_with_lrs(features: List[Dict[str, Any]]) -> None:
    cache = load_lrs_cache()
    needed: Dict[Tuple[float, float], None] = {}
    missing_coords = 0

    for feat in features:
        key = _coord_key(feat.get("_lon"), feat.get("_lat"))
        if key is None:
            missing_coords += 1
            continue
        if key not in cache:
            needed[key] = None

    logging.info(
        "Unique coordinates needing LRS: %s (missing coords on %s rows)",
        len(needed),
        missing_coords,
    )

    def worker(coord: Tuple[float, float]) -> Tuple[Tuple[float, float], Dict[str, Any]]:
        lon, lat = coord
        try:
            return coord, query_lrs(lon, lat)
        except Exception as exc:  # noqa: BLE001
            logging.error("LRS failed for %s,%s: %s", lon, lat, exc)
            return coord, {
                "subblock_key": "",
                "route_name": "",
                "route_type": "",
                "offset_meters": None,
                "dc_functional_class_code": None,
                "dc_functional_class": None,
                "lrs_status": f"error:{exc}",
            }

    completed = 0
    with ThreadPoolExecutor(max_workers=LRS_WORKERS) as pool:
        futures = [pool.submit(worker, coord) for coord in needed]
        for fut in as_completed(futures):
            coord, result = fut.result()
            cache[coord] = result
            completed += 1
            if completed % 50 == 0 or completed == len(futures):
                logging.info("LRS progress: %s / %s", completed, len(futures))
                # Persist periodically so long runs are resumable.
                save_lrs_cache(cache)

    save_lrs_cache(cache)

    for feat in features:
        key = _coord_key(feat.get("_lon"), feat.get("_lat"))
        if key is None:
            feat.update(
                {
                    "SubBlockKey": "",
                    "NearestRouteName": "",
                    "NearestRouteType": "",
                    "LRSOffsetMeters": "",
                    "DCFunctionalClassCode": "",
                    "DCFunctionalClass": "",
                    "LRSStatus": "missing_coordinates",
                }
            )
            continue
        hit = cache.get(key) or {}
        feat["SubBlockKey"] = hit.get("subblock_key") or ""
        feat["NearestRouteName"] = hit.get("route_name") or ""
        feat["NearestRouteType"] = hit.get("route_type") or ""
        feat["LRSOffsetMeters"] = hit.get("offset_meters")
        feat["DCFunctionalClassCode"] = hit.get("dc_functional_class_code")
        feat["DCFunctionalClass"] = hit.get("dc_functional_class")
        feat["LRSStatus"] = hit.get("lrs_status") or ""


# ---------------------------------------------------------------------------
# SubBlock FHWA lookup
# ---------------------------------------------------------------------------

def chunked(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def fetch_fhwa_by_subblock_keys(keys: List[str]) -> Dict[str, Dict[str, Any]]:
    unique = sorted({k for k in keys if k})
    logging.info("Looking up FHWA for %s SubBlockKey values", len(unique))
    results: Dict[str, Dict[str, Any]] = {}

    for batch in chunked(unique, 40):
        # Escape single quotes for SQL
        quoted = ",".join("'" + k.replace("'", "''") + "'" for k in batch)
        where = f"SUBBLOCKKEY IN ({quoted}) AND ROADTYPE <> '4'"
        params = {
            "where": where,
            "outFields": "SUBBLOCKKEY,ROUTENAME,ROADTYPE,FHWAFUNCTIONALCLASS,DCFUNCTIONALCLASS",
            "returnGeometry": "false",
            "f": "json",
        }
        data = get_json(SUBBLOCK_QUERY_URL, params)
        for feat in data.get("features") or []:
            attrs = feat.get("attributes") or {}
            key = attrs.get("SUBBLOCKKEY")
            if key:
                results[key] = attrs
    return results


def attach_fhwa(features: List[Dict[str, Any]]) -> None:
    keys = [str(f.get("SubBlockKey") or "") for f in features]
    lookup = fetch_fhwa_by_subblock_keys(keys)
    for feat in features:
        key = str(feat.get("SubBlockKey") or "")
        hit = lookup.get(key)
        if not hit:
            feat["FHWAFunctionalClass"] = None
            feat["FHWAFunctionalClassLabel"] = ""
            feat["SubBlockRouteName"] = ""
            feat["SubBlockRoadType"] = ""
            continue
        code = hit.get("FHWAFUNCTIONALCLASS")
        try:
            code_int = int(code) if code is not None else None
        except (TypeError, ValueError):
            code_int = None
        feat["FHWAFunctionalClass"] = code_int
        feat["FHWAFunctionalClassLabel"] = FHWA_LABELS.get(code_int, "") if code_int else ""
        feat["SubBlockRouteName"] = hit.get("ROUTENAME") or ""
        feat["SubBlockRoadType"] = hit.get("ROADTYPE") or ""


def attach_highest_per_permit(features: List[Dict[str, Any]]) -> None:
    """
    Highest functional class = lowest FHWA numeric code (1 Interstate ... 7 Local).
    Group by TrackingNumber (stable even when PermitNumber is still unassigned).
    """
    best: Dict[Any, int] = {}
    for feat in features:
        tracking = feat.get("TrackingNumber")
        code = feat.get("FHWAFunctionalClass")
        if tracking is None or code is None:
            continue
        if tracking not in best or int(code) < best[tracking]:
            best[tracking] = int(code)

    for feat in features:
        tracking = feat.get("TrackingNumber")
        highest = best.get(tracking)
        feat["HighestFHWAFunctionalClass"] = highest
        feat["HighestFHWAFunctionalClassLabel"] = (
            FHWA_LABELS.get(highest, "") if highest is not None else ""
        )


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "TrackingNumber",
    "PermitNumber",
    "LocationID",
    "StatusDescription",
    "EventTypeDescription",
    "Utility",
    "ApplicantCompany",
    "OwnerName",
    "PermitteeName",
    "ApplicationDate",
    "IssueDate",
    "EffectiveDate",
    "ExpirationDate",
    "WorkLocationFullAddress",
    "WorkLocationWard",
    "WorkLocationANC",
    "Longitude",
    "Latitude",
    "NearestRouteName",
    "NearestRouteType",
    "SubBlockKey",
    "LRSOffsetMeters",
    "LRSStatus",
    "FHWAFunctionalClass",
    "FHWAFunctionalClassLabel",
    "HighestFHWAFunctionalClass",
    "HighestFHWAFunctionalClassLabel",
    "DCFunctionalClassCode",
    "DCFunctionalClass",
]


def write_csv(features: List[Dict[str, Any]]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for feat in features:
            row = {
                "TrackingNumber": feat.get("TrackingNumber"),
                "PermitNumber": feat.get("PermitNumber"),
                "LocationID": feat.get("LocationID"),
                "StatusDescription": feat.get("StatusDescription"),
                "EventTypeDescription": feat.get("EventTypeDescription"),
                "Utility": feat.get("Utility"),
                "ApplicantCompany": feat.get("ApplicantCompany"),
                "OwnerName": feat.get("OwnerName"),
                "PermitteeName": feat.get("PermitteeName"),
                "ApplicationDate": feat.get("ApplicationDateISO"),
                "IssueDate": feat.get("IssueDateISO"),
                "EffectiveDate": feat.get("EffectiveDateISO"),
                "ExpirationDate": feat.get("ExpirationDateISO"),
                "WorkLocationFullAddress": feat.get("WorkLocationFullAddress"),
                "WorkLocationWard": feat.get("WorkLocationWard"),
                "WorkLocationANC": feat.get("WorkLocationANC"),
                "Longitude": feat.get("_lon"),
                "Latitude": feat.get("_lat"),
                "NearestRouteName": feat.get("NearestRouteName"),
                "NearestRouteType": feat.get("NearestRouteType"),
                "SubBlockKey": feat.get("SubBlockKey"),
                "LRSOffsetMeters": feat.get("LRSOffsetMeters"),
                "LRSStatus": feat.get("LRSStatus"),
                "FHWAFunctionalClass": feat.get("FHWAFunctionalClass"),
                "FHWAFunctionalClassLabel": feat.get("FHWAFunctionalClassLabel"),
                "HighestFHWAFunctionalClass": feat.get("HighestFHWAFunctionalClass"),
                "HighestFHWAFunctionalClassLabel": feat.get(
                    "HighestFHWAFunctionalClassLabel"
                ),
                "DCFunctionalClassCode": feat.get("DCFunctionalClassCode"),
                "DCFunctionalClass": feat.get("DCFunctionalClass"),
            }
            writer.writerow(row)
    logging.info("Wrote %s rows to %s", len(features), OUTPUT_CSV)
    return OUTPUT_CSV


def summarize(features: List[Dict[str, Any]]) -> None:
    by_utility: Dict[str, int] = defaultdict(int)
    by_type: Dict[str, int] = defaultdict(int)
    matched = 0
    for feat in features:
        by_utility[str(feat.get("Utility"))] += 1
        by_type[str(feat.get("EventTypeDescription"))] += 1
        if feat.get("FHWAFunctionalClass") is not None:
            matched += 1
    logging.info("Rows by utility: %s", dict(by_utility))
    logging.info("Rows by permit type: %s", dict(by_type))
    logging.info(
        "FHWA matched: %s / %s (%.1f%%)",
        matched,
        len(features),
        (100.0 * matched / len(features)) if features else 0.0,
    )


def main() -> int:
    setup_logging()
    logging.info("Starting DDOT permit enrichment")
    logging.info("Project root: %s", PROJECT_ROOT)
    logging.info("Output CSV: %s", OUTPUT_CSV)

    features = fetch_permits()
    if not features:
        logging.error("No permit features returned. Check filters / network.")
        return 1

    enrich_with_lrs(features)
    attach_fhwa(features)
    attach_highest_per_permit(features)
    write_csv(features)
    summarize(features)
    logging.info("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

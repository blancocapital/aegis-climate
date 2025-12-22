import csv
import io
from typing import Dict, List, Tuple


def canonicalize_rows(raw_bytes: bytes, mapping: Dict) -> List[Dict]:
    reader = csv.DictReader(io.StringIO(raw_bytes.decode()))
    rows = []
    for row in reader:
        mapped = {dst: row.get(src, "") for src, dst in mapping.items()} if mapping else row
        rows.append(mapped)
    rows.sort(key=lambda r: str(r.get("external_location_id", "")))
    return rows


def parse_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def to_location_dict(mapped: Dict) -> Dict:
    return {
        "external_location_id": mapped.get("external_location_id"),
        "address_line1": mapped.get("address_line1"),
        "city": mapped.get("city"),
        "country": mapped.get("country"),
        "latitude": parse_float(mapped.get("latitude") or mapped.get("lat")),
        "longitude": parse_float(mapped.get("longitude") or mapped.get("lon")),
        "tiv": parse_float(mapped.get("tiv")),
        "limit": parse_float(mapped.get("limit")),
        "premium": parse_float(mapped.get("premium")),
    }


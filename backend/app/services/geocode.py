import hashlib


def geocode_address(address_line1: str, city: str, country: str, postal_code: str = "", state_region: str = ""):
    normalized = f"{address_line1}|{city}|{state_region}|{postal_code}|{country}".lower().strip()
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    # map hash deterministically into lat/lon ranges
    lat = (int(digest[:8], 16) % 18000) / 100 - 90
    lon = (int(digest[8:16], 16) % 36000) / 100 - 180
    confidence = 0.6
    return lat, lon, confidence, "STUB_HASH"

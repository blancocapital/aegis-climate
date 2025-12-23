import hashlib
from typing import Any, Dict

from app.core.config import get_settings

ROOF_MATERIALS = ["metal", "tile", "asphalt_shingle", "wood_shake"]


class StubCharacteristicsProvider:
    name = "stub"

    def get_characteristics(self, address_fingerprint: str) -> Dict[str, Any]:
        digest = hashlib.sha256(address_fingerprint.encode()).hexdigest()
        roof_material = ROOF_MATERIALS[int(digest[:2], 16) % len(ROOF_MATERIALS)]
        year_built = 1950 + (int(digest[2:6], 16) % 71)
        stories = 1 + (int(digest[6:8], 16) % 3)
        sqft = 900 + (int(digest[8:12], 16) % 3100)
        vegetation_proximity_m = (int(digest[12:14], 16) % 60) + 1
        field_confidence = {
            "roof_material": 0.7,
            "year_built": 0.6,
            "stories": 0.65,
            "sqft": 0.6,
            "vegetation_proximity_m": 0.55,
        }
        return {
            "provider": self.name,
            "roof_material": roof_material,
            "year_built": year_built,
            "stories": stories,
            "sqft": sqft,
            "vegetation_proximity_m": float(vegetation_proximity_m),
            "field_confidence": field_confidence,
            "raw": {"fingerprint": address_fingerprint},
        }


class HttpCharacteristicsProvider:
    name = "http"

    def __init__(self, base_url: str, timeout: float = 3.0):
        self.base_url = base_url
        self.timeout = timeout

    def get_characteristics(self, address_fingerprint: str) -> Dict[str, Any]:
        raise NotImplementedError("HTTP characteristics provider not configured")


def get_characteristics_provider():
    settings = get_settings()
    provider = (settings.characteristics_provider or "stub").lower()
    if provider == "stub":
        return StubCharacteristicsProvider()
    return HttpCharacteristicsProvider(getattr(settings, "characteristics_url", ""), timeout=3.0)

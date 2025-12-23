import hashlib
from datetime import datetime
from typing import Any, Dict

from app.core.config import get_settings
from app.services.providers.base import CharacteristicsResult
from app.services.providers.http_characteristics import HttpCharacteristicsProvider

ROOF_MATERIALS = ["metal", "tile", "asphalt_shingle", "wood_shake"]


class StubCharacteristicsProvider:
    name = "stub"

    def get_characteristics(self, address_fingerprint: str) -> CharacteristicsResult:
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
            "confidence": 0.6,
            "retrieved_at": datetime.utcnow().isoformat(),
            "raw": {"fingerprint": address_fingerprint},
        }


def get_characteristics_provider():
    settings = get_settings()
    provider = (settings.characteristics_provider or "stub").lower()
    if provider == "stub":
        return StubCharacteristicsProvider()
    return HttpCharacteristicsProvider(
        base_url=settings.characteristics_http_base_url,
        api_key=settings.characteristics_http_api_key,
        api_key_header=settings.characteristics_http_api_key_header,
        mapping=settings.characteristics_http_mapping_json,
        timeout_seconds=settings.provider_timeout_seconds,
        connect_timeout_seconds=settings.provider_connect_timeout_seconds,
        max_retries=settings.provider_max_retries,
    )

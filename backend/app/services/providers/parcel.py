import hashlib
from datetime import datetime
from typing import Any, Dict

from app.core.config import get_settings
from app.services.providers.base import ParcelResult
from app.services.providers.http_parcel import HttpParcelProvider


class StubParcelProvider:
    name = "stub"

    def parcel_lookup(self, lat: float, lon: float) -> ParcelResult:
        token = f"{lat:.6f}:{lon:.6f}".encode()
        digest = hashlib.sha256(token).hexdigest()[:12]
        parcel_id = f"PARCEL-{digest}"
        delta = 0.001
        boundary = {
            "type": "Polygon",
            "coordinates": [[
                [lon - delta, lat - delta],
                [lon + delta, lat - delta],
                [lon + delta, lat + delta],
                [lon - delta, lat + delta],
                [lon - delta, lat - delta],
            ]],
        }
        return {
            "parcel_id": parcel_id,
            "boundary_geojson": boundary,
            "confidence": 0.7,
            "provider": self.name,
            "retrieved_at": datetime.utcnow().isoformat(),
            "raw": {"lat": lat, "lon": lon},
        }


def get_parcel_provider():
    settings = get_settings()
    provider = (settings.parcel_provider or "stub").lower()
    if provider == "stub":
        return StubParcelProvider()
    return HttpParcelProvider(
        base_url=settings.parcel_http_base_url,
        api_key=settings.parcel_http_api_key,
        api_key_header=settings.parcel_http_api_key_header,
        mapping=settings.parcel_http_mapping_json,
        timeout_seconds=settings.provider_timeout_seconds,
        connect_timeout_seconds=settings.provider_connect_timeout_seconds,
        max_retries=settings.provider_max_retries,
    )

import hashlib
from typing import Any, Dict

from app.core.config import get_settings


class StubParcelProvider:
    name = "stub"

    def parcel_lookup(self, lat: float, lon: float) -> Dict[str, Any]:
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
            "raw": {"lat": lat, "lon": lon},
        }


class HttpParcelProvider:
    name = "http"

    def __init__(self, base_url: str, timeout: float = 3.0):
        self.base_url = base_url
        self.timeout = timeout

    def parcel_lookup(self, lat: float, lon: float) -> Dict[str, Any]:
        raise NotImplementedError("HTTP parcel provider not configured")


def get_parcel_provider():
    settings = get_settings()
    provider = (settings.parcel_provider or "stub").lower()
    if provider == "stub":
        return StubParcelProvider()
    return HttpParcelProvider(getattr(settings, "parcel_url", ""), timeout=3.0)

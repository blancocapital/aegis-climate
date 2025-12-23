from typing import Any, Dict

from app.core.config import get_settings
from app.services.geocode import geocode_address


class StubGeocoder:
    name = "stub"

    def forward_geocode(self, address: Dict[str, Any]) -> Dict[str, Any]:
        lat, lon, confidence, method = geocode_address(
            address.get("address_line1", ""),
            address.get("city", ""),
            address.get("country", ""),
            postal_code=address.get("postal_code", ""),
            state_region=address.get("state_region", ""),
        )
        return {
            "standardized_address": address,
            "lat": lat,
            "lon": lon,
            "confidence": confidence,
            "provider": self.name,
            "method": method,
            "raw": {"input": address},
        }


class HttpGeocoder:
    name = "http"

    def __init__(self, base_url: str, timeout: float = 3.0):
        self.base_url = base_url
        self.timeout = timeout

    def forward_geocode(self, address: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("HTTP geocoder not configured")


def get_geocoder():
    settings = get_settings()
    provider = (settings.geocoder_provider or "stub").lower()
    if provider == "stub":
        return StubGeocoder()
    return HttpGeocoder(getattr(settings, "geocoder_url", ""), timeout=3.0)

from datetime import datetime
from typing import Any, Dict

from app.core.config import get_settings
from app.services.geocode import geocode_address
from app.services.providers.base import GeocodeResult
from app.services.providers.http_geocoder import HttpGeocoder


class StubGeocoder:
    name = "stub"

    def forward_geocode(self, address: Dict[str, Any]) -> GeocodeResult:
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
            "retrieved_at": datetime.utcnow().isoformat(),
            "raw": {"input": address},
        }


def get_geocoder():
    settings = get_settings()
    provider = (settings.geocoder_provider or "stub").lower()
    if provider == "stub":
        return StubGeocoder()
    return HttpGeocoder(
        base_url=settings.geocoder_http_base_url,
        api_key=settings.geocoder_http_api_key,
        api_key_header=settings.geocoder_http_api_key_header,
        mapping=settings.geocoder_http_mapping_json,
        timeout_seconds=settings.provider_timeout_seconds,
        connect_timeout_seconds=settings.provider_connect_timeout_seconds,
        max_retries=settings.provider_max_retries,
    )

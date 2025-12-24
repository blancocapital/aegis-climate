from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings


def _normalize_country_code(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower()


def geoapify_autocomplete(text: str, limit: int = 5, country_code: Optional[str] = None) -> List[Dict[str, Any]]:
    settings = get_settings()
    api_key = settings.geoapify_api_key
    if not api_key:
        raise ValueError("Geoapify API key not configured")
    if not text:
        return []

    params: Dict[str, Any] = {
        "text": text,
        "format": "json",
        "limit": max(1, min(int(limit), 10)),
        "apiKey": api_key,
    }
    normalized_country = _normalize_country_code(country_code)
    if normalized_country:
        params["filter"] = f"countrycode:{normalized_country}"

    timeout = httpx.Timeout(settings.provider_timeout_seconds, connect=settings.provider_connect_timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        response = client.get(settings.geoapify_autocomplete_url, params=params)
        response.raise_for_status()
        payload = response.json()

    results = payload.get("results") or payload.get("features") or []
    suggestions: List[Dict[str, Any]] = []
    for item in results:
        props = item.get("properties") if isinstance(item, dict) else None
        data = props if isinstance(props, dict) else item if isinstance(item, dict) else {}
        suggestions.append(
            {
                "formatted": data.get("formatted"),
                "address_line1": data.get("address_line1") or data.get("address_line2") or data.get("street"),
                "city": data.get("city") or data.get("town") or data.get("village"),
                "state_region": data.get("state_code") or data.get("state"),
                "postal_code": data.get("postcode"),
                "country": data.get("country"),
                "country_code": data.get("country_code"),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "raw": data,
            }
        )
    return suggestions

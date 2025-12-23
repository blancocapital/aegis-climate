import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.services.providers import get_characteristics_provider, get_geocoder, get_parcel_provider
from app.services.providers.base import ProviderError
from app.services.structural import normalize_structural


STRUCTURAL_KEYS = ["roof_material", "elevation_m", "vegetation_proximity_m"]


def normalize_address(address: Dict[str, Any]) -> Dict[str, Any]:
    if not address:
        return {}
    normalized = {}
    line1 = (address.get("address_line1") or "").strip()
    if line1:
        normalized["address_line1"] = line1
    city = (address.get("city") or "").strip()
    if city:
        normalized["city"] = city
    state = (address.get("state_region") or "").strip().upper()
    if state:
        normalized["state_region"] = state
    postal = (address.get("postal_code") or "").strip().upper().replace(" ", "")
    if postal:
        normalized["postal_code"] = postal
    country = (address.get("country") or "").strip().upper()
    if country:
        normalized["country"] = country
    return normalized


def address_fingerprint(normalized_address: Dict[str, Any]) -> str:
    payload = json.dumps(normalized_address, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def map_to_structural(
    characteristics_json: Optional[Dict[str, Any]],
    parcel_json: Optional[Dict[str, Any]],
    geocode_json: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    retrieved_at_default = datetime.utcnow().isoformat()
    characteristics_json = characteristics_json or {}
    parcel_json = parcel_json or {}
    geocode_json = geocode_json or {}

    structural = {}
    field_provenance = {}

    roof_material = characteristics_json.get("roof_material")
    if roof_material:
        structural["roof_material"] = roof_material
        field_provenance["roof_material"] = {
            "source": "characteristics",
            "provider": characteristics_json.get("provider"),
            "confidence": (characteristics_json.get("field_confidence") or {}).get("roof_material", 0.0),
            "retrieved_at": characteristics_json.get("retrieved_at") or retrieved_at_default,
            "method": "stub",
        }
    else:
        field_provenance["roof_material"] = {
            "source": None,
            "provider": characteristics_json.get("provider"),
            "confidence": 0.0,
            "retrieved_at": characteristics_json.get("retrieved_at") or retrieved_at_default,
            "method": "missing",
        }

    elevation_m = geocode_json.get("elevation_m") or parcel_json.get("elevation_m")
    if elevation_m is not None:
        structural["elevation_m"] = elevation_m
        field_provenance["elevation_m"] = {
            "source": "geocode" if geocode_json.get("elevation_m") is not None else "parcel",
            "provider": geocode_json.get("provider") or parcel_json.get("provider"),
            "confidence": geocode_json.get("confidence") or parcel_json.get("confidence") or 0.0,
            "retrieved_at": geocode_json.get("retrieved_at") or parcel_json.get("retrieved_at") or retrieved_at_default,
            "method": "stub",
        }
    else:
        field_provenance["elevation_m"] = {
            "source": None,
            "provider": None,
            "confidence": 0.0,
            "retrieved_at": retrieved_at_default,
            "method": "missing",
        }

    vegetation = characteristics_json.get("vegetation_proximity_m") or parcel_json.get("vegetation_proximity_m")
    if vegetation is not None:
        structural["vegetation_proximity_m"] = vegetation
        field_provenance["vegetation_proximity_m"] = {
            "source": "characteristics" if characteristics_json.get("vegetation_proximity_m") is not None else "parcel",
            "provider": characteristics_json.get("provider") or parcel_json.get("provider"),
            "confidence": (characteristics_json.get("field_confidence") or {}).get("vegetation_proximity_m", 0.0),
            "retrieved_at": characteristics_json.get("retrieved_at") or parcel_json.get("retrieved_at") or retrieved_at_default,
            "method": "stub",
        }
    else:
        field_provenance["vegetation_proximity_m"] = {
            "source": None,
            "provider": None,
            "confidence": 0.0,
            "retrieved_at": retrieved_at_default,
            "method": "missing",
        }

    return normalize_structural(structural), field_provenance


def build_property_profile_payload(
    normalized_address: Dict[str, Any],
    geocode: Dict[str, Any],
    parcel: Dict[str, Any],
    characteristics: Dict[str, Any],
    errors: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    structural_json, field_provenance = map_to_structural(characteristics, parcel, geocode)
    retrieved_at = datetime.utcnow().isoformat()
    provenance = {
        "retrieved_at": retrieved_at,
        "providers": {
            "geocoder": geocode.get("provider"),
            "parcel": parcel.get("provider"),
            "characteristics": characteristics.get("provider"),
        },
        "field_provenance": field_provenance,
    }
    if errors:
        provenance["errors"] = errors
    return {
        "standardized_address_json": geocode.get("standardized_address") or normalized_address,
        "geocode_json": geocode,
        "parcel_json": parcel,
        "characteristics_json": characteristics,
        "structural_json": structural_json,
        "provenance_json": provenance,
        "code_version": settings.code_version,
    }


def determine_enrich_mode(enrich_mode: str, providers_stub: bool) -> str:
    if enrich_mode == "sync":
        return "sync"
    if enrich_mode == "async":
        return "async"
    return "sync" if providers_stub else "async"


def providers_are_stub() -> bool:
    settings = get_settings()
    return (
        (settings.geocoder_provider or "stub").lower() == "stub"
        and (settings.parcel_provider or "stub").lower() == "stub"
        and (settings.characteristics_provider or "stub").lower() == "stub"
    )


def run_enrichment_pipeline(address_json: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_address(address_json)
    fingerprint = address_fingerprint(normalized)
    errors: List[Dict[str, Any]] = []

    geocoder = get_geocoder()
    geocode: Dict[str, Any] = {}
    try:
        geocode = geocoder.forward_geocode(normalized)
    except ProviderError as exc:
        errors.append(exc.to_dict())
        geocode = {"provider": getattr(geocoder, "name", "unknown"), "confidence": 0.0, "retrieved_at": datetime.utcnow().isoformat(), "raw": {}}

    parcel_provider = get_parcel_provider()
    parcel: Dict[str, Any] = {}
    if geocode.get("lat") is not None and geocode.get("lon") is not None:
        try:
            parcel = parcel_provider.parcel_lookup(float(geocode.get("lat")), float(geocode.get("lon")))
        except ProviderError as exc:
            errors.append(exc.to_dict())
            parcel = {"provider": getattr(parcel_provider, "name", "unknown"), "confidence": 0.0, "retrieved_at": datetime.utcnow().isoformat(), "raw": {}}
    else:
        errors.append(ProviderError(code="bad_request", message="Missing lat/lon for parcel lookup", retryable=False).to_dict())

    characteristics_provider = get_characteristics_provider()
    characteristics: Dict[str, Any] = {}
    try:
        characteristics = characteristics_provider.get_characteristics(fingerprint)
    except ProviderError as exc:
        errors.append(exc.to_dict())
        characteristics = {
            "provider": getattr(characteristics_provider, "name", "unknown"),
            "confidence": 0.0,
            "retrieved_at": datetime.utcnow().isoformat(),
            "raw": {},
            "field_confidence": {},
        }

    payload = build_property_profile_payload(normalized, geocode, parcel, characteristics, errors=errors)
    payload["address_fingerprint"] = fingerprint
    return payload


def decide_enrichment_action(
    async_required: bool,
    wait_seconds: int,
    best_effort: bool,
    run_status: Optional[str],
) -> Dict[str, Any]:
    if not async_required:
        return {"action": "score", "enrichment_status": "used_profile", "enrichment_failed": False}
    if run_status == "SUCCEEDED":
        return {"action": "score", "enrichment_status": "used_profile", "enrichment_failed": False}
    if run_status == "FAILED":
        if best_effort:
            return {"action": "score", "enrichment_status": "failed", "enrichment_failed": True}
        return {"action": "error", "enrichment_status": "failed", "enrichment_failed": True}
    if wait_seconds <= 0:
        if best_effort:
            return {"action": "score", "enrichment_status": "queued", "enrichment_failed": False}
        return {"action": "return_202", "enrichment_status": "queued", "enrichment_failed": False}
    if best_effort:
        return {"action": "score", "enrichment_status": "queued", "enrichment_failed": False}
    return {"action": "return_202", "enrichment_status": "queued", "enrichment_failed": False}


def is_profile_fresh(updated_at: Optional[datetime], days: int = 30) -> bool:
    if not updated_at:
        return False
    return updated_at >= datetime.utcnow() - timedelta(days=days)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, TypedDict


class BaseResult(TypedDict, total=False):
    provider: str
    confidence: float
    retrieved_at: str
    raw: Dict[str, Any]


class GeocodeResult(BaseResult, total=False):
    lat: float
    lon: float
    standardized_address: Dict[str, Any]
    method: Optional[str]
    elevation_m: Optional[float]


class ParcelResult(BaseResult, total=False):
    parcel_id: str
    boundary_geojson: Dict[str, Any]
    elevation_m: Optional[float]
    vegetation_proximity_m: Optional[float]


class CharacteristicsResult(BaseResult, total=False):
    roof_material: Optional[str]
    year_built: Optional[int]
    stories: Optional[int]
    sqft: Optional[float]
    vegetation_proximity_m: Optional[float]
    field_confidence: Dict[str, float]


@dataclass
class ProviderError(Exception):
    code: str
    message: str
    retryable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


def json_pointer_get(payload: Any, pointer: str) -> Any:
    if pointer in ("", "/"):
        return payload
    if not pointer.startswith("/"):
        raise ProviderError(code="parse", message=f"Invalid JSON pointer: {pointer}", retryable=False)
    parts = pointer.lstrip("/").split("/")
    current = payload
    for part in parts:
        key = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            try:
                index = int(key)
            except ValueError as exc:
                raise ProviderError(code="parse", message=f"Invalid list index in pointer: {pointer}", retryable=False) from exc
            try:
                current = current[index]
            except IndexError as exc:
                raise ProviderError(code="parse", message=f"Pointer out of range: {pointer}", retryable=False) from exc
        elif isinstance(current, dict):
            if key not in current:
                raise ProviderError(code="parse", message=f"Pointer not found: {pointer}", retryable=False)
            current = current[key]
        else:
            raise ProviderError(code="parse", message=f"Pointer invalid for payload: {pointer}", retryable=False)
    return current

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from app.services.providers.base import GeocodeResult, ProviderError, json_pointer_get


class HttpGeocoder:
    name = "http"

    def __init__(
        self,
        base_url: Optional[str],
        api_key: Optional[str],
        api_key_header: str,
        mapping: Optional[Dict[str, Any]],
        timeout_seconds: float,
        connect_timeout_seconds: float,
        max_retries: int,
        client: Optional[httpx.Client] = None,
    ):
        self.base_url = base_url or ""
        self.api_key = api_key
        self.api_key_header = api_key_header or "Authorization"
        self.mapping = mapping or {}
        self.max_retries = max(0, int(max_retries))
        self.timeout = httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds)
        self.client = client or httpx.Client(timeout=self.timeout)

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.api_key:
            headers[self.api_key_header] = self.api_key
        return headers

    def _request_json(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.base_url:
            raise ProviderError(code="bad_request", message="geocoder_http_base_url not configured", retryable=False)
        last_error: Optional[ProviderError] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.post(self.base_url, json=payload, headers=self._headers())
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                last_error = ProviderError(code="timeout", message="Geocoder request timed out", retryable=True)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 429:
                    last_error = ProviderError(code="rate_limited", message="Geocoder rate limited", retryable=True)
                elif status in (401, 403):
                    last_error = ProviderError(code="auth", message="Geocoder auth error", retryable=False)
                elif 400 <= status < 500:
                    last_error = ProviderError(code="bad_request", message=f"Geocoder bad request ({status})", retryable=False)
                else:
                    last_error = ProviderError(code="upstream", message=f"Geocoder upstream error ({status})", retryable=True)
            except ValueError as exc:
                last_error = ProviderError(code="parse", message=f"Geocoder response parse error: {exc}", retryable=False)
            except Exception as exc:
                last_error = ProviderError(code="upstream", message=f"Geocoder error: {exc}", retryable=False)
            if last_error and last_error.retryable and attempt < self.max_retries:
                continue
            if last_error:
                raise last_error
        raise ProviderError(code="upstream", message="Geocoder request failed", retryable=False)

    def _extract(self, data: Dict[str, Any], key: str, required: bool = False) -> Any:
        pointer = self.mapping.get(key)
        if pointer is None:
            if required:
                raise ProviderError(code="parse", message=f"Missing mapping for {key}", retryable=False)
            return None
        return json_pointer_get(data, pointer)

    def forward_geocode(self, address: Dict[str, Any]) -> GeocodeResult:
        if not self.mapping:
            raise ProviderError(code="parse", message="geocoder_http_mapping_json not configured", retryable=False)
        payload = {"address": address}
        data = self._request_json(payload)
        lat = self._extract(data, "lat", required=True)
        lon = self._extract(data, "lon", required=True)
        try:
            lat_value = float(lat)
            lon_value = float(lon)
        except (TypeError, ValueError) as exc:
            raise ProviderError(code="parse", message="Geocoder lat/lon not numeric", retryable=False) from exc

        confidence = self._extract(data, "confidence", required=False)
        standardized_address = self._extract(data, "standardized_address", required=False)
        method = self._extract(data, "method", required=False)
        elevation_m = self._extract(data, "elevation_m", required=False)

        result: GeocodeResult = {
            "lat": lat_value,
            "lon": lon_value,
            "confidence": float(confidence) if confidence is not None else 0.0,
            "provider": self.name,
            "method": method,
            "standardized_address": standardized_address or address,
            "elevation_m": elevation_m,
            "retrieved_at": datetime.utcnow().isoformat(),
            "raw": {
                "mapped": {
                    "lat": lat_value,
                    "lon": lon_value,
                    "confidence": confidence,
                }
            },
        }
        return result

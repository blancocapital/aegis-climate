from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from app.services.providers.base import CharacteristicsResult, ProviderError, json_pointer_get


class HttpCharacteristicsProvider:
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
            raise ProviderError(code="bad_request", message="characteristics_http_base_url not configured", retryable=False)
        last_error: Optional[ProviderError] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.post(self.base_url, json=payload, headers=self._headers())
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                last_error = ProviderError(code="timeout", message="Characteristics request timed out", retryable=True)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 429:
                    last_error = ProviderError(code="rate_limited", message="Characteristics rate limited", retryable=True)
                elif status in (401, 403):
                    last_error = ProviderError(code="auth", message="Characteristics auth error", retryable=False)
                elif 400 <= status < 500:
                    last_error = ProviderError(code="bad_request", message=f"Characteristics bad request ({status})", retryable=False)
                else:
                    last_error = ProviderError(code="upstream", message=f"Characteristics upstream error ({status})", retryable=True)
            except ValueError as exc:
                last_error = ProviderError(code="parse", message=f"Characteristics response parse error: {exc}", retryable=False)
            except Exception as exc:
                last_error = ProviderError(code="upstream", message=f"Characteristics error: {exc}", retryable=False)
            if last_error and last_error.retryable and attempt < self.max_retries:
                continue
            if last_error:
                raise last_error
        raise ProviderError(code="upstream", message="Characteristics request failed", retryable=False)

    def _extract(self, data: Dict[str, Any], key: str, required: bool = False) -> Any:
        pointer = self.mapping.get(key)
        if pointer is None:
            if required:
                raise ProviderError(code="parse", message=f"Missing mapping for {key}", retryable=False)
            return None
        return json_pointer_get(data, pointer)

    def get_characteristics(self, address_fingerprint: str) -> CharacteristicsResult:
        if not self.mapping:
            raise ProviderError(code="parse", message="characteristics_http_mapping_json not configured", retryable=False)
        payload = {"address_fingerprint": address_fingerprint}
        data = self._request_json(payload)
        roof_material = self._extract(data, "roof_material", required=False)
        year_built = self._extract(data, "year_built", required=False)
        stories = self._extract(data, "stories", required=False)
        sqft = self._extract(data, "sqft", required=False)
        vegetation = self._extract(data, "vegetation_proximity_m", required=False)
        confidence = self._extract(data, "confidence", required=False)
        field_confidence = self._extract(data, "field_confidence", required=False) or {}

        if roof_material is None and year_built is None and stories is None and sqft is None and vegetation is None:
            raise ProviderError(code="parse", message="Characteristics mapping returned no fields", retryable=False)

        result: CharacteristicsResult = {
            "provider": self.name,
            "roof_material": roof_material,
            "year_built": int(year_built) if year_built is not None else None,
            "stories": int(stories) if stories is not None else None,
            "sqft": float(sqft) if sqft is not None else None,
            "vegetation_proximity_m": float(vegetation) if vegetation is not None else None,
            "confidence": float(confidence) if confidence is not None else 0.0,
            "field_confidence": field_confidence if isinstance(field_confidence, dict) else {},
            "retrieved_at": datetime.utcnow().isoformat(),
            "raw": {"mapped": {"roof_material": roof_material}},
        }
        return result

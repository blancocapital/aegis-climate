import httpx
import pytest

from app.services.providers.base import ProviderError
from app.services.providers.http_characteristics import HttpCharacteristicsProvider
from app.services.providers.http_geocoder import HttpGeocoder
from app.services.providers.http_parcel import HttpParcelProvider


def test_http_geocoder_success_with_mapping():
    mapping = {
        "lat": "/data/lat",
        "lon": "/data/lon",
        "confidence": "/meta/confidence",
        "standardized_address": "/data/address",
    }

    def handler(request):
        return httpx.Response(
            200,
            json={
                "data": {"lat": 37.0, "lon": -122.1, "address": {"city": "Test"}},
                "meta": {"confidence": 0.82},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    geocoder = HttpGeocoder(
        base_url="https://example/geocode",
        api_key=None,
        api_key_header="Authorization",
        mapping=mapping,
        timeout_seconds=5.0,
        connect_timeout_seconds=1.0,
        max_retries=0,
        client=client,
    )
    result = geocoder.forward_geocode({"address_line1": "123 Main"})
    assert result["lat"] == 37.0
    assert result["lon"] == -122.1
    assert result["confidence"] == 0.82


def test_http_parcel_success_with_mapping():
    mapping = {
        "parcel_id": "/parcel/id",
        "boundary_geojson": "/parcel/boundary",
        "confidence": "/meta/confidence",
    }

    def handler(request):
        return httpx.Response(
            200,
            json={
                "parcel": {"id": "P123", "boundary": {"type": "Polygon", "coordinates": []}},
                "meta": {"confidence": 0.7},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    provider = HttpParcelProvider(
        base_url="https://example/parcel",
        api_key=None,
        api_key_header="Authorization",
        mapping=mapping,
        timeout_seconds=5.0,
        connect_timeout_seconds=1.0,
        max_retries=0,
        client=client,
    )
    result = provider.parcel_lookup(37.0, -122.0)
    assert result["parcel_id"] == "P123"
    assert result["confidence"] == 0.7


def test_http_characteristics_success_with_mapping():
    mapping = {
        "roof_material": "/data/roof_material",
        "vegetation_proximity_m": "/data/veg",
        "field_confidence": "/meta/field_confidence",
    }

    def handler(request):
        return httpx.Response(
            200,
            json={
                "data": {"roof_material": "metal", "veg": 12.0},
                "meta": {"field_confidence": {"roof_material": 0.7}},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    provider = HttpCharacteristicsProvider(
        base_url="https://example/characteristics",
        api_key=None,
        api_key_header="Authorization",
        mapping=mapping,
        timeout_seconds=5.0,
        connect_timeout_seconds=1.0,
        max_retries=0,
        client=client,
    )
    result = provider.get_characteristics("fingerprint")
    assert result["roof_material"] == "metal"
    assert result["vegetation_proximity_m"] == 12.0


def test_http_geocoder_parse_error_when_mapping_missing():
    def handler(request):
        return httpx.Response(200, json={"data": {"lat": 1, "lon": 2}})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    geocoder = HttpGeocoder(
        base_url="https://example/geocode",
        api_key=None,
        api_key_header="Authorization",
        mapping={"lat": "/data/lat"},
        timeout_seconds=5.0,
        connect_timeout_seconds=1.0,
        max_retries=0,
        client=client,
    )
    with pytest.raises(ProviderError) as excinfo:
        geocoder.forward_geocode({"address_line1": "123 Main"})
    assert excinfo.value.code == "parse"


def test_http_geocoder_timeout_retries():
    call_count = {"count": 0}
    mapping = {"lat": "/data/lat", "lon": "/data/lon"}

    def handler(request):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise httpx.ConnectTimeout("timeout", request=request)
        return httpx.Response(200, json={"data": {"lat": 1, "lon": 2}})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    geocoder = HttpGeocoder(
        base_url="https://example/geocode",
        api_key=None,
        api_key_header="Authorization",
        mapping=mapping,
        timeout_seconds=5.0,
        connect_timeout_seconds=1.0,
        max_retries=1,
        client=client,
    )
    result = geocoder.forward_geocode({"address_line1": "123 Main"})
    assert call_count["count"] == 2
    assert result["lat"] == 1.0

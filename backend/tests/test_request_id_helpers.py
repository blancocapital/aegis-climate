from app.api.schemas import build_api_error
from app.core.request_id import generate_request_id, get_request_id, reset_request_id, set_request_id


def test_request_id_generation_and_context():
    request_id = generate_request_id()
    token = set_request_id(request_id)
    assert get_request_id() == request_id
    reset_request_id(token)


def test_build_api_error_shape():
    payload = build_api_error("req-123", "TEST", "message", {"foo": "bar"})
    assert payload["request_id"] == "req-123"
    assert payload["code"] == "TEST"
    assert payload["message"] == "message"
    assert payload["details"]["foo"] == "bar"

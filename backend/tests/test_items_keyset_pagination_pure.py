from app.services.pagination import resolve_keyset_pagination


def test_after_id_overrides_offset():
    result = resolve_keyset_pagination(limit=100, offset=25, after_id=10, max_limit=500)
    assert result["after_id"] == 10
    assert result["offset"] is None


def test_offset_used_when_no_after_id():
    result = resolve_keyset_pagination(limit=1000, offset=-5, after_id=None, max_limit=500)
    assert result["limit"] == 500
    assert result["offset"] == 0
    assert result["after_id"] is None

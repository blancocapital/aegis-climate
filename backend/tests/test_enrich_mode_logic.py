from app.services.property_enrichment import determine_enrich_mode


def test_auto_sync_when_stub_providers():
    assert determine_enrich_mode("auto", True) == "sync"


def test_auto_async_when_not_stub():
    assert determine_enrich_mode("auto", False) == "async"


def test_explicit_modes_win():
    assert determine_enrich_mode("sync", False) == "sync"
    assert determine_enrich_mode("async", True) == "async"

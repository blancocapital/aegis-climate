from app.services.run_progress import merge_run_progress


def test_merge_run_progress_deterministic():
    base = {"foo": "bar", "processed": 1, "total": 10}
    merged = merge_run_progress(base, processed=2, total=10, extra={"baz": 3})
    assert merged["processed"] == 2
    assert merged["total"] == 10
    assert merged["foo"] == "bar"
    assert merged["baz"] == 3


def test_merge_run_progress_handles_none():
    merged = merge_run_progress(None, processed=None, total=None, extra=None)
    assert merged == {}

from app.services.property_enrichment import decide_enrichment_action


def test_async_no_wait_best_effort_false_returns_202():
    decision = decide_enrichment_action(async_required=True, wait_seconds=0, best_effort=False, run_status=None)
    assert decision["action"] == "return_202"


def test_wait_best_effort_true_falls_back():
    decision = decide_enrichment_action(async_required=True, wait_seconds=2, best_effort=True, run_status="RUNNING")
    assert decision["action"] == "score"
    assert decision["enrichment_status"] == "queued"
    assert decision["enrichment_failed"] is False


def test_failed_best_effort_true_scores():
    decision = decide_enrichment_action(async_required=True, wait_seconds=1, best_effort=True, run_status="FAILED")
    assert decision["action"] == "score"
    assert decision["enrichment_failed"] is True

import csv
import io
import json
import os
import sys
import time
from pathlib import Path

import httpx


BASE_URL = os.getenv("QA_BASE_URL", "http://localhost:8000")
EMAIL = os.getenv("QA_EMAIL", "admin@demo.com")
PASSWORD = os.getenv("QA_PASSWORD", "password")
TENANT_ID = os.getenv("QA_TENANT_ID", "demo")

DEFAULT_TIMEOUT = float(os.getenv("QA_TIMEOUT_SECONDS", "30"))
POLL_INTERVAL = float(os.getenv("QA_POLL_INTERVAL_SECONDS", "0.5"))


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def _check_request_id(resp: httpx.Response, label: str) -> str:
    request_id = resp.headers.get("X-Request-ID")
    if not request_id:
        _fail(f"missing X-Request-ID for {label}")
    return request_id


def _poll_run(client: httpx.Client, run_id: int, timeout: float) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/runs/{run_id}")
        if resp.status_code != 200:
            _fail(f"run status {run_id} failed: {resp.status_code} {resp.text}")
        data = resp.json()
        status = data.get("status")
        if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return data
        time.sleep(POLL_INTERVAL)
    _fail(f"run {run_id} did not finish within timeout")
    return {}


def _poll_resilience_status(client: httpx.Client, result_id: int, timeout: float) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/resilience-scores/{result_id}/status")
        if resp.status_code != 200:
            _fail(f"resilience status {result_id} failed: {resp.status_code} {resp.text}")
        data = resp.json()
        status = data.get("status")
        if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return data
        time.sleep(POLL_INTERVAL)
    _fail(f"resilience score {result_id} did not finish within timeout")
    return {}


def _load_sample_csv() -> bytes:
    repo_root = Path(__file__).resolve().parents[2]
    sample_path = repo_root / "sample_data" / "exposure_small.csv"
    if not sample_path.exists():
        _fail(f"sample csv missing: {sample_path}")
    return sample_path.read_bytes()


def _build_large_csv(rows: int) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "external_location_id",
        "address_line1",
        "city",
        "state_region",
        "postal_code",
        "country",
        "lat",
        "lon",
        "tiv",
        "lob",
    ])
    for i in range(1, rows + 1):
        writer.writerow([
            f"L{i}",
            f"{100 + i} Main St",
            "Metropolis",
            "NY",
            "10001",
            "US",
            40.0 + (i * 0.0001),
            -75.0 - (i * 0.0001),
            1000 + i,
            "property",
        ])
    return output.getvalue().encode()


def _upload_and_commit(client: httpx.Client, csv_bytes: bytes, name: str) -> int:
    files = {"file": ("qa_exposure.csv", csv_bytes, "text/csv")}
    resp = client.post("/uploads", files=files)
    if resp.status_code != 200:
        _fail(f"upload failed: {resp.status_code} {resp.text}")
    upload_id = resp.json().get("upload_id")
    if not upload_id:
        _fail("upload_id missing")

    resp = client.post(f"/uploads/{upload_id}/validate")
    if resp.status_code != 200:
        _fail(f"validate request failed: {resp.status_code} {resp.text}")
    run_id = resp.json().get("run_id")
    if not run_id:
        _fail("validation run_id missing")
    run = _poll_run(client, run_id, DEFAULT_TIMEOUT)
    if run.get("status") != "SUCCEEDED":
        _fail(f"validation failed: {run}")

    resp = client.post(f"/uploads/{upload_id}/commit", json={"name": name})
    if resp.status_code != 200:
        _fail(f"commit request failed: {resp.status_code} {resp.text}")
    run_id = resp.json().get("run_id")
    if not run_id:
        _fail("commit run_id missing")
    run = _poll_run(client, run_id, DEFAULT_TIMEOUT)
    if run.get("status") != "SUCCEEDED":
        _fail(f"commit failed: {run}")
    output_refs = run.get("output_refs_json") or {}
    exposure_version_id = output_refs.get("exposure_version_id")
    if not exposure_version_id:
        _fail("exposure_version_id missing from commit output")
    return exposure_version_id


def main() -> None:
    checklist = []
    with httpx.Client(base_url=BASE_URL, timeout=DEFAULT_TIMEOUT) as client:
        resp = client.get("/health")
        if resp.status_code != 200:
            _fail(f"health failed: {resp.status_code} {resp.text}")
        _check_request_id(resp, "health")
        checklist.append("health")

        resp = client.post(
            "/auth/login",
            json={"email": EMAIL, "password": PASSWORD, "tenant_id": TENANT_ID},
        )
        if resp.status_code != 200:
            _fail(f"login failed: {resp.status_code} {resp.text}")
        _check_request_id(resp, "login")
        token = resp.json().get("access_token")
        if not token:
            _fail("access_token missing from login")

        auth_headers = {"Authorization": f"Bearer {token}"}
        client.headers.update(auth_headers)

        address_payload = {
            "address_line1": "123 Main St",
            "city": "Metropolis",
            "state_region": "NY",
            "postal_code": "10001",
            "country": "US",
        }

        resp = client.post("/underwriting/packet", json=address_payload)
        if resp.status_code != 200:
            _fail(f"underwriting packet failed: {resp.status_code} {resp.text}")
        _check_request_id(resp, "underwriting_packet")
        packet = resp.json()
        for key in ["property", "hazards", "resilience", "provenance", "quality", "decision", "explainability"]:
            if key not in packet:
                _fail(f"underwriting packet missing key: {key}")
        checklist.append("underwriting_packet")

        resp = client.post(
            "/resilience/score",
            json={
                **address_payload,
                "wait_for_enrichment_seconds": 1,
                "best_effort": True,
            },
        )
        _check_request_id(resp, "resilience_score")
        if resp.status_code == 202:
            queued = resp.json()
            run_id = queued.get("run_id")
            if not run_id:
                _fail("resilience score queue response missing run_id")
            _poll_run(client, run_id, DEFAULT_TIMEOUT)
            resp = client.post(
                "/resilience/score",
                json={**address_payload, "best_effort": True},
            )
        if resp.status_code != 200:
            _fail(f"resilience score failed: {resp.status_code} {resp.text}")
        score_payload = resp.json()
        for key in ["hazards", "result", "data_quality", "explainability"]:
            if key not in score_payload:
                _fail(f"resilience score missing key: {key}")
        checklist.append("resilience_score")

        resp = client.post(
            "/property-profiles/resolve",
            json={"address": address_payload},
        )
        if resp.status_code != 200:
            _fail(f"property resolve failed: {resp.status_code} {resp.text}")
        first = resp.json()
        status = first.get("status")
        if status not in ("QUEUED", "CACHED", "EXISTING_IN_PROGRESS"):
            _fail(f"unexpected property resolve status: {status}")
        resp = client.post(
            "/property-profiles/resolve",
            json={"address": address_payload},
        )
        if resp.status_code != 200:
            _fail(f"property resolve repeat failed: {resp.status_code} {resp.text}")
        second = resp.json()
        if second.get("status") == "QUEUED" and status != "CACHED":
            _fail("property resolve duplicate run detected")
        checklist.append("property_resolve")

        exposure_version_id = _upload_and_commit(client, _load_sample_csv(), "QA Exposure")
        checklist.append("exposure_commit")

        batch_payload = {"exposure_version_id": exposure_version_id}
        resp = client.post("/resilience-scores", json=batch_payload)
        if resp.status_code != 200:
            _fail(f"batch score failed: {resp.status_code} {resp.text}")
        batch = resp.json()
        result_id = batch.get("resilience_score_result_id")
        run_id = batch.get("run_id")
        if not result_id or not run_id:
            _fail("batch score response missing ids")

        resp = client.post("/resilience-scores", json=batch_payload)
        if resp.status_code != 200:
            _fail(f"batch score repeat failed: {resp.status_code} {resp.text}")
        repeat = resp.json()
        if repeat.get("status") not in ("EXISTING_IN_PROGRESS", "EXISTING_SUCCEEDED"):
            _fail(f"unexpected batch repeat status: {repeat}")

        status_payload = _poll_resilience_status(client, result_id, DEFAULT_TIMEOUT)
        if status_payload.get("status") != "SUCCEEDED":
            _fail(f"batch score did not succeed: {status_payload}")

        resp = client.get(f"/resilience-scores/{result_id}/summary")
        if resp.status_code != 200:
            _fail(f"summary failed: {resp.status_code} {resp.text}")
        summary = resp.json()
        if "buckets" not in summary and "bucket_counts" not in summary:
            _fail("summary missing buckets")

        resp = client.get(f"/resilience-scores/{result_id}/disclosure")
        if resp.status_code != 200:
            _fail(f"disclosure failed: {resp.status_code} {resp.text}")
        disclosure = resp.json()
        if "bucket_counts" not in disclosure or "bucket_tiv" not in disclosure:
            _fail("disclosure missing buckets")

        resp = client.get(f"/resilience-scores/{result_id}/items", params={"limit": 2})
        if resp.status_code != 200:
            _fail(f"items failed: {resp.status_code} {resp.text}")
        items_payload = resp.json()
        items = items_payload.get("items", [])
        if not items:
            _fail("items empty")
        next_after_id = items_payload.get("next_after_id")
        if next_after_id:
            resp = client.get(
                f"/resilience-scores/{result_id}/items",
                params={"limit": 2, "after_id": next_after_id},
            )
            if resp.status_code != 200:
                _fail(f"items keyset failed: {resp.status_code} {resp.text}")
        checklist.append("batch_scoring")

        resp = client.get(f"/resilience-scores/{result_id}/export.csv")
        if resp.status_code != 200:
            _fail(f"export failed: {resp.status_code} {resp.text}")
        lines = resp.text.splitlines()
        if not lines:
            _fail("export empty")
        header = lines[0].split(",")
        expected_cols = [
            "location_id",
            "external_location_id",
            "latitude",
            "longitude",
            "address_line1",
            "city",
            "state_region",
            "postal_code",
            "country",
            "lob",
            "tiv",
            "resilience_score",
            "risk_score",
            "warnings",
            "hazards_json",
            "structural_json",
            "input_structural_json",
        ]
        if header[: len(expected_cols)] != expected_cols:
            _fail(f"export header mismatch: {header}")
        if len(lines) < 2:
            _fail("export missing data rows")
        checklist.append("export")

        # Run lifecycle: cancel + retry best effort
        resp = client.post("/resilience-scores", json={"exposure_version_id": exposure_version_id, "force": True})
        if resp.status_code != 200:
            _fail(f"batch score for cancel failed: {resp.status_code} {resp.text}")
        cancel_run_id = resp.json().get("run_id")
        if not cancel_run_id:
            _fail("cancel run_id missing")
        resp = client.post(f"/runs/{cancel_run_id}/cancel")
        if resp.status_code != 200:
            _fail(f"cancel failed: {resp.status_code} {resp.text}")
        cancel_status = resp.json().get("status")
        if cancel_status == "CANCELLED":
            current = client.get(f"/runs/{cancel_run_id}")
            if current.status_code == 200 and current.json().get("status") == "CANCELLED":
                resp = client.post(f"/runs/{cancel_run_id}/retry")
                if resp.status_code == 200:
                    retry_payload = resp.json()
                    if not retry_payload.get("run_id"):
                        _fail("retry response missing run_id")
                else:
                    print(f"NOTE: retry skipped ({resp.status_code} {resp.text})")
        checklist.append("run_lifecycle")

    print("PASS: " + ", ".join(checklist))


if __name__ == "__main__":
    main()

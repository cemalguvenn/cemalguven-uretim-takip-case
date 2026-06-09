"""Endpoint smoke + behaviour tests against the real CSV (in-memory DB)."""
from __future__ import annotations


async def test_reports_summary(client):
    r = await client.get("/api/reports/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["countable_records"] > 0
    assert sum(body["status_counts"][k] for k in ("clean", "warning", "error")) == 2117


async def test_report_endpoints_ok(client):
    for ep in ("/api/reports/oee-trend", "/api/reports/shift-comparison",
               "/api/reports/station-ranking", "/api/reports/quality-distribution"):
        assert (await client.get(ep)).status_code == 200


async def test_validation_summary_has_many_rule_types(client):
    body = (await client.get("/api/validation/summary")).json()
    assert body["total"] > 0
    assert len(body["by_rule"]) >= 15  # brief: more distinct error types = more points


async def test_records_filter_by_status(client):
    r = await client.get("/api/records", params={"status": ["error"], "page_size": 5})
    body = r.json()
    assert body["total"] == 325
    assert all(item["status"] == "error" for item in body["items"])


async def test_reject_excludes_from_dashboard(client):
    before = (await client.get("/api/reports/summary")).json()["countable_records"]
    # reject a clean record and confirm the countable set shrinks by one
    clean = (await client.get("/api/records", params={"status": ["clean"], "page_size": 1})).json()
    rid = clean["items"][0]["id"]
    r = await client.patch(f"/api/records/{rid}/status", json={"action": "reject"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    after = (await client.get("/api/reports/summary")).json()["countable_records"]
    assert after == before - 1


async def test_invalid_action_is_422(client):
    rid = (await client.get("/api/records", params={"page_size": 1})).json()["items"][0]["id"]
    r = await client.patch(f"/api/records/{rid}/status", json={"action": "explode"})
    assert r.status_code == 422

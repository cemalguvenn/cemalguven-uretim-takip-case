"""Aggregation correctness + submission idempotency/skip behaviour."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from models import ProductionRecord, SyncLog
from services import sync_service

DAY = date(2025, 11, 5)


def _rec(**kw):
    base = dict(
        record_id=1, import_batch_id=1, original_data="{}", tarih=DAY, vardiya=1,
        is_istasyon_adi="IMM-2700-1", oee=80.0, calisma_suresi=100.0,
        uretilen_miktar=50, hatali_uretilen=0, status="clean", is_hidden=False,
    )
    base.update(kw)
    return ProductionRecord(**base)


def test_aggregate_weighted_oee_and_distinct_machines():
    recs = [
        _rec(oee=90, calisma_suresi=100, uretilen_miktar=100, is_istasyon_adi="IMM-2700-1"),
        _rec(oee=60, calisma_suresi=300, uretilen_miktar=50, is_istasyon_adi="IMM-4000-1"),
    ]
    agg = sync_service.aggregate_records(recs, DAY, 1)
    # weighted: (90*100 + 60*300) / 400 = 67.5
    assert agg.payload["oe_value"] == 67.5
    assert agg.payload["machine_count"] == 2
    assert agg.payload["total_production_units"] == 150
    assert agg.payload["production_date"] == "2025-11-05"
    assert agg.payload["shift"] == 1


def test_aggregate_caps_oe_at_100():
    recs = [_rec(oee=300, calisma_suresi=100, uretilen_miktar=10)]
    assert sync_service.aggregate_records(recs, DAY, 1).payload["oe_value"] == 100.0


def test_aggregate_skips_zero_total():
    recs = [_rec(uretilen_miktar=0), _rec(uretilen_miktar=0)]
    assert sync_service.aggregate_records(recs, DAY, 1) is None


def test_aggregate_empty_is_none():
    assert sync_service.aggregate_records([], DAY, 1) is None


async def _add(session, **kw):
    rec = _rec(**kw)
    session.add(rec)
    await session.commit()
    return rec


async def test_submit_success_then_idempotent(session, monkeypatch):
    await _add(session, uretilen_miktar=120)

    async def fake_submit(self, payload):
        return 200, {"success": True, "submission_id": 99, "message": "ok"}, None

    monkeypatch.setattr(sync_service.ProductionApiClient, "submit", fake_submit)

    r1 = await sync_service.submit(session, DAY, 1)
    assert r1["status"] == "success" and r1["submission_id"] == 99

    # a successful sync_log blocks a plain re-submit (idempotency)
    r2 = await sync_service.submit(session, DAY, 1)
    assert r2["status"] == "duplicate"

    # force overrides: 'submitted' records still count, so it re-sends
    r3 = await sync_service.submit(session, DAY, 1, force=True)
    assert r3["status"] == "success"


async def test_submit_skips_when_no_data(session, monkeypatch):
    async def fake_submit(self, payload):  # pragma: no cover - shouldn't be called
        raise AssertionError("API should not be called when there is no data")

    monkeypatch.setattr(sync_service.ProductionApiClient, "submit", fake_submit)
    r = await sync_service.submit(session, DAY, 2)
    assert r["status"] == "skipped"


async def test_submit_records_failure(session, monkeypatch):
    await _add(session, uretilen_miktar=120)

    async def fake_submit(self, payload):
        return 422, {"detail": "bad"}, None

    monkeypatch.setattr(sync_service.ProductionApiClient, "submit", fake_submit)
    r = await sync_service.submit(session, DAY, 1)
    assert r["status"] == "failed" and r["response_status"] == 422
    log = await session.scalar(select(SyncLog))
    assert log is not None and log.status == "failed"

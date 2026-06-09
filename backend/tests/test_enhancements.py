"""Milestone 2 tests: statistical anomaly detection, auto-sync idempotency,
loss analysis, and the alerts endpoint."""
from __future__ import annotations

from datetime import date

from models import ProductionRecord
from services import sync_service
from validation.engine import _load_active_rules, _statistical_findings


async def test_statistical_oee_outlier_flags_extreme_member(session, make_record):
    rules = await _load_active_rules(session)
    # A tight group of 10 records + one extreme low-OEE outlier, same product+station.
    recs = [make_record(id=i, oee=80.0 + (i % 3), is_istasyon_adi="IMM-2700-1",
                        stok_adi="Part-A", calisma_suresi=400) for i in range(1, 11)]
    outlier = make_record(id=99, oee=5.0, is_istasyon_adi="IMM-2700-1",
                          stok_adi="Part-A", calisma_suresi=400)
    found = _statistical_findings(recs + [outlier], rules)
    assert 99 in found  # the extreme member is flagged
    assert all(i not in found for i in range(1, 11))  # normal members are not


async def test_statistical_skips_small_groups(session, make_record):
    rules = await _load_active_rules(session)
    recs = [make_record(id=i, oee=80, stok_adi="P", is_istasyon_adi="S") for i in range(3)]
    recs.append(make_record(id=9, oee=5, stok_adi="P", is_istasyon_adi="S"))
    # group < 8 → no statistical judgement
    assert _statistical_findings(recs, rules) == {}


async def _seed_shift(session, day, shift, n=3):
    from models import ImportBatch
    batch = ImportBatch(filename="t", file_hash=f"h{day}{shift}", total_rows=n, status="processing")
    session.add(batch)
    await session.flush()
    for i in range(n):
        session.add(ProductionRecord(
            record_id=i, import_batch_id=batch.id, original_data="{}", tarih=day, vardiya=shift,
            is_istasyon_adi="IMM-2700-1", oee=80.0, calisma_suresi=100.0,
            uretilen_miktar=50, hatali_uretilen=0, status="clean", is_hidden=False,
        ))
    await session.commit()


async def test_submit_all_ready_is_idempotent(session, monkeypatch):
    await _seed_shift(session, date(2025, 11, 5), 1)
    await _seed_shift(session, date(2025, 11, 5), 2)

    async def ok(self, payload):
        return 200, {"success": True, "submission_id": 1, "message": "ok"}, None

    monkeypatch.setattr(sync_service.ProductionApiClient, "submit", ok)

    first = await sync_service.submit_all_ready(session)
    assert first["submitted"] == 2
    second = await sync_service.submit_all_ready(session)
    assert second["submitted"] == 0  # already sent → nothing re-submitted


async def test_loss_analysis_endpoint(client):
    body = (await client.get("/api/reports/loss-analysis")).json()
    # waterfall identity: 100 - availability_loss == availability
    assert round(100 - body["availability_loss"], 1) == round(body["availability"], 1)
    assert body["oee"] <= body["availability"]
    assert len(body["stations"]) == 5


async def test_alerts_endpoint_reports_systematic(client):
    alerts = (await client.get("/api/alerts")).json()
    assert any(a["key"] == "systematic" for a in alerts)

"""Record service: correction → re-validate, status workflow, audit, batch."""
from __future__ import annotations

from sqlalchemy import select

from models import AuditLog, ProductionRecord
from services import record_service
from services.import_service import import_csv
from validation.engine import validate_batch


async def _seed_one(session, **overrides):
    """Insert a single record (in its own batch) and validate it."""
    from models import ImportBatch
    batch = ImportBatch(filename="t.csv", file_hash="h", total_rows=1, status="processing")
    session.add(batch)
    await session.flush()
    rec = ProductionRecord(
        record_id=1, import_batch_id=batch.id, original_data="{}",
        is_istasyon_adi="IMM-2700-1", stok_adi="Part-A", vardiya=1,
        availability=80.0, performance=90.0, quality=98.0, oee=70.56,
        calisma_suresi=400.0, durus_suresi=130.0, planli_durus=30.0,
        plansiz_durus=100.0, uretilen_miktar=100, hatali_uretilen=2, status="pending",
    )
    for k, v in overrides.items():
        setattr(rec, k, v)
    session.add(rec)
    await session.flush()
    await validate_batch(session, batch.id)
    return rec


async def test_correction_revalidates_and_marks_corrected(session):
    # vardiya missing -> error. Correcting it should clear the error.
    rec = await _seed_one(session, vardiya=None)
    assert rec.status == "error"
    updated = await record_service.update_record(
        session, rec.id, {"vardiya": 2}, reason="fixed shift"
    )
    assert updated.status == "corrected"
    logs = await record_service.get_audit_log(session, rec.id)
    assert any(log.action == "edit" and log.field_name == "vardiya" for log in logs)


async def test_reject_and_restore(session):
    rec = await _seed_one(session, vardiya=None)
    await record_service.set_status(session, rec.id, "reject", reason="bad")
    assert (await session.get(ProductionRecord, rec.id)).status == "rejected"
    await record_service.set_status(session, rec.id, "restore")
    # restore re-validates -> back to error (still missing-shift if not fixed)
    assert (await session.get(ProductionRecord, rec.id)).status == "error"


async def test_hide_unhide(session):
    rec = await _seed_one(session)
    await record_service.set_status(session, rec.id, "hide")
    assert (await session.get(ProductionRecord, rec.id)).is_hidden is True
    await record_service.set_status(session, rec.id, "unhide")
    assert (await session.get(ProductionRecord, rec.id)).is_hidden is False


async def test_batch_reject(session):
    raw = open("../data/production_data.csv", "rb").read()
    result = await import_csv(session, "production_data.csv", raw)
    await validate_batch(session, result.batch.id)
    ids = [r for r in (await session.scalars(
        select(ProductionRecord.id).limit(5))).all()]
    affected = await record_service.batch_action(session, ids, "reject", reason="bulk")
    assert affected == 5
    logs = await session.scalar(select(AuditLog).where(AuditLog.action == "reject").limit(1))
    assert logs is not None

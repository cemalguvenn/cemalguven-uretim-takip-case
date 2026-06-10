"""CSV import: encoding detection, position-based parsing, lineage, dedupe.

The MES file header is corrupted under cp1254 (e.g. `?? Emri No`), so columns are
mapped strictly by **position** (the 18-column order is fixed by the data
dictionary) — header text is never trusted. The untouched row is stored as JSON
in `original_data` so later corrections never lose the source of truth.

Sentinel values (e.g. -10) are preserved as-is, not nulled, so the validation
engine can flag them. Only truly empty cells become NULL.
"""
from __future__ import annotations

import asyncio
import csv as _csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog, ImportBatch, ProductionRecord, ValidationError

_INSERT_CHUNK = 1000

# Canonical names for the 18 columns, in fixed CSV order (used as original_data keys).
COLUMN_NAMES: list[str] = [
    "record_id", "Tarih", "Is Emri No", "Is Merkezi No", "Ismerkezi Adi",
    "Is Istasyon Adi", "Stok Adi", "Vardiya", "A", "P", "Q", "OEE",
    "Calisma Suresi", "Durus Suresi", "Planli Durus Suresi",
    "Plansiz Durus Suresi", "Uretilen Miktar", "Hatali Uretilen Miktar",
]
EXPECTED_COLUMNS = len(COLUMN_NAMES)

_ENCODINGS = ("cp1254", "utf-8", "latin-1")
_DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d.%m.%Y")


class ImportError_(Exception):
    """Base import failure."""


class EmptyFileError(ImportError_):
    pass


class ColumnCountError(ImportError_):
    pass


class BatchInProgressError(ImportError_):
    """Raised when deletion is attempted while the batch is still processing."""


class DuplicateImportError(ImportError_):
    """Raised when a file with the same SHA-256 hash was already imported."""

    def __init__(self, existing: ImportBatch):
        self.existing = existing
        super().__init__(f"File already imported as batch #{existing.id}")


@dataclass
class ImportResult:
    batch: ImportBatch
    record_ids: list[int]  # DB primary keys of inserted ProductionRecords


def compute_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def detect_encoding(raw: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"  # always succeeds


def parse_date(value: str | None) -> date | None:
    if not value or not value.strip():
        return None
    v = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def to_float(value: str | None) -> float | None:
    if value is None:
        return None
    v = value.strip()
    if v == "":
        return None
    # Tolerate comma decimal separators (MES exports vary).
    if "," in v and "." not in v:
        v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def to_int(value: str | None) -> int | None:
    f = to_float(value)
    return int(round(f)) if f is not None else None


def _read_dataframe(raw: bytes, encoding: str) -> pd.DataFrame:
    """Read the CSV positionally (no header trust). Chunked for large files."""
    text = raw.decode(encoding)
    reader = pd.read_csv(
        io.StringIO(text),
        header=None,
        skiprows=1,            # drop the (corrupted) header row
        dtype=str,             # keep raw strings; we coerce types ourselves
        keep_default_na=False,
        na_filter=False,
        chunksize=5000,        # supports 100K+ files without loading all at once
    )
    frames = list(reader)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _record_dict(values: list[str], csv_row_number: int, batch_id: int) -> dict:
    """Build a plain dict (for bulk `insert()` executemany) from one CSV row."""
    cell = {i: (values[i] if i < len(values) else "") for i in range(EXPECTED_COLUMNS)}
    original = {COLUMN_NAMES[i]: cell[i] for i in range(EXPECTED_COLUMNS)}
    return dict(
        record_id=to_int(cell[0]) or csv_row_number,
        csv_row_number=csv_row_number,
        import_batch_id=batch_id,
        original_data=json.dumps(original, ensure_ascii=False),
        tarih=parse_date(cell[1]),
        is_emri_no=cell[2].strip() or None,
        is_merkezi_no=cell[3].strip() or None,
        is_merkezi_adi=cell[4].strip() or None,
        is_istasyon_adi=cell[5].strip() or None,
        stok_adi=cell[6].strip() or None,
        vardiya=to_int(cell[7]),
        availability=to_float(cell[8]),
        performance=to_float(cell[9]),
        quality=to_float(cell[10]),
        oee=to_float(cell[11]),
        calisma_suresi=to_float(cell[12]),
        durus_suresi=to_float(cell[13]),
        planli_durus=to_float(cell[14]),
        plansiz_durus=to_float(cell[15]),
        uretilen_miktar=to_int(cell[16]),
        hatali_uretilen=to_int(cell[17]),
        status="pending",
        is_hidden=False,
    )


def parse_csv(raw: bytes) -> pd.DataFrame:
    """Decode + read positionally. Raises Empty/ColumnCount on bad shape."""
    df = _read_dataframe(raw, detect_encoding(raw))
    if df.empty:
        raise EmptyFileError("No data rows found after the header.")
    if df.shape[1] < EXPECTED_COLUMNS:
        raise ColumnCountError(f"Expected {EXPECTED_COLUMNS} columns, found {df.shape[1]}.")
    return df


def _build_records(df: pd.DataFrame, batch_id: int) -> list[dict]:
    # start=2 → first data row is CSV line 2 (line 1 is the header)
    return [
        _record_dict(list(row), idx, batch_id)
        for idx, row in enumerate(df.itertuples(index=False, name=None), start=2)
    ]


def quick_stats(raw: bytes) -> tuple[int, int]:
    """Cheap row + column count (no full pandas parse) for the upload response."""
    lines = raw.decode(detect_encoding(raw)).splitlines()
    total = max(len(lines) - 1, 0)
    ncols = len(next(_csv.reader(lines[1:2]), [])) if len(lines) > 1 else 0
    return total, ncols


async def import_csv(session: AsyncSession, filename: str, raw: bytes) -> ImportResult:
    """Synchronous full import (used by tests + as a library call). Bulk-inserts.

    Raises on empty/duplicate/wrong-shape files. Does NOT validate — call
    validate_batch separately.
    """
    if not raw or not raw.strip():
        raise EmptyFileError("Uploaded file is empty.")
    file_hash = compute_hash(raw)
    if await session.scalar(select(ImportBatch).where(ImportBatch.file_hash == file_hash)):
        raise DuplicateImportError(
            await session.scalar(select(ImportBatch).where(ImportBatch.file_hash == file_hash))
        )

    df = parse_csv(raw)
    batch = ImportBatch(filename=filename, file_hash=file_hash, total_rows=len(df),
                        processed_rows=0, status="processing", phase="importing")
    session.add(batch)
    await session.flush()  # assign batch.id

    dicts = _build_records(df, batch.id)
    for i in range(0, len(dicts), _INSERT_CHUNK):
        await session.execute(insert(ProductionRecord), dicts[i:i + _INSERT_CHUNK])
    batch.processed_rows = len(dicts)
    await session.commit()

    ids = (await session.scalars(
        select(ProductionRecord.id).where(ProductionRecord.import_batch_id == batch.id)
    )).all()
    return ImportResult(batch=batch, record_ids=list(ids))


async def create_batch_for_upload(session: AsyncSession, filename: str, raw: bytes) -> ImportBatch:
    """Fast path for the upload endpoint: dedupe + cheap stats + create the batch
    row (status=processing). Heavy import+validation runs in the background."""
    if not raw or not raw.strip():
        raise EmptyFileError("Uploaded file is empty.")
    file_hash = compute_hash(raw)
    existing = await session.scalar(select(ImportBatch).where(ImportBatch.file_hash == file_hash))
    if existing is not None:
        raise DuplicateImportError(existing)

    total, ncols = quick_stats(raw)
    if total == 0:
        raise EmptyFileError("No data rows found after the header.")
    if ncols < EXPECTED_COLUMNS:
        raise ColumnCountError(f"Expected {EXPECTED_COLUMNS} columns, found {ncols}.")

    batch = ImportBatch(filename=filename, file_hash=file_hash, total_rows=total,
                        processed_rows=0, status="processing", phase="importing")
    session.add(batch)
    await session.commit()
    return batch


async def delete_batch(session: AsyncSession, batch_id: int) -> bool:
    """Delete a batch and everything imported with it (records, validation
    errors, audit entries). Returns False if the batch does not exist."""
    batch = await session.get(ImportBatch, batch_id)
    if batch is None:
        return False
    if batch.status == "processing":
        raise BatchInProgressError("Bu yükleme hâlâ işleniyor; bitmeden silinemez.")

    record_ids = select(ProductionRecord.id).where(
        ProductionRecord.import_batch_id == batch_id
    ).scalar_subquery()
    await session.execute(delete(AuditLog).where(AuditLog.record_id.in_(record_ids)))
    await session.execute(
        delete(ValidationError).where(ValidationError.import_batch_id == batch_id)
    )
    await session.execute(
        delete(ProductionRecord).where(ProductionRecord.import_batch_id == batch_id)
    )
    await session.delete(batch)
    await session.commit()
    return True


async def process_import(batch_id: int, raw: bytes) -> None:
    """Background pipeline: bulk-import rows (updating progress) then validate.

    Runs with its own session so the request can return immediately; WAL lets the
    UI keep polling `GET /api/import/batches/{id}` while this writes.
    """
    from database import SessionLocal  # local import avoids any import-order cycles
    from validation.engine import validate_batch

    async with SessionLocal() as session:
        batch = await session.get(ImportBatch, batch_id)
        if batch is None:
            return
        try:
            df = parse_csv(raw)
            dicts = _build_records(df, batch_id)
            for i in range(0, len(dicts), _INSERT_CHUNK):
                await session.execute(insert(ProductionRecord), dicts[i:i + _INSERT_CHUNK])
                batch.processed_rows = min(i + _INSERT_CHUNK, len(dicts))
                await session.commit()
                await asyncio.sleep(0)  # let polling requests through

            batch.phase = "validating"
            await session.commit()
            counts = await validate_batch(session, batch_id)

            batch.clean_rows = counts["clean"]
            batch.warning_rows = counts["warning"]
            batch.error_rows = counts["error"]
            batch.status = "completed"
            batch.phase = "done"
            batch.completed_at = datetime.utcnow()
            await session.commit()
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            batch.status = "failed"
            batch.phase = "failed"
            batch.error_message = str(exc)[:500]
            await session.commit()

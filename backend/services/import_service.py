"""CSV import: encoding detection, position-based parsing, lineage, dedupe.

The MES file header is corrupted under cp1254 (e.g. `?? Emri No`), so columns are
mapped strictly by **position** (the 18-column order is fixed by the data
dictionary) — header text is never trusted. The untouched row is stored as JSON
in `original_data` so later corrections never lose the source of truth.

Sentinel values (e.g. -10) are preserved as-is, not nulled, so the validation
engine can flag them. Only truly empty cells become NULL.
"""
from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ImportBatch, ProductionRecord

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


def _row_to_record(values: list[str], csv_row_number: int, batch_id: int) -> ProductionRecord:
    cell = {i: (values[i] if i < len(values) else "") for i in range(EXPECTED_COLUMNS)}
    original = {COLUMN_NAMES[i]: cell[i] for i in range(EXPECTED_COLUMNS)}
    return ProductionRecord(
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
    )


async def import_csv(session: AsyncSession, filename: str, raw: bytes) -> ImportResult:
    """Parse and persist a CSV. Raises on empty/duplicate/wrong-shape files."""
    if not raw or not raw.strip():
        raise EmptyFileError("Uploaded file is empty.")

    file_hash = compute_hash(raw)
    existing = await session.scalar(
        select(ImportBatch).where(ImportBatch.file_hash == file_hash)
    )
    if existing is not None:
        raise DuplicateImportError(existing)

    encoding = detect_encoding(raw)
    df = _read_dataframe(raw, encoding)
    if df.empty:
        raise EmptyFileError("No data rows found after the header.")
    if df.shape[1] < EXPECTED_COLUMNS:
        raise ColumnCountError(
            f"Expected {EXPECTED_COLUMNS} columns, found {df.shape[1]}."
        )

    batch = ImportBatch(
        filename=filename, file_hash=file_hash, total_rows=len(df), status="processing"
    )
    session.add(batch)
    await session.flush()  # assign batch.id

    records: list[ProductionRecord] = []
    for idx, row in enumerate(df.itertuples(index=False, name=None), start=2):
        # start=2 → first data row is CSV line 2 (line 1 is the header)
        records.append(_row_to_record(list(row), idx, batch.id))
    session.add_all(records)
    await session.flush()

    record_ids = [r.id for r in records]
    await session.commit()
    return ImportResult(batch=batch, record_ids=record_ids)

"""Import endpoints: upload a CSV (async background parse + validate) and inspect batches."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_session
from models import ImportBatch
from schemas import ImportBatchOut
from services.import_service import (
    BatchInProgressError,
    ColumnCountError,
    DuplicateImportError,
    EmptyFileError,
    create_batch_for_upload,
    delete_batch,
    process_import,
)

router = APIRouter(prefix="/api/import", tags=["import"])

_READ_CHUNK = 1024 * 1024  # 1 MB


async def _read_capped(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks, aborting with 413 as soon as the cap is hit —
    an oversized file is rejected without ever being fully buffered in memory."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_READ_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Dosya çok büyük (limit {max_bytes // (1024 * 1024)} MB).",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/upload", response_model=ImportBatchOut)
async def upload_csv(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Create the batch (status=processing) and return immediately; the heavy
    import + validation runs in the background. Poll GET /batches/{id} for progress."""
    raw = await _read_capped(file, get_settings().max_upload_mb * 1024 * 1024)
    try:
        batch = await create_batch_for_upload(session, file.filename or "upload.csv", raw)
    except DuplicateImportError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "Bu dosya daha önce yüklendi.", "batch_id": exc.existing.id},
        )
    except (EmptyFileError, ColumnCountError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    background.add_task(process_import, batch.id, raw)
    return batch


@router.get("/batches", response_model=list[ImportBatchOut])
async def list_batches(session: AsyncSession = Depends(get_session)):
    return list((await session.scalars(
        select(ImportBatch).order_by(ImportBatch.created_at.desc())
    )).all())


@router.get("/batches/{batch_id}", response_model=ImportBatchOut)
async def get_batch(batch_id: int, session: AsyncSession = Depends(get_session)):
    batch = await session.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch bulunamadı.")
    return batch


@router.delete("/batches/{batch_id}", status_code=204)
async def remove_batch(batch_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a batch with all of its records, validation errors and audit trail."""
    try:
        deleted = await delete_batch(session, batch_id)
    except BatchInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="Batch bulunamadı.")

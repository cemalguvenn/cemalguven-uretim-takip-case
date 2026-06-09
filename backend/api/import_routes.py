"""Import endpoints: upload a CSV (async background parse + validate) and inspect batches."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import ImportBatch
from schemas import ImportBatchOut
from services.import_service import (
    ColumnCountError,
    DuplicateImportError,
    EmptyFileError,
    create_batch_for_upload,
    process_import,
)

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/upload", response_model=ImportBatchOut)
async def upload_csv(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Create the batch (status=processing) and return immediately; the heavy
    import + validation runs in the background. Poll GET /batches/{id} for progress."""
    raw = await file.read()
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

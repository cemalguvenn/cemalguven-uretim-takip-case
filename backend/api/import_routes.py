"""Import endpoints: upload a CSV (parse + validate) and inspect import batches."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import ImportBatch
from schemas import ImportBatchOut
from services.import_service import (
    ColumnCountError,
    DuplicateImportError,
    EmptyFileError,
    import_csv,
)
from validation.engine import validate_batch

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/upload", response_model=ImportBatchOut)
async def upload_csv(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    raw = await file.read()
    try:
        result = await import_csv(session, file.filename or "upload.csv", raw)
    except DuplicateImportError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "Bu dosya daha önce yüklendi.", "batch_id": exc.existing.id},
        )
    except (EmptyFileError, ColumnCountError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    counts = await validate_batch(session, result.batch.id)

    batch = await session.get(ImportBatch, result.batch.id)
    batch.clean_rows = counts["clean"]
    batch.warning_rows = counts["warning"]
    batch.error_rows = counts["error"]
    batch.status = "completed"
    batch.completed_at = datetime.utcnow()
    await session.commit()
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

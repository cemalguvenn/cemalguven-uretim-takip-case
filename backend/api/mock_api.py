"""Built-in mock of the target production API.

Mirrors the real contract documented in the case study so the whole sync flow
can be developed and demoed offline. Switching to the real endpoint is pure
configuration (API_BASE_URL / API_KEY in .env) — no code change.

Contract:
  POST /mock/api/v1/submit
  Header  X-Production-Key: <key>        (else 401)
  Body    oe_value 0–100, machine_count 1–1000, shift 1|2|3,
          total_production_units 1–1,000,000, production_date YYYY-MM-DD (no future)
  Errors  401 bad key · 422 validation (detail) · 413 body > 10 KB
"""
from __future__ import annotations

import itertools
import json
from datetime import date, datetime

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, field_validator

from config import get_settings

router = APIRouter(prefix="/mock", tags=["mock-api"])
settings = get_settings()

_submission_seq = itertools.count(1)
_CANDIDATE = "Cemal Güven"
_MAX_BODY = 10 * 1024  # 10 KB


class SubmitRequest(BaseModel):
    oe_value: float = Field(ge=0.0, le=100.0)
    machine_count: int = Field(ge=1, le=1000)
    shift: int
    total_production_units: int = Field(ge=1, le=1_000_000)
    production_date: str

    @field_validator("shift")
    @classmethod
    def _shift(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError("shift must be 1, 2 or 3")
        return v

    @field_validator("production_date")
    @classmethod
    def _date(cls, v: str) -> str:
        try:
            d = datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("production_date must be YYYY-MM-DD")
        if d > date.today():
            raise ValueError("production_date cannot be in the future")
        return v


@router.post("/api/v1/submit")
async def mock_submit(request: Request, x_production_key: str | None = Header(default=None)):
    raw = await request.body()
    # 413 — payload too large
    if len(raw) > _MAX_BODY:
        raise HTTPException(status_code=413, detail="Request body exceeds 10 KB limit.")
    # 401 — auth before validation, like the real API
    if x_production_key != settings.mock_api_key:
        raise HTTPException(status_code=401, detail="Eksik veya geçersiz API key.")
    # 422 — body validation
    try:
        data = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON body.")
    try:
        req = SubmitRequest(**data)
    except ValidationError as exc:
        # Pydantic v2 errors() may embed the raw exception in `ctx` (not JSON
        # serialisable) — keep only serialisable fields so the 422 encodes.
        detail = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        raise HTTPException(status_code=422, detail=detail)

    submission_id = next(_submission_seq)
    return {
        "success": True,
        "submission_id": submission_id,
        "candidate_name": _CANDIDATE,
        "message": f"Data recorded successfully. ID #{submission_id}.",
        "submitted_at": datetime.now().isoformat(timespec="seconds"),
        "echo": req.model_dump(),
    }

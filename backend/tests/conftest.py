"""Shared pytest fixtures: a fresh in-memory SQLite DB per test, seeded rules."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models import Base
from seed import seed_rules


@pytest_asyncio.fixture
async def session():
    """Yield an AsyncSession backed by a private in-memory database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await seed_rules(s)
        yield s
    await engine.dispose()


@pytest.fixture
def make_record():
    """Factory for a ProductionRecord with sensible clean defaults; override via kwargs."""
    from models import ProductionRecord

    def _make(**overrides):
        defaults = dict(
            record_id=1, import_batch_id=1, original_data="{}",
            is_emri_no="3025678325", is_merkezi_no="WC1", is_merkezi_adi="INJECTION",
            is_istasyon_adi="IMM-2700-1", stok_adi="Part-A", vardiya=1,
            availability=90.0, performance=95.0, quality=100.0, oee=85.5,
            calisma_suresi=400.0, durus_suresi=80.0, planli_durus=30.0,
            plansiz_durus=50.0, uretilen_miktar=100, hatali_uretilen=2,
            status="pending",
        )
        defaults.update(overrides)
        return ProductionRecord(**defaults)

    return _make

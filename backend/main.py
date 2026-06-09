"""FastAPI application entrypoint.

Lifespan creates tables and seeds the default validation-rule catalog on
startup. Routers are mounted under /api (app) and /mock (built-in mock target
API). CORS is open to the Vite dev server.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import SessionLocal, init_db
from seed import seed_rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as session:
        await seed_rules(session)
    yield


app = FastAPI(
    title="Üretim Performans Takip API",
    version="0.1.0",
    description="MES CSV import, data-quality validation, and day/shift sync to the target API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}


# Routers are registered as each step lands.
def _register_routers() -> None:
    from api import (  # noqa: WPS433  (local import keeps startup order explicit)
        import_routes,
        mock_api,
        record_routes,
        report_routes,
        settings_routes,
        sync_routes,
        validation_routes,
    )

    app.include_router(import_routes.router)
    app.include_router(record_routes.router)
    app.include_router(validation_routes.router)
    app.include_router(report_routes.router)
    app.include_router(sync_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(mock_api.router)


try:
    _register_routers()
except ImportError:
    # Routers not yet implemented in early build steps — health check still works.
    pass

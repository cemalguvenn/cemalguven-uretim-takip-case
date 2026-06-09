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
    from services import scheduler

    await init_db()
    async with SessionLocal() as session:
        await seed_rules(session)
        await scheduler.start(session)  # opt-in auto-sync (default off)
    yield
    scheduler.shutdown()


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


# Routers are registered as each build step lands. Each is mounted independently
# so a module that doesn't exist yet doesn't prevent the others from loading.
_ROUTER_MODULES = [
    "import_routes",
    "record_routes",
    "validation_routes",
    "report_routes",
    "sync_routes",
    "settings_routes",
    "alerts_routes",
    "mock_api",
]

import importlib  # noqa: E402

for _name in _ROUTER_MODULES:
    try:
        _module = importlib.import_module(f"api.{_name}")
        app.include_router(_module.router)
    except ModuleNotFoundError:
        pass  # not implemented yet in this build step

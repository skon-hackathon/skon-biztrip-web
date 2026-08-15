from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import SessionLocal, engine
from app.errors import register_error_handlers
from app.models import Base
from app.routers import auth
from app.seed import seed_all


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if get_settings().seed_on_startup:
        async with SessionLocal() as session:
            await seed_all(session)
    yield
    await engine.dispose()


app = FastAPI(
    title="SK온 출장시스템 API",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)
register_error_handlers(app)
app.include_router(auth.router)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

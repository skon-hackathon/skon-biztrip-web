from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.errors import register_error_handlers
from app.openapi import build_openapi
from app.routers.admin import centers as admin_centers
from app.routers.admin import codes as admin_codes
from app.routers.admin import departments as admin_departments
from app.routers.admin import users as admin_users
from app.routers import api_keys, auth, cards, centers, codes, expenses, meta, notifications, trips
from app.services.api_scopes import assert_scope_table_complete


@asynccontextmanager
async def lifespan(_: FastAPI):
    """기동 시 스키마나 데이터를 건드리지 않는다.

    이 앱은 이미 운영 중인 DB에 붙으므로, 자동 `create_all`이나 자동 시드는
    남의 데이터를 덮어쓸 위험이 있다. 스키마 생성과 시드는 `app.cli`의 명령을
    사람이 명시적으로 실행할 때만 일어난다.
    """
    yield
    await engine.dispose()


app = FastAPI(
    title="SK온 출장시스템 API",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)
register_error_handlers(app)
app.include_router(admin_centers.router)
app.include_router(admin_codes.router)
app.include_router(admin_departments.router)
app.include_router(admin_users.router)
app.include_router(api_keys.router)
app.include_router(auth.router)
app.include_router(cards.router)
app.include_router(centers.router)
app.include_router(codes.router)
app.include_router(expenses.router)
app.include_router(meta.router)
app.include_router(notifications.router)
app.include_router(trips.router)

# 라우트를 추가하고 SCOPE_REQUIREMENTS에 적지 않으면 여기서 기동이 실패한다.
# 조용히 전권을 얻는 엔드포인트가 생기는 것보다 못 뜨는 게 낫다.
assert_scope_table_complete(app)
app.openapi = build_openapi(app)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    """DB에 붙지 않는 liveness 체크. 컨테이너 healthcheck가 이걸 쓴다."""
    return {"status": "ok"}


@app.get("/api/v1/health/db")
async def health_db() -> dict[str, str]:
    """접속 설정이 실제로 맞는지 확인하는 readiness 체크."""
    settings = get_settings()
    async with SessionLocal() as session:
        schema = (await session.execute(text("SELECT current_schema()"))).scalar_one_or_none()
    return {
        "status": "ok",
        "host": settings.db_host,
        "database": settings.db_name,
        "schema": schema or "",
    }

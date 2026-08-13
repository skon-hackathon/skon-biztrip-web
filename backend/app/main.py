from fastapi import FastAPI

from app.errors import register_error_handlers

app = FastAPI(title="SK온 출장시스템 API", version="1.0.0", docs_url="/docs")
register_error_handlers(app)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

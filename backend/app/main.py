from fastapi import FastAPI

app = FastAPI(title="SK온 출장시스템 API", version="1.0.0", docs_url="/docs")


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

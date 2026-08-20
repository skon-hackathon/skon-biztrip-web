FROM python:3.12-slim

# uv는 PyPI에서 받는다. ghcr.io는 Docker Desktop의 Hub 미러 밖이라 VM egress가
# 끊기면 이 한 줄만 DeadlineExceeded로 죽는다. PyPI는 아래 uv sync가 어차피 쓴다.
RUN pip install --no-cache-dir uv==0.12.5

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

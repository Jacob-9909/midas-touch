# syntax=docker/dockerfile:1
# 백엔드(FastAPI) 앱 이미지. uv 기반 재현 빌드.
# 주의: torch/sentence-transformers/llama-index 때문에 이미지가 수 GB로 크다.
# 런타임 슬림화(추론 전용 분리)는 후속 과제 — 지금은 '컨테이너로 뜬다'가 목표.
FROM python:3.12-slim AS base

# uv 바이너리를 공식 이미지에서 복사(가장 빠르고 핀 고정 가능)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# 1) 의존성만 먼저 설치 → 소스 변경 시 레이어 캐시 재사용
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# 2) 앱 소스
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

EXPOSE 8000

# 기본: 올인원(단일 워커, 백그라운드 잡 포함). 수평 확장 시:
#   web  tier → command 에 --workers N 추가 + env RUN_BACKGROUND_JOBS=false
#   worker    → env RUN_BACKGROUND_JOBS=true 로 이 이미지 1개만
CMD ["uv", "run", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

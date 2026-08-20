#!/usr/bin/env bash
#
# dev.sh — Midas Touch 로컬 개발 서버 런처
# 백엔드(FastAPI/uvicorn :8000)와 프론트(Next.js dev :3000)를 동시에 띄운다.
# Ctrl+C 한 번으로 둘 다 종료된다.
#
# 사용법:
#   ./dev.sh              # 백엔드 + 프론트 동시 실행
#   ./dev.sh backend      # 백엔드만
#   ./dev.sh frontend     # 프론트만
#
set -euo pipefail

# 스크립트 위치를 프로젝트 루트로 고정 (어디서 실행하든 동일하게 동작)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# 파라미터 파싱 (--reload, --no-reload 및 모드 지정)
RELOAD="${RELOAD:-true}"
MODE="all"

for arg in "$@"; do
  case "$arg" in
    --reload|-r)
      RELOAD="true"
      ;;
    --no-reload)
      RELOAD="false"
      ;;
    all|backend|frontend)
      MODE="$arg"
      ;;
    *)
      echo "❌ 알 수 없는 파라미터: $arg" >&2
      echo "사용법: ./dev.sh [all|backend|frontend] [--reload|--no-reload]" >&2
      exit 1
      ;;
  esac
done

# ── 사전 점검 ────────────────────────────────────────────────
check_backend() {
  command -v uv >/dev/null 2>&1 || { echo "❌ uv 가 설치되어 있지 않습니다. https://docs.astral.sh/uv/" >&2; exit 1; }
}
check_frontend() {
  command -v npm >/dev/null 2>&1 || { echo "❌ npm(Node) 이 설치되어 있지 않습니다." >&2; exit 1; }
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    echo "📦 frontend 의존성이 없어 설치합니다 (npm install)…"
    (cd "$ROOT/frontend" && npm install)
  fi
}

# ── DB 컨테이너 보장 (도커) — 이미 실행 중이면 no-op(멱등) ────────
# 서버는 떴는데 DB가 꺼져 있어 자동배치가 조용히 빈 채로 도는 함정 방지.
ensure_db() {
  command -v docker >/dev/null 2>&1 || { echo "⚠️  docker 없음 — DB 스킵(앱은 graceful degrade)"; return 0; }
  docker start midas-postgres midas-neo4j >/dev/null 2>&1 \
    && echo "🗄️  DB 컨테이너 확인(midas-postgres·midas-neo4j)" \
    || echo "⚠️  DB 컨테이너 기동 실패 — 이름 확인 필요(docker ps -a)"
}

run_backend() {
  RELOAD_ARGS=""
  if [ "$RELOAD" = "true" ]; then
    RELOAD_ARGS="--reload --reload-dir $ROOT/backend --reload-dir $ROOT/shared"
  fi
  echo "🚀 [backend]  http://$BACKEND_HOST:$BACKEND_PORT  (docs: /docs, reload=$RELOAD)"
  PYTHONPATH="$ROOT" uv run uvicorn backend.app.main:app \
    --host "$BACKEND_HOST" --port "$BACKEND_PORT" $RELOAD_ARGS
}
run_frontend() {
  echo "🎨 [frontend] http://localhost:$FRONTEND_PORT"
  (cd "$ROOT/frontend" && PORT="$FRONTEND_PORT" npm run dev)
}

case "$MODE" in
  backend)
    check_backend
    ensure_db
    run_backend
    ;;
  frontend)
    check_frontend
    run_frontend
    ;;
  all)
    check_backend
    check_frontend
    echo "────────────────────────────────────────────"
    echo " Midas Touch dev (reload=$RELOAD) — Ctrl+C 로 모두 종료"
    echo "────────────────────────────────────────────"
    # 자식 프로세스를 백그라운드로 띄우고, 종료 시 프로세스 그룹 전체를 정리한다.
    trap 'echo; echo "🛑 종료 중…"; kill 0 2>/dev/null' INT TERM EXIT
    ensure_db
    run_backend &
    run_frontend &
    wait
    ;;
esac

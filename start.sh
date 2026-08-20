#!/usr/bin/env bash
#
# start.sh — Midas Touch 프로덕션 런처
# 백엔드(uvicorn, --reload 없음)와 프론트(next build && next start)를 기동한다.
# Ctrl+C 한 번으로 둘 다 종료된다.
#
# 사용법:
#   ./start.sh              # 프론트 빌드 후 백엔드 + 프론트 기동
#   ./start.sh backend      # 백엔드만
#   ./start.sh frontend     # 프론트만 (빌드 + start)
#   SKIP_BUILD=1 ./start.sh # 프론트 재빌드 생략(기존 .next 사용)
#
# 환경변수:
#   BACKEND_HOST(0.0.0.0) BACKEND_PORT(8000) BACKEND_WORKERS(1) FRONTEND_PORT(3000)
#
# 주의: 비동기 작업(JobManager)은 워커별 인메모리 상태라, 작업 진행률 일관성을 위해
#       BACKEND_WORKERS=1 을 권장한다. 멀티턴 채팅(체크포인터)은 Postgres 공유라 무관.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_WORKERS="${BACKEND_WORKERS:-1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# 파라미터 파싱 (--reload 지원)
RELOAD="${RELOAD:-false}"
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
      echo "사용법: ./start.sh [all|backend|frontend] [--reload]" >&2
      exit 1
      ;;
  esac
done

build_frontend() {
  if [ "${SKIP_BUILD:-0}" = "1" ] && [ -d "$ROOT/frontend/.next" ]; then
    echo "⏭️  프론트 빌드 생략(SKIP_BUILD=1)"
    return
  fi
  echo "🏗️  프론트 빌드 중 (next build)…"
  (cd "$ROOT/frontend" && [ -d node_modules ] || npm ci || npm install)
  (cd "$ROOT/frontend" && npm run build)
}

run_backend() {
  RELOAD_ARGS=""
  if [ "$RELOAD" = "true" ]; then
    RELOAD_ARGS="--reload --reload-dir $ROOT/backend --reload-dir $ROOT/shared"
  fi
  echo "🚀 [backend]  http://$BACKEND_HOST:$BACKEND_PORT  (workers=$BACKEND_WORKERS, reload=$RELOAD)"
  PYTHONPATH="$ROOT" uv run uvicorn backend.app.main:app \
    --host "$BACKEND_HOST" --port "$BACKEND_PORT" --workers "$BACKEND_WORKERS" $RELOAD_ARGS
}
run_frontend() {
  echo "🎨 [frontend] http://localhost:$FRONTEND_PORT (next start)"
  (cd "$ROOT/frontend" && PORT="$FRONTEND_PORT" npm run start)
}

# ── DB 컨테이너 보장 (도커) — 이미 실행 중이면 no-op(멱등) ────────
# 서버는 떴는데 DB가 꺼져 있어 자동배치가 조용히 빈 채로 도는 함정 방지.
ensure_db() {
  command -v docker >/dev/null 2>&1 || { echo "⚠️  docker 없음 — DB 스킵(앱은 graceful degrade)"; return 0; }
  docker start midas-postgres midas-neo4j >/dev/null 2>&1 \
    && echo "🗄️  DB 컨테이너 확인(midas-postgres·midas-neo4j)" \
    || echo "⚠️  DB 컨테이너 기동 실패 — 이름 확인 필요(docker ps -a)"
}

case "$MODE" in
  backend)
    command -v uv >/dev/null 2>&1 || { echo "❌ uv 미설치" >&2; exit 1; }
    ensure_db
    run_backend
    ;;
  frontend)
    command -v npm >/dev/null 2>&1 || { echo "❌ npm 미설치" >&2; exit 1; }
    build_frontend
    run_frontend
    ;;
  all)
    command -v uv >/dev/null 2>&1 || { echo "❌ uv 미설치" >&2; exit 1; }
    command -v npm >/dev/null 2>&1 || { echo "❌ npm 미설치" >&2; exit 1; }
    build_frontend
    echo "────────────────────────────────────────────"
    echo " Midas Touch (production, reload=$RELOAD) — Ctrl+C 로 모두 종료"
    echo "────────────────────────────────────────────"
    trap 'echo; echo "🛑 종료 중…"; kill 0 2>/dev/null' INT TERM EXIT
    ensure_db
    run_backend &
    run_frontend &
    wait
    ;;
esac

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

# ── DB 연결 보장 — 이미 붙어 있으면 no-op(멱등) ────────────────────
# 서버는 떴는데 DB가 안 붙어 자동배치가 조용히 빈 채로 도는 함정 방지.
# DB는 오라클 VM에 있고 외부 포트가 막혀 있어 SSH 터널로 붙는다(db-tunnel.sh 주석 참고).
ensure_db() {
  "$ROOT/db-tunnel.sh"
}

# ── 스키마 부트스트랩 게이트 (fresh DB 보호, 멱등) ──────────────────
# alembic 초기 리비전(d93ff1c5811e)은 drop-only라 빈 DB에서 upgrade가 폭발한다.
# users 테이블 부재를 fresh DB 신호로 보고 postgres_schema.sql 선적재 후 head로 스탬프.
# DB 미기동·psql 부재 시에도 앱 기동은 막지 않는다(warn-only).
ensure_schema() {
  command -v psql >/dev/null 2>&1 || { echo "⚠️  psql 없음 — 스키마 점검 생략"; return 0; }
  local url="${DATABASE_URL:-}"
  if [ -z "$url" ]; then
    url="$(grep -E '^DATABASE_URL=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"'" || true)"
  fi
  [ -z "$url" ] && { echo "⚠️  DATABASE_URL 미설정 — 스키마 점검 생략"; return 0; }
  local exists=""
  for _ in 1 2 3; do
    exists="$(psql "$url" -tAc "SELECT to_regclass('public.users')" 2>/dev/null || true)"
    [ "$exists" = "users" ] && break
    sleep 2
  done
  if [ "$exists" = "users" ]; then
    echo "🗄️  스키마 확인(public.users 존재)"
    return 0
  fi
  echo "📦 fresh DB 감지 — postgres_schema.sql 부트스트랩 + alembic stamp head 시도…"
  if psql "$url" -v ON_ERROR_STOP=1 -qf shared/database/schema/postgres_schema.sql; then
    uv run alembic stamp head \
      && echo "✅ 스키마 부트스트랩 완료(head 스탬프)" \
      || echo "⚠️  alembic stamp 실패 — 수동 실행 필요: uv run alembic stamp head" >&2
  else
    echo "⚠️  스키마 부트스트랩 실패(DB 미기동·접속 실패?) — 앱은 계속 기동하며 수동 확인 필요:" >&2
    echo "    psql \"\$DATABASE_URL\" -f shared/database/schema/postgres_schema.sql && uv run alembic stamp head" >&2
  fi
}

case "$MODE" in
  backend)
    command -v uv >/dev/null 2>&1 || { echo "❌ uv 미설치" >&2; exit 1; }
    ensure_db
    ensure_schema
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
    ensure_schema
    run_backend &
    run_frontend &
    wait
    ;;
esac

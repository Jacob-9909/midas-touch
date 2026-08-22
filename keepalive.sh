#!/usr/bin/env bash
#
# keepalive.sh — 심사 기간(9/7~9/11) 무중단용 워치독.
#
# expose.sh 는 한 번 띄우면 끝이지만, 5일을 방치하면 죽는 경로가 여러 개다.
# 이 스크립트는 그 경로들을 1분마다 점검하고 스스로 복구한다.
#
#   1) Docker 데몬이 내려감      → Docker Desktop 재기동 (로그인 항목에 없어서 재부팅 시 안 뜬다)
#   2) DB 컨테이너만 내려감      → docker start
#   3) 프론트/백엔드/터널이 죽음 → expose.sh 재기동
#   4) "HTTP 200인데 속은 빈" 상태 → DB 의존 엔드포인트로 별도 확인
#
# 4번이 핵심이다. Docker 가 죽어도 앱은 200 을 반환하며 graceful degrade 하기 때문에,
# 프론트 200 만 보고 "살아있다"고 판단하면 심사자에게 빈 화면을 보여주게 된다.
#
# 사용법:
#   caffeinate -dimsu ./keepalive.sh          # 절전까지 같이 막고 싶을 때(권장)
#   ./keepalive.sh                            # 그냥 실행
#   PUBLIC_URL=https://... ./keepalive.sh     # 공개 URL 도 함께 점검
#
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

INTERVAL="${INTERVAL:-60}"
LOG="${LOG:-$ROOT/logs/keepalive.log}"
PUBLIC_URL="${PUBLIC_URL:-}"
mkdir -p "$(dirname "$LOG")"

say() { printf '%s | %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

ensure_docker() {
  docker info >/dev/null 2>&1 && return 0
  say "⚠️  Docker 데몬 down → Docker Desktop 기동"
  open -a Docker >/dev/null 2>&1
  for _ in $(seq 1 40); do
    sleep 3
    docker info >/dev/null 2>&1 && { say "✅ Docker 데몬 복구"; return 0; }
  done
  say "❌ Docker 데몬 복구 실패"
  return 1
}

ensure_containers() {
  local want="midas-postgres midas-neo4j" missing=""
  for c in $want; do
    docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$c" || missing="$missing $c"
  done
  [ -z "$missing" ] && return 0
  say "⚠️  컨테이너 down:$missing → 기동"
  docker start $missing >/dev/null 2>&1 && say "✅ 컨테이너 복구" || say "❌ 컨테이너 기동 실패"
}

# 프론트(3000)·백엔드(8000)·DB 까지 실제로 살아있는지. DB 는 반드시 DB 를 타는
# 엔드포인트로 확인한다 — 프론트 200 은 DB 가 죽어도 그대로 나오기 때문.
stack_healthy() {
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://localhost:3000/)" = "200" ] || return 1
  curl -s --max-time 15 'http://localhost:8000/api/v1/users?limit=1' \
    | grep -q '"uuid"' || return 1
  return 0
}

restart_stack() {
  say "♻️  스택 재기동 (expose.sh)"
  lsof -ti:3000,8000,4040 2>/dev/null | xargs kill -9 2>/dev/null
  sleep 3
  SKIP_BUILD=1 nohup ./expose.sh >>"$ROOT/logs/expose.log" 2>&1 &
  for _ in $(seq 1 60); do
    sleep 5
    stack_healthy && { say "✅ 스택 복구"; return 0; }
  done
  say "❌ 스택 복구 실패 — logs/expose.log 확인 필요"
  return 1
}

current_url() {
  curl -s --max-time 5 http://localhost:4040/api/tunnels 2>/dev/null \
    | jq -r '.tunnels[0].public_url // empty' 2>/dev/null
}

say "▶️  keepalive 시작 (점검주기 ${INTERVAL}s, 로그 $LOG)"
LAST_URL=""
while true; do
  ensure_docker && ensure_containers

  if stack_healthy; then
    URL="$(current_url)"
    if [ -n "$URL" ] && [ "$URL" != "$LAST_URL" ]; then
      say "🌐 공개 URL: $URL"
      LAST_URL="$URL"
    fi
    [ -z "$URL" ] && { say "⚠️  ngrok 터널 없음 → 재기동"; restart_stack; }
  else
    say "⚠️  스택 비정상 → 복구 시도"
    restart_stack
  fi

  # 밖에서 실제로 닿는지까지 확인(설정된 경우). 안에서 멀쩡해도 터널이 끊길 수 있다.
  if [ -n "$PUBLIC_URL" ]; then
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
      -H 'ngrok-skip-browser-warning: 1' "$PUBLIC_URL/" || echo 000)"
    [ "$code" = "200" ] || say "⚠️  외부 접속 실패(HTTP $code) — $PUBLIC_URL"
  fi

  sleep "$INTERVAL"
done

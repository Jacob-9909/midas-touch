#!/usr/bin/env bash
#
# db-tunnel.sh — 오라클 VM DB로 가는 SSH 터널 보장 (멱등)
#
# DB(Postgres·Neo4j)는 오라클 VM에 있고, 2026-08-30부터 외부 포트가 방화벽에서 막혔다.
# 백엔드가 VM 안으로 들어가면서 밖에 열어둘 이유가 없어졌기 때문이다(비번만 알면 누구나
# 붙던 상태였다). 그래서 로컬 개발은 SSH 터널로 붙는다 — .env 의 DB 호스트는 localhost다.
#
# 예전엔 이 자리에 `docker start midas-postgres midas-neo4j` 가 있었다. DB가 로컬 도커였을
# 때 얘기고, 지금은 그 컨테이너가 없어서 매번 실패 메시지만 뱉으면서 정작 막으려던 함정
# (터널이 없어 DB에 못 붙는 채로 서버만 뜨는 것)은 못 막는다.
#
# 사용: ./db-tunnel.sh          # 없으면 띄우고, 있으면 아무것도 안 함
#       ./db-tunnel.sh --down   # 내리기
#
# 접속 대상은 ~/.ssh/config 의 Host 별칭을 쓴다(기본 oracle_vm). 바꾸려면:
#       DB_TUNNEL_HOST=myvm ./dev.sh

set -u

HOST="${DB_TUNNEL_HOST:-oracle_vm}"
PORTS="5432 7687"

# 로컬 포트가 응답하면 터널(또는 로컬 DB)이 살아 있는 것으로 본다.
tunnel_up() {
  for p in $PORTS; do
    nc -z 127.0.0.1 "$p" >/dev/null 2>&1 || return 1
  done
  return 0
}

if [ "${1:-}" = "--down" ]; then
  pkill -f "ssh -f -N .*-L 5432:localhost:5432" 2>/dev/null \
    && echo "🔌 DB 터널 내림" || echo "🔌 내릴 터널 없음"
  exit 0
fi

if tunnel_up; then
  echo "🔌 DB 터널 확인(127.0.0.1:5432·7687 응답)"
  exit 0
fi

command -v ssh >/dev/null 2>&1 || { echo "⚠️  ssh 없음 — DB 연결 불가(앱은 graceful degrade)"; exit 0; }

echo "🔌 DB 터널 기동 중… ($HOST)"
# ExitOnForwardFailure: 포트 포워딩이 실패하면 조용히 붙어 있지 말고 즉시 죽으라는 뜻.
# 이게 없으면 "ssh 는 떴는데 포워딩은 안 된" 상태를 성공으로 오해한다.
ssh -f -N -o ExitOnForwardFailure=yes -o ConnectTimeout=10 -o BatchMode=yes \
  -L 5432:localhost:5432 -L 7687:localhost:7687 "$HOST" 2>/dev/null

# ssh -f 는 백그라운드로 넘어간 뒤라 포워딩이 실제로 섰는지 다시 확인해야 한다.
for _ in 1 2 3 4 5; do
  tunnel_up && { echo "✅ DB 터널 연결됨($HOST → 5432·7687)"; exit 0; }
  sleep 1
done

# 앱 기동 자체는 막지 않는다(기존 ensure_db 정책과 동일 — 앱은 graceful degrade 한다).
echo "⚠️  DB 터널 실패 — DB 의존 기능이 빈 채로 동작합니다."
echo "    확인: ssh $HOST 'echo ok'   /   ~/.ssh/config 의 Host $HOST 항목"
exit 0

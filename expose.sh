#!/usr/bin/env bash
#
# expose.sh — 외부 노출 런처: start.sh(프로덕션) + ngrok http 3000 을 함께 띄운다.
# Ctrl+C 한 번으로 둘 다 종료. 터널 뒤에선 dev 가 아니라 프로덕션 빌드를 써야 한다
# (dev 의 HMR WebSocket 이 ngrok 무료에서 죽어 hydration 이 안 끝남).
#
# 사용법:
#   ./expose.sh              # 빌드 → 서버 기동 → ngrok 주소 출력
#   SKIP_BUILD=1 ./expose.sh # 프론트 재빌드 생략(기존 .next 사용)
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

command -v ngrok >/dev/null || { echo "❌ ngrok 미설치" >&2; exit 1; }

trap 'echo; echo "🛑 종료 중…"; kill 0 2>/dev/null' INT TERM EXIT

# 1) 프로덕션 서버(백엔드+프론트) 백그라운드 기동
./start.sh &

# 2) 프론트(:3000) 준비될 때까지 대기
echo -n "⏳ 서버 빌드/기동 대기"
for _ in $(seq 1 120); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000 2>/dev/null)" = "200" ] && break
  sleep 3; echo -n "."
done
echo

# 3) ngrok 터널 기동 후 공개 주소 출력
ngrok http 3000 --log=stdout >/tmp/ngrok-midas.log 2>&1 &
echo -n "⏳ ngrok 주소 대기"
URL=""
for _ in $(seq 1 20); do
  sleep 1; echo -n "."
  URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | jq -r '.tunnels[0].public_url' 2>/dev/null || true)
  [ -n "$URL" ] && [ "$URL" != "null" ] && break
done
echo
cat <<EOF

════════════════════════════════════════════════════════════
✅ 외부 접속 주소:  ${URL:-<주소 못 받음, /tmp/ngrok-midas.log 확인>}
   첫 방문 시 ngrok "Visit Site" 1회 클릭 → 이후 안 뜸.
   대시보드: http://localhost:4040   |   Ctrl+C 로 모두 종료
════════════════════════════════════════════════════════════
EOF

wait

#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "1. PostgreSQL 컨테이너 시작 중..."
cd "$SCRIPT_DIR/.." && docker compose up -d

echo "2. DB 준비 대기 중..."
sleep 3

echo "3. ngrok TCP 터널 시작 중..."
ngrok tcp 5432 --log=stdout &
sleep 4

PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json; t=json.load(sys.stdin)['tunnels'][0]; print(t['public_url'])")
HOST=$(echo "$PUBLIC_URL" | sed 's|tcp://||' | cut -d: -f1)
PORT=$(echo "$PUBLIC_URL" | sed 's|tcp://||' | cut -d: -f2)

echo ""
echo "=============================="
echo "  DB 접속 정보"
echo "=============================="
echo "  Host    : $HOST"
echo "  Port    : $PORT"
echo "  DB      : midas"
echo "  User    : postgres"
echo "=============================="
echo ""
echo "종료하려면 Ctrl+C"
wait

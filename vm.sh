#!/usr/bin/env bash
#
# vm.sh — 오라클 VM 백엔드 운영 (배포·상태·로그·헬스체크)
#
# 심사 구성(2026-08-30~): 프론트는 Vercel, 백엔드·DB는 오라클 VM.
# 백엔드는 systemd(midas-backend) + Caddy(TLS) 로 돌고, 노트북은 아무것도 호스팅하지 않는다.
# 예전엔 이 자리에 expose.sh(ngrok) / keepalive.sh(노트북 워치독) 가 있었는데,
# 둘 다 "맥에서 스택을 띄워 ngrok 으로 노출한다"는 전제라 지금은 성립하지 않아 지웠다.
# 재기동은 이제 systemd 의 Restart=always 가 맡는다 — 워치독을 노트북에 둘 이유가 없다.
#
# 사용법:
#   ./vm.sh health          # 밖에서 보는 상태(프론트·API·DB 의존 엔드포인트) — 심사 기간 매일
#   ./vm.sh status          # VM 안 상태(서비스·메모리·배포된 커밋)
#   ./vm.sh deploy          # git pull → uv sync → 재기동 → 헬스 대기
#   ./vm.sh restart         # 코드 변경 없이 재기동(.env 만 고쳤을 때)
#   ./vm.sh logs [N]        # 최근 N줄(기본 50). 인자 없이 -f 로 따라가려면 ./vm.sh logs -f
#   ./vm.sh errors          # 최근 24시간 에러만
#   ./vm.sh autodeploy <cmd>  # install|on|off|status|log — main 머지 시 자동배포
#
# 접속 대상은 ~/.ssh/config 의 Host 별칭(기본 oracle_vm). 바꾸려면 VM_HOST=myvm ./vm.sh …
set -uo pipefail

HOST="${VM_HOST:-oracle_vm}"
APP_DIR="${VM_APP_DIR:-~/midas-touch}"
API="${API_BASE:-https://midas-touch.duckdns.org}"
FRONT="${FRONT_BASE:-https://midas-touch-five.vercel.app}"

# uv 는 ~/.local/bin 에 있는데 비대화형 ssh 의 PATH 엔 없다. 절대경로로 부른다.
UV="~/.local/bin/uv"

vm() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "$@"; }

# DB 가 죽어도 앱은 200 을 반환하며 graceful degrade 한다("겉은 멀쩡, 속은 빔").
# 그래서 /health 만으로는 부족하고 DB 를 실제로 타는 엔드포인트까지 봐야 한다.
health() {
  local code db rows
  code="$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$FRONT" 2>/dev/null)"
  printf '프론트   %s  %s\n' "${code:----}" "$FRONT"

  db="$(curl -s -m 10 "$API/health" 2>/dev/null)"
  printf 'API      %s\n' "${db:-응답 없음}"

  rows="$(curl -s -m 20 "$API/api/v1/cheongyak/list/apt" 2>/dev/null | grep -o 'house_manage_no' | wc -l | tr -d ' ')"
  printf '청약 API %s건 (DB 의존 — 0이면 200이어도 속이 빈 것)\n' "${rows:-0}"

  [ "$code" = "200" ] && [ "${rows:-0}" -gt 0 ] && return 0
  return 1
}

wait_healthy() {
  # 재기동하면 bge-m3 임베딩 모델을 다시 로드한다(캐시가 있어도 수십 초).
  # 이걸 안 기다리고 바로 curl 하면 멀쩡한 배포를 실패로 오해한다.
  printf '⏳ 헬스 대기'
  for _ in $(seq 1 60); do
    if curl -s -m 5 "$API/health" 2>/dev/null | grep -q '"database":"healthy"'; then
      printf ' ✅\n'; return 0
    fi
    printf '.'; sleep 5
  done
  printf ' ❌ (3분 초과)\n'
  echo "   로그 확인: ./vm.sh logs 80" >&2
  return 1
}

case "${1:-health}" in
  health)
    health && echo "✅ 정상" || { echo "❌ 이상 — ./vm.sh status 로 VM 안을 볼 것" >&2; exit 1; }
    ;;

  status)
    echo "── 서비스 ──"
    vm 'systemctl is-active midas-backend caddy postgresql neo4j 2>&1 | paste -d" " - - - - \
        | xargs printf "backend=%s caddy=%s postgres=%s neo4j=%s\n"'
    echo "── 메모리 ──"
    vm 'free -h | sed -n 2p'
    echo "── 배포된 커밋 ──"
    vm "cd $APP_DIR && git log --oneline -1 && git status --porcelain | head -3"
    echo "── 밖에서 보는 상태 ──"
    health
    ;;

  deploy)
    echo "── 로컬 main 과 대조 ──"
    git fetch -q origin main 2>/dev/null
    echo "origin/main: $(git rev-parse --short origin/main)"
    echo "VM        : $(vm "cd $APP_DIR && git rev-parse --short HEAD")"

    echo "── pull + 의존성 ──"
    # uv sync 는 lock 이 안 바뀌었으면 몇 초에 끝난다. 바뀌었을 때만 오래 걸린다.
    vm "cd $APP_DIR && git pull --ff-only && $UV sync" || { echo "❌ pull/sync 실패" >&2; exit 1; }

    echo "── 재기동 ──"
    vm 'sudo -n systemctl restart midas-backend' || { echo "❌ 재기동 실패" >&2; exit 1; }
    wait_healthy || exit 1
    health
    ;;

  restart)
    vm 'sudo -n systemctl restart midas-backend' || { echo "❌ 재기동 실패" >&2; exit 1; }
    wait_healthy || exit 1
    health
    ;;

  logs)
    if [ "${2:-}" = "-f" ]; then
      vm -t 'sudo -n journalctl -u midas-backend -f'
    else
      vm "sudo -n journalctl -u midas-backend -n ${2:-50} --no-pager"
    fi
    ;;

  errors)
    # 대소문자를 구분한다. -i 로 하면 INFO 로그의 `'errors': 0` 같은 필드명까지 걸려
    # 정상 라인이 에러로 둔갑한다(실제로 겪음).
    # 파이프 끝의 tail 이 항상 0 을 반환해서 `|| echo` 는 안 먹는다 — 출력으로 판단한다.
    out="$(vm 'sudo -n journalctl -u midas-backend --since "24 hours ago" --no-pager \
        | grep -E "ERROR|CRITICAL|Traceback|Killed process|[Oo]ut of memory" | tail -40')"
    [ -n "$out" ] && echo "$out" || echo "✅ 최근 24시간 에러 없음"
    ;;

  autodeploy)
    # 자동배포는 VM이 GitHub를 2분마다 폴링하는 방식이다(pull). Actions에서 ssh로
    # 밀어넣지 않는 이유는 infra/vm-autodeploy.sh 주석 참고 — 요약하면 셸이 열리는
    # 키를 레포 시크릿에 두게 되는데 이 VM은 DB도 같이 돌린다.
    case "${2:-status}" in
      install)
        vm "cd $APP_DIR && sudo -n cp infra/midas-autodeploy.service infra/midas-autodeploy.timer /etc/systemd/system/ \
            && sudo -n systemctl daemon-reload \
            && sudo -n systemctl enable --now midas-autodeploy.timer" \
          && echo "✅ 자동배포 설치·기동" || { echo "❌ 설치 실패" >&2; exit 1; }
        vm 'systemctl list-timers midas-autodeploy.timer --no-pager | head -2'
        ;;
      on)
        vm 'sudo -n systemctl enable --now midas-autodeploy.timer' && echo "✅ 자동배포 ON"
        ;;
      off)
        # 심사 중엔 꺼두는 게 낫다 — 재기동이 심사자 채팅 한복판에 떨어질 수 있다.
        vm 'sudo -n systemctl disable --now midas-autodeploy.timer' && echo "⏸️  자동배포 OFF (배포는 ./vm.sh deploy 로 수동)"
        ;;
      status)
        vm 'systemctl is-enabled midas-autodeploy.timer 2>/dev/null || echo "미설치"'
        vm 'systemctl list-timers midas-autodeploy.timer --no-pager 2>/dev/null | head -2'
        ;;
      log)
        vm "sudo -n journalctl -u midas-autodeploy -n ${3:-40} --no-pager"
        ;;
      *)
        echo "사용법: ./vm.sh autodeploy [install|on|off|status|log [N]]" >&2; exit 1 ;;
    esac
    ;;

  *)
    echo "사용법: ./vm.sh [health|status|deploy|restart|logs [N|-f]|errors|autodeploy <cmd>]" >&2
    exit 1
    ;;
esac

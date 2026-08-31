#!/usr/bin/env bash
#
# vm-autodeploy.sh — VM이 GitHub를 폴링해서 main 이 움직이면 스스로 배포한다.
#
# 왜 pull 방식인가: GitHub Actions 에서 ssh 로 밀어넣으려면 셸이 열리는 SSH 키를
# 레포 시크릿에 넣어야 한다. 이 VM 은 DB 도 같이 돌리므로, main 에 푸시 가능한 사람과
# 워크플로에 섞인 서드파티 액션이 전부 DB 호스트의 셸을 얻는다. pull 은 시크릿도
# 새 인바운드 통로도 필요 없다(레포가 공개라 git pull 에 인증이 없다).
#
# 설치·조작은 맥에서: ./vm.sh autodeploy install|on|off|status|log
#
# 안전장치 3개:
#   1) CI 통과한 커밋만 배포한다. 2026-08-31 에 main 룰셋에도 required_status_checks
#      를 걸었으니 이제 이중 방어다. 그래도 남겨 두는 이유 — 룰셋은 레포 설정이라
#      누가 끄면 조용히 사라지고, 여기 게이트는 코드라 지우면 diff 에 남는다.
#   2) 백엔드와 무관한 변경(문서·프론트)이면 pull 만 하고 재기동하지 않는다.
#      재기동은 bge-m3 재로드로 수십 초 죽는다 — 문서 오타 하나에 낼 비용이 아니다.
#   3) 재기동 후 헬스가 안 오면 직전 커밋으로 되돌리고 다시 띄운다.
#      깨진 코드가 올라가도 스스로 복구한다.

set -uo pipefail

REPO_DIR="${REPO_DIR:-/home/ubuntu/midas-touch}"
UV="${UV:-/home/ubuntu/.local/bin/uv}"
BRANCH=main
API="https://api.github.com/repos/Jacob-9909/midas-touch"
HEALTH="http://127.0.0.1:8000/health"

log() { printf '%s | %s\n' "$(date '+%F %T')" "$*"; }

# 타이머가 겹쳐 들어와 pull 중에 재기동하는 사고를 막는다.
exec 9>/tmp/midas-autodeploy.lock
flock -n 9 || { log "이전 실행이 아직 도는 중 — 건너뜀"; exit 0; }

cd "$REPO_DIR" || { log "❌ $REPO_DIR 없음"; exit 1; }

git fetch -q origin "$BRANCH" || { log "❌ git fetch 실패(네트워크?)"; exit 1; }

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"
[ "$LOCAL" = "$REMOTE" ] && exit 0          # 변화 없음 — 조용히 끝낸다(로그 안 더럽힘)

log "새 커밋 감지: ${LOCAL:0:7} → ${REMOTE:0:7}"

# ── 1) CI 게이트 ────────────────────────────────────────────────
# 공개 레포라 인증 없이 조회된다. 아직 도는 중이면 다음 틱에서 다시 본다.
#
# 백엔드 CI 체크 하나만 본다. "실패한 체크가 하나라도 있으면 거부"로 하면 나중에
# 다른 체크(Vercel 배포 등)가 붙었을 때 백엔드와 무관한 이유로 영영 안 뜬다.
CHECKS="$(curl -s -m 20 -H 'Accept: application/vnd.github+json' "$API/commits/$REMOTE/check-runs")"
GATE="$(printf '%s' "$CHECKS" \
  | jq -r '.check_runs[]? | select(.name | startswith("backend")) | "\(.status):\(.conclusion)"' 2>/dev/null | head -1)"

case "$GATE" in
  completed:success) ;;                                   # 통과 — 계속
  "")                log "⏳ 백엔드 CI 아직 없음 — 보류"; exit 0 ;;
  completed:*)       log "❌ 백엔드 CI ${GATE#completed:} — ${REMOTE:0:7} 배포하지 않는다"; exit 0 ;;
  *)                 log "⏳ 백엔드 CI 진행 중($GATE) — 보류"; exit 0 ;;
esac

# ── 2) 백엔드와 상관있는 변경인가 ────────────────────────────────
CHANGED="$(git diff --name-only "$LOCAL" "$REMOTE")"
git pull -q --ff-only origin "$BRANCH" || { log "❌ pull 실패(로컬 변경 있음?)"; exit 1; }

if printf '%s' "$CHANGED" | grep -q '^infra/midas-backend.service$'; then
  log "⚠️  systemd 유닛이 바뀌었다 — 자동 적용하지 않는다. VM에서 직접:"
  log "    sudo cp infra/midas-backend.service /etc/systemd/system/ && sudo systemctl daemon-reload"
fi

if ! printf '%s' "$CHANGED" | grep -qE '^(backend/|shared/|pipelines/|alembic/|pyproject\.toml|uv\.lock)'; then
  log "✅ pull 완료 — 백엔드 무관 변경(문서·프론트)이라 재기동 생략"
  exit 0
fi

# ── 3) 배포 + 실패 시 롤백 ──────────────────────────────────────
log "백엔드 변경 있음 — uv sync"
"$UV" sync -q || log "⚠️  uv sync 경고(계속 진행)"

restart_and_wait() {
  sudo -n systemctl restart midas-backend || return 1
  for _ in $(seq 1 40); do            # 최대 200초 — 모델 로드 감안
    sleep 5
    curl -s -m 5 "$HEALTH" 2>/dev/null | grep -q '"database":"healthy"' && return 0
  done
  return 1
}

if restart_and_wait; then
  log "✅ 배포 완료: $(git log --oneline -1)"
  exit 0
fi

log "❌ 재기동 후 헬스 실패 — ${LOCAL:0:7} 로 롤백"
git reset -q --hard "$LOCAL"
"$UV" sync -q
if restart_and_wait; then
  log "↩️  롤백 성공 — ${LOCAL:0:7} 로 복구됨. ${REMOTE:0:7} 은 배포되지 않았다."
else
  log "🚨 롤백 후에도 헬스 실패 — 사람이 봐야 한다. journalctl -u midas-backend -n 100"
fi
exit 1

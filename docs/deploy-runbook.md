# 배포 런북 — 2026 금융 AI Challenge

**공개 URL(심사 제출용)**: https://midas-touch-five.vercel.app
**API**: https://midas-touch.duckdns.org
**필수 가동 시간**: 2026-09-07 11:00 ~ 09-11 23:59 (연속 5일)

**구성(2026-08-30 결정)**: 프론트는 **Vercel**, 백엔드·DB는 **오라클 VM**(2 OCPU / 12GB, Ubuntu 22.04).
VM에는 Docker가 없고 **Postgres 17·Neo4j가 systemd 네이티브 서비스**로 돈다 — 백엔드도 컨테이너
없이 uv로 띄운다(이미지 빌드도, 컨테이너→호스트 DB 네트워킹도 필요 없다).

```
브라우저 ──HTTPS──> Vercel (Next.js 정적·SSR)
    └────HTTPS──> midas-touch.duckdns.org ─Caddy(TLS)─> backend:8000 ─┬─ postgres(pgvector)
                     (오라클 VM 161.33.134.252)            └─ neo4j
```

- 프론트는 `NEXT_PUBLIC_API_BASE`로 **백엔드를 직접** 호출한다. Vercel rewrites로 프록시하지 **않는다** —
  챗 한 턴이 2분 넘게 걸리는 경우가 있어 서버리스 함수 실행 시간 제한에 SSE가 잘릴 수 있다.
- 그래서 백엔드에 **도메인 + TLS가 필수**다. Vercel은 HTTPS라 브라우저가 `http://` 백엔드를 호출하지
  못하고(mixed content 차단), Let's Encrypt는 IP에 인증서를 발급하지 않는다.
- 노트북 상주(`caffeinate`)·ngrok 경고 페이지·터널 끊김이 이 구성에서 전부 사라진다.

> **이전 구성(로컬 맥 + ngrok)의 `expose.sh`·`keepalive.sh`는 2026-08-31에 지웠다.**
> 노트북이 아무것도 호스팅하지 않게 되면서 전제가 사라졌고, 재기동은 systemd 의
> `Restart=always` 가 맡는다. 운영은 `./vm.sh` 하나로 한다.

---

## 0. 사전 준비 (1회, VM 이전 시)

- [x] **도메인 확보** — `midas-touch.duckdns.org` (DuckDNS 무료 서브도메인)
- [ ] **A 레코드** `midas-touch.duckdns.org` → `161.33.134.252`
- [x] **VM 방화벽 80·443 open** (확인 완료). 오라클은 두 군데를 다 열어야 한다 —
      ① 콘솔의 VCN Security List(ingress 80/443) ② VM 안의 iptables/firewalld.
      **80을 닫으면 Let's Encrypt HTTP-01 챌린지가 실패해 인증서가 안 나온다.**
- [ ] VM에 `uv`, `caddy`, `git` 설치 (§1)
- [x] 레포 clone + `.env` 이관 + `CORS_ALLOW_ORIGINS` 설정 (2026-08-30 완료)
      (`.env`는 git에 없으므로 별도로 안전하게 전달할 것)

---

## 1. 백엔드 띄우기 (오라클 VM)

```bash
# ── 1) 도구 설치 ──────────────────────────────────────────
sudo apt-get update && sudo apt-get install -y git curl debian-keyring debian-archive-keyring apt-transport-https

# uv (파이썬 3.12+ 를 알아서 받아온다 — 시스템 파이썬 3.10 을 건드리지 않는다)
curl -LsSf https://astral.sh/uv/install.sh | sh

# caddy (공식 저장소)
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update && sudo apt-get install -y caddy

# ── 2) 레포 + .env ───────────────────────────────────────
cd ~ && git clone https://github.com/Jacob-9909/midas-touch.git
cd midas-touch
# .env 는 git 에 없다. 맥에서 scp 로 옮긴다:
#   scp .env ubuntu@161.33.134.252:~/midas-touch/.env
# 옮긴 뒤 VM 기준으로 고칠 값:
#   POSTGRES_HOST=localhost / DATABASE_URL 의 호스트 → localhost
#   NEO4J_URL=bolt://localhost:7687
#   CORS_ALLOW_ORIGINS=https://midas-touch-five.vercel.app,https://midas-touch-cj0336j-gmailcoms-projects.vercel.app,http://localhost:3000
chmod 600 .env

# ── 3) 의존성 (torch 때문에 5~10분) ───────────────────────
~/.local/bin/uv sync

# ── 4) 서비스 등록 ───────────────────────────────────────
sudo cp infra/midas-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now midas-backend

sudo cp infra/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

첫 기동은 bge-m3 임베딩 모델(약 2.3GB) 다운로드 때문에 **5~10분** 걸린다. 유닛의
`TimeoutStartSec=600`이 그 시간을 벌어 준다.

```bash
# 백엔드 로그 (모델 로딩 → Uvicorn running 까지)
sudo journalctl -u midas-backend -f

# 인증서 발급 로그 (실패하면 여기 이유가 찍힌다)
sudo journalctl -u caddy -f

# 헬스체크
curl -s https://midas-touch.duckdns.org/health
# → {"status":"healthy","database":"healthy","neo4j":"healthy","neo4j_url":"bolt://..."}
#   status 는 둘 다 살았을 때만 healthy, 하나라도 죽으면 degraded(코드는 계속 200).
```

**메모리(12GB, 실측 사용 3.2GB / 여유 6.6GB)**: Postgres·Neo4j가 이미 3.2GB를 쓰고 있어
백엔드에 `MemoryMax=6G`를 걸어 뒀다. 상한이 없으면 모델 로딩 중 커널이 **DB를 골라 죽일 수도**
있다 — 상한을 걸면 초과 시 백엔드만 정리된다.

```bash
free -h
systemctl show midas-backend -p MemoryCurrent
```

> 모델 로딩 중 OOM이 반복되면 스왑 4GB를 붙이는 게 가장 싸다(디스크 181GB 여유):
> ```bash
> sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
> sudo mkswap /swapfile && sudo swapon /swapfile
> echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
> ```

### 이후 재배포 (코드가 바뀌었을 때)

위 §1은 최초 1회다. 그 다음부터는 맥에서 한 줄이다.

```bash
./vm.sh deploy     # git pull --ff-only → uv sync → 재기동 → 헬스 초록 될 때까지 대기
```

재기동하면 bge-m3 를 다시 로드하느라 수십 초 응답이 없다. `vm.sh` 가 `database: healthy`
가 뜰 때까지 기다렸다가 결과를 보여주므로, **바로 curl 해서 실패로 오해하지 말 것.**

### 자동배포 (2026-08-31~)

VM 이 2분마다 main 을 폴링해서 스스로 배포한다. **수동 `./vm.sh deploy` 는 이제 급할 때만
쓰면 된다.** push 가 아니라 pull 인 이유는 `infra/vm-autodeploy.sh` 주석에 있다 — 요약하면
Actions 에서 ssh 로 밀어넣으려면 셸이 열리는 키를 레포 시크릿에 둬야 하는데 이 VM 은 DB 도
같이 돌린다.

```bash
./vm.sh autodeploy status      # 타이머 상태
./vm.sh autodeploy log 40      # 무슨 일이 있었나
./vm.sh autodeploy off         # 심사 기간엔 꺼두길 권장
./vm.sh autodeploy on
```

안전장치 3개:

| 장치 | 막는 것 |
|---|---|
| CI 게이트 | 백엔드 CI 가 통과한 커밋만 배포. main 룰셋의 `required_status_checks`(2026-08-31 추가)와 **이중 방어** — 룰셋은 레포 설정이라 누가 끄면 조용히 사라지지만 이 게이트는 코드라 지우면 diff 에 남는다 |
| 변경 범위 판정 | 문서·프론트만 바뀌면 pull 만 하고 재기동 생략(재기동 = 수십 초 다운) |
| 롤백 | 재기동 후 헬스가 안 오면 직전 커밋으로 되돌리고 다시 띄운다 |

> **심사 기간(9/7~9/11)엔 `./vm.sh autodeploy off` 를 권한다.** 재기동이 심사자 채팅
> 한복판에 떨어질 수 있다. 그동안 배포가 필요하면 `./vm.sh deploy` 로 타이밍을 골라서 한다.

> `infra/midas-backend.service`(systemd 유닛)가 바뀐 경우는 **자동 적용하지 않는다.**
> 로그로만 알리므로 VM 에서 직접 `sudo cp` + `daemon-reload` 할 것.

---

## 2. 프론트 띄우기 (Vercel)

프로젝트 설정:

프로젝트는 이미 연결돼 있다(`vercel link` 완료, 프로젝트명 `midas-touch`).
`frontend/`에서 `vercel --prod --yes` 하면 재배포된다.

| 항목 | 값 | 현재 |
|---|---|---|
| Root Directory | `frontend` | ✅ (2026-08-31 `.` → `frontend` 수정) |
| Framework | Next.js (자동 감지) | ✅ |
| Build Command | 기본값 | ✅ |

> **Root Directory 는 대시보드 Settings → Build and Deployment 에 있다**(General 이 아니다).
> 2026-08-31 이전엔 `.` 이었는데, `frontend/` 안에서 `vercel --prod` 를 돌리면 CLI 가
> 그 디렉터리를 배포 루트로 업로드해서 **CLI 배포만으로는 안 깨졌다.** git 연동은
> 레포 루트에서 빌드하므로 `.` 인 채로 켰으면 루트에 `package.json` 이 없어 깨졌을 것이다
> — 사이트는 기존 배포로 살아 있고 자동배포만 조용히 안 되는, 늦게 발견되는 형태로.

환경변수 (Production + Preview 양쪽):

```
NEXT_PUBLIC_API_BASE=https://midas-touch.duckdns.org
NEXT_PUBLIC_AUTH_ENABLED=true
```

> ⚠️ Preview 환경변수는 CLI(54.6.1)가 `--yes`를 줘도 계속 브랜치를 물어 등록에 실패한다.
> 어차피 preview URL은 배포마다 오리진이 달라 CORS에 막히므로, **심사에는 프로덕션 도메인만** 쓴다.
>
> `NEXT_PUBLIC_*`은 **빌드 타임에 번들에 박힌다.** 값을 바꾸면 반드시 재배포해야 반영된다.
> 로컬 `frontend/.env.local`은 `NEXT_PUBLIC_API_BASE=`(빈 값)로 두어 rewrites 프록시를 계속 쓴다.

### 배포 방법 (현재: 수동)

**레포에 Vercel git 연동이 안 걸려 있다(웹훅 없음).** main 에 머지해도 프론트는
자동 배포되지 않는다 — 실제로 2026-08-31 에 #57 의 UI 개선이 하루 동안 심사자
화면에 안 반영된 채로 있었다. 프론트를 고쳤으면 **반드시** 아래를 직접 돌릴 것:

```bash
cd frontend && vercel --prod --yes      # 반드시 frontend/ 안에서
```

자동화하려면 ① Vercel 대시보드 → Settings → Git 에서 레포 연결(GitHub App 인가
필요) ② **그 전에** Root Directory 를 `frontend` 로 변경. 순서를 바꾸면 빌드가 깨진다.

배포 후 백엔드 `.env`의 `CORS_ALLOW_ORIGINS`에 **실제 Vercel 도메인**을 넣고 백엔드를 재기동한다.
이걸 빼먹으면 화면은 뜨는데 모든 API가 CORS로 막혀 빈 화면처럼 보인다.

```bash
./vm.sh restart    # 맥에서. (VM 안이면 sudo systemctl restart midas-backend)
```

---

## 3. 살아있는지 확인 (심사 기간 중 매일 1회)

```bash
./vm.sh health     # 프론트 + /health + DB 의존 엔드포인트를 한 번에
./vm.sh status     # 위에 더해 VM 안(서비스 4개·메모리·배포된 커밋)까지
./vm.sh errors     # 최근 24시간 에러만
```

**프론트 200만 보고 안심하면 안 된다.** DB가 죽어도 앱은 200을 반환하며 graceful degrade 하기
때문에 겉은 멀쩡하고 속만 빈 상태가 된다(실제로 배포 중 한 번 겪음). 반드시 DB 의존
엔드포인트까지 확인할 것.

---

## 4. 알려진 취약점과 대응

| 위험 | 증상 | 대응 |
|---|---|---|
| 인증서 발급 실패 | `https://midas-touch.duckdns.org` 접속 불가, Caddy 로그에 챌린지 실패 | 80 포트 개방(VCN + OS 방화벽 양쪽)과 A 레코드 전파 확인 |
| CORS 누락 | 화면은 뜨는데 데이터가 전부 빔, 콘솔에 CORS 에러 | `CORS_ALLOW_ORIGINS`에 Vercel 도메인 추가 후 backend 재기동 |
| Vercel 프리뷰 도메인 | 프리뷰 URL마다 오리진이 달라 CORS에 막힘 | 심사에는 **프로덕션 도메인**을 제출하고 그 오리진만 고정 허용 |
| `NEXT_PUBLIC_*` 미반영 | 값은 바꿨는데 동작이 그대로 | 빌드 타임 주입이라 재배포 필요 |
| **env 값에 주석이 섞임** | `/health`는 초록인데 챗·임베딩만 깨짐. 로그에 `cache warm failed (embedding)` | systemd `EnvironmentFile`은 값 뒤 `#` 주석을 자르지 않는다. 유닛은 `uv run --env-file .env`를 쓰도록 돼 있으니 되돌리지 말 것. 확인: `sudo tr '\0' '\n' < /proc/$(pgrep -f 'uvicorn backend')/environ \| grep AGENT_LLM_MODEL` |
| OOM | 백엔드가 조용히 재시작 반복 | `journalctl -u midas-backend | grep -i oom`, 유닛의 `MemoryMax` 조정 또는 스왑 추가(§1) |
| 인증서 유실 | 재발급 시도 → Let's Encrypt rate limit | `/var/lib/caddy` 를 지우지 말 것 |
| PR 이 머지 안 됨 | "Required statuses must pass" | 2026-08-31 부터 main 룰셋이 `backend (ruff + pytest)`·`frontend (eslint + tsc)` 통과를 요구한다. CI 를 고쳐서 통과시킬 것 — 급하면 룰셋에서 잠시 해제(설정 → Rules → protect) |
| 로컬에서 DB가 안 붙음 | `./dev.sh` 는 떴는데 청약·주식이 전부 빔, 기동 로그에 `DB 터널 실패` | DB 포트(5432·7687)는 VM 방화벽에서 막혀 있고 로컬은 SSH 터널로만 붙는다. `./db-tunnel.sh` 수동 실행 → 실패하면 `ssh oracle_vm 'echo ok'` 로 SSH 자체를 먼저 확인 |
| 심사용 체험 계정 | 심사자가 로그인 못 함 | `/login` 화면의 `demo@midas.touch` 계정이 **배포 DB에** 있는지 확인 |

---

## 5. 심사 기간 체크리스트

**9/7 제출 직전**
- [ ] 제출 URL = Vercel **프로덕션** 도메인인지 확인(프리뷰 URL 제출 금지)
- [ ] **프론트가 최신 main 인지** — git 연동이 없으면 자동배포가 안 된다.
      `cd frontend && vercel ls | head -3` 의 배포 시각이 마지막 프론트 머지보다 뒤인지
- [ ] `/health`가 `database: healthy`인지
- [ ] 새 시크릿창으로 처음부터 밟아보기 (§6)
- [ ] 체험 계정으로 실제 로그인되는지
- [ ] `./vm.sh status` 로 서비스 4개·메모리 여유 확인

**9/7 ~ 9/11 매일**
- [ ] `./vm.sh health` 1회
- [ ] `./vm.sh errors` (최근 24시간 에러)

---

## 6. 심사자 동선 재현 (제출 전 필수)

시크릿창에서 공개 URL로 접속 후 — 기능명세서 검증 절차와 동일하다. 괄호가 실측값이다.

1. `/login` — **"체험 계정으로 바로 시작"** 한 번에 랜딩 도달
2. `/` — 히어로가 "피싱·환각·틀린 세법 답변 한 번에 잡는 AI 보안 비서".
   우측 카드의 청약가점 예시가 **15년 +32 / 4명 +25 / 15년 +17 = 74**로 합이 맞는지
3. "사기 검증 먼저 체험하기" → `/chat` — 판정 **위험(90점)**, 행동 요령에
   **"저장돼 있던 번호로 확인"**(재다이얼 안내가 아님), 말미에 **5겹 방어 증명 카드(5줄)**.
   토큰이 한 글자씩 흘러야 함(뭉텅이로 오면 SSE 버퍼링 재발 — §7)
4. `/security` — 프리셋 "시스템 프롬프트 추출" 발사 → 내부 설정 미공개 + 한국어 거절
5. `/cheongyak` — 상단 KPI "실시간 분양 공고"와 하단 지도 뱃지 **숫자가 일치**해야 함(둘 다 108건 류).
   기본 가점 **20/84**, "만 30세 미만이면서 미혼" 체크 시 **12/84** + 무주택칸 비활성
6. 공고 선택 → 상세 → 당첨가점 표에 "내 점수 대비" 열 → "이 청약으로 자금계획 세우기"
7. `/simulator` — 목표 4,000만/자산 2,000만/월 60만/3.5% vs 6.0%에서 **30개월 vs 27개월, 3개월 단축**

---

## 7. 트러블슈팅

**챗봇이 아무것도 안 뱉는다**
SSE가 어딘가에서 버퍼링되는 것이다. 앞단부터 하나씩 벗겨 격리한다.

```bash
# ① 백엔드 직접 (VM 안에서)
curl -sN -X POST http://127.0.0.1:8000/api/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"t","message":"청약 가점이 뭔가요?","user_uuid":"e7926df30b8f48c09b33684f3075f60f"}' | head -c 200

# ② Caddy 경유
curl -sN -X POST https://midas-touch.duckdns.org/api/v1/chat/stream -H 'Content-Type: application/json' \
  -d '{"session_id":"t","message":"청약 가점이 뭔가요?","user_uuid":"e7926df30b8f48c09b33684f3075f60f"}' | head -c 200
```

①은 나오는데 ②가 안 나오면 Caddy 설정이다 — `infra/Caddyfile`의 `flush_interval -1`과
`text/event-stream`을 `encode`에서 제외한 부분이 살아 있는지 확인.
로컬(같은 오리진)에서만 재현되면 `frontend/next.config.ts`의 `compress: false`를 확인한다.

**화면은 뜨는데 데이터가 전부 비어 있다**
브라우저 콘솔에 CORS 에러가 있는지 먼저 본다. 있으면 `CORS_ALLOW_ORIGINS` 문제(§4).
없으면 DB가 내려간 것:
```bash
curl -s https://midas-touch.duckdns.org/health
systemctl status midas-backend postgresql neo4j --no-pager | head -30
```

**청약 목록이 비어 있다**
공공데이터 API(api.odcloud.kr) 점검일 수 있다. `CHEONGYAK_API_KEY` 확인:
```bash
curl -s "https://midas-touch.duckdns.org/api/v1/cheongyak/list/apt" | head -c 200
```

**전부 재기동**
```bash
sudo systemctl restart midas-backend caddy
sudo journalctl -u midas-backend -n 50 --no-pager
```

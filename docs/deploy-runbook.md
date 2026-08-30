# 배포 런북 — 2026 금융 AI Challenge

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

> **이전 구성(로컬 맥 + ngrok)**은 `expose.sh` / `keepalive.sh`로 그대로 남아 있다.
> VM 이전이 심사 전에 안 끝나면 §6 폴백으로 되돌아갈 수 있다.

---

## 0. 사전 준비 (1회, VM 이전 시)

- [x] **도메인 확보** — `midas-touch.duckdns.org` (DuckDNS 무료 서브도메인)
- [ ] **A 레코드** `midas-touch.duckdns.org` → `161.33.134.252`
- [x] **VM 방화벽 80·443 open** (확인 완료). 오라클은 두 군데를 다 열어야 한다 —
      ① 콘솔의 VCN Security List(ingress 80/443) ② VM 안의 iptables/firewalld.
      **80을 닫으면 Let's Encrypt HTTP-01 챌린지가 실패해 인증서가 안 나온다.**
- [ ] VM에 `uv`, `caddy`, `git` 설치 (§1)
- [ ] 레포 clone + `.env`를 VM으로 옮기고 `CORS_ALLOW_ORIGINS` 채우기
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
#   CORS_ALLOW_ORIGINS=https://<vercel-도메인>
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
# → {"status":"healthy","database":"healthy","neo4j":"bolt://..."}
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

## 2. 프론트 띄우기 (Vercel)

프로젝트 설정:

| 항목 | 값 |
|---|---|
| Root Directory | `frontend` |
| Framework | Next.js (자동 감지) |
| Build Command | 기본값 |

환경변수 (Production + Preview 양쪽):

```
NEXT_PUBLIC_API_BASE=https://midas-touch.duckdns.org
NEXT_PUBLIC_AUTH_ENABLED=true
```

> `NEXT_PUBLIC_*`은 **빌드 타임에 번들에 박힌다.** 값을 바꾸면 반드시 재배포해야 반영된다.
> 로컬 `frontend/.env.local`은 `NEXT_PUBLIC_API_BASE=`(빈 값)로 두어 rewrites 프록시를 계속 쓴다.

배포 후 백엔드 `.env`의 `CORS_ALLOW_ORIGINS`에 **실제 Vercel 도메인**을 넣고 백엔드를 재기동한다.
이걸 빼먹으면 화면은 뜨는데 모든 API가 CORS로 막혀 빈 화면처럼 보인다.

```bash
sudo systemctl restart midas-backend
```

---

## 3. 살아있는지 확인 (심사 기간 중 매일 1회)

```bash
F=https://<vercel-도메인>
A=https://midas-touch.duckdns.org

curl -s -o /dev/null -w "front %{http_code}\n" "$F"
curl -s "$A/health"
curl -s "$A/api/v1/cheongyak/list/apt" | head -c 120   # 외부 API까지 살았는지
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
| OOM | 백엔드가 조용히 재시작 반복 | `journalctl -u midas-backend | grep -i oom`, 유닛의 `MemoryMax` 조정 또는 스왑 추가(§1) |
| 인증서 유실 | 재발급 시도 → Let's Encrypt rate limit | `/var/lib/caddy` 를 지우지 말 것 |
| 심사용 체험 계정 | 심사자가 로그인 못 함 | `/login` 화면의 `demo@midas.touch` 계정이 **배포 DB에** 있는지 확인 |

---

## 5. 심사 기간 체크리스트

**9/7 제출 직전**
- [ ] 제출 URL = Vercel **프로덕션** 도메인인지 확인(프리뷰 URL 제출 금지)
- [ ] `/health`가 `database: healthy`인지
- [ ] 새 시크릿창으로 처음부터 밟아보기 (§6)
- [ ] 체험 계정으로 실제 로그인되는지
- [ ] `free -h` 로 메모리 여유 확인

**9/7 ~ 9/11 매일**
- [ ] §3 헬스체크 1회
- [ ] `sudo journalctl -u midas-backend --since '24 hours ago' | grep -i error | head`

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

**폴백(VM 이전이 안 끝났을 때)**: 기존 ngrok 경로가 그대로 산다.
```bash
./expose.sh
caffeinate -dimsu env PUBLIC_URL=https://gathering-disliking-hypnoses.ngrok-free.dev ./keepalive.sh
```
단 무료 티어의 "You are about to visit…" 인터스티셜을 심사자가 먼저 보게 된다 —
금융 서비스 심사에서 특히 불리하므로 폴백으로만 쓴다.

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

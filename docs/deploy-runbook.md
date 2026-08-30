# 배포 런북 — 2026 금융 AI Challenge

**필수 가동 시간**: 2026-09-07 11:00 ~ 09-11 23:59 (연속 5일)

**구성(2026-08-30 결정)**: 프론트는 **Vercel**, 백엔드·DB는 **오라클 VM**(2 OCPU / 12GB).

```
브라우저 ──HTTPS──> Vercel (Next.js 정적·SSR)
    └────HTTPS──> api.<도메인> ─Caddy(TLS)─> backend:8000 ─┬─ postgres(pgvector)
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

- [ ] **도메인 확보**. 서브도메인 하나면 된다(예: `api.midas-touch.xyz`).
      보유 도메인이 없으면 DuckDNS 같은 무료 서브도메인도 Caddy DNS 챌린지로 발급 가능.
- [ ] **A 레코드** `api.<도메인>` → `161.33.134.252`
- [ ] **VM 방화벽 80·443 open**. 오라클은 두 군데를 다 열어야 한다 —
      ① 콘솔의 VCN Security List(ingress 80/443) ② VM 안의 iptables/firewalld.
      **80을 닫으면 Let's Encrypt HTTP-01 챌린지가 실패해 인증서가 안 나온다.**
- [ ] VM에 Docker + Compose v2 설치
- [ ] 레포와 `.env`를 VM으로 옮기고 `API_DOMAIN`, `CORS_ALLOW_ORIGINS` 채우기
      (`.env`는 git에 없으므로 별도로 안전하게 전달할 것)

---

## 1. 백엔드 띄우기 (오라클 VM)

```bash
cd ~/midas-touch/infra

# base + VM 오버레이. 오버레이가 하는 일:
#   Caddy(TLS) 추가 / DB 포트 외부 노출 차단 / 12GB 상자 기준 메모리 상한
docker compose --env-file ../.env \
  -f docker-compose.yml -f docker-compose.vm.yml up -d --build
```

첫 기동은 이미지 빌드(torch 때문에 수 GB)와 bge-m3 모델 다운로드로 **10~20분** 걸릴 수 있다.

```bash
# 인증서 발급 로그 확인 (실패하면 여기 이유가 찍힌다)
docker logs -f midas-caddy | head -40

# 헬스체크
curl -s https://api.<도메인>/health
# → {"status":"healthy","database":"healthy","neo4j":"bolt://..."}
```

**메모리 배분(12GB)**: backend 6G(임베딩 모델이 프로세스 안에서 torch로 로드) / neo4j 3G /
postgres 1.5G / 나머지 OS·페이지캐시. 상한을 안 박으면 Neo4j가 힙을 크게 잡아 백엔드가
모델 로딩 중 OOM으로 죽는다 — 오버레이에 못 박아 뒀다.

```bash
docker stats --no-stream   # 실제 사용량 확인
```

---

## 2. 프론트 띄우기 (Vercel)

프로젝트 설정:

| 항목 | 값 |
|---|---|
| Root Directory | `frontend` |
| Framework | Next.js (자동 감지) |
| Build Command | 기본값 |

환경변수 (Production + Preview 양쪽):

```
NEXT_PUBLIC_API_BASE=https://api.<도메인>
NEXT_PUBLIC_AUTH_ENABLED=true
```

> `NEXT_PUBLIC_*`은 **빌드 타임에 번들에 박힌다.** 값을 바꾸면 반드시 재배포해야 반영된다.
> 로컬 `frontend/.env.local`은 `NEXT_PUBLIC_API_BASE=`(빈 값)로 두어 rewrites 프록시를 계속 쓴다.

배포 후 백엔드 `.env`의 `CORS_ALLOW_ORIGINS`에 **실제 Vercel 도메인**을 넣고 백엔드를 재기동한다.
이걸 빼먹으면 화면은 뜨는데 모든 API가 CORS로 막혀 빈 화면처럼 보인다.

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.vm.yml up -d backend
```

---

## 3. 살아있는지 확인 (심사 기간 중 매일 1회)

```bash
F=https://<vercel-도메인>
A=https://api.<도메인>

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
| 인증서 발급 실패 | `https://api.<도메인>` 접속 불가, Caddy 로그에 챌린지 실패 | 80 포트 개방(VCN + OS 방화벽 양쪽)과 A 레코드 전파 확인 |
| CORS 누락 | 화면은 뜨는데 데이터가 전부 빔, 콘솔에 CORS 에러 | `CORS_ALLOW_ORIGINS`에 Vercel 도메인 추가 후 backend 재기동 |
| Vercel 프리뷰 도메인 | 프리뷰 URL마다 오리진이 달라 CORS에 막힘 | 심사에는 **프로덕션 도메인**을 제출하고 그 오리진만 고정 허용 |
| `NEXT_PUBLIC_*` 미반영 | 값은 바꿨는데 동작이 그대로 | 빌드 타임 주입이라 재배포 필요 |
| OOM | 백엔드가 조용히 재시작 반복 | `docker stats` 확인, 오버레이의 메모리 상한 조정 |
| 인증서 볼륨 유실 | 재발급 시도 → Let's Encrypt rate limit | `caddy_data` 볼륨을 지우지 말 것 |
| 심사용 체험 계정 | 심사자가 로그인 못 함 | `/login` 화면의 `demo@midas.touch` 계정이 **배포 DB에** 있는지 확인 |

---

## 5. 심사 기간 체크리스트

**9/7 제출 직전**
- [ ] 제출 URL = Vercel **프로덕션** 도메인인지 확인(프리뷰 URL 제출 금지)
- [ ] `/health`가 `database: healthy`인지
- [ ] 새 시크릿창으로 처음부터 밟아보기 (§6)
- [ ] 체험 계정으로 실제 로그인되는지
- [ ] `docker stats`로 메모리 여유 확인

**9/7 ~ 9/11 매일**
- [ ] §3 헬스체크 1회
- [ ] `docker logs --since 24h midas-backend | grep -i error | head`

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
# ① 백엔드 직접 (컨테이너 안)
docker exec midas-backend curl -sN -X POST http://localhost:8000/api/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"t","message":"청약 가점이 뭔가요?","user_uuid":"e7926df30b8f48c09b33684f3075f60f"}' | head -c 200

# ② Caddy 경유
curl -sN -X POST https://api.<도메인>/api/v1/chat/stream -H 'Content-Type: application/json' \
  -d '{"session_id":"t","message":"청약 가점이 뭔가요?","user_uuid":"e7926df30b8f48c09b33684f3075f60f"}' | head -c 200
```

①은 나오는데 ②가 안 나오면 Caddy 설정이다 — `infra/Caddyfile`의 `flush_interval -1`과
`text/event-stream`을 `encode`에서 제외한 부분이 살아 있는지 확인.
로컬(같은 오리진)에서만 재현되면 `frontend/next.config.ts`의 `compress: false`를 확인한다.

**화면은 뜨는데 데이터가 전부 비어 있다**
브라우저 콘솔에 CORS 에러가 있는지 먼저 본다. 있으면 `CORS_ALLOW_ORIGINS` 문제(§4).
없으면 DB가 내려간 것:
```bash
curl -s https://api.<도메인>/health
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.vm.yml ps
```

**청약 목록이 비어 있다**
공공데이터 API(api.odcloud.kr) 점검일 수 있다. `CHEONGYAK_API_KEY` 확인:
```bash
curl -s "https://api.<도메인>/api/v1/cheongyak/list/apt" | head -c 200
```

**전부 재기동**
```bash
cd ~/midas-touch/infra
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.vm.yml restart
```

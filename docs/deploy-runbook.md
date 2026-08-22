# 배포 런북 — 2026 금융 AI Challenge

**공개 URL**: https://gathering-disliking-hypnoses.ngrok-free.dev
**필수 가동 시간**: 2026-09-07 11:00 ~ 09-11 23:59 (연속 5일)
**방식**: 로컬 맥에서 `expose.sh`(프로덕션 빌드 + ngrok 터널), `keepalive.sh`가 감시·자동복구

---

## 1. 띄우기

```bash
cd ~/Develop/midas-touch

# 스택 기동 (프론트 빌드 → 백엔드/프론트 → ngrok)
./expose.sh

# 별도 터미널에서 워치독 (절전 방지까지 같이)
caffeinate -dimsu env PUBLIC_URL=https://gathering-disliking-hypnoses.ngrok-free.dev ./keepalive.sh
```

`expose.sh`가 마지막에 공개 URL을 출력한다. `SKIP_BUILD=1 ./expose.sh`면 프론트 재빌드를 건너뛴다.

## 2. 살아있는지 확인 (심사 기간 중 매일 1회 권장)

```bash
U=https://gathering-disliking-hypnoses.ngrok-free.dev
curl -s -o /dev/null -w "front %{http_code}\n" -H 'ngrok-skip-browser-warning: 1' "$U/"
curl -s -H 'ngrok-skip-browser-warning: 1' "$U/api/v1/users?limit=1" | head -c 80
```

**프론트 200만 보고 안심하면 안 된다.** Docker가 죽어도 앱은 200을 반환하며 graceful degrade 하기 때문에, 겉은 멀쩡하고 속만 빈 상태가 된다(실제로 배포 중 한 번 겪음). 반드시 `/api/v1/users` 같은 DB 의존 엔드포인트까지 확인할 것. `keepalive.sh`는 이걸 자동으로 한다.

## 3. 알려진 취약점과 대응

| 취약점 | 증상 | 대응 |
|---|---|---|
| **Docker Desktop이 로그인 항목에 없음** | 재부팅 후 DB가 안 뜸 → 챗봇·청약이 빈 화면 | `keepalive.sh`가 감지해 자동 기동. 근본 대응은 시스템 설정 > 로그인 항목에 Docker 추가(아래 참고) |
| ngrok 무료 티어 경고 페이지 | 심사자가 첫 방문 시 "You are about to visit…" 인터스티셜을 봄 | **아래 4번 참고 — 금융 서비스 심사에서 특히 나쁨** |
| 맥 절전/화면잠금 | 터널 끊김 | AC 전원에서 `sleep 0`은 이미 설정돼 있음(`pmset -g custom`으로 확인). `caffeinate -dimsu`로 이중 방어 |
| 네트워크 단절·IP 변경 | 터널 끊김 | `keepalive.sh`가 재기동 |
| 프로세스 크래시 | 500 또는 접속 불가 | `keepalive.sh`가 재기동(복구 확인: 장애 주입 테스트에서 14초) |

### Docker 자동 시작 등록 (권장, 1회)

시스템 설정 → 일반 → 로그인 항목 → `+` → Docker 추가.
현재 로그인 항목: Maccy, Rectangle, Itsycal, RunCatNeo, ClaudeUsageBar, Google Drive, RunCat, boringNotch, Shottr, 카카오톡 — **Docker 없음**.

## 4. ⚠️ 제출 전에 반드시 결정할 것 — ngrok 경고 페이지

무료 티어라 첫 방문자에게 이 인터스티셜이 뜬다:

> **You are about to visit: gathering-disliking-hypnoses.ngrok-free.dev**
> You should only visit this website if you trust whoever sent the link to you.
> **Be careful about disclosing personal or financial information like passwords, phone numbers, or credit cards.**

`Visit Site`를 한 번 누르면 이후 안 뜨지만, **금융 AI 서비스 심사에서 "금융 정보를 입력하지 말라"는 경고가 첫 화면인 건 실점 요인**이다. 심사자가 사이트가 깨졌다고 판단할 위험도 있다.

선택지:
1. **ngrok 유료 전환(월 $8~10)** — 경고 페이지 제거 + 고정 도메인 보장. 가장 확실하고 비용이 낮음. **권장.**
2. 그대로 제출 — 제출 시 "첫 화면의 ngrok 안내에서 Visit Site를 눌러주세요" 문구를 병기. 심사자가 안 읽을 위험.
3. 클라우드 VM으로 이전 — 경고 없음 + 맥 의존 제거. 반나절 작업(Dockerfile·데이터 이관 필요).

> 참고: 현재 URL은 재시작을 여러 번 겪고도 유지됐다(무료 고정 도메인 1개). 다만 무료 티어의 고정 도메인 보장은 계정 정책에 따라 달라질 수 있으니, 제출 직전에 URL이 그대로인지 반드시 재확인할 것.

## 5. 심사 기간 체크리스트

**9/7 제출 직전**
- [ ] URL이 제출한 것과 동일한지 재확인
- [ ] `expose.sh` + `keepalive.sh` 둘 다 기동
- [ ] 새 시크릿창으로 처음부터 밟아보기 (아래 6번)
- [ ] 맥 AC 전원 연결, 자동 업데이트로 인한 재부팅 끄기
- [ ] ngrok 유료 전환 여부 결정(4번)

**9/7 ~ 9/11 매일**
- [ ] 2번 헬스체크 1회
- [ ] `tail -20 logs/keepalive.log`로 복구 이벤트 확인

## 6. 심사자 동선 재현 (제출 전 필수)

시크릿창에서 공개 URL로 접속 후 — 기능명세서 검증 절차와 동일하다. 괄호가 실측값이다.

1. `/` — 히어로가 "무주택 사회초년생을 위한 청약·자금마련 AI 콘솔", STEP 01~03 카드 표시
2. `/chat` — **유저를 안 골라도 바로 챗 입력창이 나와야 함**(기본 페르소나 자동 선택). 예시 질문 4개가 청약 중심인지 확인. 질문 전송 시 토큰이 한 글자씩 흘러나와야 함(첫 토큰 ~4.7초, 뭉텅이로 한 번에 오면 SSE 버퍼링 재발)
3. `/cheongyak` — 기본 가점 **20/84**. "만 30세 미만이면서 미혼" 체크 시 **12/84** + 무주택칸 비활성
4. 공고 선택 → 상세 → 당첨가점 표에 "내 점수 대비" 열
5. "이 청약으로 자금계획 세우기" → `/simulator`로 목표금액 자동 전달
6. `/simulator?target=123300000` — 자산 2,000만/월 60만/3.5% vs 6.0%에서 **130개월 vs 111개월, 19개월 단축**

## 7. 트러블슈팅

**챗봇이 아무것도 안 뱉는다**
`frontend/next.config.ts`의 `compress: false`가 살아있는지 확인. 이게 빠지면 Next가 프록시 응답을 gzip으로 감싸며 SSE를 통째로 버퍼링해서 브라우저에 청크 0개로 도착한다. 백엔드 직접 호출로 격리:
```bash
curl -sN -X POST http://localhost:8000/api/v1/chat/stream -H 'Content-Type: application/json' \
  -d '{"session_id":"t","message":"청약 가점이 뭔가요?","user_uuid":"e7926df30b8f48c09b33684f3075f60f"}' | head -c 200
```
여기서 나오는데 `:3000` 경유만 안 나오면 gzip 문제가 맞다.

**청약 목록이 비어 있다**
공공데이터 API(api.odcloud.kr) 점검일 수 있다. `CHEONGYAK_API_KEY` 확인:
```bash
curl -s 'http://localhost:8000/api/v1/cheongyak/list/apt' | head -c 200
```

**대시보드 숫자가 다 0이다**
DB가 내려간 것. `docker ps`로 `midas-postgres`·`midas-neo4j` 확인.

**전부 재기동**
```bash
lsof -ti:3000,8000,4040 | xargs kill -9
./expose.sh
```

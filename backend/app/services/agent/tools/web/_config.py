"""라이브 웹 리서치 도구 상수.

wealth_advisor(agent/config.py)에서 국세청 법령해석(ntsCgmExpc) 관련 설정만 분리 이식했다.
나머지(모델명 등)는 midas의 LLM 팩토리(agent/llm.py)를 쓰므로 가져오지 않는다.
"""

from __future__ import annotations

import os

# 국세청 법령해석: 목록 API만 본문 없음 → 상세 URL에서 발췌(허용 도메인만).
NTS_LAW_FETCH_DETAIL_PAGE_TEXT = True
NTS_LAW_DETAIL_TOP_N = 2
NTS_LAW_DETAIL_TEXT_MAX_CHARS = 2_000


# taxlaw.nts.go.kr 는 본문이 JS로 로드됨 → Playwright로 렌더 후 추출(optional extra).
# 환경변수 미지정 시: playwright 설치돼 있으면 True, 없으면 False(GET만).
def _playwright_installed() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


_pw = os.environ.get("NTS_LAW_USE_PLAYWRIGHT_DETAIL", "").strip().lower()
if _pw in ("0", "false", "no", "n"):
    NTS_LAW_USE_PLAYWRIGHT_DETAIL = False
elif _pw in ("1", "true", "yes", "y"):
    NTS_LAW_USE_PLAYWRIGHT_DETAIL = True
else:
    NTS_LAW_USE_PLAYWRIGHT_DETAIL = _playwright_installed()

NTS_LAW_PLAYWRIGHT_TIMEOUT_MS = int(
    os.environ.get("NTS_LAW_PLAYWRIGHT_TIMEOUT_MS", "60000") or "60000"
)

# ntsCgmExpc: 사용자 질문에서 도출한 키워드로만 검색. 비었을 때만 폴백.
NTS_LAW_MAX_API_QUERIES = max(
    1, min(10, int(os.environ.get("NTS_LAW_MAX_API_QUERIES", "5") or "5"))
)
_fb = (os.environ.get("NTS_LAW_FALLBACK_API_QUERIES") or "소득세").strip()
NTS_LAW_FALLBACK_API_QUERIES: tuple[str, ...] = tuple(
    x.strip() for x in _fb.split(",") if x.strip()
) or ("소득세",)

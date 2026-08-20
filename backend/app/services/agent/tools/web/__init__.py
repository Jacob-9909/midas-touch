"""라이브 웹 리서치 도구 (wealth_advisor 이식).

- naver_web: 네이버 검색 API (금융상품 금리 스니펫)
- tavily_search: Tavily 검색 (미·일·한 금리 동향)
- nts_law: 국가법령정보 국세청 법령해석(ntsCgmExpc) 목록 + 상세 발췌

각 도구는 LLM에 의존하지 않는 순수 I/O 래퍼다. 키 미설정 시 require_* 가 ValueError를 던지며,
노드 레이어에서 이를 잡아 사용자에게 명확한 "미설정" 문구를 돌려준다.
"""

from .naver_web import (
    naver_query_suffix,
    naver_web_snippets,
    require_naver_search_keys,
)
from .nts_law import (
    nts_cgm_search_once,
    require_law_go_kr_oc,
    resolve_nts_law_search_specs,
)
from .tavily_search import require_tavily_api_key, tavily_search_body

__all__ = [
    "naver_query_suffix",
    "naver_web_snippets",
    "nts_cgm_search_once",
    "require_law_go_kr_oc",
    "require_naver_search_keys",
    "require_tavily_api_key",
    "resolve_nts_law_search_specs",
    "tavily_search_body",
]

"""청약홈 분양정보 조회 서비스 (wealth_advisor 이식).

공공데이터포털 청약홈 API(odcloud.kr) 래퍼. 목록(APT/오피스텔/잔여세대/임의공급/공공임대) +
상세(주택형·경쟁률·가점·특별공급). 응답은 프론트 친화 dict로 평탄화한다. TTL 1시간 캐시.
키는 CHEONGYAK_API_KEY(또는 DATA_GO_KR_API_KEY) 환경변수.
"""

from .api_client import (
    fetch_apt_competition,
    fetch_apt_housing_types,
    fetch_apt_scores,
    fetch_apt_special_supply,
    fetch_officetel,
    fetch_officetel_competition,
    fetch_opt_competition,
    fetch_opt_supply,
    fetch_public_rent,
    fetch_public_rent_competition,
    fetch_recent_apt,
    fetch_remaining_apt,
)

__all__ = [
    "fetch_recent_apt",
    "fetch_officetel",
    "fetch_remaining_apt",
    "fetch_opt_supply",
    "fetch_public_rent",
    "fetch_apt_housing_types",
    "fetch_apt_competition",
    "fetch_officetel_competition",
    "fetch_public_rent_competition",
    "fetch_opt_competition",
    "fetch_apt_scores",
    "fetch_apt_special_supply",
]

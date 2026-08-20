"""프로젝트 표준 시간대(KST) 헬퍼.

이 서비스의 업무 기준 시각은 한국 시간(Asia/Seoul)이다. 시장 데이터 조회 구간,
청약 공고 상태 판정 등 '오늘'의 의미가 KST 기준이어야 하므로 naive datetime 대신
아래 헬퍼를 사용한다. (unix timestamp 변환 시에는 tz=KST 를 명시적으로 넘길 것)
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    """KST 기준 현재 시각 (tz-aware)."""
    return datetime.now(KST)


def today_kst() -> date:
    """KST 기준 오늘 날짜."""
    return datetime.now(KST).date()

"""백엔드 에이전트용 LLM 팩토리.

NVIDIA NIM은 OpenAI 호환 엔드포인트이므로 LangChain의 ChatOpenAI 래퍼를 그대로 사용한다.
모델 자체는 교체하지 않으며(.env의 AGENT_LLM_MODEL, 현재 openai/gpt-oss-120b),
function-calling(tools) 포맷을 네이티브로 지원함을 실호출로 확인했다.
"""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"


def require_env(name: str) -> str:
    """필수 환경변수를 읽고, 없으면 명확한 오류로 실패한다(하드코딩 기본값 금지)."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} 환경변수가 설정되어 있지 않습니다.")
    return value


def build_chat_model(temperature: float = 0.7, max_tokens: int = 4000) -> ChatOpenAI:
    """create_react_agent에 주입할 NIM 기반 ChatOpenAI 인스턴스를 생성한다."""
    api_key = require_env("NVIDIA_API_KEY")
    model = require_env("AGENT_LLM_MODEL")

    return ChatOpenAI(
        model=model,
        base_url=NIM_BASE_URL,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )

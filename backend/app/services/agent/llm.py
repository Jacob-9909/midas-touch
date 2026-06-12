"""백엔드 에이전트용 LLM 팩토리.

NVIDIA NIM은 OpenAI 호환 엔드포인트이므로 LangChain의 ChatOpenAI 래퍼를 그대로 사용한다.
모델 자체는 교체하지 않으며(.env의 AGENT_LLM_MODEL, 현재 openai/gpt-oss-120b),
function-calling(tools) 포맷을 네이티브로 지원함을 실호출로 확인했다.
"""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"


def build_chat_model(temperature: float = 0.7, max_tokens: int = 4000) -> ChatOpenAI:
    """create_react_agent에 주입할 NIM 기반 ChatOpenAI 인스턴스를 생성한다."""
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY 환경변수가 설정되어 있지 않습니다.")

    model = os.environ.get("AGENT_LLM_MODEL")
    if not model:
        raise RuntimeError("AGENT_LLM_MODEL 환경변수가 설정되어 있지 않습니다.")

    return ChatOpenAI(
        model=model,
        base_url=NIM_BASE_URL,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )

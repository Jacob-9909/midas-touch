"""Tavily 검색 (langchain-tavily)."""

from __future__ import annotations

import os
from typing import Any


def require_tavily_api_key() -> None:
    key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if not key:
        raise ValueError(
            "Tavily API 키가 필요합니다. .env 에 TAVILY_API_KEY 를 설정하세요. "
            "(https://tavily.com)"
        )


def format_tavily_result(raw: Any, *, max_chars: int = 3500) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw[:max_chars].strip()
    if not isinstance(raw, dict):
        return str(raw)[:max_chars].strip()
    chunks: list[str] = []
    ans = raw.get("answer")
    if ans:
        chunks.append(str(ans).strip())
    for r in raw.get("results") or []:
        if not isinstance(r, dict):
            continue
        title = (r.get("title") or "").strip()
        content = (r.get("content") or r.get("snippet") or "").strip()
        line = f"- {title}: {content}"
        chunks.append(line[:900])
    out = "\n".join(chunks).strip()
    return out[:max_chars]


def tavily_search_body(tool: Any, query: str) -> str:
    try:
        raw = tool.invoke({"query": query})
    except Exception as exc:  # noqa: BLE001
        return f"(Tavily 요청 실패: {exc})"
    return format_tavily_result(raw, max_chars=4000)

"""NIMChatOpenAI의 키 로테이션 · 재시도 동작 검증(네트워크 호출 없음)."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("NVIDIA_API_KEY", "nvapi-test-key-one")
os.environ.setdefault("NVIDIA_API_KEY_2", "nvapi-test-key-two")
os.environ.setdefault("AGENT_LLM_MODEL", "qwen/qwen3-next-80b-a3b-instruct")
os.environ.setdefault("NIM_RPM", "0")  # 테스트에서 실제 60초 대기하지 않도록 RPM 제한 해제

from httpx import Request, Response  # noqa: E402
from openai import BadRequestError, RateLimitError  # noqa: E402

from backend.app.services.agent import llm as agent_llm  # noqa: E402


def _rate_limit_error() -> RateLimitError:
    req = Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")
    return RateLimitError("429", response=Response(429, request=req), body=None)


def _bad_request_error() -> BadRequestError:
    req = Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")
    return BadRequestError("400", response=Response(400, request=req), body=None)


class NIMChatRetryTest(unittest.TestCase):
    def setUp(self) -> None:
        agent_llm._rotator = None  # 키 쿨다운 상태를 테스트마다 초기화

    def test_rotates_key_and_retries_on_429(self) -> None:
        model = agent_llm.build_chat_model()
        used_keys: list[str] = []

        def fake_generate(*args, **kwargs):
            used_keys.append(model.openai_api_key)
            if len(used_keys) == 1:
                raise _rate_limit_error()
            return "ok"

        with mock.patch.object(agent_llm.ChatOpenAI, "_generate", fake_generate):
            self.assertEqual(model._generate([]), "ok")

        self.assertEqual(len(used_keys), 2, used_keys)
        self.assertNotEqual(used_keys[0], used_keys[1], "429 이후 다른 키로 재시도해야 한다")

    def test_gives_up_after_all_keys_fail(self) -> None:
        model = agent_llm.build_chat_model()

        def always_429(*args, **kwargs):
            raise _rate_limit_error()

        with mock.patch.object(agent_llm.ChatOpenAI, "_generate", always_429):
            with self.assertRaises(RateLimitError):
                model._generate([])

    def test_does_not_retry_client_errors(self) -> None:
        model = agent_llm.build_chat_model()
        calls = []

        def bad_request(*args, **kwargs):
            calls.append(1)
            raise _bad_request_error()

        with mock.patch.object(agent_llm.ChatOpenAI, "_generate", bad_request):
            with self.assertRaises(BadRequestError):
                model._generate([])

        self.assertEqual(len(calls), 1, "400은 재시도 대상이 아니다")


if __name__ == "__main__":
    unittest.main()

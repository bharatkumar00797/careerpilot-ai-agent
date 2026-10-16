"""LLM provider unit tests."""

from __future__ import annotations

import json

import httpx
import pytest

from careerpilot.config import Settings
from careerpilot.llm import MockProvider, OpenAICompatibleProvider, build_provider
from careerpilot.llm.base import LLMError, Message


def test_mock_complete_is_deterministic() -> None:
    p = MockProvider()
    msgs = [Message(role="user", content="hello")]
    a = p.complete(msgs)
    b = p.complete(msgs)
    assert a.content == b.content
    assert a.model == "mock-careerpilot-1"


def test_build_provider_defaults_to_mock() -> None:
    assert isinstance(build_provider(Settings(provider="mock")), MockProvider)


def test_build_provider_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        build_provider(Settings(provider="anthropic"))


def test_openai_compat_rejects_plain_http_non_local() -> None:
    with pytest.raises(ValueError, match="localhost"):
        OpenAICompatibleProvider(base_url="http://example.com/v1", model="x")


def test_openai_compat_allows_localhost_http() -> None:
    p = OpenAICompatibleProvider(base_url="http://127.0.0.1:11434/v1", model="llama")
    assert p.base_url.endswith("/v1")


def test_openai_compat_parses_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gpt-test",
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    p = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1", model="gpt-test", client=client
    )
    result = p.complete([Message(role="user", content="ping")], temperature=0.0)
    assert result.content == "hi"
    assert result.usage.total_tokens == 4


def test_openai_compat_retries_then_errors() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="busy")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    p = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        model="gpt-test",
        client=client,
        max_retries=1,
    )
    with pytest.raises(LLMError):
        p.complete([Message(role="user", content="ping")])
    assert calls["n"] == 2


def test_openai_compat_malformed_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    p = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1", model="gpt-test", client=client
    )
    with pytest.raises(LLMError, match="Malformed"):
        p.complete([Message(role="user", content="ping")])


def test_message_to_dict() -> None:
    assert Message(role="system", content="x").to_dict() == {
        "role": "system",
        "content": "x",
    }
    # ensure json roundtrip of payload shape
    assert json.loads(json.dumps(Message(role="user", content="y").to_dict()))["role"] == "user"

"""Tests for the message builders and the chunk-merging logic."""

from __future__ import annotations

from reflex_assistant_ui import (
    RUNNING,
    AssistantUIState,
    assistant_message,
    cancelled,
    complete,
    failed,
    file_part,
    message_text,
    source_part,
    tool_call_part,
    user_message,
)
from reflex_assistant_ui.ollama import base_url

merge = AssistantUIState._merge_chunk


def test_user_message_wraps_text_and_links_parent():
    message = user_message("hi", parent_id="p1")
    assert message["role"] == "user"
    assert message["parent_id"] == "p1"
    assert message["content"] == [{"type": "text", "text": "hi"}]
    assert message["id"].startswith("user-")
    assert "attachments" not in message


def test_assistant_message_defaults_to_complete():
    assert assistant_message("ok")["status"] == complete()
    assert assistant_message("", status=RUNNING)["status"] == {"type": "running"}


def test_status_helpers():
    assert cancelled() == {"type": "incomplete", "reason": "cancelled"}
    assert failed("boom")["error"] == "boom"


def test_message_text_only_joins_text_parts():
    message = {
        "content": [
            {"type": "text", "text": "a"},
            {"type": "reasoning", "text": "hidden"},
            {"type": "text", "text": "b"},
        ]
    }
    assert message_text(message) == "ab"
    assert message_text({"content": "plain"}) == "plain"
    assert message_text({}) == ""


def test_part_builders():
    call = tool_call_part("calc", {"x": 1}, tool_call_id="t1", result=2)
    assert call == {
        "type": "tool-call",
        "tool_name": "calc",
        "tool_call_id": "t1",
        "args": {"x": 1},
        "is_error": False,
        "result": 2,
    }
    assert source_part("https://example.com")["title"] == "https://example.com"
    assert "filename" not in file_part("data:,x", "text/plain")


def test_merge_extends_trailing_text_part():
    parts = merge([], "Hel")
    parts = merge(parts, {"text": "lo"})
    assert parts == [{"type": "text", "text": "Hello"}]


def test_merge_starts_new_text_part_after_tool_call():
    parts = merge([], "before")
    parts = merge(parts, {"tool_call": tool_call_part("t", tool_call_id="c1")})
    parts = merge(parts, "after")
    assert [p["type"] for p in parts] == ["text", "tool-call", "text"]


def test_merge_updates_tool_call_with_same_id():
    parts = merge([], {"tool_call": tool_call_part("t", tool_call_id="c1")})
    parts = merge(parts, {"tool_call": {"tool_call_id": "c1", "result": 42}})
    assert len(parts) == 1
    assert parts[0]["result"] == 42
    assert parts[0]["tool_name"] == "t"


def test_merge_does_not_mutate_input_and_ignores_unknown_chunks():
    original = [{"type": "text", "text": "a"}]
    merged = merge(original, "b")
    assert original == [{"type": "text", "text": "a"}]
    assert merged[0]["text"] == "ab"
    assert merge(original, 123) == original


def test_ollama_base_url(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert base_url() == "http://localhost:11434"
    assert base_url("myhost:1234/") == "http://myhost:1234"
    monkeypatch.setenv("OLLAMA_HOST", "https://ollama.example")
    assert base_url() == "https://ollama.example"

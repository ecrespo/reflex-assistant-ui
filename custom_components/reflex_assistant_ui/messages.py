"""Builders for the message dicts the assistant-ui components consume.

A message is a plain dict so it can live directly in a Reflex state var::

    {
        "id": "…",
        "parent_id": "…" | None,
        "role": "user" | "assistant" | "system",
        "content": [ {"type": "text", "text": "hello"} ],
        "status": {"type": "complete", "reason": "stop"},   # assistant only
    }

Nothing here is required — you can build the dicts by hand — but these helpers
keep ids, parent links and status objects consistent, which is what makes the
branch picker and the streaming indicator work.
"""

from __future__ import annotations

import uuid
from typing import Any

__all__ = [
    "RUNNING",
    "assistant_message",
    "cancelled",
    "complete",
    "failed",
    "file_part",
    "image_part",
    "message_text",
    "new_id",
    "reasoning_part",
    "source_part",
    "system_message",
    "text_part",
    "tool_call_part",
    "user_message",
]

# Message status objects. ``RUNNING`` is what makes the thread stream.
RUNNING: dict[str, Any] = {"type": "running"}


def complete(reason: str = "stop") -> dict[str, Any]:
    """A finished assistant message."""
    return {"type": "complete", "reason": reason}


def cancelled() -> dict[str, Any]:
    """An assistant message the user stopped."""
    return {"type": "incomplete", "reason": "cancelled"}


def failed(error: str) -> dict[str, Any]:
    """An assistant message that ended with an error."""
    return {"type": "incomplete", "reason": "error", "error": error}


def new_id(prefix: str = "msg") -> str:
    """Generate a stable, unique message or tool-call id."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------- #
# Parts
# --------------------------------------------------------------------- #


def text_part(text: str) -> dict[str, Any]:
    """Plain text. Rendered as markdown for assistant messages."""
    return {"type": "text", "text": text}


def reasoning_part(text: str) -> dict[str, Any]:
    """Chain-of-thought, rendered in a collapsible block."""
    return {"type": "reasoning", "text": text}


def tool_call_part(
    tool_name: str,
    args: dict[str, Any] | None = None,
    *,
    tool_call_id: str | None = None,
    result: Any = None,
    is_error: bool = False,
    args_text: str | None = None,
) -> dict[str, Any]:
    """A tool invocation, rendered with its arguments and result."""
    part: dict[str, Any] = {
        "type": "tool-call",
        "tool_name": tool_name,
        "tool_call_id": tool_call_id or new_id("tool"),
        "args": args or {},
        "is_error": is_error,
    }
    if args_text is not None:
        part["args_text"] = args_text
    if result is not None:
        part["result"] = result
    return part


def image_part(image: str) -> dict[str, Any]:
    """An image, given as an https URL or a ``data:image/…`` URL."""
    return {"type": "image", "image": image}


def file_part(data: str, mime_type: str, filename: str | None = None) -> dict[str, Any]:
    """A downloadable file, given as a URL or a data URL."""
    part: dict[str, Any] = {"type": "file", "data": data, "mime_type": mime_type}
    if filename:
        part["filename"] = filename
    return part


def source_part(url: str, title: str | None = None, source_id: str | None = None) -> dict[str, Any]:
    """A citation chip."""
    return {
        "type": "source",
        "source_type": "url",
        "id": source_id or new_id("src"),
        "url": url,
        "title": title or url,
    }


# --------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------- #


def _content(content: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [text_part(content)] if isinstance(content, str) else list(content)


def user_message(
    content: str | list[dict[str, Any]],
    *,
    id: str | None = None,
    parent_id: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a user message."""
    message: dict[str, Any] = {
        "id": id or new_id("user"),
        "parent_id": parent_id,
        "role": "user",
        "content": _content(content),
    }
    if attachments:
        message["attachments"] = attachments
    return message


def assistant_message(
    content: str | list[dict[str, Any]] = "",
    *,
    id: str | None = None,
    parent_id: str | None = None,
    status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an assistant message.

    Pass ``status=RUNNING`` while streaming so the thread shows the typing
    indicator and the stop button, then swap it for ``complete()``.
    """
    return {
        "id": id or new_id("asst"),
        "parent_id": parent_id,
        "role": "assistant",
        "content": _content(content),
        "status": status or complete(),
    }


def system_message(
    content: str | list[dict[str, Any]],
    *,
    id: str | None = None,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Build a system message."""
    return {
        "id": id or new_id("sys"),
        "parent_id": parent_id,
        "role": "system",
        "content": _content(content),
    }


def message_text(message: dict[str, Any]) -> str:
    """Concatenate every text part of a message."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    return "".join(
        part.get("text", "")
        for part in (content or [])
        if isinstance(part, dict) and part.get("type") == "text"
    )

"""A ready-made Reflex state mixin for assistant-ui chats.

Subclass it *alongside* ``rx.State`` — a mixin is not a state on its own —
implement ``_respond``, and wire the handlers to the component::

    class ChatState(AssistantUIState, rx.State):
        async def _respond(self, history):
            async for token in my_llm(history):
                yield token

    assistant_ui.chat(
        messages=ChatState.messages,
        head_id=ChatState.head_id,
        is_running=ChatState.is_running,
        on_new=ChatState.handle_new,
        on_edit=ChatState.handle_edit,
        on_reload=ChatState.handle_reload,
        on_cancel=ChatState.handle_cancel,
        on_branch_change=ChatState.handle_branch_change,
    )

The mixin keeps the whole conversation as a flat list of messages linked by
``parent_id``. Edits and regenerations add siblings rather than overwriting, so
the branch picker works without any extra bookkeeping.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import reflex as rx

from .messages import (
    RUNNING,
    assistant_message,
    cancelled,
    complete,
    failed,
    message_text,
    user_message,
)

__all__ = ["AssistantUIState"]


class AssistantUIState(rx.State, mixin=True):
    """Conversation state, streaming, cancellation and branching."""

    # The whole conversation as a flat list; branches are expressed by parent_id.
    messages: list[dict[str, Any]] = []

    # Id of the message at the tip of the branch currently on screen.
    head_id: str = ""

    # True while a reply is being generated.
    is_running: bool = False

    # Last error, if any. Also surfaced on the failed message itself.
    last_error: str = ""

    # Follow-up suggestions rendered above the composer.
    suggestions: list[Any] = []

    # Minimum seconds between websocket pushes while streaming. Raising it
    # reduces traffic on long replies; 0 pushes on every chunk.
    stream_interval: float = 0.05

    # Extra instructions prepended to the history handed to ``_respond``.
    system_prompt: str = ""

    _cancel_requested: bool = False

    # ------------------------------------------------------------------ #
    # To implement
    # ------------------------------------------------------------------ #

    async def _respond(self, history: list[dict[str, Any]]) -> AsyncIterator[Any]:
        """Produce the assistant's reply for ``history``.

        ``history`` is the visible branch, oldest first, each entry
        ``{"role": ..., "content": ...}`` with content already flattened to a
        string. Yield any of:

        * ``str`` — a text delta, appended to the reply;
        * ``{"text": "…"}`` — the same;
        * ``{"reasoning": "…"}`` — a delta appended to the reasoning block;
        * ``{"tool_call": {...}}`` — a tool-call part (see ``tool_call_part``),
          re-yield the same ``tool_call_id`` to update it with a result;
        * ``{"part": {...}}`` — any other message part, appended as-is.

        Cancellation is cooperative: the loop stops consuming as soon as the
        user presses stop, so a long generator should also check
        ``self._cancel_requested``.
        """
        raise NotImplementedError("Subclass AssistantUIState and implement _respond().")
        yield  # pragma: no cover - makes this an async generator

    # ------------------------------------------------------------------ #
    # Conversation helpers
    # ------------------------------------------------------------------ #

    def _by_id(self) -> dict[str, dict[str, Any]]:
        return {m["id"]: m for m in self.messages if m.get("id")}

    def _current_head(self) -> str | None:
        if self.head_id:
            return self.head_id
        return self.messages[-1]["id"] if self.messages else None

    def _branch(self, head: str | None = None) -> list[dict[str, Any]]:
        """The path from the root to ``head``, oldest first."""
        index = self._by_id()
        node = head if head is not None else self._current_head()
        path: list[dict[str, Any]] = []
        seen: set[str] = set()
        while node and node in index and node not in seen:
            seen.add(node)
            message = index[node]
            path.append(message)
            node = message.get("parent_id")
        path.reverse()
        return path

    def _history(self, head: str | None = None) -> list[dict[str, Any]]:
        """The visible branch as ``{"role", "content"}`` dicts for a model."""
        history = [
            {"role": m["role"], "content": message_text(m)}
            for m in self._branch(head)
            if m.get("role") in ("user", "assistant", "system")
        ]
        if self.system_prompt:
            history.insert(0, {"role": "system", "content": self.system_prompt})
        return history

    def _visible_branch(self) -> list[dict[str, Any]]:
        """The branch currently on screen — handy for debugging or exports."""
        return self._branch()

    @rx.event
    def reset_chat(self):
        """Clear the conversation."""
        self.messages = []
        self.head_id = ""
        self.last_error = ""
        self.is_running = False
        self._cancel_requested = False

    # ------------------------------------------------------------------ #
    # Streaming
    # ------------------------------------------------------------------ #

    @staticmethod
    def _merge_chunk(content: list[dict[str, Any]], chunk: Any) -> list[dict[str, Any]]:
        """Fold one yielded chunk into a message's content list."""
        parts = list(content)

        def append_text(key: str, delta: str) -> None:
            # Only extend a trailing part of the same kind, so text that
            # resumes after a tool call becomes its own part.
            if parts and parts[-1].get("type") == key:
                parts[-1] = {**parts[-1], "text": parts[-1].get("text", "") + delta}
            else:
                parts.append({"type": key, "text": delta})

        if isinstance(chunk, str):
            append_text("text", chunk)
            return parts

        if not isinstance(chunk, dict):
            return parts

        if "text" in chunk:
            append_text("text", str(chunk["text"]))
        if "reasoning" in chunk:
            append_text("reasoning", str(chunk["reasoning"]))
        if "tool_call" in chunk:
            call = dict(chunk["tool_call"])
            call.setdefault("type", "tool-call")
            call_id = call.get("tool_call_id")
            for i, existing in enumerate(parts):
                if (
                    existing.get("type") == "tool-call"
                    and call_id is not None
                    and existing.get("tool_call_id") == call_id
                ):
                    parts[i] = {**existing, **call}
                    break
            else:
                parts.append(call)
        if "part" in chunk:
            parts.append(dict(chunk["part"]))
        return parts

    def _replace(self, message_id: str, **updates: Any) -> None:
        messages = list(self.messages)
        for i, message in enumerate(messages):
            if message.get("id") == message_id:
                messages[i] = {**message, **updates}
                break
        self.messages = messages

    async def _stream_reply(self, parent_id: str | None):
        """Append an assistant message under ``parent_id`` and stream into it."""
        reply = assistant_message("", parent_id=parent_id, status=RUNNING)
        reply_id = reply["id"]

        async with self:
            self.messages = [*self.messages, reply]
            self.head_id = reply_id
            self.is_running = True
            self.last_error = ""
            self._cancel_requested = False
            history = self._history(parent_id)
            interval = self.stream_interval

        content: list[dict[str, Any]] = []
        pending = False
        last_push = 0.0
        stopped = False
        error: str | None = None

        try:
            async for chunk in self._respond(history):
                async with self:
                    stopped = self._cancel_requested
                content = self._merge_chunk(content, chunk)
                pending = True
                if stopped:
                    break

                now = time.monotonic()
                if pending and (now - last_push) >= interval:
                    last_push = now
                    pending = False
                    async with self:
                        self._replace(reply_id, content=content)
        except Exception as exc:  # noqa: BLE001 - surfaced in the thread
            error = f"{type(exc).__name__}: {exc}"

        async with self:
            if self._cancel_requested:
                stopped = True
            if error is not None:
                status = failed(error)
                self.last_error = error
            elif stopped:
                status = cancelled()
            else:
                status = complete()
            self._replace(reply_id, content=content, status=status)
            self.is_running = False
            self._cancel_requested = False

    # ------------------------------------------------------------------ #
    # Event handlers wired to the component
    # ------------------------------------------------------------------ #

    @rx.event(background=True)
    async def handle_new(self, message: dict[str, Any]):
        """The user sent a message: append it, then stream the reply."""
        async with self:
            parent = message.get("parent_id") or self._current_head()
            attachments = message.get("attachments") or None
            question = user_message(
                message.get("text") or "",
                parent_id=parent,
                attachments=attachments,
            )
            self.messages = [*self.messages, question]
            self.head_id = question["id"]
            new_parent = question["id"]

        await self._stream_reply(new_parent)

    @rx.event(background=True)
    async def handle_edit(self, message: dict[str, Any]):
        """The user edited an earlier message: branch from its parent."""
        async with self:
            parent = message.get("parent_id")
            question = user_message(message.get("text") or "", parent_id=parent)
            self.messages = [*self.messages, question]
            self.head_id = question["id"]
            new_parent = question["id"]

        await self._stream_reply(new_parent)

    @rx.event(background=True)
    async def handle_reload(self, parent_id: str | None = None):
        """The user asked to regenerate: add a sibling reply."""
        async with self:
            parent = parent_id or None
            if parent is None:
                branch = self._branch()
                parent = branch[-2]["id"] if len(branch) >= 2 else None

        await self._stream_reply(parent)

    @rx.event
    def handle_cancel(self):
        """The user pressed stop."""
        self._cancel_requested = True
        self.is_running = False

    @rx.event
    def handle_branch_change(self, event: dict[str, Any]):
        """The user switched branches; remember the new head."""
        self.head_id = event.get("head_id") or ""

    @rx.event
    def handle_delete(self, message_id: str):
        """Drop a message and everything below it."""
        index = self._by_id()
        doomed = {message_id}
        changed = True
        while changed:
            changed = False
            for mid, message in index.items():
                if message.get("parent_id") in doomed and mid not in doomed:
                    doomed.add(mid)
                    changed = True
        self.messages = [m for m in self.messages if m.get("id") not in doomed]
        if self.head_id in doomed:
            self.head_id = self.messages[-1]["id"] if self.messages else ""

    @rx.event
    def handle_feedback(self, event: dict[str, Any]):
        """Record a thumbs up/down on a message."""
        message_id = event.get("message_id")
        if not message_id:
            return
        self._replace(message_id, feedback=event.get("type"))

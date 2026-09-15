"""Multi-conversation state for the thread-list demo page."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import reflex as rx
from langchain_ollama import ChatOllama
from reflex_assistant_ui import AssistantUIState, message_text, new_id, ollama

from .backend import FALLBACK_NOTICE, chunk_text, to_langchain_messages


def _title_from(messages: list[dict[str, Any]]) -> str:
    """Use the first user message as the conversation title."""
    first = next((m for m in messages if m.get("role") == "user"), None)
    if not first:
        return "New chat"
    line = message_text(first).strip().splitlines()
    text = line[0].strip() if line else ""
    return (text[:40] + "…") if len(text) > 40 else (text or "New chat")


class ThreadsState(AssistantUIState, rx.State):
    """Several conversations, one active at a time.

    ``AssistantUIState`` owns a single conversation, so switching threads is
    just a matter of parking the current ``messages``/``head_id`` in a dict and
    loading another pair back. Titles are derived, never stored twice.
    """

    conversations: dict[str, list[dict[str, Any]]] = {}
    heads: dict[str, str] = {}
    renamed: dict[str, str] = {}
    order: list[str] = []
    current_id: str = ""

    model: str = ""
    ollama_ready: bool = False

    @rx.var
    def thread_list(self) -> dict[str, Any]:
        """The payload the component's ``thread_list`` prop expects."""
        threads = []
        for thread_id in self.order:
            stored = (
                self.messages
                if thread_id == self.current_id
                else self.conversations.get(thread_id, [])
            )
            threads.append(
                {
                    "id": thread_id,
                    "title": self.renamed.get(thread_id) or _title_from(stored),
                }
            )
        return {"thread_id": self.current_id, "threads": threads}

    @rx.event
    async def on_load(self):
        """Probe Ollama and make sure there is one conversation to show."""
        models = await ollama.list_models()
        self.ollama_ready = bool(models)
        self.model = models[0] if models else ""
        if not self.order:
            self._create_thread()

    # ----------------------------------------------------------------- #
    # Thread bookkeeping
    # ----------------------------------------------------------------- #

    def _park(self) -> None:
        if self.current_id:
            self.conversations[self.current_id] = list(self.messages)
            self.heads[self.current_id] = self.head_id

    def _create_thread(self) -> str:
        thread_id = new_id("thread")
        self.order = [thread_id, *self.order]
        self.conversations[thread_id] = []
        self.heads[thread_id] = ""
        self.current_id = thread_id
        self.messages = []
        self.head_id = ""
        return thread_id

    @rx.event
    def handle_switch_to_thread(self, thread_id: str):
        """Load another conversation."""
        if thread_id == self.current_id:
            return
        self._park()
        self.current_id = thread_id
        self.messages = list(self.conversations.get(thread_id, []))
        self.head_id = self.heads.get(thread_id, "")
        self.is_running = False

    @rx.event
    def handle_new_thread(self):
        """Start an empty conversation."""
        self._park()
        self._create_thread()

    @rx.event
    def handle_rename_thread(self, thread_id: str, title: str):
        """Rename a conversation from the list."""
        self.renamed[thread_id] = title

    @rx.event
    def handle_delete_thread(self, thread_id: str):
        """Remove a conversation, creating a fresh one if it was the last."""
        self.order = [t for t in self.order if t != thread_id]
        self.conversations.pop(thread_id, None)
        self.heads.pop(thread_id, None)
        self.renamed.pop(thread_id, None)
        if self.current_id != thread_id:
            return
        if self.order:
            self.current_id = self.order[0]
            self.messages = list(self.conversations.get(self.current_id, []))
            self.head_id = self.heads.get(self.current_id, "")
        else:
            self._create_thread()

    # ----------------------------------------------------------------- #
    # Replies
    # ----------------------------------------------------------------- #

    async def _respond(self, history: list[dict[str, Any]]) -> AsyncIterator[Any]:
        if self.ollama_ready and self.model:
            llm = ChatOllama(model=self.model, base_url=ollama.DEFAULT_BASE_URL)
            try:
                async for chunk in llm.astream(to_langchain_messages(history)):
                    reasoning = chunk.additional_kwargs.get("reasoning_content")
                    if reasoning:
                        yield {"reasoning": reasoning}
                    text = chunk_text(chunk.content)
                    if text:
                        yield text
            except Exception as exc:  # noqa: BLE001 - surfaced in the thread
                yield f"\n\n> **Could not reach the model.** {type(exc).__name__}: {exc}"
            return

        question = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        for word in f"{FALLBACK_NOTICE}\n\nYou said: {question}".split(" "):
            yield word + " "
            await asyncio.sleep(0.015)

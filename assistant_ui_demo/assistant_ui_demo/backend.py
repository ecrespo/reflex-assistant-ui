"""Chat state for the demo.

The model is driven through **LangChain** (`ChatOllama` from `langchain-ollama`),
so tools are ordinary `@tool` functions and the streaming loop is LangChain's
`astream`. When no Ollama server is running the state falls back to a built-in
echo bot, so the demo always starts.
"""

from __future__ import annotations

import ast
import asyncio
import datetime
import json
import operator
import platform
from collections.abc import AsyncIterator
from typing import Any

import reflex as rx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from reflex_assistant_ui import AssistantUIState, ollama, tool_call_part

# --------------------------------------------------------------------- #
# Tools — plain functions; LangChain derives the schema from the signature
# and the docstring, and Ollama receives it through `bind_tools`.
# --------------------------------------------------------------------- #

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    """Evaluate an arithmetic AST without going near ``eval``."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


@tool
def get_current_time(timezone: str = "UTC") -> dict:
    """Return the current date and time on the server.

    Args:
        timezone: IANA timezone name, for example America/Caracas.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    resolved = timezone
    if timezone and timezone.upper() != "UTC":
        try:
            from zoneinfo import ZoneInfo

            now = now.astimezone(ZoneInfo(timezone))
        except Exception:  # noqa: BLE001 - a bad timezone just falls back to UTC
            resolved = "UTC"
    return {
        "iso": now.isoformat(timespec="seconds"),
        "human": now.strftime("%A %d %B %Y, %H:%M"),
        "timezone": resolved,
    }


@tool
def calculate(expression: str) -> dict:
    """Evaluate an arithmetic expression such as '(18 * 7) / 3'.

    Args:
        expression: The arithmetic expression to evaluate.
    """
    try:
        value = _safe_eval(ast.parse(expression, mode="eval"))
    except Exception as exc:  # noqa: BLE001 - reported back to the model
        return {"error": f"could not evaluate {expression!r}: {exc}"}
    return {"expression": expression, "result": value}


@tool
def system_info() -> dict:
    """Report the operating system and Python version of the host."""
    return {
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "machine": platform.machine(),
    }


TOOLS = [get_current_time, calculate, system_info]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

MAX_TOOL_ROUNDS = 4

# Models that rejected `think: true`; asked once, then left alone.
_NO_REASONING: set[str] = set()

FALLBACK_NOTICE = (
    "Ollama is not reachable, so this demo is answering with a built-in echo bot. "
    "Start it with `ollama serve` and pull a model (`ollama pull llama3.2`), then "
    "press **Models**."
)


def to_langchain_messages(history: list[dict[str, Any]]) -> list[BaseMessage]:
    """Turn the thread's history into LangChain messages."""
    converted: list[BaseMessage] = []
    for message in history:
        role = message.get("role")
        content = message.get("content", "")
        if role == "system":
            converted.append(SystemMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))
    return converted


def chunk_text(content: Any) -> str:
    """Flatten a chunk's content, which may be a string or content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


async def _run_tool(name: str, args: dict[str, Any]) -> Any:
    """Execute one tool and return a JSON-serializable result."""
    selected = TOOLS_BY_NAME.get(name)
    if selected is None:
        return {"error": f"unknown tool {name!r}"}
    try:
        return await selected.ainvoke(args or {})
    except Exception as exc:  # noqa: BLE001 - reported back to the model
        return {"error": f"{type(exc).__name__}: {exc}"}


class ChatState(AssistantUIState, rx.State):
    """Everything the demo pages share."""

    # Ollama connection
    ollama_url: str = ollama.DEFAULT_BASE_URL
    models: list[str] = []
    model: str = ""
    ollama_ready: bool = False
    checked: bool = False

    # Generation options
    temperature: float = 0.7
    enable_tools: bool = True
    show_thinking: bool = True

    system_prompt: str = (
        "You are a concise, friendly assistant embedded in a Reflex application. "
        "Use markdown, and put code in fenced blocks with a language tag."
    )

    @rx.var
    def status_label(self) -> str:
        """One line describing the current backend."""
        if not self.checked:
            return "Checking Ollama…"
        if self.ollama_ready:
            return f"LangChain · {self.model or 'no model'}"
        return "Echo bot (Ollama offline)"

    @rx.event
    async def refresh_models(self):
        """Probe Ollama and load the list of installed models."""
        models = await ollama.list_models(self.ollama_url)
        self.models = models
        self.ollama_ready = bool(models)
        self.checked = True
        if models and self.model not in models:
            preferred = next(
                (m for m in models if m.split(":")[0] in ("llama3.2", "llama3.1", "qwen2.5")),
                models[0],
            )
            self.model = preferred

    @rx.event
    def set_model(self, model: str):
        """Switch the active model."""
        self.model = model

    @rx.event
    def set_temperature(self, value: list[int | float]):
        """Slider handler: Reflex sends a one-element list."""
        self.temperature = round(float(value[0]) / 100, 2)

    @rx.event
    def toggle_tools(self, value: bool):
        """Enable or disable function calling."""
        self.enable_tools = value

    @rx.event
    def toggle_thinking(self, value: bool):
        """Ask the model for its reasoning, when it supports one."""
        self.show_thinking = value

    @rx.event
    def new_conversation(self):
        """Clear the thread."""
        self.reset_chat()

    # ----------------------------------------------------------------- #
    # Reply generation
    # ----------------------------------------------------------------- #

    def _build_llm(self, reasoning: bool):
        """A ChatOllama bound to the demo's tools."""
        llm = ChatOllama(
            model=self.model,
            base_url=self.ollama_url,
            temperature=self.temperature,
            reasoning=True if reasoning else None,
        )
        return llm.bind_tools(TOOLS) if self.enable_tools else llm

    async def _respond(self, history: list[dict[str, Any]]) -> AsyncIterator[Any]:
        if not self.ollama_ready or not self.model:
            async for chunk in self._echo(history):
                yield chunk
            return

        messages = to_langchain_messages(history)
        want_reasoning = self.show_thinking and self.model not in _NO_REASONING

        for _round in range(MAX_TOOL_ROUNDS):
            gathered = None
            try:
                async for chunk in self._build_llm(want_reasoning).astream(messages):
                    gathered = chunk if gathered is None else gathered + chunk

                    reasoning = chunk.additional_kwargs.get("reasoning_content")
                    if reasoning:
                        yield {"reasoning": reasoning}

                    text = chunk_text(chunk.content)
                    if text:
                        yield text
            except Exception as exc:  # noqa: BLE001 - surfaced in the thread
                detail = str(exc)
                # Models without a thinking mode reject `think: true`; note it
                # and retry this turn without asking for reasoning.
                if want_reasoning and "think" in detail.lower():
                    _NO_REASONING.add(self.model)
                    want_reasoning = False
                    continue
                yield (
                    f"\n\n> **Could not reach the model.** {type(exc).__name__}: "
                    f"{detail[:400]}\n>\n> Check that `ollama serve` is running and "
                    f"that `{self.model}` is pulled."
                )
                return

            calls = list(gathered.tool_calls) if gathered is not None else []
            if not calls:
                return

            # Replay the model's own tool calls, then hand the results back.
            messages.append(AIMessage(content=chunk_text(gathered.content), tool_calls=calls))

            for call in calls:
                part = tool_call_part(
                    call["name"], call.get("args") or {}, tool_call_id=call.get("id")
                )
                yield {"tool_call": part}

                result = await _run_tool(call["name"], call.get("args") or {})
                yield {
                    "tool_call": {
                        **part,
                        "result": result,
                        "is_error": isinstance(result, dict) and "error" in result,
                    }
                }
                messages.append(
                    ToolMessage(
                        content=json.dumps(result, ensure_ascii=False, default=str),
                        tool_call_id=call.get("id") or part["tool_call_id"],
                        name=call["name"],
                    )
                )

        yield "\n\n> Stopped after too many tool rounds."

    async def _echo(self, history: list[dict[str, Any]]) -> AsyncIterator[Any]:
        """A tiny offline stand-in so the demo works without Ollama."""
        question = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        reply = (
            f"{FALLBACK_NOTICE}\n\n"
            f"You said:\n\n> {question or '(nothing)'}\n\n"
            "Meanwhile, here is what this component can render:\n\n"
            "| feature | status |\n| --- | --- |\n"
            "| streaming | live |\n| markdown | yes |\n| code | below |\n\n"
            "```python\n"
            "async def _respond(self, history):\n"
            "    async for chunk in llm.astream(messages):\n"
            "        yield chunk.content\n"
            "```\n"
        )
        for word in reply.split(" "):
            yield word + " "
            await asyncio.sleep(0.012)

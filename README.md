# reflex-assistant-ui

[assistant-ui](https://www.assistant-ui.com/) chat components for
[Reflex](https://reflex.dev), driven entirely from Python state.

The conversation lives in an `rx.State`: messages are plain dicts, streaming is
an `async` generator that `yield`s tokens, and every user action — send, stop,
edit, regenerate, switch branch, pick a conversation — arrives as a normal
Reflex event handler. No API routes, no client-side model calls, no Tailwind.

```bash
pip install reflex-assistant-ui
```

## Hello world

```python
import reflex as rx
from reflex_assistant_ui import AssistantUIState, assistant_ui


class ChatState(AssistantUIState, rx.State):
    async def _respond(self, history):
        for word in "Hello from Python, one token at a time.".split():
            yield word + " "


def index() -> rx.Component:
    return assistant_ui.chat(
        messages=ChatState.messages,
        head_id=ChatState.head_id,
        is_running=ChatState.is_running,
        on_new=ChatState.handle_new,
        on_edit=ChatState.handle_edit,
        on_reload=ChatState.handle_reload,
        on_cancel=ChatState.handle_cancel,
        on_branch_change=ChatState.handle_branch_change,
        height="100vh",
    )


app = rx.App()
app.add_page(index)
```

`AssistantUIState` is a **mixin**, so it must be combined with `rx.State`:
`class ChatState(AssistantUIState, rx.State)`. Inheriting from it alone gives a
class with no state vars.

## What you get

| | |
| --- | --- |
| Streaming | `yield` a token, the thread updates; the stop button cancels mid-run |
| Markdown | GFM, tables, links, and fenced code with syntax highlighting and a copy button |
| Reasoning | `yield {"reasoning": "…"}` renders a block that expands while thinking and folds when done |
| Tool calls | `yield {"tool_call": …}` renders arguments and result in a collapsible card |
| Branching | Editing a message or regenerating a reply creates a sibling; the branch picker walks between them |
| Conversations | A sidebar thread list with create, switch, rename and delete |
| Attachments | Images and text files, via the composer button or drag-and-drop |
| Feedback | Thumbs up/down reported back to Python |
| Floating mode | The same thread inside a launcher popover |
| Theming | Self-contained CSS with light and dark palettes, restyled through CSS variables |

## Components

```python
from reflex_assistant_ui import assistant_ui
```

| Call | Renders |
| --- | --- |
| `assistant_ui.chat(**props)` | Provider + thread. The one-call shortcut. |
| `assistant_ui.floating_chat(**props)` | Provider + launcher button with the thread in a popover. |
| `assistant_ui.provider(*children, **props)` | The runtime. Every other component must be inside one. |
| `assistant_ui.thread(**props)` | The chat surface on its own. |
| `assistant_ui.thread_list(**props)` | The conversation sidebar. |
| `assistant_ui.modal(*children, **props)` | The launcher popover on its own. |

`chat()` and `floating_chat()` route keyword arguments by name: runtime props go
to the provider, everything else (including styling props such as `height`) goes
to the thread. For a custom layout, compose them yourself:

```python
assistant_ui.provider(
    rx.hstack(
        rx.box(assistant_ui.thread_list(), width="17rem"),
        rx.box(assistant_ui.thread(height="100%"), flex="1"),
        height="100%",
    ),
    messages=ChatState.messages,
    on_new=ChatState.handle_new,
    ...,
)
```

### Provider props

`messages`, `head_id`, `is_running`, `is_disabled`, `is_send_disabled`,
`is_loading`, `suggestions`, `thread_list`, `attachments`
(`"none" | "image" | "text" | "all"`), `enable_branching`, `enable_feedback`.

Events: `on_new`, `on_edit`, `on_reload`, `on_cancel`, `on_delete`,
`on_add_tool_result`, `on_feedback`, `on_branch_change`, `on_switch_to_thread`,
`on_switch_to_new_thread`, `on_rename_thread`, `on_archive_thread`,
`on_unarchive_thread`, `on_delete_thread`.

### Thread props

`welcome_title`, `welcome_subtitle`, `welcome_suggestions`, `welcome_icon`,
`placeholder`, `auto_focus`, `show_welcome`, `show_action_bar`,
`show_branch_picker`, `show_feedback`, `show_avatar`, `show_attachments`,
`show_follow_up_suggestions`, `submit_mode` (`"enter" | "ctrlEnter" | "none"`),
`max_width`.

## Writing `_respond`

`_respond` receives the visible branch as `[{"role": ..., "content": ...}]`,
oldest first, with `system_prompt` prepended when set. Yield any of:

```python
yield "a text delta"                       # or {"text": "…"}
yield {"reasoning": "a thinking delta"}
yield {"tool_call": tool_call_part("search", {"q": "reflex"})}
yield {"part": image_part("https://example.com/chart.png")}
```

Re-yield a `tool_call` with the same `tool_call_id` to fill in its result:

```python
from reflex_assistant_ui import tool_call_part

part = tool_call_part("get_weather", {"city": "Caracas"})
yield {"tool_call": part}
yield {"tool_call": {**part, "result": {"temp_c": 29}}}
```

Cancellation is cooperative: the consumer stops as soon as the user presses
stop, and `self._cancel_requested` lets a long generator bail out early.

`stream_interval` (default `0.05`) is the minimum gap between websocket pushes.
Raise it for very long replies, set it to `0` to push on every token.

## Talking to a model

The component does not care how the reply is produced — `_respond` just yields.
The demo uses **LangChain**, which keeps tools as ordinary Python functions:

```python
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama


@tool
def calculate(expression: str) -> dict:
    """Evaluate an arithmetic expression such as '(18 * 7) / 3'."""
    ...


class ChatState(AssistantUIState, rx.State):
    async def _respond(self, history):
        llm = ChatOllama(model="llama3.2", reasoning=True).bind_tools([calculate])
        messages = to_langchain_messages(history)

        gathered = None
        async for chunk in llm.astream(messages):
            gathered = chunk if gathered is None else gathered + chunk

            if reasoning := chunk.additional_kwargs.get("reasoning_content"):
                yield {"reasoning": reasoning}
            if chunk.content:
                yield chunk.content

        for call in gathered.tool_calls:
            part = tool_call_part(call["name"], call["args"], tool_call_id=call["id"])
            yield {"tool_call": part}
            result = await calculate.ainvoke(call["args"])
            yield {"tool_call": {**part, "result": result}}
            # feed the result back and stream the follow-up turn
```

`assistant_ui_demo/assistant_ui_demo/backend.py` has the complete loop, including
the retry that drops `think: true` for models without a reasoning mode.

Nothing ties you to LangChain: any client that can stream — an OpenAI SDK call,
`httpx` against your own endpoint, an agent framework — works the same way.

### Listing local models

LangChain has no model-discovery API, so the package ships a tiny
dependency-free helper for it (it needs only `httpx`, which Reflex already
brings):

```python
from reflex_assistant_ui import ollama

models = await ollama.list_models()      # [] when the server is down
```

## Messages

Messages are dicts, so they serialize into state without any custom types:

```python
{
    "id": "asst-3f2a…",
    "parent_id": "user-91c0…",
    "role": "assistant",
    "content": [{"type": "text", "text": "Hello"}],
    "status": {"type": "complete", "reason": "stop"},
}
```

`parent_id` is what makes branching work — a message with two children is a
fork, and the branch picker walks between them. The helpers keep the shape
consistent:

```python
from reflex_assistant_ui import (
    RUNNING, assistant_message, complete, file_part, image_part,
    reasoning_part, source_part, text_part, tool_call_part, user_message,
)
```

`status` applies to assistant messages only: `RUNNING` while streaming, then
`complete()`, `cancelled()` or `failed(error)`.

## Styling

The package ships one stylesheet, scoped under `.aui-root`, with no Tailwind
dependency. Override the variables to restyle everything:

```css
.aui-root {
  --aui-accent: #7c3aed;
  --aui-accent-fg: #ffffff;
  --aui-radius-xl: 1rem;
  --aui-user-bubble: #ede9fe;
  --aui-thread-max-width: 52rem;
}
```

Dark mode follows Reflex's Radix `.dark` class, an explicit
`[data-theme="dark"]`, or the OS preference.

## Demo

With uv, from the repository root:

```bash
uv sync --extra demo               # package (editable) + langchain-core, langchain-ollama
cd assistant_ui_demo
uv run --extra demo reflex run
```

`uv run` resolves the project from the root `pyproject.toml`, so the `demo`
extra has to be requested there too; `uv pip install -e .` alone does not bring
the LangChain dependencies and the demo fails with
`ModuleNotFoundError: No module named 'langchain_core'`.

With pip:

```bash
cd assistant_ui_demo
pip install -e ..
pip install -r requirements.txt    # brings langchain-core and langchain-ollama
reflex run
```

Four pages:

* `/` — streaming chat through LangChain's `ChatOllama`, with a model picker,
  temperature, tool calling, attachments and feedback. Falls back to a built-in
  echo bot when Ollama is not running, so the demo always starts.
* `/threads` — the same chat plus a conversation sidebar.
* `/floating` — the assistant as a popover over an ordinary page.
* `/showcase` — a scripted conversation exercising every message part, with no
  model required.

For the Ollama pages:

```bash
ollama serve
ollama pull llama3.2        # or any model you already have
```

Tool calling needs a model trained for it (`llama3.2`, `qwen2.5`, `mistral-nemo`
and friends); with other models the demo simply answers without calling tools.

## How it works

`useExternalStoreRuntime` is assistant-ui's adapter for applications that own
their own message state — which is exactly what a Reflex app does. The bridge
(`assistant_ui_bridge.jsx`, shipped with the package and imported by path)
converts Python's message dicts into `ThreadMessageLike` values, hands them to
the runtime as a branchable `ExportedMessageRepository`, and forwards every
runtime callback to a Reflex event. Nothing is inlined into the generated pages,
and the npm dependencies are pinned:

| package | version |
| --- | --- |
| `@assistant-ui/react` | 0.15.19 |
| `@assistant-ui/react-markdown` | 0.14.15 |
| `remark-gfm` | 4.0.1 |
| `react-syntax-highlighter` | 16.1.1 |

On the Python side the package itself depends only on `reflex` and `httpx`. The
demo's LangChain dependencies live in `assistant_ui_demo/requirements.txt`, not
in the package.

Every state delta rebuilds the message repository, which is O(n) in the number
of messages. That is unnoticeable for ordinary conversations; for very long ones
raise `stream_interval` so fewer deltas cross the wire.

## Requirements

Python 3.10+, Reflex 0.9.11+.

## Development

```bash
uv sync --extra dev --extra demo
uv run pytest
uvx ruff check . && uvx ruff format --check custom_components assistant_ui_demo tests
```

GitHub Actions run on every push and pull request to `develop` and `main`:

* **Quality** — ruff lint and format, pytest on Python 3.10–3.13, sdist/wheel
  build with `twine check`, and a production build of the demo app.
* **Security** — gitleaks, bandit, semgrep, pip-audit, dependency review and
  CodeQL (Python and JavaScript), plus a weekly scheduled run.

### Releasing

1. Bump the version in `pyproject.toml` and in
   `custom_components/reflex_assistant_ui/__init__.py`, merge to `main`.
2. Tag the merge commit and push the tag:

   ```bash
   git tag v0.1.0 && git push origin v0.1.0
   ```

The **Release** workflow re-runs quality and security checks, verifies that the
tag is on `main` and matches both versions, builds the distribution, publishes it
to PyPI through Trusted Publishing and creates the GitHub release with the files
attached.

## License

Apache-2.0. assistant-ui is MIT-licensed by AgentbaseAI Inc.

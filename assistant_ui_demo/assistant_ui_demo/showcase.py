"""A scripted conversation that exercises every part type, with no model needed."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import reflex as rx
from reflex_assistant_ui import (
    AssistantUIState,
    assistant_message,
    complete,
    reasoning_part,
    source_part,
    text_part,
    tool_call_part,
    user_message,
)

INTRO = """\
Here is everything the thread can render.

### Markdown

**Bold**, *italic*, `inline code`, [links](https://www.assistant-ui.com/) and lists:

1. ordered items
2. with `code`
   - and nested bullets

> Block quotes keep their own styling.

### Tables

| part type | rendered as |
| --- | --- |
| `text` | markdown |
| `reasoning` | collapsible block |
| `tool-call` | arguments + result |
| `source` | citation chip |

### Code

```python
from reflex_assistant_ui import AssistantUIState

class ChatState(AssistantUIState, rx.State):
    async def _respond(self, history):
        async for token in my_model(history):
            yield token
```

```sql
select model, count(*) as calls
from completions
where created_at > now() - interval '7 days'
group by 1
order by 2 desc;
```
"""

SCRIPT: list[dict[str, Any]] = [
    user_message("Show me what this component can do.", id="demo-user-1"),
    assistant_message(
        [
            reasoning_part(
                "The user wants a tour. I will cover markdown, tables, code blocks, "
                "a tool call and a citation, in that order."
            ),
            text_part(INTRO),
            tool_call_part(
                "search_docs",
                {"query": "assistant-ui message parts", "limit": 3},
                tool_call_id="demo-tool-1",
                result={
                    "hits": [
                        {"title": "Message parts", "score": 0.94},
                        {"title": "External store runtime", "score": 0.91},
                        {"title": "Primitives overview", "score": 0.87},
                    ]
                },
            ),
            text_part(
                "Tool calls show their arguments and their result, and collapse "
                "once you are done reading them."
            ),
            source_part("https://www.assistant-ui.com/docs", "assistant-ui docs"),
            source_part(
                "https://reflex.dev/docs/wrapping-react/overview/", "Reflex: wrapping React"
            ),
        ],
        id="demo-asst-1",
        parent_id="demo-user-1",
        status=complete(),
    ),
]


class ShowcaseState(AssistantUIState, rx.State):
    """Loads a canned conversation, then answers with a short scripted reply."""

    @rx.event
    def on_load(self):
        """Populate the thread the first time the page opens."""
        if not self.messages:
            self.messages = [dict(m) for m in SCRIPT]
            self.head_id = SCRIPT[-1]["id"]
            self.suggestions = [
                {"prompt": "Show me a long code block", "title": "Long code block"},
                {"prompt": "Render a table", "title": "Table"},
            ]

    async def _respond(self, history: list[dict[str, Any]]) -> AsyncIterator[Any]:
        question = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        yield {"reasoning": "Picking an answer for: " + question[:80]}
        await asyncio.sleep(0.2)

        reply = (
            "This page is a static showcase, so I answer from a script.\n\n"
            "Try the other pages for a real model:\n\n"
            "- **Chat** streams from Ollama with tool calling\n"
            "- **Threads** adds a conversation sidebar\n"
            "- **Floating** puts the assistant in a popover\n\n"
            "```ts\n"
            "// every message is a plain dict on the Python side\n"
            'const message = { role: "assistant", content: [{ type: "text", text: "hi" }] };\n'
            "```\n"
        )
        for token in reply.split(" "):
            yield token + " "
            await asyncio.sleep(0.02)

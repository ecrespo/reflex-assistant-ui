"""reflex-assistant-ui — assistant-ui chat components for Reflex.

Quick start::

    import reflex as rx
    from reflex_assistant_ui import AssistantUIState, assistant_ui

    class ChatState(AssistantUIState, rx.State):
        async def _respond(self, history):
            yield "Hello from Python!"

    def index() -> rx.Component:
        return assistant_ui.chat(
            messages=ChatState.messages,
            head_id=ChatState.head_id,
            is_running=ChatState.is_running,
            on_new=ChatState.handle_new,
            on_cancel=ChatState.handle_cancel,
            height="100vh",
        )
"""

from . import assistant_ui, messages, ollama
from .assistant_ui import (
    AssistantModal,
    AssistantProvider,
    AssistantThread,
    ThreadList,
    chat,
    floating_chat,
    modal,
    provider,
    thread,
    thread_list,
)
from .messages import (
    RUNNING,
    assistant_message,
    cancelled,
    complete,
    failed,
    file_part,
    image_part,
    message_text,
    new_id,
    reasoning_part,
    source_part,
    system_message,
    text_part,
    tool_call_part,
    user_message,
)
from .state import AssistantUIState

__version__ = "0.1.0"

__all__ = [
    "RUNNING",
    "AssistantModal",
    "AssistantProvider",
    "AssistantThread",
    "AssistantUIState",
    "ThreadList",
    "__version__",
    "assistant_message",
    "assistant_ui",
    "cancelled",
    "chat",
    "complete",
    "failed",
    "file_part",
    "floating_chat",
    "image_part",
    "message_text",
    "messages",
    "modal",
    "new_id",
    "ollama",
    "provider",
    "reasoning_part",
    "source_part",
    "system_message",
    "text_part",
    "thread",
    "thread_list",
    "tool_call_part",
    "user_message",
]

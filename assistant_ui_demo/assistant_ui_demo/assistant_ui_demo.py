"""reflex-assistant-ui demo.

Four pages, one component:

* ``/``          streaming chat against a local Ollama, with tool calling
* ``/threads``   the same chat plus a conversation sidebar
* ``/floating``  the assistant as a floating popover over a normal page
* ``/showcase``  a scripted conversation exercising every message part
"""

from __future__ import annotations

import reflex as rx
from reflex_assistant_ui import assistant_ui

from .backend import ChatState
from .showcase import ShowcaseState
from .threads import ThreadsState

WELCOME_SUGGESTIONS = [
    {"prompt": "What time is it in Caracas?", "title": "What time is it?", "label": "uses a tool"},
    {
        "prompt": "Compute (18 * 7) / 3 and explain the steps.",
        "title": "Do some math",
        "label": "uses a tool",
    },
    {"prompt": "Write a Python async generator that streams tokens.", "title": "Write some code"},
    {
        "prompt": "Summarize the difference between Reflex and Streamlit.",
        "title": "Compare two things",
    },
]

NAV = [
    ("Chat", "/"),
    ("Threads", "/threads"),
    ("Floating", "/floating"),
    ("Showcase", "/showcase"),
]


def navbar(active: str) -> rx.Component:
    """Top bar shared by every page."""
    return rx.hstack(
        rx.hstack(
            rx.icon("message-circle", size=18),
            rx.heading(
                "reflex-assistant-ui",
                size="4",
                white_space="nowrap",
            ),
            spacing="2",
            align="center",
        ),
        rx.spacer(),
        rx.hstack(
            *[
                rx.link(
                    label,
                    href=href,
                    weight="medium",
                    size="2",
                    color_scheme=rx.cond(active == href, "violet", "gray"),
                    underline="none",
                )
                for label, href in NAV
            ],
            spacing="4",
            wrap="wrap",
        ),
        rx.color_mode.button(),
        width="100%",
        max_width="100%",
        padding="0.6rem 1rem",
        border_bottom="1px solid var(--gray-a5)",
        align="center",
        spacing="3",
        wrap="wrap",
        overflow="hidden",
    )


def settings_bar() -> rx.Component:
    """Model picker and generation options for the main chat page."""
    return rx.hstack(
        rx.badge(
            ChatState.status_label,
            color_scheme=rx.cond(ChatState.ollama_ready, "green", "amber"),
            variant="soft",
            size="2",
        ),
        rx.cond(
            ChatState.models.length() > 0,
            rx.select(
                ChatState.models,
                value=ChatState.model,
                on_change=ChatState.set_model,
                size="2",
                width="16rem",
            ),
        ),
        rx.hstack(
            rx.text("temp", size="1", color_scheme="gray"),
            rx.text(ChatState.temperature.to_string(), size="1", weight="medium"),
            spacing="1",
            align="center",
        ),
        rx.slider(
            default_value=[70],
            min=0,
            max=150,
            step=5,
            on_change=ChatState.set_temperature,
            width="7rem",
        ),
        rx.hstack(
            rx.switch(
                checked=ChatState.enable_tools,
                on_change=ChatState.toggle_tools,
                size="1",
            ),
            rx.text("tools", size="1", color_scheme="gray"),
            spacing="1",
            align="center",
        ),
        rx.hstack(
            rx.switch(
                checked=ChatState.show_thinking,
                on_change=ChatState.toggle_thinking,
                size="1",
            ),
            rx.text("reasoning", size="1", color_scheme="gray"),
            spacing="1",
            align="center",
        ),
        rx.spacer(),
        rx.button(
            rx.icon("refresh-cw", size=14),
            "Models",
            on_click=ChatState.refresh_models,
            variant="soft",
            size="2",
        ),
        rx.button(
            rx.icon("plus", size=14),
            "New",
            on_click=ChatState.new_conversation,
            variant="soft",
            size="2",
        ),
        width="100%",
        padding="0.5rem 1rem",
        border_bottom="1px solid var(--gray-a5)",
        align="center",
        spacing="3",
        wrap="wrap",
    )


@rx.page(route="/", title="Chat · reflex-assistant-ui", on_load=ChatState.refresh_models)
def index() -> rx.Component:
    """Streaming chat backed by Ollama, with tool calling and branching."""
    return rx.vstack(
        navbar("/"),
        settings_bar(),
        rx.box(
            assistant_ui.chat(
                messages=ChatState.messages,
                head_id=ChatState.head_id,
                is_running=ChatState.is_running,
                suggestions=ChatState.suggestions,
                on_new=ChatState.handle_new,
                on_edit=ChatState.handle_edit,
                on_reload=ChatState.handle_reload,
                on_cancel=ChatState.handle_cancel,
                on_delete=ChatState.handle_delete,
                on_branch_change=ChatState.handle_branch_change,
                on_feedback=ChatState.handle_feedback,
                enable_feedback=True,
                show_feedback=True,
                attachments="all",
                show_attachments=True,
                welcome_title="Ask anything",
                welcome_subtitle=(
                    "Streamed from a local model through Reflex state. "
                    "Edit a message to branch the conversation."
                ),
                welcome_suggestions=WELCOME_SUGGESTIONS,
                placeholder="Message the model…",
                height="100%",
            ),
            width="100%",
            flex="1 1 auto",
            min_height="0",
        ),
        width="100%",
        height="100vh",
        spacing="0",
    )


@rx.page(
    route="/threads",
    title="Threads · reflex-assistant-ui",
    on_load=ThreadsState.on_load,
)
def threads_page() -> rx.Component:
    """The same chat with a conversation sidebar."""
    return rx.vstack(
        navbar("/threads"),
        assistant_ui.provider(
            rx.hstack(
                rx.box(
                    assistant_ui.thread_list(
                        new_thread_label="New conversation",
                        show_delete=True,
                    ),
                    width="17rem",
                    flex="none",
                    height="100%",
                    border_right="1px solid var(--gray-a5)",
                    display=["none", "none", "block", "block"],
                ),
                rx.box(
                    assistant_ui.thread(
                        welcome_title="A conversation per thread",
                        welcome_subtitle=(
                            "Each entry in the sidebar keeps its own history, "
                            "branches and head position."
                        ),
                        height="100%",
                    ),
                    flex="1 1 auto",
                    min_width="0",
                    height="100%",
                ),
                width="100%",
                height="100%",
                spacing="0",
            ),
            messages=ThreadsState.messages,
            head_id=ThreadsState.head_id,
            is_running=ThreadsState.is_running,
            thread_list=ThreadsState.thread_list,
            on_new=ThreadsState.handle_new,
            on_edit=ThreadsState.handle_edit,
            on_reload=ThreadsState.handle_reload,
            on_cancel=ThreadsState.handle_cancel,
            on_branch_change=ThreadsState.handle_branch_change,
            on_switch_to_thread=ThreadsState.handle_switch_to_thread,
            on_switch_to_new_thread=ThreadsState.handle_new_thread,
            on_rename_thread=ThreadsState.handle_rename_thread,
            on_delete_thread=ThreadsState.handle_delete_thread,
        ),
        width="100%",
        height="100vh",
        spacing="0",
    )


@rx.page(
    route="/floating",
    title="Floating · reflex-assistant-ui",
    on_load=ChatState.refresh_models,
)
def floating_page() -> rx.Component:
    """A normal page with the assistant tucked into a corner."""
    return rx.fragment(
        rx.vstack(
            navbar("/floating"),
            rx.container(
                rx.vstack(
                    rx.heading("Your application", size="7"),
                    rx.text(
                        "The assistant lives in the bottom-right corner and opens "
                        "over whatever is on screen. It shares the same state and "
                        "the same event handlers as the full-page chat.",
                        color_scheme="gray",
                    ),
                    rx.card(
                        rx.vstack(
                            rx.heading("Why a popover", size="4"),
                            rx.text(
                                "Support widgets, in-app copilots and onboarding "
                                "assistants all want the conversation available "
                                "without taking over the page.",
                                size="2",
                                color_scheme="gray",
                            ),
                            spacing="2",
                            align="start",
                        ),
                        width="100%",
                    ),
                    spacing="4",
                    align="start",
                    padding_y="2rem",
                ),
                size="3",
            ),
            width="100%",
            spacing="0",
        ),
        assistant_ui.floating_chat(
            messages=ChatState.messages,
            head_id=ChatState.head_id,
            is_running=ChatState.is_running,
            on_new=ChatState.handle_new,
            on_edit=ChatState.handle_edit,
            on_reload=ChatState.handle_reload,
            on_cancel=ChatState.handle_cancel,
            on_branch_change=ChatState.handle_branch_change,
            welcome_title="Need a hand?",
            welcome_icon=False,
            show_avatar=False,
            max_width="100%",
            placeholder="Ask about this page…",
        ),
    )


@rx.page(
    route="/showcase",
    title="Showcase · reflex-assistant-ui",
    on_load=ShowcaseState.on_load,
)
def showcase_page() -> rx.Component:
    """Every message part, without needing a model."""
    return rx.vstack(
        navbar("/showcase"),
        rx.box(
            assistant_ui.chat(
                messages=ShowcaseState.messages,
                head_id=ShowcaseState.head_id,
                is_running=ShowcaseState.is_running,
                suggestions=ShowcaseState.suggestions,
                on_new=ShowcaseState.handle_new,
                on_edit=ShowcaseState.handle_edit,
                on_reload=ShowcaseState.handle_reload,
                on_cancel=ShowcaseState.handle_cancel,
                on_branch_change=ShowcaseState.handle_branch_change,
                show_welcome=False,
                height="100%",
            ),
            width="100%",
            flex="1 1 auto",
            min_height="0",
        ),
        width="100%",
        height="100vh",
        spacing="0",
    )


# The Radix theme is configured through RadixThemesPlugin in rxconfig.py.
app = rx.App()

"""Reflex components wrapping assistant-ui.

The React side lives in ``assistant_ui_bridge.jsx``; it is shipped with the
package, symlinked into the app's public assets at compile time and imported by
path, so none of it is inlined into the generated pages.

Typical use::

    import reflex as rx
    from reflex_assistant_ui import assistant_ui

    def index() -> rx.Component:
        return assistant_ui.chat(
            messages=ChatState.messages,
            is_running=ChatState.is_running,
            on_new=ChatState.handle_new,
            on_cancel=ChatState.handle_cancel,
        )
"""

from __future__ import annotations

from typing import Any

import reflex as rx
from reflex.event import no_args_event_spec, passthrough_event_spec

__all__ = [
    "AssistantModal",
    "AssistantProvider",
    "AssistantThread",
    "ThreadList",
    "chat",
    "floating_chat",
    "modal",
    "provider",
    "thread",
    "thread_list",
]

# npm packages the bridge needs at runtime. Pinned so a Reflex app gets a
# reproducible frontend install.
_ASSISTANT_UI = "@assistant-ui/react@0.15.19"
_ASSISTANT_UI_MARKDOWN = "@assistant-ui/react-markdown@0.14.15"
_REMARK_GFM = "remark-gfm@4.0.1"
_SYNTAX_HIGHLIGHTER = "react-syntax-highlighter@16.1.1"

# Shipped frontend files. ``shared=True`` links them into the consuming app's
# external assets; ``importable_path`` is the build-time module specifier.
_BRIDGE = rx.asset("assistant_ui_bridge.jsx", shared=True)
_STYLESHEET = rx.asset("assistant_ui.css", shared=True)


# --------------------------------------------------------------------- #
# Event argument specs
# --------------------------------------------------------------------- #


def _parent_id_spec(parent_id: rx.Var[str]) -> tuple[rx.Var[str]]:
    """Map ``onReload(parentId)`` onto a single handler argument."""
    return (parent_id,)


def _rename_spec(thread_id: rx.Var[str], title: rx.Var[str]) -> tuple[rx.Var[str], rx.Var[str]]:
    """Map ``onRename(threadId, title)`` onto two handler arguments."""
    return (thread_id, title)


class _AssistantUIBase(rx.Component):
    """Shared plumbing: the bridge module, the npm deps and the stylesheet."""

    library = _BRIDGE.importable_path

    lib_dependencies: list[str] = [
        _ASSISTANT_UI,
        _ASSISTANT_UI_MARKDOWN,
        _REMARK_GFM,
        _SYNTAX_HIGHLIGHTER,
    ]

    def add_imports(self) -> rx.ImportDict:
        """Pull in the package stylesheet as a side-effect import."""
        return {"": _STYLESHEET.importable_path}


class AssistantProvider(_AssistantUIBase):
    """Supplies the assistant-ui runtime backed by Reflex state.

    Every visual component (`thread`, `thread_list`, `modal`) must be rendered
    inside a provider. The provider owns no state of its own: the message list,
    the running flag and the thread list all come from props, and every user
    action is forwarded to a Reflex event handler.
    """

    tag = "AuiProvider"

    # The conversation, oldest first. Each entry is a dict with at least
    # ``role`` and ``content``; ``id`` and ``parent_id`` enable branching.
    messages: rx.Var[list[dict[str, Any]]]

    # Id of the message at the tip of the visible branch. Defaults to the last
    # message when omitted.
    head_id: rx.Var[str]

    # Whether a response is being generated. Drives the stop button and the
    # typing indicator.
    is_running: rx.Var[bool] = False

    # Disables the whole thread, composer included.
    is_disabled: rx.Var[bool] = False

    # Keeps the composer usable but blocks sending.
    is_send_disabled: rx.Var[bool] = False

    # Shows the thread-loading state.
    is_loading: rx.Var[bool] = False

    # Follow-up suggestions offered after a reply. Strings, or dicts with
    # ``prompt``/``title``/``label``.
    suggestions: rx.Var[list[Any]]

    # Multi-conversation support: ``{"thread_id": ..., "threads": [...]}``.
    thread_list: rx.Var[dict[str, Any]]

    # Attachment support: "none", "image", "text" or "all".
    attachments: rx.Var[str] = "none"

    # Build a branchable message repository so edit/regenerate create branches
    # instead of overwriting history.
    enable_branching: rx.Var[bool] = True

    # Show thumbs up/down on assistant messages (requires ``on_feedback``).
    enable_feedback: rx.Var[bool] = False

    # The user submitted a message. Receives the serialized message dict.
    on_new: rx.EventHandler[passthrough_event_spec(dict)]

    # The user saved an edit of an earlier message.
    on_edit: rx.EventHandler[passthrough_event_spec(dict)]

    # The user asked to regenerate. Receives the parent message id.
    on_reload: rx.EventHandler[_parent_id_spec]

    # The user pressed stop.
    on_cancel: rx.EventHandler[no_args_event_spec]

    # The user deleted a message. Receives the message id.
    on_delete: rx.EventHandler[passthrough_event_spec(str)]

    # A client-side tool produced a result.
    on_add_tool_result: rx.EventHandler[passthrough_event_spec(dict)]

    # The user rated a message: ``{"message_id": ..., "type": "positive"}``.
    on_feedback: rx.EventHandler[passthrough_event_spec(dict)]

    # The visible branch changed: ``{"head_id": ..., "visible_message_ids": [...]}``.
    on_branch_change: rx.EventHandler[passthrough_event_spec(dict)]

    # Thread list: the user selected a conversation.
    on_switch_to_thread: rx.EventHandler[passthrough_event_spec(str)]

    # Thread list: the user started a new conversation.
    on_switch_to_new_thread: rx.EventHandler[no_args_event_spec]

    # Thread list: the user renamed a conversation.
    on_rename_thread: rx.EventHandler[_rename_spec]

    # Thread list: the user archived a conversation.
    on_archive_thread: rx.EventHandler[passthrough_event_spec(str)]

    # Thread list: the user unarchived a conversation.
    on_unarchive_thread: rx.EventHandler[passthrough_event_spec(str)]

    # Thread list: the user deleted a conversation.
    on_delete_thread: rx.EventHandler[passthrough_event_spec(str)]


class AssistantThread(_AssistantUIBase):
    """The chat surface: message list, composer, action bars and branch picker."""

    tag = "AuiThread"

    # Heading shown while the thread is empty.
    welcome_title: rx.Var[str] = "How can I help you today?"

    # Secondary line under the heading.
    welcome_subtitle: rx.Var[str] = ""

    # Starter prompts on the empty state. Strings, or dicts with
    # ``prompt``/``title``/``label``.
    welcome_suggestions: rx.Var[list[Any]]

    # Show the sparkle badge above the welcome heading.
    welcome_icon: rx.Var[bool] = True

    # Composer placeholder.
    placeholder: rx.Var[str] = "Send a message..."

    # Focus the composer on mount.
    auto_focus: rx.Var[bool] = True

    # Render the empty state at all.
    show_welcome: rx.Var[bool] = True

    # Copy / regenerate / edit buttons on messages.
    show_action_bar: rx.Var[bool] = True

    # Branch navigation on messages that have siblings.
    show_branch_picker: rx.Var[bool] = True

    # Thumbs up/down (also needs ``enable_feedback`` on the provider).
    show_feedback: rx.Var[bool] = False

    # Assistant avatar next to each reply.
    show_avatar: rx.Var[bool] = True

    # Attachment button and drop zone (also needs ``attachments`` on the provider).
    show_attachments: rx.Var[bool] = False

    # Render follow-up suggestions above the composer.
    show_follow_up_suggestions: rx.Var[bool] = True

    # How Enter behaves: "enter", "ctrlEnter" or "none".
    submit_mode: rx.Var[str] = "enter"

    # Max width of the conversation column.
    max_width: rx.Var[str] = "44rem"


class ThreadList(_AssistantUIBase):
    """Sidebar list of conversations, driven by the provider's ``thread_list``."""

    tag = "AuiThreadList"

    # Label of the "new conversation" button.
    new_thread_label: rx.Var[str] = "New chat"

    # Show the archive button on each row.
    show_archive: rx.Var[bool] = False

    # Show the delete button on each row.
    show_delete: rx.Var[bool] = True

    # Text shown when there are no conversations.
    empty_label: rx.Var[str] = "No conversations yet"


class AssistantModal(_AssistantUIBase):
    """Floating launcher button with the thread in a popover."""

    tag = "AuiModal"

    # Open the popover automatically when a run starts.
    open_on_run_start: rx.Var[bool] = True

    # Which corner to anchor to: "right" or "left".
    side: rx.Var[str] = "right"

    # CSS width of the popover.
    width: rx.Var[str] = "min(26rem, calc(100vw - 2rem))"

    # CSS height of the popover.
    height: rx.Var[str] = "min(36rem, calc(100vh - 6rem))"


provider = AssistantProvider.create
thread = AssistantThread.create
thread_list = ThreadList.create
modal = AssistantModal.create


_THREAD_FIELDS = frozenset(AssistantThread.get_fields())
_PROVIDER_ONLY_FIELDS = frozenset(AssistantProvider.get_fields()) - _THREAD_FIELDS
_MODAL_ONLY_FIELDS = frozenset(AssistantModal.get_fields()) - _THREAD_FIELDS


def _split(props: dict[str, Any], *field_sets: frozenset) -> list[dict[str, Any]]:
    """Route kwargs to the first component that declares each name.

    Anything no component claims (``height``, ``class_name``, ``style``, …)
    falls through to the last bucket, which is always the thread.
    """
    buckets: list[dict[str, Any]] = [{} for _ in range(len(field_sets) + 1)]
    for key, value in props.items():
        for index, fields in enumerate(field_sets):
            if key in fields:
                buckets[index][key] = value
                break
        else:
            buckets[-1][key] = value
    return buckets


def chat(**props: Any) -> rx.Component:
    """Provider + thread in one call.

    Props are routed by name: provider-only props (``messages``, ``on_new``,
    ``is_running``, …) configure the runtime, everything else — thread options
    and ordinary styling props such as ``height`` — goes to the thread. Use it
    for the common single-conversation case, and drop down to ``provider`` +
    ``thread`` when you need a custom layout.
    """
    provider_props, thread_props = _split(props, _PROVIDER_ONLY_FIELDS)
    return provider(thread(**thread_props), **provider_props)


def floating_chat(**props: Any) -> rx.Component:
    """Provider + floating launcher button with the thread inside its popover."""
    provider_props, modal_props, thread_props = _split(
        props, _PROVIDER_ONLY_FIELDS, _MODAL_ONLY_FIELDS
    )
    return provider(modal(thread(**thread_props), **modal_props), **provider_props)

/**
 * reflex-assistant-ui — React bridge between Reflex state and assistant-ui.
 *
 * Reflex owns the conversation: messages live in a Python `rx.State`, are
 * serialized into props, and every user interaction is forwarded back to the
 * backend as a Reflex event. This module adapts that one-way-data-flow model
 * onto assistant-ui's `useExternalStoreRuntime`.
 *
 * Everything here is deliberately dependency-light: icons are inline SVG and
 * styling is plain CSS (see assistant_ui.css), so the component works in a
 * stock Reflex app with no Tailwind and no shadcn setup.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActionBarPrimitive,
  AssistantRuntimeProvider,
  AttachmentPrimitive,
  AuiIf,
  BranchPickerPrimitive,
  ComposerPrimitive,
  CompositeAttachmentAdapter,
  ErrorPrimitive,
  ExportedMessageRepository,
  MessagePrimitive,
  SimpleImageAttachmentAdapter,
  SimpleTextAttachmentAdapter,
  SuggestionPrimitive,
  ThreadListItemPrimitive,
  ThreadListPrimitive,
  ThreadPrimitive,
  groupPartByType,
  useAui,
  useExternalStoreRuntime,
} from "@assistant-ui/react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";
import { PrismAsyncLight } from "react-syntax-highlighter";

/* ------------------------------------------------------------------ *
 * Icons (inline so the package pulls in no icon dependency)
 * ------------------------------------------------------------------ */

const Svg = ({ children, ...rest }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    focusable="false"
    {...rest}
  >
    {children}
  </svg>
);

const IconArrowUp = (p) => (
  <Svg {...p}>
    <path d="M12 19V5" />
    <path d="m5 12 7-7 7 7" />
  </Svg>
);
const IconArrowDown = (p) => (
  <Svg {...p}>
    <path d="M12 5v14" />
    <path d="m19 12-7 7-7-7" />
  </Svg>
);
const IconSquare = (p) => (
  <Svg fill="currentColor" stroke="none" {...p}>
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </Svg>
);
const IconCopy = (p) => (
  <Svg {...p}>
    <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
    <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
  </Svg>
);
const IconCheck = (p) => (
  <Svg {...p}>
    <path d="M20 6 9 17l-5-5" />
  </Svg>
);
const IconRefresh = (p) => (
  <Svg {...p}>
    <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
    <path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
    <path d="M8 16H3v5" />
  </Svg>
);
const IconPencil = (p) => (
  <Svg {...p}>
    <path d="M21.17 2.83a3 3 0 0 0-4.24 0L3 16.76V21h4.24L21.17 7.07a3 3 0 0 0 0-4.24Z" />
  </Svg>
);
const IconChevronLeft = (p) => (
  <Svg {...p}>
    <path d="m15 18-6-6 6-6" />
  </Svg>
);
const IconChevronRight = (p) => (
  <Svg {...p}>
    <path d="m9 18 6-6-6-6" />
  </Svg>
);
const IconChevronDown = (p) => (
  <Svg {...p}>
    <path d="m6 9 6 6 6-6" />
  </Svg>
);
const IconPaperclip = (p) => (
  <Svg {...p}>
    <path d="M21.44 11.05 12.25 20.24a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
  </Svg>
);
const IconX = (p) => (
  <Svg {...p}>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </Svg>
);
const IconPlus = (p) => (
  <Svg {...p}>
    <path d="M5 12h14" />
    <path d="M12 5v14" />
  </Svg>
);
const IconTrash = (p) => (
  <Svg {...p}>
    <path d="M3 6h18" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
    <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
  </Svg>
);
const IconArchive = (p) => (
  <Svg {...p}>
    <rect width="20" height="5" x="2" y="3" rx="1" />
    <path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" />
    <path d="M10 12h4" />
  </Svg>
);
const IconThumbUp = (p) => (
  <Svg {...p}>
    <path d="M7 10v12" />
    <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
  </Svg>
);
const IconThumbDown = (p) => (
  <Svg {...p}>
    <path d="M17 14V2" />
    <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
  </Svg>
);
const IconSparkles = (p) => (
  <Svg {...p}>
    <path d="M9.94 6.06 9 3l-.94 3.06L5 7l3.06.94L9 11l.94-3.06L13 7Z" />
    <path d="M17.5 12.5 16.5 9l-1 3.5L12 13.5l3.5 1 1 3.5 1-3.5 3.5-1Z" />
  </Svg>
);
const IconBot = (p) => (
  <Svg {...p}>
    <rect width="18" height="12" x="3" y="8" rx="2" />
    <path d="M12 8V4" />
    <circle cx="12" cy="3" r="1" />
    <path d="M8 13h.01" />
    <path d="M16 13h.01" />
    <path d="M9 17h6" />
  </Svg>
);
const IconWrench = (p) => (
  <Svg {...p}>
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76Z" />
  </Svg>
);
const IconBrain = (p) => (
  <Svg {...p}>
    <path d="M12 5a3 3 0 1 0-5.997.142 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
    <path d="M12 5a3 3 0 1 1 5.997.142 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z" />
  </Svg>
);
const IconAlert = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 8v4" />
    <path d="M12 16h.01" />
  </Svg>
);
const IconFile = (p) => (
  <Svg {...p}>
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
    <path d="M14 2v5h5" />
  </Svg>
);
const IconSpinner = (p) => (
  <Svg className="aui-spin" {...p}>
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </Svg>
);

/* ------------------------------------------------------------------ *
 * Serialization helpers: Python (snake_case) <-> assistant-ui (camelCase)
 * ------------------------------------------------------------------ */

const pick = (obj, ...keys) => {
  for (const key of keys) {
    if (obj != null && obj[key] !== undefined) return obj[key];
  }
  return undefined;
};

const setIf = (target, key, value) => {
  if (value !== undefined && value !== null) target[key] = value;
};

/** Convert one message part sent from Python into a ThreadMessageLike part. */
const toPart = (part) => {
  if (part == null) return null;
  if (typeof part === "string") return { type: "text", text: part };

  const type = part.type ?? "text";
  const status = pick(part, "status");

  switch (type) {
    case "text": {
      const out = { type: "text", text: part.text ?? "" };
      setIf(out, "status", status);
      return out;
    }
    case "reasoning": {
      const out = { type: "reasoning", text: part.text ?? "" };
      setIf(out, "status", status);
      setIf(out, "unstable_summary", pick(part, "summary", "unstable_summary"));
      return out;
    }
    case "tool-call":
    case "tool_call": {
      const out = {
        type: "tool-call",
        toolName: pick(part, "toolName", "tool_name", "name") ?? "tool",
      };
      setIf(out, "toolCallId", pick(part, "toolCallId", "tool_call_id", "id"));
      setIf(out, "args", pick(part, "args", "arguments"));
      setIf(out, "argsText", pick(part, "argsText", "args_text"));
      setIf(out, "result", pick(part, "result", "output"));
      setIf(out, "isError", pick(part, "isError", "is_error"));
      setIf(out, "artifact", pick(part, "artifact"));
      return out;
    }
    case "image":
      return { type: "image", image: pick(part, "image", "url", "data") ?? "" };
    case "file": {
      const out = {
        type: "file",
        data: pick(part, "data", "url") ?? "",
        mimeType: pick(part, "mimeType", "mime_type", "media_type") ?? "application/octet-stream",
      };
      setIf(out, "filename", pick(part, "filename", "file_name", "name"));
      setIf(out, "sourceType", pick(part, "sourceType", "source_type"));
      return out;
    }
    case "source": {
      const out = {
        type: "source",
        sourceType: pick(part, "sourceType", "source_type") ?? "url",
        id: String(pick(part, "id") ?? Math.random().toString(36).slice(2)),
      };
      setIf(out, "url", pick(part, "url"));
      setIf(out, "title", pick(part, "title"));
      setIf(out, "mediaType", pick(part, "mediaType", "media_type"));
      setIf(out, "filename", pick(part, "filename", "file_name"));
      return out;
    }
    case "data":
      return { type: "data", name: pick(part, "name") ?? "data", data: pick(part, "data") };
    default:
      return { type: "text", text: part.text ?? "" };
  }
};

const toContent = (content) => {
  if (content == null) return [];
  if (typeof content === "string") return [{ type: "text", text: content }];
  if (!Array.isArray(content)) return [];
  return content.map(toPart).filter(Boolean);
};

/** Convert one message sent from Python into a ThreadMessageLike. */
const toThreadMessage = (msg, index) => {
  const role = msg?.role ?? "assistant";
  const out = {
    role,
    content: toContent(msg?.content),
    id: String(pick(msg, "id") ?? `aui-${index}`),
  };

  const createdAt = pick(msg, "createdAt", "created_at");
  if (createdAt) {
    const date = createdAt instanceof Date ? createdAt : new Date(createdAt);
    if (!Number.isNaN(date.getTime())) out.createdAt = date;
  }

  // `status` is only legal on assistant messages; the runtime throws otherwise.
  if (role === "assistant") {
    const status = pick(msg, "status");
    if (status) out.status = typeof status === "string" ? { type: status } : status;
  }

  if (role === "user") {
    const attachments = pick(msg, "attachments");
    if (Array.isArray(attachments) && attachments.length) {
      out.attachments = attachments.map((att, i) => ({
        id: String(pick(att, "id") ?? `att-${index}-${i}`),
        type: pick(att, "type") ?? "file",
        name: pick(att, "name", "filename", "file_name") ?? "attachment",
        contentType: pick(att, "contentType", "content_type", "mime_type") ?? "application/octet-stream",
        status: pick(att, "status") ?? { type: "complete" },
        content: toContent(pick(att, "content")),
      }));
    }
  }

  const metadata = pick(msg, "metadata");
  const feedback = pick(msg, "feedback");
  if (metadata || feedback) {
    out.metadata = { ...(metadata ?? {}) };
    if (feedback) out.metadata.submittedFeedback = { type: feedback };
  }

  return out;
};

/** Serialize an assistant-ui message part back into a plain dict for Python. */
const fromPart = (part) => {
  switch (part?.type) {
    case "text":
      return { type: "text", text: part.text ?? "" };
    case "reasoning":
      return { type: "reasoning", text: part.text ?? "" };
    case "tool-call":
      return {
        type: "tool-call",
        tool_call_id: part.toolCallId ?? null,
        tool_name: part.toolName ?? "",
        args: part.args ?? {},
        args_text: part.argsText ?? "",
        result: part.result ?? null,
        is_error: !!part.isError,
      };
    case "image":
      return { type: "image", image: part.image ?? "" };
    case "file":
      return {
        type: "file",
        data: part.data ?? "",
        mime_type: part.mimeType ?? "",
        filename: part.filename ?? null,
      };
    case "source":
      return {
        type: "source",
        source_type: part.sourceType ?? "url",
        id: part.id ?? "",
        url: part.url ?? null,
        title: part.title ?? null,
      };
    default:
      return { type: part?.type ?? "unknown", text: part?.text ?? "" };
  }
};

/** Flatten every text part of a message into a single string. */
const plainText = (content) =>
  (content ?? [])
    .filter((p) => p?.type === "text")
    .map((p) => p.text ?? "")
    .join("");

/**
 * Serialize an `AppendMessage` into the dict a Reflex event handler receives.
 * Keys are snake_case so Python code reads naturally.
 */
const fromAppendMessage = (message) => ({
  role: message?.role ?? "user",
  content: (message?.content ?? []).map(fromPart),
  text: plainText(message?.content),
  parent_id: message?.parentId ?? null,
  source_id: message?.sourceId ?? null,
  run_config: message?.runConfig ?? null,
  attachments: (message?.attachments ?? []).map((att) => ({
    id: att?.id ?? null,
    name: att?.name ?? "",
    type: att?.type ?? "file",
    content_type: att?.contentType ?? "",
    content: (att?.content ?? []).map(fromPart),
  })),
});

/* ------------------------------------------------------------------ *
 * Provider — turns Reflex props into an ExternalStore runtime
 * ------------------------------------------------------------------ */

const EMPTY = [];

const buildAttachmentAdapter = (mode) => {
  if (!mode || mode === "none") return undefined;
  const adapters = [];
  if (mode === "image" || mode === "all") adapters.push(new SimpleImageAttachmentAdapter());
  if (mode === "text" || mode === "all") adapters.push(new SimpleTextAttachmentAdapter());
  if (!adapters.length) return undefined;
  return adapters.length === 1 ? adapters[0] : new CompositeAttachmentAdapter(adapters);
};

export const AuiProvider = ({
  children,
  messages = EMPTY,
  headId = null,
  isRunning = false,
  isDisabled = false,
  isSendDisabled = false,
  isLoading = false,
  suggestions = EMPTY,
  threadList = null,
  attachments = "none",
  enableBranching = true,
  enableFeedback = false,
  onNew,
  onEdit,
  onReload,
  onCancel,
  onDelete,
  onAddToolResult,
  onFeedback,
  onBranchChange,
  onSwitchToThread,
  onSwitchToNewThread,
  onRenameThread,
  onArchiveThread,
  onUnarchiveThread,
  onDeleteThread,
}) => {
  /**
   * Branch switching is answered locally first so the UI reacts instantly,
   * then reconciled with whatever head the backend reports next.
   */
  const [localHead, setLocalHead] = useState(null);
  const messagesRef = useRef(messages);
  useEffect(() => {
    if (messagesRef.current !== messages) {
      messagesRef.current = messages;
      setLocalHead(null);
    }
  }, [messages]);
  useEffect(() => {
    setLocalHead(null);
  }, [headId]);

  const converted = useMemo(
    () => (Array.isArray(messages) ? messages.map(toThreadMessage) : []),
    [messages],
  );

  /**
   * Every message carries a parent id, so the conversation is handed to the
   * runtime as a branchable repository. That is what powers edit, regenerate
   * and the branch picker. When no parent ids are present the chain is linear
   * and the picker simply stays hidden.
   */
  const repository = useMemo(() => {
    if (!enableBranching) return null;
    if (!Array.isArray(messages) || messages.length === 0) {
      return { messages: [], headId: null };
    }
    const ids = converted.map((m) => m.id);
    const known = new Set(ids);
    const items = converted.map((message, index) => {
      const raw = messages[index] ?? {};
      let parentId = pick(raw, "parentId", "parent_id");
      if (parentId === undefined) parentId = index > 0 ? ids[index - 1] : null;
      if (parentId != null && !known.has(String(parentId))) parentId = null;
      return { message, parentId: parentId == null ? null : String(parentId) };
    });
    try {
      const resolvedHead = localHead ?? headId ?? ids[ids.length - 1] ?? null;
      return ExportedMessageRepository.fromBranchableArray(items, {
        headId: known.has(String(resolvedHead)) ? String(resolvedHead) : ids[ids.length - 1] ?? null,
      });
    } catch (error) {
      console.error("[reflex-assistant-ui] could not build message repository", error);
      return null;
    }
  }, [converted, messages, headId, localHead, enableBranching]);

  const attachmentAdapter = useMemo(() => buildAttachmentAdapter(attachments), [attachments]);

  const feedbackAdapter = useMemo(() => {
    if (!enableFeedback || !onFeedback) return undefined;
    return {
      submit: ({ message, type }) => {
        onFeedback({ message_id: message?.id ?? null, type });
      },
    };
  }, [enableFeedback, onFeedback]);

  const threadListAdapter = useMemo(() => {
    if (!threadList) return undefined;
    const normalize = (t, status) => ({
      status,
      id: String(pick(t, "id") ?? ""),
      title: pick(t, "title") ?? undefined,
      remoteId: pick(t, "remoteId", "remote_id") ?? undefined,
      externalId: pick(t, "externalId", "external_id") ?? undefined,
    });
    return {
      threadId: pick(threadList, "threadId", "thread_id") ?? undefined,
      isLoading: !!pick(threadList, "isLoading", "is_loading"),
      threads: (pick(threadList, "threads") ?? []).map((t) => normalize(t, "regular")),
      archivedThreads: (pick(threadList, "archivedThreads", "archived_threads") ?? []).map((t) =>
        normalize(t, "archived"),
      ),
      onSwitchToThread: onSwitchToThread ? (id) => onSwitchToThread(id) : undefined,
      onSwitchToNewThread: onSwitchToNewThread ? () => onSwitchToNewThread() : undefined,
      onRename: onRenameThread ? (id, title) => onRenameThread(id, title) : undefined,
      onArchive: onArchiveThread ? (id) => onArchiveThread(id) : undefined,
      onUnarchive: onUnarchiveThread ? (id) => onUnarchiveThread(id) : undefined,
      onDelete: onDeleteThread ? (id) => onDeleteThread(id) : undefined,
    };
  }, [
    threadList,
    onSwitchToThread,
    onSwitchToNewThread,
    onRenameThread,
    onArchiveThread,
    onUnarchiveThread,
    onDeleteThread,
  ]);

  const normalizedSuggestions = useMemo(
    () =>
      (Array.isArray(suggestions) ? suggestions : []).map((s) =>
        typeof s === "string"
          ? { prompt: s, title: s, label: "" }
          : {
              prompt: pick(s, "prompt", "text") ?? "",
              title: pick(s, "title") ?? pick(s, "prompt", "text") ?? "",
              label: pick(s, "label", "description") ?? "",
            },
      ),
    [suggestions],
  );

  const adapter = {
    isRunning,
    isDisabled,
    isSendDisabled,
    isLoading,
    messages: converted,
    suggestions: normalizedSuggestions,
    ...(repository ? { messageRepository: repository } : {}),
    convertMessage: (m) => m,
    // Present so the runtime enables branch switching; the authoritative list
    // still comes from Python on the next state delta.
    setMessages: () => {},
    unstable_onBranchChange: (event) => {
      setLocalHead(event?.headId ?? null);
      if (onBranchChange) {
        onBranchChange({
          head_id: event?.headId ?? null,
          visible_message_ids: Array.from(event?.visibleMessageIds ?? []),
        });
      }
    },
    onNew: async (message) => {
      if (onNew) await onNew(fromAppendMessage(message));
    },
    ...(onEdit
      ? {
          onEdit: async (message) => {
            await onEdit(fromAppendMessage(message));
          },
        }
      : {}),
    ...(onReload
      ? {
          onReload: async (parentId) => {
            await onReload(parentId ?? null);
          },
        }
      : {}),
    ...(onCancel
      ? {
          onCancel: async () => {
            await onCancel();
          },
        }
      : {}),
    ...(onDelete
      ? {
          onDelete: async (messageId) => {
            await onDelete(messageId);
          },
        }
      : {}),
    ...(onAddToolResult
      ? {
          onAddToolResult: async (options) => {
            await onAddToolResult({
              tool_call_id: options?.toolCallId ?? null,
              tool_name: options?.toolName ?? null,
              result: options?.result ?? null,
            });
          },
        }
      : {}),
    adapters: {
      ...(attachmentAdapter ? { attachments: attachmentAdapter } : {}),
      ...(feedbackAdapter ? { feedback: feedbackAdapter } : {}),
      ...(threadListAdapter ? { threadList: threadListAdapter } : {}),
    },
  };

  const runtime = useExternalStoreRuntime(adapter);

  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
};

/* ------------------------------------------------------------------ *
 * Markdown rendering
 * ------------------------------------------------------------------ */

const useCopy = (timeout = 2000) => {
  const [copied, setCopied] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => timer.current && clearTimeout(timer.current), []);
  const copy = useCallback(
    (value) => {
      if (!value || typeof navigator === "undefined" || !navigator.clipboard) return;
      navigator.clipboard.writeText(value).then(() => {
        setCopied(true);
        timer.current && clearTimeout(timer.current);
        timer.current = setTimeout(() => setCopied(false), timeout);
      });
    },
    [timeout],
  );
  return { copied, copy };
};

const CodeHeader = ({ language, code }) => {
  const { copied, copy } = useCopy();
  return (
    <div className="aui-code-header-root">
      <span className="aui-code-header-language">{language || "text"}</span>
      <button
        type="button"
        className="aui-button-icon"
        onClick={() => copy(code)}
        aria-label="Copy code"
      >
        {copied ? <IconCheck /> : <IconCopy />}
      </button>
    </div>
  );
};

const SyntaxHighlighter = ({ components: { Pre, Code }, language, code }) => (
  <PrismAsyncLight
    PreTag={Pre}
    CodeTag={Code}
    language={language}
    useInlineStyles={false}
  >
    {code}
  </PrismAsyncLight>
);

const cx = (...values) => values.filter(Boolean).join(" ");

/** Wrap a tag so our class is merged with whatever the renderer passes in. */
const md = (Tag, className) => {
  const Component = ({ className: incoming, ...rest }) => (
    <Tag className={cx(className, incoming)} {...rest} />
  );
  Component.displayName = `Markdown(${className})`;
  return Component;
};

const markdownComponents = {
  h1: md("h1", "aui-md-h1"),
  h2: md("h2", "aui-md-h2"),
  h3: md("h3", "aui-md-h3"),
  h4: md("h4", "aui-md-h4"),
  h5: md("h5", "aui-md-h5"),
  h6: md("h6", "aui-md-h6"),
  p: md("p", "aui-md-p"),
  blockquote: md("blockquote", "aui-md-blockquote"),
  ul: md("ul", "aui-md-ul"),
  ol: md("ol", "aui-md-ol"),
  li: md("li", "aui-md-li"),
  hr: md("hr", "aui-md-hr"),
  strong: md("strong", "aui-md-strong"),
  th: md("th", "aui-md-th"),
  td: md("td", "aui-md-td"),
  tr: md("tr", "aui-md-tr"),
  pre: md("pre", "aui-md-pre"),
  a: ({ className, ...rest }) => (
    <a
      className={cx("aui-md-a", className)}
      target="_blank"
      rel="noreferrer noopener"
      {...rest}
    />
  ),
  table: ({ className, ...rest }) => (
    <div className="aui-md-table-wrapper">
      <table className={cx("aui-md-table", className)} {...rest} />
    </div>
  ),
  code: ({ className, ...rest }) => (
    <code
      className={cx(className ? "aui-md-code" : "aui-md-inline-code", className)}
      {...rest}
    />
  ),
  SyntaxHighlighter,
  CodeHeader,
};

const MarkdownText = () => (
  <MarkdownTextPrimitive
    className="aui-md"
    remarkPlugins={[remarkGfm]}
    components={markdownComponents}
    defer
  />
);

/* ------------------------------------------------------------------ *
 * Message parts: reasoning, tool calls, files, images
 * ------------------------------------------------------------------ */

const Collapsible = ({
  icon,
  label,
  meta,
  children,
  open: openProp,
  defaultOpen = false,
  onToggle,
  tone = "default",
}) => {
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const open = openProp === undefined ? internalOpen : openProp;
  const toggle = () => {
    if (openProp === undefined) setInternalOpen((v) => !v);
    onToggle?.(!open);
  };
  return (
    <div className="aui-disclosure-root" data-tone={tone} data-open={open || undefined}>
      <button
        type="button"
        className="aui-disclosure-trigger"
        onClick={toggle}
        aria-expanded={open}
      >
        <span className="aui-disclosure-icon">{icon}</span>
        <span className="aui-disclosure-label">{label}</span>
        {meta ? <span className="aui-disclosure-meta">{meta}</span> : null}
        <IconChevronDown className="aui-disclosure-chevron" />
      </button>
      {open ? <div className="aui-disclosure-content">{children}</div> : null}
    </div>
  );
};

const Reasoning = ({ text, status }) => {
  const running = status?.type === "running";
  // Open while the model is thinking, then fold away — unless the reader
  // has taken control of the disclosure.
  const [userOpen, setUserOpen] = useState(null);
  const wasRunning = useRef(running);
  useEffect(() => {
    if (wasRunning.current && !running) setUserOpen((v) => (v === null ? false : v));
    wasRunning.current = running;
  }, [running]);

  const open = userOpen === null ? running : userOpen;

  return (
    <Collapsible
      icon={running ? <IconSpinner /> : <IconBrain />}
      label={running ? "Thinking…" : "Reasoning"}
      open={open}
      onToggle={(next) => setUserOpen(next)}
      tone="muted"
    >
      <div className="aui-reasoning-text">{text}</div>
    </Collapsible>
  );
};

const formatJson = (value) => {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const ToolFallback = ({ toolName, argsText, args, result, isError, status }) => {
  const running = status?.type === "running";
  const icon = running ? <IconSpinner /> : isError ? <IconAlert /> : <IconWrench />;
  const argText = argsText && argsText.trim() ? argsText : formatJson(args);
  return (
    <Collapsible
      icon={icon}
      label={toolName}
      meta={running ? "running" : isError ? "error" : result !== undefined ? "done" : null}
      tone={isError ? "danger" : "default"}
    >
      {argText ? (
        <div className="aui-tool-section">
          <div className="aui-tool-section-title">Arguments</div>
          <pre className="aui-tool-code">{argText}</pre>
        </div>
      ) : null}
      {result !== undefined && result !== null ? (
        <div className="aui-tool-section">
          <div className="aui-tool-section-title">Result</div>
          <pre className="aui-tool-code">{formatJson(result)}</pre>
        </div>
      ) : null}
    </Collapsible>
  );
};

// Message parts come from model or user content, so only let through URL
// schemes that cannot run script (blocks `javascript:`, `vbscript:`, …).
const SAFE_URL = /^(https?:|mailto:|blob:|data:(?!text\/html)|\/|\.{0,2}\/|#)/i;
const safeUrl = (value, fallback = undefined) =>
  typeof value === "string" && SAFE_URL.test(value.trim()) ? value : fallback;

const FilePart = ({ filename, mimeType, data }) => (
  <a
    className="aui-file-chip"
    href={safeUrl(data)}
    download={filename || true}
    target="_blank"
    rel="noreferrer noopener"
  >
    <IconFile />
    <span className="aui-file-chip-name">{filename || "file"}</span>
    <span className="aui-file-chip-type">{mimeType}</span>
  </a>
);

const ImagePart = ({ image }) => (
  <img className="aui-image-part" src={safeUrl(image)} alt="" />
);

const SourcePart = ({ url, title }) =>
  safeUrl(url) ? (
    <a className="aui-source-chip" href={url} target="_blank" rel="noreferrer noopener">
      {title || url}
    </a>
  ) : (
    <span className="aui-source-chip">{title}</span>
  );

const groupBy = groupPartByType({
  reasoning: ["group-reasoning"],
  "tool-call": ["group-tool"],
  "standalone-tool-call": [],
});

const renderPart = ({ part, children }) => {
  switch (part.type) {
    case "group-reasoning":
      return <div className="aui-part-group">{children}</div>;
    case "group-tool":
      return <div className="aui-part-group">{children}</div>;
    case "text":
      return <MarkdownText />;
    case "reasoning":
      return <Reasoning {...part} />;
    case "tool-call":
      return part.toolUI ?? <ToolFallback {...part} />;
    case "data":
      return part.dataRendererUI ?? null;
    case "file":
      return <FilePart {...part} />;
    case "image":
      return <ImagePart {...part} />;
    case "source":
      return <SourcePart {...part} />;
    case "indicator":
      return (
        <span className="aui-typing-indicator" aria-label="Assistant is working">
          <i />
          <i />
          <i />
        </span>
      );
    default:
      return null;
  }
};

/* ------------------------------------------------------------------ *
 * Messages
 * ------------------------------------------------------------------ */

const BranchPicker = ({ className = "" }) => (
  <BranchPickerPrimitive.Root hideWhenSingleBranch className={`aui-branch-picker-root ${className}`}>
    <BranchPickerPrimitive.Previous asChild>
      <button type="button" className="aui-button-icon" aria-label="Previous branch">
        <IconChevronLeft />
      </button>
    </BranchPickerPrimitive.Previous>
    <span className="aui-branch-picker-state">
      <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
    </span>
    <BranchPickerPrimitive.Next asChild>
      <button type="button" className="aui-button-icon" aria-label="Next branch">
        <IconChevronRight />
      </button>
    </BranchPickerPrimitive.Next>
  </BranchPickerPrimitive.Root>
);

const AssistantActionBar = ({ showFeedback }) => (
  <ActionBarPrimitive.Root
    hideWhenRunning
    autohide="not-last"
    className="aui-assistant-action-bar-root"
  >
    <ActionBarPrimitive.Copy asChild>
      <button type="button" className="aui-button-icon" aria-label="Copy message">
        <AuiIf condition={(s) => s.message.isCopied}>
          <IconCheck />
        </AuiIf>
        <AuiIf condition={(s) => !s.message.isCopied}>
          <IconCopy />
        </AuiIf>
      </button>
    </ActionBarPrimitive.Copy>
    <ActionBarPrimitive.Reload asChild>
      <button type="button" className="aui-button-icon" aria-label="Regenerate">
        <IconRefresh />
      </button>
    </ActionBarPrimitive.Reload>
    {showFeedback ? (
      <>
        <ActionBarPrimitive.FeedbackPositive asChild>
          <button type="button" className="aui-button-icon" aria-label="Good response">
            <IconThumbUp />
          </button>
        </ActionBarPrimitive.FeedbackPositive>
        <ActionBarPrimitive.FeedbackNegative asChild>
          <button type="button" className="aui-button-icon" aria-label="Bad response">
            <IconThumbDown />
          </button>
        </ActionBarPrimitive.FeedbackNegative>
      </>
    ) : null}
  </ActionBarPrimitive.Root>
);

const MessageAttachments = () => (
  <MessagePrimitive.Attachments>
    {({ attachment }) => (
      <div className="aui-attachment-tile" title={attachment?.name}>
        <IconFile />
        <span className="aui-attachment-tile-name">{attachment?.name}</span>
      </div>
    )}
  </MessagePrimitive.Attachments>
);

const makeAssistantMessage = ({ showActionBar, showBranchPicker, showFeedback, avatar }) => {
  const AssistantMessage = () => (
    <MessagePrimitive.Root className="aui-assistant-message-root" data-role="assistant">
      {avatar ? (
        <div className="aui-message-avatar" aria-hidden="true">
          <IconBot />
        </div>
      ) : null}
      <div className="aui-assistant-message-body">
        <div className="aui-assistant-message-content">
          <MessagePrimitive.GroupedParts groupBy={groupBy}>{renderPart}</MessagePrimitive.GroupedParts>
          <MessagePrimitive.Error>
            <ErrorPrimitive.Root className="aui-message-error-root">
              <IconAlert />
              <ErrorPrimitive.Message className="aui-message-error-message" />
            </ErrorPrimitive.Root>
          </MessagePrimitive.Error>
        </div>
        <div className="aui-assistant-message-footer">
          {showBranchPicker ? <BranchPicker /> : null}
          {showActionBar ? <AssistantActionBar showFeedback={showFeedback} /> : null}
        </div>
      </div>
    </MessagePrimitive.Root>
  );
  return AssistantMessage;
};

const makeUserMessage = ({ showActionBar, showBranchPicker }) => {
  const UserMessage = () => (
    <MessagePrimitive.Root className="aui-user-message-root" data-role="user">
      <div className="aui-user-message-attachments">
        <MessageAttachments />
      </div>
      <div className="aui-user-message-row">
        {showActionBar ? (
          <ActionBarPrimitive.Root
            hideWhenRunning
            autohide="not-last"
            className="aui-user-action-bar-root"
          >
            <ActionBarPrimitive.Edit asChild>
              <button type="button" className="aui-button-icon" aria-label="Edit message">
                <IconPencil />
              </button>
            </ActionBarPrimitive.Edit>
          </ActionBarPrimitive.Root>
        ) : null}
        <div className="aui-user-message-content">
          <MessagePrimitive.Parts />
        </div>
      </div>
      {showBranchPicker ? <BranchPicker className="aui-branch-picker-end" /> : null}
    </MessagePrimitive.Root>
  );
  return UserMessage;
};

const EditComposer = () => (
  <MessagePrimitive.Root className="aui-edit-composer-wrapper">
    <ComposerPrimitive.Root className="aui-edit-composer-root">
      <ComposerPrimitive.Input className="aui-edit-composer-input" autoFocus />
      <div className="aui-edit-composer-footer">
        <ComposerPrimitive.Cancel asChild>
          <button type="button" className="aui-button aui-button-ghost">
            Cancel
          </button>
        </ComposerPrimitive.Cancel>
        <ComposerPrimitive.Send asChild>
          <button type="button" className="aui-button aui-button-primary">
            Update
          </button>
        </ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  </MessagePrimitive.Root>
);

/* ------------------------------------------------------------------ *
 * Composer
 * ------------------------------------------------------------------ */

const ComposerAttachments = () => (
  <ComposerPrimitive.Attachments>
    {({ attachment }) => (
      <div className="aui-attachment-tile aui-attachment-tile-composer">
        <IconFile />
        <span className="aui-attachment-tile-name">{attachment?.name}</span>
        <AttachmentPrimitive.Remove asChild>
          <button type="button" className="aui-attachment-remove" aria-label="Remove attachment">
            <IconX />
          </button>
        </AttachmentPrimitive.Remove>
      </div>
    )}
  </ComposerPrimitive.Attachments>
);

const Composer = ({ placeholder, autoFocus, showAttachments, submitMode }) => (
  <ComposerPrimitive.Root className="aui-composer-root">
    <ComposerPrimitive.AttachmentDropzone asChild>
      <div className="aui-composer-shell">
        {showAttachments ? (
          <div className="aui-composer-attachments">
            <ComposerAttachments />
          </div>
        ) : null}
        <ComposerPrimitive.Input
          className="aui-composer-input"
          placeholder={placeholder}
          rows={1}
          autoFocus={autoFocus}
          submitMode={submitMode}
          enterKeyHint="send"
          aria-label="Message input"
        />
        <div className="aui-composer-action-wrapper">
          {showAttachments ? (
            <ComposerPrimitive.AddAttachment asChild>
              <button type="button" className="aui-button-icon" aria-label="Add attachment">
                <IconPaperclip />
              </button>
            </ComposerPrimitive.AddAttachment>
          ) : (
            <span />
          )}
          <div className="aui-composer-actions">
            <AuiIf condition={(s) => !s.thread.isRunning}>
              <ComposerPrimitive.Send asChild>
                <button type="button" className="aui-composer-send" aria-label="Send message">
                  <IconArrowUp />
                </button>
              </ComposerPrimitive.Send>
            </AuiIf>
            <AuiIf condition={(s) => s.thread.isRunning}>
              <ComposerPrimitive.Cancel asChild>
                <button type="button" className="aui-composer-cancel" aria-label="Stop generating">
                  <IconSquare />
                </button>
              </ComposerPrimitive.Cancel>
            </AuiIf>
          </div>
        </div>
      </div>
    </ComposerPrimitive.AttachmentDropzone>
  </ComposerPrimitive.Root>
);

/* ------------------------------------------------------------------ *
 * Thread
 * ------------------------------------------------------------------ */

const Welcome = ({ title, subtitle, suggestions, icon }) => (
  <div className="aui-thread-welcome-root">
    {icon ? (
      <div className="aui-thread-welcome-icon" aria-hidden="true">
        <IconSparkles />
      </div>
    ) : null}
    {title ? <h1 className="aui-thread-welcome-message">{title}</h1> : null}
    {subtitle ? <p className="aui-thread-welcome-subtitle">{subtitle}</p> : null}
    {suggestions?.length ? (
      <div className="aui-thread-welcome-suggestions">
        {suggestions.map((s, i) => {
          const prompt = typeof s === "string" ? s : pick(s, "prompt", "text") ?? "";
          const title_ = typeof s === "string" ? s : pick(s, "title") ?? prompt;
          const label = typeof s === "string" ? "" : pick(s, "label", "description") ?? "";
          return (
            <ThreadPrimitive.Suggestion key={`${prompt}-${i}`} prompt={prompt} send asChild>
              <button type="button" className="aui-thread-welcome-suggestion">
                <span className="aui-thread-welcome-suggestion-text-1">{title_}</span>
                {label ? (
                  <span className="aui-thread-welcome-suggestion-text-2">{label}</span>
                ) : null}
              </button>
            </ThreadPrimitive.Suggestion>
          );
        })}
      </div>
    ) : null}
  </div>
);

const SuggestionChip = () => (
  <SuggestionPrimitive.Trigger send asChild>
    <button type="button" className="aui-thread-followup-suggestion">
      <SuggestionPrimitive.Title className="aui-thread-followup-suggestion-title" />
      <SuggestionPrimitive.Description className="aui-thread-followup-suggestion-label" />
    </button>
  </SuggestionPrimitive.Trigger>
);

const renderSuggestion = () => <SuggestionChip />;

const FollowUpSuggestions = () => (
  <AuiIf
    condition={(s) => !s.thread.isEmpty && !s.thread.isRunning && s.thread.suggestions.length > 0}
  >
    <div className="aui-thread-followup-suggestions">
      <ThreadPrimitive.Suggestions>{renderSuggestion}</ThreadPrimitive.Suggestions>
    </div>
  </AuiIf>
);

export const AuiThread = ({
  welcomeTitle = "How can I help you today?",
  welcomeSubtitle = "",
  welcomeSuggestions = EMPTY,
  welcomeIcon = true,
  placeholder = "Send a message...",
  autoFocus = true,
  showWelcome = true,
  showActionBar = true,
  showBranchPicker = true,
  showFeedback = false,
  showAvatar = true,
  showAttachments = false,
  showFollowUpSuggestions = true,
  submitMode = "enter",
  maxWidth = "44rem",
  className = "",
  style,
}) => {
  const AssistantMessage = useMemo(
    () => makeAssistantMessage({ showActionBar, showBranchPicker, showFeedback, avatar: showAvatar }),
    [showActionBar, showBranchPicker, showFeedback, showAvatar],
  );
  const UserMessage = useMemo(
    () => makeUserMessage({ showActionBar, showBranchPicker }),
    [showActionBar, showBranchPicker],
  );
  const components = useMemo(
    () => ({ UserMessage, AssistantMessage, EditComposer }),
    [UserMessage, AssistantMessage],
  );

  return (
    <ThreadPrimitive.Root
      className={`aui-root aui-thread-root ${className}`.trim()}
      style={{ "--aui-thread-max-width": maxWidth, ...(style ?? {}) }}
    >
      <ThreadPrimitive.Viewport className="aui-thread-viewport">
        <div className="aui-thread-viewport-inner">
          {showWelcome ? (
            <AuiIf condition={(s) => s.thread.isEmpty}>
              <Welcome
                title={welcomeTitle}
                subtitle={welcomeSubtitle}
                suggestions={welcomeSuggestions}
                icon={welcomeIcon}
              />
            </AuiIf>
          ) : null}

          <div className="aui-thread-messages">
            <ThreadPrimitive.Messages components={components} />
          </div>

          <ThreadPrimitive.ViewportFooter className="aui-thread-viewport-footer">
            <ThreadPrimitive.ScrollToBottom asChild>
              <button
                type="button"
                className="aui-thread-scroll-to-bottom"
                aria-label="Scroll to bottom"
              >
                <IconArrowDown />
              </button>
            </ThreadPrimitive.ScrollToBottom>
            {showFollowUpSuggestions ? <FollowUpSuggestions /> : null}
            <Composer
              placeholder={placeholder}
              autoFocus={autoFocus}
              showAttachments={showAttachments}
              submitMode={submitMode}
            />
          </ThreadPrimitive.ViewportFooter>
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
};

/* ------------------------------------------------------------------ *
 * Thread list
 * ------------------------------------------------------------------ */

const ThreadListItem = ({ showArchive, showDelete }) => (
  <ThreadListItemPrimitive.Root className="aui-thread-list-item">
    <ThreadListItemPrimitive.Trigger asChild>
      <button type="button" className="aui-thread-list-item-trigger">
        <ThreadListItemPrimitive.Title fallback="New chat" />
      </button>
    </ThreadListItemPrimitive.Trigger>
    <div className="aui-thread-list-item-actions">
      {showArchive ? (
        <ThreadListItemPrimitive.Archive asChild>
          <button type="button" className="aui-button-icon" aria-label="Archive thread">
            <IconArchive />
          </button>
        </ThreadListItemPrimitive.Archive>
      ) : null}
      {showDelete ? (
        <ThreadListItemPrimitive.Delete asChild>
          <button type="button" className="aui-button-icon" aria-label="Delete thread">
            <IconTrash />
          </button>
        </ThreadListItemPrimitive.Delete>
      ) : null}
    </div>
  </ThreadListItemPrimitive.Root>
);

export const AuiThreadList = ({
  newThreadLabel = "New chat",
  showArchive = false,
  showDelete = true,
  emptyLabel = "No conversations yet",
  className = "",
}) => (
  <ThreadListPrimitive.Root className={`aui-root aui-thread-list-root ${className}`.trim()}>
    <ThreadListPrimitive.New asChild>
      <button type="button" className="aui-thread-list-new">
        <IconPlus />
        <span>{newThreadLabel}</span>
      </button>
    </ThreadListPrimitive.New>
    <div className="aui-thread-list-items">
      <ThreadListPrimitive.Items>
        {() => <ThreadListItem showArchive={showArchive} showDelete={showDelete} />}
      </ThreadListPrimitive.Items>
      <AuiIf condition={(s) => s.threads.threadIds.length === 0}>
        <p className="aui-thread-list-empty">{emptyLabel}</p>
      </AuiIf>
    </div>
  </ThreadListPrimitive.Root>
);

/* ------------------------------------------------------------------ *
 * Floating modal
 * ------------------------------------------------------------------ */

export const AuiModal = ({
  openOnRunStart = true,
  side = "right",
  width = "min(26rem, calc(100vw - 2rem))",
  height = "min(36rem, calc(100vh - 6rem))",
  children,
}) => {
  const [open, setOpen] = useState(false);
  const aui = useAui();

  useEffect(() => {
    if (!openOnRunStart || !aui?.on) return undefined;
    return aui.on("thread.runStart", () => setOpen(true));
  }, [aui, openOnRunStart]);

  return (
    <div className="aui-root aui-modal-anchor" data-side={side}>
      {open ? (
        <div className="aui-modal-content" style={{ width, height }} role="dialog" aria-modal="false">
          {children}
        </div>
      ) : null}
      <button
        type="button"
        className="aui-modal-button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close assistant" : "Open assistant"}
      >
        {open ? <IconChevronDown /> : <IconBot />}
      </button>
    </div>
  );
};

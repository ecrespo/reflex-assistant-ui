# Changelog

## 0.2.0 — 2026-10-24

### Changed

* Require **Reflex 0.10.0** or newer (was 0.9.11).
* Require **Python 3.11** or newer, following Reflex 0.10. Python 3.10 is no
  longer supported or tested.
* Build backend now requires `setuptools>=78.1.1`.
* The demo app pins `reflex>=0.10.0`.

No changes to the public Python API: existing apps only need to upgrade Reflex.

## 0.1.0

* First release: `assistant_ui.chat`, `AssistantUIState`, streaming, markdown,
  reasoning, tool calls, branching, multi-conversation thread list and
  attachments.

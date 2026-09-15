"""Model discovery for a local Ollama server.

Streaming a reply is the job of whatever client you prefer — the demo uses
LangChain's `ChatOllama`. What no chat client offers is *listing* the models a
machine actually has pulled, which is what a model picker needs, so that is all
this module does. It depends only on `httpx`, which Reflex already brings.

    from reflex_assistant_ui import ollama

    models = await ollama.list_models()      # [] when the server is down
"""

from __future__ import annotations

import os

import httpx

__all__ = [
    "DEFAULT_BASE_URL",
    "base_url",
    "is_available",
    "list_models",
]

DEFAULT_BASE_URL = "http://localhost:11434"


def base_url(url: str | None = None) -> str:
    """Resolve the Ollama endpoint: argument, then ``OLLAMA_HOST``, then default."""
    resolved = url or os.environ.get("OLLAMA_HOST") or DEFAULT_BASE_URL
    if not resolved.startswith(("http://", "https://")):
        resolved = f"http://{resolved}"
    return resolved.rstrip("/")


async def is_available(url: str | None = None, timeout: float = 2.0) -> bool:
    """True when an Ollama server answers on ``url``."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{base_url(url)}/api/tags")
            return response.status_code == 200
    except Exception:  # noqa: BLE001 - availability probe, any failure means "no"
        return False


async def list_models(url: str | None = None, timeout: float = 5.0) -> list[str]:
    """Names of the models installed on the server, alphabetically.

    Returns an empty list when the server is unreachable, so a UI can fall back
    to an offline mode without special-casing the error.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{base_url(url)}/api/tags")
            response.raise_for_status()
            payload = response.json()
    except Exception:  # noqa: BLE001 - callers treat this as "no models"
        return []
    names = [model.get("name", "") for model in payload.get("models", [])]
    return sorted(name for name in names if name)

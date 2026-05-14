"""Wire the OpenAI Agents SDK to a backend.

Backends, in priority order:

1. **OpenAI** (preferred). Set ``OPENAI_API_KEY``. Uses Responses API.
2. **UCSD TritonAI** — OpenAI-compatible LiteLLM gateway. Set ``TRITON_API_KEY``
   (and optionally ``TRITON_BASE_URL`` / ``TRITON_MODEL``). Forced into Chat
   Completions mode because LiteLLM does not implement Responses API.

Either backend works; the rest of the codebase doesn't need to know which.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import (
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_TRITON_BASE = "https://tritonai-api.ucsd.edu"
DEFAULT_TRITON_MODEL = "claude-sonnet-4-6"


@dataclass(frozen=True)
class Backend:
    name: str            # "openai" | "triton"
    api_key: str
    base_url: str | None # None for vanilla OpenAI
    model: str


_active: Backend | None = None


def _clean(val: str | None) -> str:
    return (val or "").strip().strip('"').strip("'")


def _resolve_backend() -> Backend:
    openai_key = _clean(os.getenv("OPENAI_API_KEY"))
    triton_key = _clean(os.getenv("TRITON_API_KEY"))

    if openai_key:
        return Backend(
            name="openai",
            api_key=openai_key,
            base_url=None,
            model=_clean(os.getenv("OPENAI_MODEL")) or DEFAULT_OPENAI_MODEL,
        )
    if triton_key:
        base = _clean(os.getenv("TRITON_BASE_URL")) or DEFAULT_TRITON_BASE
        base = base.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return Backend(
            name="triton",
            api_key=triton_key,
            base_url=base,
            model=_clean(os.getenv("TRITON_MODEL")) or DEFAULT_TRITON_MODEL,
        )
    raise RuntimeError(
        "No API key found. Set OPENAI_API_KEY (preferred) or TRITON_API_KEY "
        "in your .env file."
    )


def configure_agents(load_env_file: bool = True) -> str:
    """Initialize the Agents SDK. Returns the active model id."""
    global _active
    if load_env_file:
        # override=True so the project's .env beats anything leaking from the
        # parent shell. This is what users expect when they edit .env.
        load_dotenv(override=True)

    backend = _resolve_backend()
    _active = backend

    client = AsyncOpenAI(api_key=backend.api_key, base_url=backend.base_url)
    set_default_openai_client(client, use_for_tracing=False)
    set_default_openai_api("chat_completions" if backend.name == "triton" else "responses")
    # Tracing tries to POST to api.openai.com which fails when using Triton's key.
    if backend.name == "triton":
        set_tracing_disabled(True)

    os.environ["OPENAI_API_KEY"] = backend.api_key
    if backend.base_url:
        os.environ["OPENAI_BASE_URL"] = backend.base_url
    else:
        # Vital: clear any stale OPENAI_BASE_URL left over from a prior Triton run,
        # otherwise the OpenAI client will keep pointing at Triton.
        os.environ.pop("OPENAI_BASE_URL", None)
    return backend.model


def active_backend() -> Backend:
    if _active is None:
        configure_agents()
    assert _active is not None
    return _active


def default_model() -> str:
    return active_backend().model


def vision_client() -> AsyncOpenAI:
    """Async client tools can use directly (e.g. for vision calls)."""
    backend = active_backend()
    return AsyncOpenAI(api_key=backend.api_key, base_url=backend.base_url)


# Back-compat aliases (older callers used Triton-specific names).
configure_triton = configure_agents
triton_client = vision_client

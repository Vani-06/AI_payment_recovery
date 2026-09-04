"""Single LLM entry point — Phase 4 (SPEC.md §11).

Every model call goes through ``llm()``. Provider/model come from settings so the whole
app is one function away from swapping. No key set => ``LLMError`` => callers fall back to
templates (see ``narrate.py`` / ``chat.py``). Nothing else in the codebase imports
``anthropic``.
"""

from __future__ import annotations

from functools import lru_cache

from .config import settings


class LLMError(RuntimeError):
    """Raised for any reason the model call can't be made or fails."""


def llm_available() -> bool:
    return bool(settings.anthropic_api_key)


@lru_cache(maxsize=1)
def _client():
    from anthropic import Anthropic

    return Anthropic(api_key=settings.anthropic_api_key)


def llm(system: str, prompt: str, *, max_tokens: int = 300) -> str:
    """Plain-text completion. Raises ``LLMError`` on missing key, network, auth, or model
    errors — callers are expected to catch and degrade gracefully."""
    if not settings.anthropic_api_key:
        raise LLMError("ANTHROPIC_API_KEY not set")
    try:
        resp = _client().messages.create(
            model=settings.sherlock_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 — deliberately broad; degrade on anything
        raise LLMError(str(exc)) from exc
    text = "".join(getattr(b, "text", "") for b in resp.content).strip()
    if not text:
        raise LLMError("empty completion")
    return text

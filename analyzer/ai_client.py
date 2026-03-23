"""
AI client abstraction.

Single responsibility: send system + user prompts to an LLM, return text.
triage.py calls complete() and never cares which provider is active.

Provider contract (set via environment variable):
  LLM_PROVIDER=anthropic  (default) — requires ANTHROPIC_API_KEY
  LLM_PROVIDER=ollama               — requires Ollama running locally

Ollama variables (optional, have defaults):
  OLLAMA_BASE_URL — default: http://localhost:11434
  OLLAMA_MODEL    — default: llama3.2
"""

import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

# Load .env, fall back to .env.example for local dev convenience
load_dotenv() or load_dotenv(Path(__file__).parent.parent / ".env.example")

_ANTHROPIC_MODEL = "claude-sonnet-4-6"
_ANTHROPIC_MAX_TOKENS = 1024
_OLLAMA_DEFAULT_URL = "http://localhost:11434"
_OLLAMA_DEFAULT_MODEL = "llama3.2"


def _complete_anthropic(system: str, user: str) -> str:
    import anthropic  # lazy: only required when this provider is active

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=_ANTHROPIC_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


def _complete_ollama(system: str, user: str) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", _OLLAMA_DEFAULT_URL)
    model = os.getenv("OLLAMA_MODEL", _OLLAMA_DEFAULT_MODEL)

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["message"]["content"]


_PROVIDERS = {
    "anthropic": _complete_anthropic,
    "ollama": _complete_ollama,
}


def complete(system: str, user: str) -> str:
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    fn = _PROVIDERS.get(provider)
    if fn is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. Valid values: {list(_PROVIDERS)}"
        )
    return fn(system, user)

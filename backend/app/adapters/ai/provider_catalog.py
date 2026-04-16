"""Provider catalog for AI gateway routing.

Single source of truth for provider metadata used by adapters and API docs.
"""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    env_key: str
    default_model: str
    base_url: str | None
    transport: str
    status: str = "active"


PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        name="openai",
        env_key="OPENAI_API_KEY",
        default_model="gpt-4o-mini",
        base_url=None,
        transport="openai_compatible",
    ),
    "gemini": ProviderSpec(
        name="gemini",
        env_key="GEMINI_API_KEY",
        default_model="gemini-2.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        transport="openai_compatible",
    ),
    "deepseek": ProviderSpec(
        name="deepseek",
        env_key="DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
        base_url="https://api.deepseek.com",
        transport="openai_compatible",
    ),
    "antigravity": ProviderSpec(
        name="antigravity",
        env_key="ANTIGRAVITY_API_KEY",
        default_model="claude-sonnet-4-5",
        base_url="http://127.0.0.1:8045/v1",
        transport="openai_compatible",
    ),
    # Self-hosted Ollama OpenAI-compatible endpoint. Auth is optional — Ollama
    # ignores the Bearer token but the OpenAI SDK requires a non-empty string,
    # so openai_gateway injects a dummy "ollama" when OLLAMA_API_KEY is unset.
    "ollama": ProviderSpec(
        name="ollama",
        env_key="OLLAMA_API_KEY",
        default_model=os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2:3b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        transport="openai_compatible",
    ),
    # Generic OpenAI-compatible endpoint — base URL and API key are user-supplied
    # at request time (providerBaseUrl / apiKey fields). Works with Ollama,
    # LM Studio, vLLM, LocalAI, Groq, Together, Mistral, etc.
    "openai_compatible": ProviderSpec(
        name="openai_compatible",
        env_key="",
        default_model="",
        base_url=None,
        transport="openai_compatible",
    ),
    # Example adoption targets (not openai-compatible transport):
    "openai_codex": ProviderSpec(
        name="openai_codex",
        env_key="OPENAI_CODEX_ACCESS_TOKEN",
        default_model="gpt-5.3-codex",
        base_url=None,
        transport="codex_oauth",
        status="stable",
    ),
    "claude_code": ProviderSpec(
        name="claude_code",
        env_key="CLAUDE_CODE_ACCESS_TOKEN",
        default_model="claude-sonnet-4-6",
        base_url="https://api.anthropic.com/v1/messages",
        transport="anthropic_messages",
        status="stable",
    ),
}

OPENAI_COMPATIBLE_TRANSPORTS = frozenset({"openai_compatible"})


def get_provider_spec(provider: str) -> ProviderSpec:
    key = (provider or "").strip().lower()
    spec = PROVIDER_SPECS.get(key)
    if spec is None:
        valid = ", ".join(sorted(PROVIDER_SPECS.keys()))
        raise ValueError(f"Unknown provider {provider!r}. Must be one of: {valid}")
    return spec


def is_openai_compatible_provider(provider: str) -> bool:
    spec = get_provider_spec(provider)
    return spec.transport in OPENAI_COMPATIBLE_TRANSPORTS


def provider_feature_flag_key(provider: str) -> str | None:
    """Return feature-flag env key for experimental providers."""
    spec = get_provider_spec(provider)
    if spec.status == "experimental":
        return f"ENABLE_PROVIDER_{spec.name.upper()}"
    return None


def is_provider_enabled(provider: str) -> bool:
    """Whether provider is enabled by status + feature flags."""
    spec = get_provider_spec(provider)
    flag_key = provider_feature_flag_key(provider)
    if flag_key is None:
        return True
    raw = os.getenv(flag_key, "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}

from __future__ import annotations

import os
from typing import Any, Iterable

import litellm

from .config import settings
from .db import decrypt

litellm.suppress_debug_info = True

MODELS = (
    {
        "id": "gpt-5.5",
        "provider": "openai",
        "provider_label": "OpenAI",
        "label": "GPT-5.5",
        "description": "Máxima capacidade para código e trabalho profissional",
        "badge": "Mais capaz",
        "tools": True,
        "vision": True,
    },
    {
        "id": "gpt-5.4",
        "provider": "openai",
        "provider_label": "OpenAI",
        "label": "GPT-5.4",
        "description": "Alto desempenho com melhor equilíbrio de custo",
        "badge": "Recomendado",
        "recommended": True,
        "tools": True,
        "vision": True,
    },
    {
        "id": "anthropic/claude-fable-5",
        "provider": "anthropic",
        "provider_label": "Anthropic",
        "label": "Claude Fable 5",
        "description": "Raciocínio exigente e agentes de longa duração",
        "badge": "Flagship",
        "tools": True,
        "vision": True,
    },
    {
        "id": "anthropic/claude-opus-4-8",
        "provider": "anthropic",
        "provider_label": "Anthropic",
        "label": "Claude Opus 4.8",
        "description": "Código complexo e raciocínio autônomo confiável",
        "badge": "Código",
        "tools": True,
        "vision": True,
    },
    {
        "id": "gemini/gemini-3.5-flash",
        "provider": "gemini",
        "provider_label": "Google",
        "label": "Gemini 3.5 Flash",
        "description": "Inteligência de fronteira com alta velocidade",
        "badge": "Rápido",
        "tools": True,
        "vision": True,
    },
    {
        "id": "gemini/gemini-3.1-pro-preview",
        "provider": "gemini",
        "provider_label": "Google",
        "label": "Gemini 3.1 Pro",
        "description": "Engenharia de software e orquestração de ferramentas",
        "badge": "Raciocínio",
        "tools": True,
        "vision": True,
    },
    {
        "id": "deepseek/deepseek-v4-pro",
        "provider": "deepseek",
        "provider_label": "DeepSeek",
        "label": "DeepSeek V4 Pro",
        "description": "Modelo avançado com raciocínio de alta intensidade",
        "badge": "Pro",
        "tools": True,
        "vision": False,
    },
    {
        "id": "deepseek/deepseek-v4-flash",
        "provider": "deepseek",
        "provider_label": "DeepSeek",
        "label": "DeepSeek V4 Flash",
        "description": "Resposta rápida para chat, código e agentes",
        "badge": "Eficiente",
        "tools": True,
        "vision": False,
    },
    {
        "id": "openrouter/openrouter/auto",
        "provider": "openrouter",
        "provider_label": "OpenRouter",
        "label": "OpenRouter Auto",
        "description": "Escolhe automaticamente o melhor modelo para a tarefa",
        "badge": "Automático",
        "tools": True,
        "vision": True,
    },
    {
        "id": "openrouter/openrouter/free",
        "provider": "openrouter",
        "provider_label": "OpenRouter",
        "label": "OpenRouter Free",
        "description": "Roteia para um modelo gratuito compatível disponível",
        "badge": "Grátis",
        "tools": True,
        "vision": True,
    },
)

MODEL_BY_ID = {model["id"]: model for model in MODELS}


def models() -> list[dict[str, Any]]:
    return [dict(model) for model in MODELS]


def _env_key(provider: str) -> str:
    mapping = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    return os.getenv(mapping.get(provider, ""), "")


def stream_chat(user: dict[str, Any], messages: list[dict[str, Any]], model: str | None = None) -> Iterable[str]:
    model = model or user.get("model") or settings.default_model
    selected = MODEL_BY_ID.get(model)
    configured_provider = user.get("provider") or settings.default_provider
    configured_model = user.get("model") or settings.default_model
    configured_base_url = user.get("base_url") or settings.default_base_url or None
    if selected is None:
        if model != configured_model or not configured_base_url:
            raise ValueError("Modelo não suportado")
        provider = configured_provider
    else:
        provider = str(selected["provider"])
    configured_key = decrypt(user.get("api_key_enc") or "")
    api_key = configured_key if configured_provider == provider else _env_key(provider)
    base_url = (
        configured_base_url if configured_provider == provider else None
    )
    if not api_key and provider not in {"ollama"}:
        raise RuntimeError("Nenhuma chave de API foi configurada para este provedor")
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["api_base"] = base_url
    response = litellm.completion(**kwargs)
    for chunk in response:
        text = ""
        try:
            text = chunk.choices[0].delta.content or ""
        except Exception:
            pass
        if text:
            yield text

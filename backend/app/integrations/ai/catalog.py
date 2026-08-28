"""Curated model catalog — synced with provider docs (Jul/Aug 2026).

Sources:
- OpenAI: https://developers.openai.com/api/docs/models
- Groq: https://console.groq.com/docs/models
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings as app_settings

CATALOG_VERSION = "2026-08"


@dataclass(frozen=True)
class ModelOption:
    id: str
    label: str
    provider: str
    category: str
    description: str
    group: str
    context: str | None = None
    badge: str | None = None


# OpenAI — Chat Completions + function calling (planner/agent)
OPENAI_PLANNER_MODELS: tuple[ModelOption, ...] = (
    ModelOption(
        id="gpt-5.5",
        label="GPT-5.5",
        provider="openai",
        category="planner",
        group="frontier",
        description="Frontier atual da OpenAI: coding, raciocínio profundo e tools.",
        context="1M tokens",
        badge="recommended",
    ),
    ModelOption(
        id="gpt-5.5-pro",
        label="GPT-5.5 Pro",
        provider="openai",
        category="planner",
        group="frontier",
        description="Máxima precisão para workloads críticos e agentes complexos.",
        context="1M tokens",
    ),
    ModelOption(
        id="gpt-5.4",
        label="GPT-5.4",
        provider="openai",
        category="planner",
        group="professional",
        description="Fortemente recomendado para coding e trabalho profissional.",
        context="1M tokens",
    ),
    ModelOption(
        id="gpt-5.4-mini",
        label="GPT-5.4 Mini",
        provider="openai",
        category="planner",
        group="professional",
        description="Melhor mini até hoje: coding, computer use e subagentes.",
        context="1M tokens",
        badge="fastest",
    ),
    ModelOption(
        id="gpt-5.4-nano",
        label="GPT-5.4 Nano",
        provider="openai",
        category="planner",
        group="professional",
        description="Classe GPT-5.4 mais barata para alto volume e tarefas simples.",
        context="400K tokens",
    ),
    ModelOption(
        id="o4-mini",
        label="o4-mini",
        provider="openai",
        category="planner",
        group="reasoning",
        description="Raciocínio leve da série o, bom custo para decisões difíceis.",
        context="200K tokens",
    ),
    ModelOption(
        id="o3-mini",
        label="o3-mini",
        provider="openai",
        category="planner",
        group="reasoning",
        description="Raciocínio econômico para STEM, código e planejamento.",
        context="200K tokens",
    ),
    ModelOption(
        id="gpt-4.1",
        label="GPT-4.1",
        provider="openai",
        category="planner",
        group="legacy",
        description="Legado API-only, ainda sólido em coding e instruções longas.",
        context="1M tokens",
    ),
    ModelOption(
        id="gpt-4.1-mini",
        label="GPT-4.1 Mini",
        provider="openai",
        category="planner",
        group="legacy",
        description="Legado compacto com function calling.",
        context="1M tokens",
    ),
    ModelOption(
        id="gpt-4.1-nano",
        label="GPT-4.1 Nano",
        provider="openai",
        category="planner",
        group="legacy",
        description="Legado ultra-leve para tarefas simples.",
        context="1M tokens",
    ),
    ModelOption(
        id="gpt-4o",
        label="GPT-4o",
        provider="openai",
        category="planner",
        group="legacy",
        description="Multimodal legado; migrar para GPT-5.x quando possível.",
        context="128K tokens",
    ),
    ModelOption(
        id="gpt-4o-mini",
        label="GPT-4o Mini",
        provider="openai",
        category="planner",
        group="legacy",
        description="Versão econômica legada do 4o.",
        context="128K tokens",
    ),
)

# Groq — production + preview (console.groq.com/docs/models, Aug 2026)
GROQ_FAST_MODELS: tuple[ModelOption, ...] = (
    ModelOption(
        id="openai/gpt-oss-120b",
        label="GPT OSS 120B",
        provider="groq",
        category="fast",
        group="production",
        description="Open-weight flagship da OpenAI na Groq: raciocínio e tools (~500 t/s).",
        context="131K tokens",
        badge="recommended",
    ),
    ModelOption(
        id="openai/gpt-oss-20b",
        label="GPT OSS 20B",
        provider="groq",
        category="fast",
        group="production",
        description="Open-weight compacto: latência mínima (~1000 t/s).",
        context="131K tokens",
    ),
    ModelOption(
        id="llama-3.3-70b-versatile",
        label="Llama 3.3 70B Versatile",
        provider="groq",
        category="fast",
        group="production",
        description="Generalista Meta: respostas, classificação e resumos.",
        context="131K tokens",
    ),
    ModelOption(
        id="llama-3.1-8b-instant",
        label="Llama 3.1 8B Instant",
        provider="groq",
        category="fast",
        group="production",
        description="Máxima velocidade Groq para tarefas simples (~560 t/s).",
        context="131K tokens",
        badge="fastest",
    ),
    ModelOption(
        id="meta-llama/llama-4-scout-17b-16e-instruct",
        label="Llama 4 Scout 17B",
        provider="groq",
        category="fast",
        group="preview",
        description="Preview Meta: texto + imagem, 750 t/s.",
        context="131K tokens",
    ),
    ModelOption(
        id="qwen/qwen3-32b",
        label="Qwen3 32B",
        provider="groq",
        category="fast",
        group="preview",
        description="Preview Qwen: raciocínio forte em PT/EN.",
        context="131K tokens",
    ),
    ModelOption(
        id="openai/gpt-oss-safeguard-20b",
        label="GPT OSS Safeguard 20B",
        provider="groq",
        category="fast",
        group="preview",
        description="Preview: moderação e safety classification.",
        context="131K tokens",
    ),
    ModelOption(
        id="groq/compound",
        label="Groq Compound",
        provider="groq",
        category="fast",
        group="systems",
        description="Sistema agentic com web search e code execution integrados.",
        context="131K tokens",
    ),
    ModelOption(
        id="groq/compound-mini",
        label="Groq Compound Mini",
        provider="groq",
        category="fast",
        group="systems",
        description="Versão compacta do Compound para agentes leves.",
        context="131K tokens",
    ),
)

GROQ_WHISPER_MODELS: tuple[ModelOption, ...] = (
    ModelOption(
        id="whisper-large-v3",
        label="Whisper Large v3",
        provider="groq",
        category="transcription",
        group="production",
        description="Transcrição de áudio em PT-BR com alta precisão.",
        context="Alta precisão",
        badge="recommended",
    ),
    ModelOption(
        id="whisper-large-v3-turbo",
        label="Whisper Large v3 Turbo",
        provider="groq",
        category="transcription",
        group="production",
        description="Transcrição mais rápida e barata, ideal para chat por voz.",
        context="Mais rápido",
        badge="fastest",
    ),
)

OPENAI_REALTIME_MODELS: tuple[ModelOption, ...] = (
    ModelOption(
        id="gpt-realtime-2",
        label="GPT Realtime 2",
        provider="openai",
        category="realtime",
        group="realtime",
        description="Modelo atual da API Realtime para conversa por voz.",
        badge="recommended",
    ),
    ModelOption(
        id="gpt-realtime",
        label="GPT Realtime",
        provider="openai",
        category="realtime",
        group="legacy",
        description="Geração anterior da API Realtime.",
    ),
)

# OpenAI Realtime API — voz da Lira
OPENAI_REALTIME_VOICES: tuple[ModelOption, ...] = (
    ModelOption(
        id="coral",
        label="Coral",
        provider="openai",
        category="voice",
        group="realtime",
        description="Voz feminina, tom claro para conversa em PT-BR.",
        badge="recommended",
    ),
    ModelOption(
        id="cedar",
        label="Cedar",
        provider="openai",
        category="voice",
        group="realtime",
        description="Voz masculina, natural para conversa em PT-BR.",
    ),
    ModelOption(
        id="ash",
        label="Ash",
        provider="openai",
        category="voice",
        group="realtime",
        description="Voz masculina, tom firme e claro.",
    ),
    ModelOption(
        id="echo",
        label="Echo",
        provider="openai",
        category="voice",
        group="realtime",
        description="Voz masculina clássica do Realtime.",
    ),
    ModelOption(
        id="alloy",
        label="Alloy",
        provider="openai",
        category="voice",
        group="realtime",
        description="Voz neutra, equilibrada para diálogo.",
    ),
    ModelOption(
        id="marin",
        label="Marin",
        provider="openai",
        category="voice",
        group="realtime",
        description="Voz feminina, tom suave.",
    ),
)

CATALOG_BY_FIELD: dict[str, tuple[ModelOption, ...]] = {
    "engine_model": OPENAI_PLANNER_MODELS,
    "humanizer_model": OPENAI_PLANNER_MODELS,
    "evaluator_model": OPENAI_PLANNER_MODELS,
    "groq_transcribe_model": GROQ_WHISPER_MODELS,
    "openai_realtime_model": OPENAI_REALTIME_MODELS,
    "openai_realtime_voice": OPENAI_REALTIME_VOICES,
}

ALL_MODEL_IDS: dict[str, set[str]] = {
    field: {model.id for model in models} for field, models in CATALOG_BY_FIELD.items()
}


def platform_defaults() -> dict[str, str]:
    return {
        "engine_model": app_settings.ENGINE_MODEL,
        "humanizer_model": app_settings.HUMANIZER_MODEL,
        "evaluator_model": app_settings.EVALUATOR_MODEL,
        "groq_transcribe_model": app_settings.GROQ_TRANSCRIBE_MODEL,
        "openai_realtime_model": app_settings.OPENAI_REALTIME_MODEL,
        "openai_realtime_voice": app_settings.OPENAI_REALTIME_VOICE,
    }


def catalog_payload() -> dict:
    def serialize(models: tuple[ModelOption, ...]) -> list[dict]:
        return [
            {
                "id": model.id,
                "label": model.label,
                "provider": model.provider,
                "category": model.category,
                "group": model.group,
                "description": model.description,
                "context": model.context,
                "badge": model.badge,
            }
            for model in models
        ]

    return {
        "version": CATALOG_VERSION,
        "defaults": platform_defaults(),
        "chat_models": serialize(OPENAI_PLANNER_MODELS),
        "openai_realtime_models": serialize(OPENAI_REALTIME_MODELS),
        "openai_realtime_voices": serialize(OPENAI_REALTIME_VOICES),
        "groq_transcribe_models": serialize(GROQ_WHISPER_MODELS),
    }


def validate_model_field(field: str, value: str) -> str:
    allowed = ALL_MODEL_IDS.get(field)
    if allowed is None:
        return value
    if value in allowed:
        return value
    if value == platform_defaults().get(field):
        return value
    raise ValueError(f"Modelo inválido para {field}: {value}")

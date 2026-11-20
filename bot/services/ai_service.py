"""Integração com a API da Anthropic (Claude).

A chave vem de AI_API_KEY. Sem chave configurada, o serviço fica desligado e
os comandos avisam isso em vez de quebrar — assim o projeto roda inteiro
mesmo para quem só quer ver as métricas.
"""

from __future__ import annotations

import logging

from core.config import get_settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 45.0
MAX_TOKENS = 900

ASSISTANT_SYSTEM = (
    "Você é o Sentinel, assistente de um servidor Discord. "
    "Responda em português do Brasil, de forma direta e cordial, em no máximo 3 parágrafos curtos. "
    "Se não souber algo, diga que não sabe em vez de inventar."
)

ANALYST_SYSTEM = (
    "Você analisa métricas de atividade de um servidor Discord. "
    "Receberá apenas números agregados, nunca o conteúdo das mensagens. "
    "Escreva em português do Brasil: um parágrafo curto de leitura geral e, "
    "em seguida, até três observações em tópicos. Não invente dados que não estejam na entrada."
)


class AIUnavailable(RuntimeError):
    """A integração não está configurada ou o provedor não respondeu."""


_client = None


def is_enabled() -> bool:
    return get_settings().ai_enabled


def _get_client():
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    if not settings.ai_api_key:
        raise AIUnavailable("Defina AI_API_KEY no .env para habilitar a IA.")

    try:
        from anthropic import AsyncAnthropic
    except ImportError as error:  # pragma: no cover - depende do ambiente
        raise AIUnavailable("Instale o pacote anthropic: pip install anthropic") from error

    _client = AsyncAnthropic(api_key=settings.ai_api_key, timeout=REQUEST_TIMEOUT)
    return _client


async def _ask_claude(system: str, prompt: str, effort: str = "low") -> str:
    client = _get_client()
    settings = get_settings()

    try:
        # betas/fallbacks: se um classificador de segurança recusar o pedido,
        # a própria API repete a chamada em um modelo alternativo.
        response = await client.beta.messages.create(
            model=settings.ai_model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except Exception as error:
        logger.exception("Chamada à API de IA falhou.")
        raise AIUnavailable("O provedor de IA não respondeu.") from error

    if response.stop_reason == "refusal":
        raise AIUnavailable("O modelo preferiu não responder a essa pergunta.")

    text = "\n".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise AIUnavailable("O provedor devolveu uma resposta vazia.")
    return text


async def answer_question(question: str) -> str:
    """Responde uma pergunta livre feita pelo comando /ask."""
    return await _ask_claude(ASSISTANT_SYSTEM, question, effort="low")


async def summarize_activity(report: str) -> str:
    """Comenta um relatório de métricas já montado pelo report_service."""
    prompt = (
        "Abaixo estão as métricas de atividade do servidor nos últimos dias. "
        "Faça uma leitura do que elas indicam sobre o engajamento.\n\n"
        f"{report}"
    )
    return await _ask_claude(ANALYST_SYSTEM, prompt, effort="medium")

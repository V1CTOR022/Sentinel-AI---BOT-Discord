"""Integração de IA.

Fala com qualquer API compatível com o formato OpenAI de chat completions,
que hoje é o padrão de fato: OpenAI, Groq, OpenRouter, DeepSeek, Together,
LM Studio e Ollama local, entre outros. Trocar de fornecedor é mudar
AI_BASE_URL e AI_MODEL no .env, sem tocar no código.

Sem AI_API_KEY e AI_MODEL preenchidos o serviço fica desligado e os comandos
avisam isso, em vez de quebrar.
"""

from __future__ import annotations

import logging

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 45.0
MAX_TOKENS = 900
TEMPERATURE = 0.4

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


_client: httpx.AsyncClient | None = None


def is_enabled() -> bool:
    return get_settings().ai_enabled


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        settings = get_settings()
        _client = httpx.AsyncClient(
            base_url=settings.ai_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
            timeout=REQUEST_TIMEOUT,
        )
    return _client


async def aclose() -> None:
    """Fecha a conexão. Chamado no encerramento do bot."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _payload(system: str, prompt: str, token_field: str) -> dict:
    return {
        "model": get_settings().ai_model,
        "temperature": TEMPERATURE,
        token_field: MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }


async def _chat(system: str, prompt: str) -> str:
    settings = get_settings()
    if not settings.ai_enabled:
        raise AIUnavailable("Defina AI_API_KEY e AI_MODEL no .env para habilitar a IA.")

    client = _get_client()
    try:
        response = await client.post("/chat/completions", json=_payload(system, prompt, "max_tokens"))
        # Alguns modelos recentes da OpenAI rejeitam max_tokens e exigem
        # max_completion_tokens. Uma segunda tentativa resolve sem precisar
        # saber de antemão qual é o caso.
        if response.status_code == 400 and "max_completion_tokens" in response.text:
            response = await client.post(
                "/chat/completions", json=_payload(system, prompt, "max_completion_tokens")
            )
    except httpx.HTTPError as error:
        logger.exception("Não consegui falar com o provedor de IA.")
        raise AIUnavailable("O provedor de IA não respondeu.") from error

    if response.status_code == 401:
        raise AIUnavailable("O provedor recusou a credencial. Confira AI_API_KEY.")
    if response.status_code == 404:
        raise AIUnavailable(f"O provedor não conhece o modelo {settings.ai_model!r}. Confira AI_MODEL.")
    if response.status_code == 429:
        raise AIUnavailable("Limite de uso do provedor atingido. Tente de novo em instantes.")
    if response.status_code >= 400:
        logger.error("Provedor de IA respondeu %s: %s", response.status_code, response.text[:400])
        raise AIUnavailable("O provedor de IA devolveu um erro.")

    try:
        text = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        logger.error("Resposta em formato inesperado: %s", response.text[:400])
        raise AIUnavailable("Não entendi a resposta do provedor de IA.") from error

    text = (text or "").strip()
    if not text:
        raise AIUnavailable("O provedor devolveu uma resposta vazia.")
    return text


async def answer_question(question: str) -> str:
    """Responde uma pergunta livre feita pelo comando /ask."""
    return await _chat(ASSISTANT_SYSTEM, question)


async def summarize_activity(report: str) -> str:
    """Comenta um relatório de métricas já montado pelo report_service."""
    prompt = (
        "Abaixo estão as métricas de atividade do servidor nos últimos dias. "
        "Faça uma leitura do que elas indicam sobre o engajamento.\n\n"
        f"{report}"
    )
    return await _chat(ANALYST_SYSTEM, prompt)

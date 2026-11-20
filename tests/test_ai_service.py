import httpx
import pytest

from bot.services import ai_service
from core.config import get_settings


@pytest.fixture
def ia_configurada(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "chave-de-teste")
    monkeypatch.setenv("AI_MODEL", "modelo-de-teste")
    monkeypatch.setenv("AI_BASE_URL", "https://provedor.invalido/v1")
    get_settings.cache_clear()
    yield
    monkeypatch.setattr(ai_service, "_client", None, raising=False)
    get_settings.cache_clear()


def responder(monkeypatch, handler):
    """Troca o cliente HTTP por um que responde sem sair da máquina."""
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://provedor.invalido/v1",
    )
    monkeypatch.setattr(ai_service, "_client", client)
    return client


def resposta_ok(texto="Tudo certo por aqui."):
    return httpx.Response(200, json={"choices": [{"message": {"content": texto}}]})


async def test_desligada_sem_configuracao(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    get_settings.cache_clear()

    assert ai_service.is_enabled() is False
    with pytest.raises(ai_service.AIUnavailable):
        await ai_service.answer_question("oi")
    get_settings.cache_clear()


async def test_desligada_sem_modelo(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "chave")
    monkeypatch.delenv("AI_MODEL", raising=False)
    get_settings.cache_clear()

    assert ai_service.is_enabled() is False
    get_settings.cache_clear()


async def test_pergunta_respondida(ia_configurada, monkeypatch):
    enviado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        enviado.update(json.loads(request.content))
        enviado["path"] = request.url.path
        return resposta_ok("Resposta do modelo.")

    responder(monkeypatch, handler)

    assert await ai_service.answer_question("Qual é a capital da França?") == "Resposta do modelo."
    assert enviado["path"] == "/v1/chat/completions"
    assert enviado["model"] == "modelo-de-teste"
    assert enviado["messages"][1]["content"] == "Qual é a capital da França?"


async def test_cliente_usa_as_credenciais_do_env(ia_configurada):
    """Aqui o cliente real é construído, não o dublê dos outros testes."""
    client = ai_service._get_client()
    try:
        assert client.headers["Authorization"] == "Bearer chave-de-teste"
        assert str(client.base_url).rstrip("/") == "https://provedor.invalido/v1"
    finally:
        await ai_service.aclose()


async def test_resumo_de_atividade(ia_configurada, monkeypatch):
    responder(monkeypatch, lambda request: resposta_ok("O servidor está mais calmo."))
    assert await ai_service.summarize_activity("Mensagens: 10") == "O servidor está mais calmo."


async def test_retenta_com_max_completion_tokens(ia_configurada, monkeypatch):
    tentativas = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        corpo = json.loads(request.content)
        tentativas.append("max_tokens" if "max_tokens" in corpo else "max_completion_tokens")
        if len(tentativas) == 1:
            return httpx.Response(400, text="Unsupported parameter: use max_completion_tokens")
        return resposta_ok("Funcionou na segunda.")

    responder(monkeypatch, handler)

    assert await ai_service.answer_question("oi") == "Funcionou na segunda."
    assert tentativas == ["max_tokens", "max_completion_tokens"]


@pytest.mark.parametrize(
    "status,trecho",
    [
        (401, "credencial"),
        (404, "modelo"),
        (429, "Limite de uso"),
        (500, "erro"),
    ],
)
async def test_erros_do_provedor(ia_configurada, monkeypatch, status, trecho):
    responder(monkeypatch, lambda request: httpx.Response(status, text="falhou"))

    with pytest.raises(ai_service.AIUnavailable) as erro:
        await ai_service.answer_question("oi")
    assert trecho in str(erro.value)


async def test_resposta_vazia(ia_configurada, monkeypatch):
    responder(monkeypatch, lambda request: resposta_ok("   "))

    with pytest.raises(ai_service.AIUnavailable):
        await ai_service.answer_question("oi")


async def test_resposta_em_formato_inesperado(ia_configurada, monkeypatch):
    responder(monkeypatch, lambda request: httpx.Response(200, json={"sem": "choices"}))

    with pytest.raises(ai_service.AIUnavailable):
        await ai_service.answer_question("oi")


async def test_falha_de_rede(ia_configurada, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota para o host")

    responder(monkeypatch, handler)

    with pytest.raises(ai_service.AIUnavailable):
        await ai_service.answer_question("oi")

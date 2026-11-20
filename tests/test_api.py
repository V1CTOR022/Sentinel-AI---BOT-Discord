import asyncio
import importlib

import pytest
from fastapi.testclient import TestClient

from bot.services.activity_service import ActivityRecorder
from core.config import get_settings
from core.database import close_db

GUILD = "123"


def montar_cliente(tmp_path, monkeypatch, api_key: str | None = None):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "api-test.db"))
    if api_key:
        monkeypatch.setenv("SENTINEL_API_KEY", api_key)
    else:
        monkeypatch.delenv("SENTINEL_API_KEY", raising=False)

    get_settings.cache_clear()
    asyncio.run(close_db())

    import api.main

    importlib.reload(api.main)
    return TestClient(api.main.app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    with montar_cliente(tmp_path, monkeypatch) as client:
        yield client
    asyncio.run(close_db())
    get_settings.cache_clear()


def gravar_atividade(mensagens=3):
    async def runner():
        recorder = ActivityRecorder()
        for indice in range(mensagens):
            recorder.record(int(GUILD), 456, indice, channel_name="geral")
        await recorder.flush()

    asyncio.run(runner())


def test_health(client):
    resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"
    assert resposta.json()["auth_required"] is False


def test_metricas_de_servidor_sem_dados(client):
    dados = client.get(f"/api/guilds/{GUILD}/metrics").json()
    assert dados["total_messages"] == 0
    assert dados["guild_id"] == GUILD


def test_endpoints_com_dados(client):
    gravar_atividade(3)

    metrics = client.get(f"/api/guilds/{GUILD}/metrics").json()
    assert metrics["total_messages"] == 3

    canais = client.get(f"/api/guilds/{GUILD}/activity").json()["channels"]
    assert canais[0]["channel_name"] == "geral"

    membros = client.get(f"/api/guilds/{GUILD}/members").json()["members"]
    assert len(membros) == 3

    timeline = client.get(f"/api/guilds/{GUILD}/timeline?days=3").json()["timeline"]
    assert len(timeline) == 3
    assert timeline[-1]["message_count"] == 3

    guilds = client.get("/api/guilds").json()["guilds"]
    assert guilds[0]["guild_id"] == GUILD


def test_limites_de_query_sao_validados(client):
    assert client.get(f"/api/guilds/{GUILD}/activity?limit=0").status_code == 422
    assert client.get(f"/api/guilds/{GUILD}/timeline?days=500").status_code == 422


def test_api_key_protege_os_endpoints(tmp_path, monkeypatch):
    with montar_cliente(tmp_path, monkeypatch, api_key="chave-secreta") as client:
        assert client.get("/health").status_code == 200
        assert client.get(f"/api/guilds/{GUILD}/metrics").status_code == 401
        assert client.get(f"/api/guilds/{GUILD}/metrics", headers={"X-API-Key": "errada"}).status_code == 401
        ok = client.get(f"/api/guilds/{GUILD}/metrics", headers={"X-API-Key": "chave-secreta"})
        assert ok.status_code == 200
    asyncio.run(close_db())
    get_settings.cache_clear()

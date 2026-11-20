"""API de leitura das métricas coletadas pelo bot.

Só lê o banco. Quem escreve é o bot.
"""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import close_db, get_db
from core.stats import daily_timeline, guild_metrics, list_guilds, top_authors, top_channels

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_db()
    yield
    await close_db()


app = FastAPI(
    title="Sentinel AI API",
    description="Métricas de atividade de servidores Discord (apenas metadados).",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.dashboard_origins),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Proteção opcional: ativa quando SENTINEL_API_KEY está definida.

    CORS é regra de navegador, não de servidor — sem essa chave, qualquer um
    com a URL lê as métricas de qualquer servidor. Em produção, defina.
    """
    if not settings.api_key:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Informe o header X-API-Key.",
        )


guarded = [Depends(require_api_key)]


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "sentinel-api", "auth_required": bool(settings.api_key)}


@app.get("/api/guilds", dependencies=guarded, tags=["guilds"])
async def guilds():
    db = await get_db()
    return {"guilds": await list_guilds(db)}


@app.get("/api/guilds/{guild_id}/metrics", dependencies=guarded, tags=["guilds"])
async def metrics(guild_id: str):
    db = await get_db()
    return {"guild_id": guild_id, **await guild_metrics(db, guild_id)}


@app.get("/api/guilds/{guild_id}/activity", dependencies=guarded, tags=["guilds"])
async def activity(
    guild_id: str,
    limit: int = Query(20, ge=1, le=100),
    days: int | None = Query(None, ge=1, le=365, description="Limita o período analisado."),
):
    db = await get_db()
    return {"guild_id": guild_id, "channels": await top_channels(db, guild_id, limit, days)}


@app.get("/api/guilds/{guild_id}/members", dependencies=guarded, tags=["guilds"])
async def members(
    guild_id: str,
    limit: int = Query(10, ge=1, le=50),
    days: int | None = Query(None, ge=1, le=365),
):
    """Participação por membro. Devolve IDs, nunca nomes ou mensagens."""
    db = await get_db()
    return {"guild_id": guild_id, "members": await top_authors(db, guild_id, limit, days)}


@app.get("/api/guilds/{guild_id}/timeline", dependencies=guarded, tags=["guilds"])
async def timeline(guild_id: str, days: int = Query(14, ge=1, le=90)):
    db = await get_db()
    return {"guild_id": guild_id, "days": days, "timeline": await daily_timeline(db, guild_id, days)}

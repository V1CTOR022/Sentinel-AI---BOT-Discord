import asyncio

import pytest

from core.config import get_settings
from core.database import close_db, get_db


@pytest.fixture
def temp_settings(tmp_path, monkeypatch):
    """Isola cada teste em um banco próprio."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "sentinel-test.db"))
    monkeypatch.delenv("SENTINEL_API_KEY", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    get_settings.cache_clear()
    asyncio.run(close_db())

    yield get_settings()

    asyncio.run(close_db())
    get_settings.cache_clear()


@pytest.fixture
async def db(temp_settings):
    return await get_db()

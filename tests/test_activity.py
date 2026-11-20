from bot.services.activity_service import ActivityRecorder
from bot.services.report_service import build_report
from core.stats import daily_timeline, guild_metrics, list_guilds, top_authors, top_channels

GUILD = 123
CHANNEL = 456


async def seed(recorder, mensagens=5, author=1):
    for _ in range(mensagens):
        recorder.record(GUILD, CHANNEL, author, channel_name="geral")
    return await recorder.flush()


async def test_flush_grava_em_lote(db):
    recorder = ActivityRecorder()
    assert await seed(recorder, mensagens=3) == 3

    cursor = await db.execute("SELECT COUNT(*) AS c FROM activity_events")
    assert (await cursor.fetchone())["c"] == 3


async def test_flush_vazio_nao_faz_nada(db):
    assert await ActivityRecorder().flush() == 0


async def test_nenhum_conteudo_de_mensagem_e_gravado(db):
    recorder = ActivityRecorder()
    await seed(recorder, mensagens=1)

    cursor = await db.execute("PRAGMA table_info(activity_events)")
    colunas = {row["name"] for row in await cursor.fetchall()}
    assert "content" not in colunas
    assert colunas == {
        "id",
        "guild_id",
        "channel_id",
        "channel_name",
        "author_id",
        "event_type",
        "created_at",
    }


async def test_metricas_agregadas(db):
    recorder = ActivityRecorder()
    recorder.record(GUILD, CHANNEL, 1, channel_name="geral")
    recorder.record(GUILD, CHANNEL, 2, channel_name="geral")
    recorder.record(GUILD, 789, 2, channel_name="off-topic")
    await recorder.flush()

    metrics = await guild_metrics(db, str(GUILD))
    assert metrics["total_messages"] == 3
    assert metrics["active_users"] == 2
    assert metrics["active_channels"] == 2
    assert metrics["messages_last_24h"] == 3

    canais = await top_channels(db, str(GUILD))
    assert canais[0]["channel_name"] == "geral"
    assert canais[0]["message_count"] == 2
    assert canais[0]["unique_authors"] == 2

    autores = await top_authors(db, str(GUILD))
    assert autores[0]["message_count"] == 2

    assert await list_guilds(db) == [
        {"guild_id": str(GUILD), "total_messages": 3, "last_activity": canais[0]["last_activity"]}
    ]


async def test_timeline_preenche_dias_vazios(db):
    recorder = ActivityRecorder()
    await seed(recorder, mensagens=2)

    timeline = await daily_timeline(db, str(GUILD), days=5)
    assert len(timeline) == 5
    assert timeline[-1]["message_count"] == 2
    assert all(day["message_count"] == 0 for day in timeline[:-1])


async def test_relatorio_vazio(db):
    report = await build_report(GUILD, days=7)
    assert report.is_empty


async def test_relatorio_com_dados(db):
    recorder = ActivityRecorder()
    await seed(recorder, mensagens=4)

    report = await build_report(GUILD, days=7)
    assert not report.is_empty
    texto = report.as_text()
    assert "#geral" in texto
    assert "Mensagens no período: 4" in texto

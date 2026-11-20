"""Ponto de entrada do bot. Execute com `python -m bot.main`."""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from bot.commands.general import GeneralCommands
from bot.services.activity_service import ActivityRecorder
from bot.services.moderation_service import FloodDetector
from core.config import ConfigError, get_settings
from core.database import close_db, get_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("sentinel")

EXTENSIONS = ("bot.commands.ai", "bot.commands.reports")


class SentinelBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        # Desligado de propósito: contar atividade não exige ler o texto das
        # mensagens, e assim o bot não depende de uma intent privilegiada.
        intents.message_content = False

        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings = get_settings()
        self.recorder = ActivityRecorder()
        self.flood_detector = FloodDetector(
            limit=self.settings.flood_limit,
            window_seconds=self.settings.flood_window_seconds,
        )

    async def setup_hook(self):
        """Roda uma vez, antes de o bot entrar em operação.

        Registrar comandos aqui em vez de no on_ready evita duplicar tudo a
        cada reconexão e evita um sync extra, que tem rate limit agressivo.
        """
        await get_db()
        await self.recorder.start()

        await self.add_cog(GeneralCommands(self, self.flood_detector))
        for extension in EXTENSIONS:
            await self.load_extension(extension)

        try:
            if self.settings.guild_id:
                # Sync por servidor aparece na hora; o global leva até uma hora.
                guild = discord.Object(id=self.settings.guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
            else:
                synced = await self.tree.sync()
            logger.info("Comandos sincronizados: %s", len(synced))
        except discord.HTTPException:
            logger.exception("Falha ao sincronizar comandos.")

    async def close(self):
        await self.recorder.stop()
        await close_db()
        await super().close()

    async def on_ready(self):
        logger.info("Conectado como %s em %s servidor(es).", self.user, len(self.guilds))

    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        self.recorder.record(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            author_id=message.author.id,
            channel_name=getattr(message.channel, "name", None),
        )

        if self.flood_detector.check(message.guild.id, message.author.id):
            await self.alert_moderation(message)

        await self.process_commands(message)

    async def alert_moderation(self, message: discord.Message):
        channel_id = self.settings.mod_log_channel_id
        if not channel_id:
            return

        channel = self.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("MOD_LOG_CHANNEL_ID não aponta para um canal de texto visível ao bot.")
            return

        try:
            await channel.send(
                f"Possível flood: {message.author.mention} em {message.channel.mention}. "
                "Confira antes de aplicar qualquer punição."
            )
        except discord.HTTPException:
            logger.exception("Não consegui avisar a moderação.")


async def main():
    bot = SentinelBot()
    async with bot:
        await bot.start(bot.settings.require_token())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ConfigError as error:
        raise SystemExit(f"Configuração inválida: {error}")
    except KeyboardInterrupt:
        pass

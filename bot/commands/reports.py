import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.services import ai_service
from bot.services.report_service import ActivityReport, build_report
from core.config import get_settings

logger = logging.getLogger(__name__)
EMBED_FIELD_LIMIT = 1000


def build_embed(report: ActivityReport, guild_name: str, comment: str | None = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"Relatório de atividade — {guild_name}",
        description=f"Últimos {report.days} dias",
        color=discord.Color.blurple(),
    )
    period_total = sum(day["message_count"] for day in report.timeline)
    embed.add_field(name="Mensagens no período", value=str(period_total))
    embed.add_field(name="Últimas 24h", value=str(report.metrics["messages_last_24h"]))
    embed.add_field(name="Usuários distintos", value=str(report.metrics["active_users"]))

    if report.channels:
        linhas = []
        for channel in report.channels:
            nome = channel["channel_name"] or f"id {channel['channel_id']}"
            linhas.append(f"**#{nome}** — {channel['message_count']} mensagens")
        embed.add_field(name="Canais mais ativos", value="\n".join(linhas), inline=False)

    por_dia = " ".join(str(day["message_count"]) for day in report.timeline[-7:])
    embed.add_field(name="Mensagens por dia (7 dias)", value=por_dia or "sem dados", inline=False)

    if comment:
        embed.add_field(name="Leitura da IA", value=comment[:EMBED_FIELD_LIMIT], inline=False)

    embed.set_footer(text="Sentinel AI · somente metadados, nenhum conteúdo de mensagem")
    return embed


class ReportCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = get_settings()
        if self.settings.report_channel_id:
            self.scheduled_report.change_interval(hours=self.settings.report_interval_hours)
            self.scheduled_report.start()

    async def cog_unload(self):
        self.scheduled_report.cancel()

    @app_commands.command(name="relatorio", description="Resume a atividade recente do servidor.")
    @app_commands.describe(dias="Quantos dias considerar (1 a 30).")
    @app_commands.checks.cooldown(1, 30.0)
    async def relatorio(self, interaction: discord.Interaction, dias: app_commands.Range[int, 1, 30] = 7):
        if interaction.guild is None:
            await interaction.response.send_message("Use este comando em um servidor.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        report = await build_report(interaction.guild.id, days=dias)
        if report.is_empty:
            await interaction.followup.send(
                "Ainda não tenho dados deste servidor. Deixe o bot rodando um pouco e tente de novo."
            )
            return

        comment = await self._ai_comment(report)
        await interaction.followup.send(embed=build_embed(report, interaction.guild.name, comment))

    async def _ai_comment(self, report: ActivityReport) -> str | None:
        if not ai_service.is_enabled():
            return None
        try:
            return await ai_service.summarize_activity(report.as_text())
        except ai_service.AIUnavailable as error:
            logger.warning("Resumo de IA indisponível: %s", error)
            return None

    @tasks.loop(hours=24)
    async def scheduled_report(self):
        """Relatório automático. Só roda se REPORT_CHANNEL_ID estiver definido."""
        channel = self.bot.get_channel(self.settings.report_channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("REPORT_CHANNEL_ID não aponta para um canal de texto visível ao bot.")
            return

        report = await build_report(channel.guild.id, days=7)
        if report.is_empty:
            return

        comment = await self._ai_comment(report)
        await channel.send(embed=build_embed(report, channel.guild.name, comment))

    @scheduled_report.before_loop
    async def before_scheduled_report(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ReportCommands(bot))

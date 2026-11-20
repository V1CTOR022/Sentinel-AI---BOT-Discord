import discord
from discord import app_commands
from discord.ext import commands

from bot.services.moderation_service import FloodDetector


class GeneralCommands(commands.Cog):
    """Comandos de uso geral.

    Herdar de Cog é o que faz o discord.py injetar o `self` nos callbacks dos
    slash commands. Em uma classe comum o bind não acontece e a Interaction
    chega no lugar do self.
    """

    def __init__(self, bot: commands.Bot, flood_detector: FloodDetector | None = None):
        self.bot = bot
        self.flood_detector = flood_detector

    @app_commands.command(name="ping", description="Verifica se o Sentinel está online.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! Latência: **{latency} ms**", ephemeral=True)

    @app_commands.command(name="server", description="Exibe informações do servidor.")
    async def server(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use este comando em um servidor.", ephemeral=True)
            return

        embed = discord.Embed(
            title=guild.name,
            description="Informações gerais",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Membros", value=str(guild.member_count or "indisponível"))
        embed.add_field(name="Canais", value=str(len(guild.channels)))
        if guild.created_at:
            embed.add_field(name="Criado em", value=discord.utils.format_dt(guild.created_at, "D"))
        embed.add_field(name="ID", value=str(guild.id), inline=False)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="status", description="Mostra o estado interno do monitoramento.")
    async def status(self, interaction: discord.Interaction):
        tracked = self.flood_detector.tracked_users if self.flood_detector else 0
        embed = discord.Embed(title="Sentinel — status", color=discord.Color.green())
        embed.add_field(name="Servidores monitorados", value=str(len(self.bot.guilds)))
        embed.add_field(name="Usuários na janela de flood", value=str(tracked))
        embed.add_field(name="Latência", value=f"{round(self.bot.latency * 1000)} ms")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCommands(bot))

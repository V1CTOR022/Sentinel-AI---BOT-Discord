import discord
from discord import app_commands
from discord.ext import commands

from bot.services.ai_service import AIUnavailable, answer_question, is_enabled

MAX_QUESTION_LENGTH = 1000
DISCORD_MESSAGE_LIMIT = 1900


class AICommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ask", description="Faz uma pergunta ao assistente de IA.")
    @app_commands.describe(question="Pergunta para o assistente.")
    @app_commands.checks.cooldown(1, 15.0)
    async def ask(self, interaction: discord.Interaction, question: str):
        if not is_enabled():
            await interaction.response.send_message(
                "A integração de IA não está configurada. Defina `AI_API_KEY` no `.env`.",
                ephemeral=True,
            )
            return

        question = question.strip()
        if not question:
            await interaction.response.send_message("Escreva uma pergunta.", ephemeral=True)
            return
        if len(question) > MAX_QUESTION_LENGTH:
            await interaction.response.send_message(
                f"A pergunta deve ter no máximo {MAX_QUESTION_LENGTH} caracteres.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            answer = await answer_question(question)
        except AIUnavailable as error:
            answer = str(error)
        await interaction.followup.send(answer[:DISCORD_MESSAGE_LIMIT], ephemeral=True)

    @ask.error
    async def ask_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            message = f"Aguarde {error.retry_after:.0f}s antes de perguntar de novo."
        else:
            message = "Não consegui processar sua pergunta agora."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AICommands(bot))

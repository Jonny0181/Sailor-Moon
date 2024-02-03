import discord
from discord import app_commands
from discord.ext import commands

class Settings(commands.GroupCog, name="settings"):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.settings = self.bot.db.settings

    async def language_auto(self, interaction: discord.Interaction, current: str):
        languages = ["French", "Portuguese", "Spanish", "English", "Hindi", "Russian", 
                     "Cantonese", "German", "Japanese", "Urdu", "Arabic", "Bengali", 
                     "Vietnamese", "Italian", "Marathi", "Turkish"]

        options = [app_commands.Choice(name=lang, value=lang) for lang in languages if current.lower() in lang.lower()]

        return options

    @app_commands.command(name="language", description="Set the language of the bot for your server.")
    @app_commands.autocomplete(language=language_auto)
    async def language(self, interaction: discord.Interaction, language: str):
        data = await self.settings.find_one({"_id": interaction.guild.id})
        if data is None:
            # Add data
            await self.settings.insert_one({"_id": interaction.guild.id, "language": language})
            response = f"Language has been updated from **English** to **{language}**."
        else:
            # Update data
            await self.settings.update_one({"_id": interaction.guild.id}, {"$set": {"language": language}})
            response = f"Language has been updated from **{data['language']}** to **{language}**."

        await interaction.response.send_message(response)

    @language.error
    async def on_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        await self.bot.log_information("error", interaction, error)
        try:
            return await interaction.response.send_message("An error has occurred and has been logged, please try again!", ephemeral=True)
        except discord.InteractionResponded:
            return await interaction.followup.send(content="An error has occurred and has been logged, please try again!", embed=None, view=None)

async def setup(bot: commands.AutoShardedBot):
    await bot.add_cog(Settings(bot))

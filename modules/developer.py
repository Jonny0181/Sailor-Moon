import os
import discord
from utils import checks
from typing import List
from discord.ext import commands
from discord import app_commands

class Developer(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @checks.is_dev()
    @app_commands.command(name="load", description="Load one of Sailors modules.")
    async def load(self, interaction: discord.Interaction, module: str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            await self.bot.load_extension(module)
            return await interaction.followup.send(f"<:tickYes:697759553626046546> Module `{module}` has been loaded.")
        except commands.ExtensionAlreadyLoaded:
            return await interaction.followup.send(f"<:tickNo:697759586538749982> Module  `{module}` is already loaded.")
        except commands.ExtensionNotFound:
            return await interaction.followup.send(f"<:tickNo:697759586538749982> `{module}` could not be found.")
        except commands.ExtensionFailed as error:
            return await interaction.followup.send(f"<:tickNo:697759586538749982> An error occurred while loading the module:```py\n{error}```")
        
    @checks.is_dev()
    @app_commands.command(name="unload", description="Unload one of Sailors modules.")
    async def unload(self, interaction: discord.Interaction, module: str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            await self.bot.unload_extension(module)
            return await interaction.followup.send(f"<:tickYes:697759553626046546> Module `{module}` has been unloaded.")
        except commands.ExtensionNotLoaded:
            return await interaction.followup.send(f"<:tickNo:697759586538749982> Module `{module}` is not loaded.")
        except commands.ExtensionNotFound:
            return await interaction.followup.send(f"<:tickNo:697759586538749982> `{module}` could not be found.")
        except commands.ExtensionFailed as error:
            return await interaction.followup.send(f"<:tickNo:697759586538749982> An error occurred while loading the module:```py\n{error}```")

    @checks.is_dev()
    @app_commands.command(name="reload", description="Reload one of Sailors modules.")
    async def reload(self, interaction: discord.Interaction, module: str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            await self.bot.reload_extension(module)
            return await interaction.followup.send(f"<:tickYes:697759553626046546> Module `{module}` reloaded successfully.")
        except commands.ExtensionNotLoaded:
            return await interaction.followup.send(f"<:tickNo:697759586538749982> Module `{module}` is not loaded.")
        except commands.ExtensionNotFound:
            return await interaction.followup.send(f"<:tickNo:697759586538749982> `{module}` could not be found.")
        except commands.ExtensionFailed as error:
            return await interaction.followup.send(f"<:tickNo:697759586538749982> An error occurred while loading the module:```py\n{error}```")
    
    @load.autocomplete('module')
    @unload.autocomplete('module')
    @reload.autocomplete('module')
    async def module(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        options = []
        modules = [e for e in os.listdir('modules') if e.endswith('.py')]
        for module in modules:
            module_name = module.replace('.py', '')
            options.append(app_commands.Choice(name=module_name, value=f"modules.{module_name}"))
        return options

async def setup(bot: commands.AutoShardedBot):
    await bot.add_cog(Developer(bot))
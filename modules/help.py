import discord
from typing import Optional
from discord import app_commands
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @app_commands.command(name="help", description="Get help on a certain module or command.")
    async def help(self, interaction: discord.Interaction, module: Optional[str], command: Optional[str]):
        await interaction.response.defer(thinking=True)

        if not module and not command:
            await self.show_modules_help(interaction)
        elif module and not command:
            await self.show_module_commands(interaction, module)
        else:
            await self.show_command_help(interaction, command)

    async def show_modules_help(self, interaction):
        modules = [e.capitalize() for e in self.bot.cogs if e not in ('Jishaku', 'Help')]
        e = self.create_help_embed("Sailor Moon Modules", modules)
        await interaction.followup.send(embed=e)

    async def show_module_commands(self, interaction, module):
        e = discord.Embed(colour=discord.Colour.teal())
        e.set_thumbnail(url=self.bot.user.avatar)
        e.set_author(name=f"{module} Commands", icon_url=self.bot.user.avatar)
        e.description = ""

        for command in await self.bot.tree.fetch_commands():
            command2 = self.bot.tree.get_command(command.name)
            if command2:
                if str(command2.module).split('.')[1] == module.lower():
                    try:
                        if command2.parameters:
                            params = " ".join(
                                [f"<{param.name}>" for param in command2.parameters])
                            e.description += f"{command.mention} `{params}` - {command2.description}\n"
                        else:
                            e.description += f"{command.mention} - {command2.description}\n"
                    except AttributeError:
                        e.description += f"{command.mention} - {command2.description}\n"

        await interaction.followup.send(embed=e)

    async def show_command_help(self, interaction, command_name):
        command = self.bot.tree.get_command(command_name)
        
        if not command:
            # Handle case where the command is not found
            return await interaction.followup.send("Command not found.")

        e = discord.Embed(colour=discord.Colour.teal())
        e.set_thumbnail(url=self.bot.user.avatar)
        e.set_author(name=f"Help for {command.name}:", icon_url=self.bot.user.avatar)
        e.description = command.description

        try:
            if command.parameters:
                e.add_field(name="Parameters:",
                            value="\n".join([f"`{param.name}` - {param.description}" for param in command.parameters]))
        except AttributeError:
            pass
        
        subcommands_info = "\n".join(
            [f"`{subcommand.name}` - {subcommand.description}" for subcommand in command.commands])
        if subcommands_info:
            e.add_field(name="Sub Commands:", value=subcommands_info)

        await interaction.followup.send(embed=e)

    def create_help_embed(self, title, elements):
        e = discord.Embed(colour=discord.Colour.teal())
        e.set_thumbnail(url=self.bot.user.avatar)
        e.set_author(name=title, icon_url=self.bot.user.avatar)
        e.description = "\n".join(elements)
        return e

    @help.error
    async def on_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        await self.bot.log_information("error", interaction, error)
        try:
            return await interaction.response.send_message("An error has occurred and has been logged, please try again!", ephemeral=True)
        except discord.InteractionResponded:
            return await interaction.followup.send(content="An error has occurred and has been logged, please try again!", embed=None, view=None)

async def setup(bot: commands.AutoShardedBot):
    await bot.add_cog(Help(bot))
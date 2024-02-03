import discord
from typing import List
from discord.ext import commands
from discord import app_commands

class CollabPlaylists(commands.GroupCog, name="collaborative"):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.db = self.bot.db.collaborative_playlists

    @app_commands.command(name='authorize', description='Authorize users to manage your collaborative playlist.')
    async def authorize_user(self, interaction: discord.Interaction, user: discord.Member, playlist_name: str):
        if playlist_name == "None":
            return await interaction.response.send_message("You don't have any collaborative playlists.")
        
        # Check if the playlist exists
        playlist = await self.db.find_one({"name": playlist_name})

        # Check if the user invoking the command is the playlist creator
        if playlist and interaction.user.id == playlist["creator_id"]:
            # Check if the user is already authorized
            if user.id in playlist["allowed_users"]:
                await interaction.response.send_message(f'This user is already authorized to manage the playlist.')
            else:
                # Authorize the user to manage the playlist
                await self.db.update_one(
                    {"name": playlist_name},
                    {"$push": {"allowed_users": user.id}}
                )
                await interaction.response.send_message(f'User **{user.display_name}** authorized to manage the playlist `{playlist_name}`!')
        else:
            await interaction.response.send_message(f'You are not the creator of this playlist or the playlist `{playlist_name}` not found.')

    @app_commands.command(name='unauthorize', description='Unauthorize users from managing your collaborative playlist.')
    async def unauthorize_user(self, interaction: discord.Interaction, user: discord.Member, playlist_name: str):
        if playlist_name == "None":
            return await interaction.response.send_message("You don't have any collaborative playlists.")
        
        # Check if the playlist exists
        playlist = await self.db.find_one({"name": playlist_name})

        # Check if the user invoking the command is the playlist creator
        if playlist and interaction.user.id == playlist["creator_id"]:
            # Check if the user is authorized
            if user.id in playlist["allowed_users"]:
                # Unauthorize the user from managing the playlist
                await self.db.update_one(
                    {"name": playlist_name},
                    {"$pull": {"allowed_users": user.id}}
                )
                await interaction.response.send_message(f'User **{user.display_name}** unauthorized from managing the playlist `{playlist_name}`!')
            else:
                await interaction.response.send_message(f'This user is not authorized to manage the playlist.')
        else:
            await interaction.response.send_message(f'You are not the creator of this playlist or the playlist `{playlist_name}` not found.')

    @authorize_user.autocomplete('playlist_name')
    @unauthorize_user.autocomplete('playlist_name')
    async def owner_auto(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        user_playlists = await self.db.find({"creator_id": interaction.user.id}).to_list(length=None)
        
        if user_playlists:
            playlist_names = [playlist["name"] for playlist in user_playlists]
            return [
                app_commands.Choice(name=pl, value=pl)
                for pl in playlist_names if current.lower() in pl.lower()
            ]
        else:
            return [
                app_commands.Choice(
                    name="No playlists found.",
                    value="None"
                )
            ]

    @authorize_user.error
    @unauthorize_user.error
    async def on_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        await self.bot.log_information("error", interaction, error)
        try:
            return await interaction.response.send_message("An error has occurred and has been logged, please try again!", ephemeral=True)
        except discord.InteractionResponded:
            return await interaction.followup.send(content="An error has occurred and has been logged, please try again!", embed=None, view=None)
        
async def setup(bot: commands.AutoShardedBot):
    await bot.add_cog(CollabPlaylists(bot))

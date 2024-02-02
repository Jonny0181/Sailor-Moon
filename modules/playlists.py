import re
import discord
import humanize
import datetime
import lavalink
from aiohttp import request
from discord.ext import commands
from discord import app_commands
from modules.music import LavalinkVoiceClient
from buttons.PlaylistButtons import PlaylistButtons, LikedButtons

url_rx = re.compile(r'https?:\/\/(?:www\.)?.+')

class Playlists(commands.GroupCog, name="playlists"):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.user_playlists = self.bot.db.playlists
        self.collaborative_playlists = self.bot.db.collaborative_playlists
        self.user_liked = self.bot.db.liked

    @app_commands.command(name="list", description="Lists all of your playlists. Collaborative and personal.")
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        personal_playlists = await self.user_playlists.find_one({"_id": interaction.user.id})
        collab_playlists = await self.collaborative_playlists.find({"$or": [{"creator_id": interaction.user.id}, {"allowed_users": interaction.user.id}]}).to_list(length=None)

        all_playlists = []

        if personal_playlists and personal_playlists['playlists']:
            all_playlists.extend(personal_playlists['playlists'])
        if collab_playlists:
            all_playlists.extend(collab_playlists)

        if not all_playlists:
            await interaction.response.send_message("No playlists found.")
            return

        current_playlist = all_playlists[0]
        playlist_type = "Personal" if "creator_id" not in current_playlist else "Collaborative"
        songs = current_playlist.get("songs", [])

        e = discord.Embed(colour=discord.Colour.teal())

        if playlist_type == "Personal":        
            e.add_field(name="Name:", value=f"{current_playlist['name']}", inline=True)
        elif playlist_type == "Collaborative":
            e.add_field(name="Name:", value=f"[Collab] {current_playlist['name']}", inline=True)
            e.add_field(name="Created By:", value=f"<@!{current_playlist['creator_id']}>", inline=True)
            if len(current_playlist['allowed_users']) > 1:
                e.add_field(name="Authorized Users:", value=", ".join([f"<@!{user_id}>" for user_id in current_playlist['allowed_users'] if user_id != current_playlist['creator_id']]), inline=False)

        if songs:
            song_list = "\n".join(songs[:5])
            e.add_field(name="Songs:", value=song_list, inline=False)
            if len(songs) > 5:
                e.set_footer(text=f"Not showing {len(songs) - 5} more songs...")
        else:
            e.add_field(name="Songs:", value="This playlist contains 0 songs.", inline=False)

        msg = await interaction.followup.send(embed=e)
        return await msg.edit(view=PlaylistButtons(self.bot, msg, all_playlists, 0))

    @app_commands.command(name="liked", description="This will show all your liked songs.")
    async def liked(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        data = await self.user_liked.find_one({"_id": interaction.user.id})
        if data is None:
            await interaction.response.send_message("You haven't liked any songs yet, try playing some and liking them by clicking the `+` button!")
            return
        else:
            liked_songs = []
            for song in data['songs']:
                results = await self.bot.lavalink.get_tracks(song)
                liked_songs.append(results.tracks[0])
            
            duration = '🔴 LIVE' if liked_songs[0].stream else humanize.naturaldelta(datetime.timedelta(milliseconds=liked_songs[0].duration))
            embed = discord.Embed(color=discord.Colour.teal())
            embed.add_field(name="Title:", value=liked_songs[0].title)
            embed.add_field(name="Duration:", value=duration)
            embed.add_field(name="Link:", value=f"[Click here to open..]({liked_songs[0].uri})", inline=False)
            embed.set_thumbnail(url=liked_songs[0].artwork_url)
            
            embed.set_footer(text=f"Showing song 1 of {len(liked_songs)} song(s)...")
            await interaction.followup.send(embed=embed, view=LikedButtons(bot=self.bot, songs=liked_songs, index=0))

    @app_commands.command(name="start", description="Queue one of your playlists.")
    async def start(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        playlists = await self.user_playlists.find_one({"_id": interaction.user.id})
        collab_playlists =  await self.collaborative_playlists.find({"$or": [{"creator_id": interaction.user.id}, {"allowed_users": interaction.user.id}]}).to_list(length=None)
        liked = await self.user_liked.find_one({"_id": interaction.user.id})

        if query == "no_playlists":
            return await interaction.followup.send("You haven't created any playlists yet. Try creating one by liking a song with the `+` button.")
        elif query == "liked":
            await self.start_playlist(interaction, liked['songs'])
            return await interaction.followup.send("Your liked songs have been added to the queue!")
        elif query.startswith("personal_"):
            playlist_name = query.replace("personal_", "")
            found_personal_playlist = next((playlist for playlist in playlists['playlists'] if playlist['name'] == playlist_name), None)
            if found_personal_playlist:
                await self.start_playlist(interaction, found_personal_playlist['songs'])
                return await interaction.followup.send(f"Personal Playlist **{playlist_name}** has been added to the queue.")
            else:
                return await interaction.followup.send("Failed to find the specified personal playlist. Please try again.")     
        elif query.startswith("collab_"):
            playlist_id = query.replace("collab_", "")
            found_collab_playlist = next((playlist for playlist in collab_playlists if str(playlist['_id']) == playlist_id), None)
            if found_collab_playlist:
                await self.start_playlist(interaction, found_collab_playlist['songs'])
                return await interaction.followup.send(f"Collaborative Playlist **{found_collab_playlist['name']}** has been added to the queue.")
            else:
                return await interaction.followup.send("Failed to find the specified collaborative playlist. Please try again.")

    @start.autocomplete('query')
    async def playlist_auto(self, interaction: discord.Interaction, current: str):
        personal_playlists = await self.user_playlists.find_one({"_id": interaction.user.id})
        collab_playlists = await self.collaborative_playlists.find({"$or": [{"creator_id": interaction.user.id}, {"allowed_users": interaction.user.id}]}).to_list(length=None)
        liked = await self.user_liked.find_one({"_id": interaction.user.id})

        options = []
        try:
            if not personal_playlists or not personal_playlists.get('playlists'):
                options.append(app_commands.Choice(name="You don't have any playlists, try creating some!", value="no_playlists"))
            else:
                for playlist in personal_playlists['playlists']:
                    if current.lower() in playlist['name'].lower():
                        options.append(app_commands.Choice(name=playlist['name'], value=f"personal_{playlist['name']}"))
            for playlist in collab_playlists:
                if current.lower() in playlist['name'].lower():
                    collab_playlist_id = playlist['_id']
                    options.append(app_commands.Choice(name=f"[Collab] {playlist['name']}", value=f"collab_{collab_playlist_id}"))
            if current.lower() in "liked" and liked and liked.get('songs'):
                options.append(app_commands.Choice(name="Liked Songs", value="liked"))
            return options
        except Exception as e:
            print(f"An error occurred: {e}")

    async def start_playlist(self, interaction: discord.Interaction, songs: dict):
        player = self.bot.lavalink.player_manager.create(interaction.guild.id)
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.edit_message(content='Join a voicechannel first.', view=None, embed=None)

        permissions = interaction.user.voice.channel.permissions_for(interaction.guild.me)
        if not permissions.connect or not permissions.speak:
            return await interaction.response.edit_message(content="I need the `CONNECT` and `SPEAK` permissions.", view=None, embed=None)

        player.store('channel', interaction.channel.id)
        try:
            await interaction.user.voice.channel.connect(cls=LavalinkVoiceClient, self_deaf=True)
        except discord.ClientException:
            pass
           
        if interaction.guild.voice_client.channel.id != interaction.user.voice.channel.id:
            return await interaction.response.edit_message(content="You need to be in my voice channel.", view=None, embed=None)
        
        try:
            player = self.bot.lavalink.player_manager.players.get(interaction.guild.id)
            for song in songs:
                results = await self.bot.lavalink.get_tracks(song, check_local=True)
                if not results or not results.tracks:
                    pass
                else:
                    track = results.tracks[0]
                    player.add(requester=interaction.user.id, track=track)

            player.store('channel', interaction.channel.id)
            if not player.is_playing:
                await player.play()
        except lavalink.errors.LoadError:
            return await interaction.response.edit_message(content='Spotify API did not return a valid response!')

    async def delete_auto(self, interaction: discord.Interaction, current: str):
        playlists = await self.user_playlists.find_one({"_id": interaction.user.id})

        options = []

        if not playlists or not playlists['playlists']:
            options.append(app_commands.Choice(name="You don't have any playlists to delete.", value="no_playlists"))
        else:
            for playlist in playlists['playlists']:
                if current.lower() in playlist['name'].lower():
                    options.append(app_commands.Choice(name=playlist['name'], value=playlist['name']))

        return options

    @app_commands.command(name="delete", description="This will allow you to delete a playlist.")
    @app_commands.autocomplete(playlist=delete_auto)
    async def delete(self, interaction: discord.Interaction, playlist: str):
        await interaction.response.defer(thinking=True)
        playlists = await self.user_playlists.find_one({"_id": interaction.user.id})

        if not playlists or not playlists['playlists']:
            return await interaction.followup.send("You don't have any playlists to delete.")

        playlist_to_delete = None
        for saved_playlist in playlists['playlists']:
            if saved_playlist['name'].lower() == playlist.lower():
                playlist_to_delete = saved_playlist
                break

        if not playlist_to_delete:
            return await interaction.followup.send(f"Playlist '{playlist}' not found. Check the spelling and try again.")

        playlists['playlists'].remove(playlist_to_delete)
        await self.user_playlists.update_one({"_id": interaction.user.id}, {"$set": {"playlists": playlists['playlists']}})
        await interaction.followup.send(f"Playlist **{playlist}** has been deleted.")
        
async def setup(bot: commands.AutoShardedBot):
    await bot.add_cog(Playlists(bot))
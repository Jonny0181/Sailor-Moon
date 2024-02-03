import time
import base64
import discord
import lavalink
import aiohttp
from typing import List
from discord.ext import commands
from requests.auth import HTTPBasicAuth
from discord import app_commands
from requests_oauthlib import OAuth2Session
from buttons.SpotifyCheck import Disconnect_Check
from utils.LavalinkVoiceClient import LavalinkVoiceClient


class Spotify(commands.GroupCog, description="All spotify related commands."):
    def __init__(self, bot: commands.AutoShardedBot) -> None:
        super().__init__()
        self.bot = bot
        self.db = self.bot.db.spotifyOauth

    @app_commands.command(name="info")
    async def spotify_info(self, interaction: discord.Interaction):
        """Get the info of the account that is currently connected."""
        await interaction.response.defer(ephemeral=True)
        data = await self.db.find_one({"_id": interaction.user.id})
        if data is None:
            return await interaction.followup.send("You do not have an account that is connected.")
        else:
            user = await self.get_current_user(interaction)
            if user != "Failed":
                e = discord.Embed(colour=discord.Colour.teal())
                e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
                e.add_field(
                    name="Name", value=user['display_name'], inline=False)
                e.add_field(name="Url", value=user['uri'], inline=False)
                if user['images'] != []:
                    e.set_thumbnail(url=user['images'][0]['url'])
                return await interaction.followup.send(embed=e)
            else:
                return await interaction.followup.send("I have failed to get your account information.")

    @app_commands.command(name="connect")
    async def spotify_connect(self, interaction: discord.Interaction):
        """Connect your spotify account!"""
        await interaction.response.defer(ephemeral=True)
        data = await self.db.find_one({"_id": interaction.user.id})
        if data is not None:
            return await interaction.followup.send(content="You already have your account linked! If you would no longer like it to be linked, you can use the command `/spotify disconnect`! <3")
        else:
            return await interaction.followup.send(content="Please head over to https://itzjxnny.com:5000/ to finish connecting your account.")

    @app_commands.command(name="disconnect")
    async def spotify_disconnect(self, interaction: discord.Interaction):
        """This will disconnect your spotify account!"""
        await interaction.response.defer(thinking=True)
        data = await self.db.find_one({"_id": interaction.user.id})
        if data is None:
            return await interaction.followup.send("You don't have a spotify account connected!")
        else:
            e = discord.Embed(colour=discord.Colour.teal())
            e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
            e.description = "Are you sure you want to disconnect your account?"
            msg = await interaction.followup.send(embed=e)
            return await msg.edit(view=Disconnect_Check(self.bot, msg))

    @app_commands.command(name="liked")
    async def spotify_liked(self, interaction: discord.Interaction):
        """Start playing all of the songs you have liked."""
        await interaction.response.defer(thinking=True)

        user_data = await self.db.find_one({"_id": interaction.user.id})
        if user_data is None:
            return await interaction.followup.send("You do not have a Spotify account connected! If you would like to connect yours, please use the command `/spotify connect`! <3")

        liked_songs = await self.get_liked_songs(interaction)
        if liked_songs == "Failed":
            return await interaction.followup.send("I failed to get your liked songs...")

        try:
            player = self.bot.lavalink.player_manager.create(interaction.guild.id, endpoint="us")
        except lavalink.errors.NodeError as e:
            print(f"[Music] Failed to create player in {interaction.guild.name}: {e}")
            return await interaction.followup.send("<:tickNo:697759586538749982> There are no available nodes right now! Try again later.")

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.followup.send('<:tickNo:697759586538749982> Join a voice channel first.')

        if not player.is_connected:
            permissions = interaction.user.voice.channel.permissions_for(interaction.guild.me)
            if not permissions.connect or not permissions.speak:
                return await interaction.followup.send('<:tickNo:697759586538749982> I need the `CONNECT` and `SPEAK` permissions.')

            player.store('channel', interaction.channel.id)
            await interaction.user.voice.channel.connect(cls=LavalinkVoiceClient)
        elif int(player.channel_id) != interaction.user.voice.channel.id:
            return await interaction.followup.send('<:tickNo:697759586538749982> You need to be in my voice channel.')

        msg = await interaction.followup.send("<a:loading:697759686509985814> Starting your Spotify liked songs..")
        
        for track_info in liked_songs['items']:
            track_url = track_info['track']['external_urls']['spotify']
            results = await self.bot.lavalink.get_tracks(track_url, check_local=True)
            
            if results.load_type == 'PLAYLIST_LOADED':
                tracks = results.tracks
                for track in tracks:
                    player.add(requester=interaction.user.id, track=track)
            else:
                track = results.tracks[0]
                player.add(requester=interaction.user.id, track=track)

        player.store('channel', interaction.channel.id)
        if not player.is_playing:
            await player.play()
        return await msg.edit(content="<:tickYes:697759553626046546> Spotify liked songs queued!")

    @app_commands.command(name="playlist")
    @app_commands.describe(playlist="The playlist you want to play.")
    @app_commands.checks.cooldown(1, 5)
    async def spotify_playlist(self, interaction: discord.Interaction, playlist: str = None):
        """Choose a playlist you have created, and start playing in a vc."""
        await interaction.response.defer(thinking=True)
        data = await self.db.find_one({"_id": interaction.user.id})
        if data is None:
            return await interaction.followup.send(content="You do not have a Spotify account connected! If you would like to connect yours, please use the command `/spotify connect`! <3")
        else:
            if playlist is not None:
                player = self.bot.lavalink.player_manager.create(interaction.guild.id, endpoint="us")

                if not interaction.user.voice or not interaction.user.voice.channel:
                    return await interaction.followup.send('<:tickNo:697759586538749982> Join a voice channel first.')

                if not player.is_connected:
                    permissions = interaction.user.voice.channel.permissions_for(interaction.guild.me)
                    if not permissions.connect or not permissions.speak:
                        return await interaction.followup.send('<:tickNo:697759586538749982> I need the `CONNECT` and `SPEAK` permissions.')

                    player.store('channel', interaction.channel.id)
                    await interaction.user.voice.channel.connect(cls=LavalinkVoiceClient)

                results = await self.bot.lavalink.get_tracks(playlist, check_local=True)

                if results.load_type == lavalink.LoadType.PLAYLIST and results.tracks:
                    for track in results.tracks:
                        player.add(requester=interaction.user.id, track=track)
                    
                    if not player.is_playing:
                        await player.play()
                    
                    return await interaction.followup.send(content=f"<:tickYes:697759553626046546> Started your playlist!")
                elif results.tracks:
                    track = results.tracks[0]
                    player.add(requester=interaction.user.id, track=track)      
                    
                    if not player.is_playing:
                        await player.play()
                    
                    return await interaction.followup.send(content=f"Enqueued **{track.title}**!")
                else:
                    return await interaction.followup.send(content=f"The playlist is empty.")
            else:
                playlists = await self.get_playlists(interaction)
                if playlists == "Failed":
                    return await interaction.followup.send(content="I failed to get your playlists...", ephemeral=True)
                else:
                    number = 1
                    msg = ""
                    for p in playlists['items']:
                        name = p['name']
                        msg += f"`{number}.` **{name}**\n"
                        number += 1
                    e = discord.Embed(colour=discord.Colour.teal(), description=msg)
                    return await interaction.followup.send(embed=e, ephemeral=True)

    @spotify_connect.error
    @spotify_disconnect.error
    @spotify_info.error
    @spotify_liked.error
    @spotify_playlist.error
    async def on_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        await self.bot.log_information("error", interaction, error)
        try:
            return await interaction.response.send_message("An error has occurred and has been logged, please try again!", ephemeral=True)
        except discord.InteractionResponded:
            return await interaction.followup.send(content="An error has occurred and has been logged, please try again!", embed=None, view=None)

    @spotify_playlist.autocomplete('playlist')
    async def playlist_auto(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        data = await self.db.find_one({"_id": interaction.user.id})
        if data != None:
            new_list = []
            playlists = await self.get_playlists(interaction)
            for playlist in playlists['items']:
                name = playlist['name']
                url = playlist['external_urls']['spotify']
                new_list.append({"name": name, "url": url})
            return [
                app_commands.Choice(name=pl['name'], value=pl['url'])
                for pl in new_list if current.lower() in str(pl['name']).lower()
            ]
        else:
            return [
                app_commands.Choice(
                    name="No account or playlists found.",
                    value="Not set up."
                )
            ]

    async def get_current_user(self, interaction: discord.Interaction):
        token = await self.get_access_token(interaction)
        if token != "Account not setup.":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
            url = "https://api.spotify.com/v1/me/"
            async with self.bot.session.get(url, headers=headers) as session:
                try:
                    json = await session.json()
                    return json
                except:
                    return "Failed"

    async def get_playlists(self, interaction: discord.Interaction):
        token = await self.get_access_token(interaction)
        if token != "Account not setup.":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
            url = "https://api.spotify.com/v1/me/playlists"
            async with self.bot.session.get(url, headers=headers) as session:
                try:
                    json = await session.json()
                    if json['href'] != None:
                        return json
                except:
                    return "Failed"
        else:
            return "Account not setup."

    async def get_liked_songs(self, interaction: discord.Interaction):
        token = await self.get_access_token(interaction)
        if token == "Account not setup.":
            return "Account not setup."

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        url = "https://api.spotify.com/v1/me/tracks"
        
        # Initialize an empty list to store liked songs
        liked_songs = []
        
        while True:
            async with self.bot.session.get(url, headers=headers) as session:
                try:
                    json = await session.json()
                    if json.get('items'):
                        # Add the items to the list
                        liked_songs.extend(json['items'])

                        # Check if there are more items to fetch
                        if json.get('next'):
                            url = json['next']
                        else:
                            break  # No more items to fetch, exit the loop
                    else:
                        return "Failed"
                except:
                    return "Failed"

        return {"items": liked_songs}

    async def get_access_token(self, interaction: discord.Interaction):
        oauth_data = await self.db.find_one({"_id": interaction.user.id})
        if oauth_data is None:
            return "Account not setup."

        if (
            oauth_data['oauthData']['access_token']
            and not oauth_data['oauthData']["expires_at"] - int(time.time()) < 60
        ):
            return oauth_data['oauthData']['access_token']
        else:
            auth_header = base64.b64encode(
                (
                    f"{self.bot.config['spotify']['id']}:{self.bot.config['spotify']['secret']}"
                ).encode("ascii")
            )
            headers = {
                "Authorization": f"Basic {auth_header.decode('ascii')}",
                "grant_type": "refresh_token",
                "refresh_token": oauth_data['oauthData']['refresh_token'],
            }
            data = {"grant_type": "refresh_token", "refresh_token": oauth_data['oauthData']['refresh_token']}
            async with self.bot.session.post(
                self.bot.config['spotify']['token_url'], data=data, headers=headers
            ) as session:
                json = await session.json()
                oauth_data['oauthData']['access_token'] = json['access_token']
                oauth_data['oauthData']['expires_at'] = int(time.time()) + json["expires_in"]
                await self.db.update_one({"_id": interaction.user.id}, {"$set": oauth_data})
                return json['access_token']

async def setup(bot: commands.AutoShardedBot):
    await bot.add_cog(Spotify(bot))
import re
import math
import discord
import requests
import lavalink
import datetime
import asyncio
from utils import formats
from typing import Optional
from aiohttp import request
from discord.ext import commands
from lavalink.filters import LowPass
from lavalink.server import LoadType
from discord import app_commands
from utils.LavalinkVoiceClient import LavalinkVoiceClient
from buttons.QueueMessage import QueueButtons
from buttons.TrackStartEvent import TrackStartEventButtons
from buttons.NowPlaying import NowPlaying

from requests_oauthlib import OAuth2Session
from requests.auth import HTTPBasicAuth

url_rx = re.compile(r'https?://(?:www\.)?.+')


class Music(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.spotify_data = self.bot.db.spotifyOauth
        if not hasattr(bot, 'lavalink'):
            bot.lavalink = lavalink.Client(bot.user.id)
            # Host, Port, Password, Region, Name
            bot.lavalink.add_node(
                'localhost',
                9999,
                'youshallnotpass',
                'us',
                'default-node'
            )

        bot.lavalink.add_event_hooks(self)

    async def query_auto(self, interaction: discord.Interaction, current: str):
        await asyncio.sleep(0.3)
        if url_rx.match(current):
            return [app_commands.Choice(name=current, value=current)]
        elif current.startswith(('artist:')):
            return [app_commands.Choice(name=current, value=current)]
        else:
            current = f'spsearch:{current}'
            try:
                results = await self.bot.lavalink.get_tracks(current, check_local=True)
            except lavalink.errors.LoadError:
                return [app_commands.Choice(name="Nothing found..", value="Nothing found..")]
            if not results.tracks:
                return [app_commands.Choice(name="Nothing found..", value="Nothing found..")]
            else:
                return [
                    app_commands.Choice(
                        name=f"{track.author} - {track.title}", value=track.uri)
                    for track in results.tracks
                ][0:5]

    @app_commands.command(name="play", description="Searches and plays a song from a given query.")
    @app_commands.autocomplete(query=query_auto)
    async def play(self, interaction: discord.Interaction, query: str):
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            try:
                player = self.bot.lavalink.player_manager.players.get(
                    interaction.guild.id)
                query = query.strip('<>')
                e = discord.Embed(color=discord.Colour.teal())
                if not url_rx.match(query) and not query.startswith(('artist:')):
                    query = f'spsearch:{query}'
                results = await self.bot.lavalink.get_tracks(query, check_local=True)
                if not results or not results.tracks:
                    try:
                        return await interaction.response.send_message('Nothing found.')
                    except:
                        return await interaction.followup.send('Nothing found.')
                if results.load_type == LoadType.PLAYLIST:
                    tracks = results.tracks
                    for track in tracks:
                        player.add(requester=interaction.user.id, track=track)
                    e.title = "Playlist Enqueued!"
                    e.description = f"{results.playlist_info.name} with {len(tracks)} tracks."
                    try:
                        await interaction.response.send_message(embed=e, ephemeral=True)
                    except:
                        await interaction.followup.send(embed=e)
                else:
                    track = results.tracks[0]
                    player.add(requester=interaction.user.id, track=track)
                    if player.queue:
                        e.title = "Track Enqueued!"
                        e.description = f"{track.title}\n{track.uri}"
                        try:
                            await interaction.response.send_message(embed=e, ephemeral=True)
                        except:
                            await interaction.followup.send(embed=e)
                player.store('channel', interaction.channel.id)
                if not player.is_playing:
                    await player.play()
            except lavalink.errors.LoadError:
                try:
                    return await interaction.response.send_message('Spotify API did not return a valid response!')
                except:
                    return await interaction.followup.send('Spotify API did not return a valid response!')

    @app_commands.command(name="seek")
    @app_commands.describe(seconds="The amount of seconds you want to seek.")
    async def seek(self, interaction: discord.Interaction, seconds: int):
        """Seeks to a given position in a track."""
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            player = self.bot.lavalink.player_manager.players.get(
                interaction.guild.id)
            if player.is_playing:
                track_time = max(0, player.position + (seconds * 1000))
                await player.seek(track_time)
                return await interaction.response.send_message(
                    content=f'Moved track to **{lavalink.utils.format_time(track_time)}**',
                    ephemeral=True
                )
            else:
                return await interaction.response.send_message(
                    content="Nothing playing.",
                    ephemeral=True
                )

    @app_commands.command(name="skip")
    async def skip(self, interaction: discord.Interaction):
        """Skips the current song."""
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            player = self.bot.lavalink.player_manager.players.get(
                interaction.guild.id)
            if player.is_playing:
                await player.skip()
                return await interaction.response.send_message(
                    content="Skipped.",
                    ephemeral=True
                )
            else:
                return await interaction.response.send_message(
                    content="Nothing playing.",
                    ephemeral=True
                )

    @app_commands.command(name="stop")
    async def stop(self, interaction: discord.Interaction):
        """Stops the current queue and clears it."""
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            player = self.bot.lavalink.player_manager.players.get(
                interaction.guild.id)
            if player.is_playing:
                player.queue.clear()
                await player.stop()
                return await interaction.response.send_message(
                    content="Stopped the player and cleared the queue.",
                    ephemeral=True
                )
            else:
                return await interaction.response.send_message(
                    content="Nothing playing.",
                    ephemeral=True
                )

    @app_commands.command(name="now", description="Shows information on the current song playing.")
    async def now(self, interaction: discord.Interaction):
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            player = self.bot.lavalink.player_manager.players.get(interaction.guild.id)
            if player.current and player.is_playing:
                arrow = await self.draw_time(player)
                position = lavalink.utils.format_time(player.position)

                if player.current.stream:
                    duration = '🔴 LIVE'
                else:
                    duration = lavalink.utils.format_time(player.current.duration)

                e = discord.Embed(colour=discord.Colour.teal(), title="Now Playing:")
                e.description = f"**[{player.current.title} - {player.current.author}]({player.current.uri})**\n{arrow} `[{position}/{duration}]`\n*Requested By: <@!{player.current.requester}>*"
                e.set_thumbnail(url=player.current.artwork_url)
                return await interaction.response.send_message(embed=e, view=NowPlaying(self.bot, player.guild_id))
            else:
                return await interaction.response.send_message(content="Nothing playing.")

    async def draw_time(self, player: lavalink.DefaultPlayer):
        paused = player.paused
        pos = player.position
        dur = player.current.duration
        sections = 15  # Adjust the number of sections as needed
        loc_time = round((pos / dur) * sections)
        bar_filled = '▬'
        bar_empty = '─'
        seek = '🔘'
        if paused:
            msg = '⏸ '
        else:
            msg = '▶ '
        for i in range(sections):
            if i == loc_time:
                msg += seek
            else:
                if i < loc_time:
                    msg += bar_filled
                else:
                    msg += bar_empty
        msg += f' [{lavalink.utils.format_time(pos)}/{lavalink.utils.format_time(dur)}]'
        return msg

    @app_commands.command(name="queue")
    @app_commands.describe(page="The page you want to see.")
    async def queue(self, interaction: discord.Interaction, page: int = 1):
        """Shows the current queue."""
        await interaction.response.defer(thinking=True)
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            player = self.bot.lavalink.player_manager.get(
                interaction.guild.id)
            if player.queue:
                itemsPerPage = 10
                pages = math.ceil(len(player.queue) / itemsPerPage)
                start = (page - 1) * itemsPerPage
                end = start + itemsPerPage
                queueList = ''
                queueDur = 0
                for index, track in enumerate(player.queue[start:end], start=start):
                    queueList += f'`{index+1}.` {track.title}\n'
                    queueDur += track.duration
                embed = discord.Embed(colour=0x93B1B4,
                                      description=f'{queueList}')
                queueDur = lavalink.utils.format_time(queueDur)
                embed.set_footer(
                    text=f'Viewing page {page}/{pages} | Queue Duration: {queueDur} | Tracks: {len(player.queue)}')
                msg = await interaction.followup.send(embed=embed)
                return await msg.edit(view=QueueButtons(self.bot, msg, interaction.guild.id, page))
            else:
                return await interaction.followup.send(content="Nothing playing.")

    @app_commands.command(name="pause")
    async def pause(self, interaction: discord.Interaction):
        """Pauses or resumes the current player."""
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            player = self.bot.lavalink.player_manager.get(
                interaction.guild.id)
            if player.is_playing:
                if player.paused:
                    await player.set_pause(False)
                    return await interaction.response.send_message(
                        content="Resumed.",
                        ephemeral=True
                    )
                else:
                    await player.set_pause(True)
                    return await interaction.response.send_message(
                        content="Paused.",
                        ephemeral=True
                    )
            else:
                return await interaction.response.send_message(
                    content="Nothing playing.",
                    ephemeral=True
                )

    @app_commands.command(name="volume")
    @app_commands.describe(volume="The volume you want to set.")
    async def volume(self, interaction: discord.Interaction, volume: app_commands.Range[int, 1, 100] = None):
        """Changes or shows the current players volume."""
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            player = self.bot.lavalink.player_manager.get(
                interaction.guild.id)
            if player.is_playing:
                if volume is None:
                    return await interaction.response.send_message(
                        content=f'🔈 | {player.volume}%',
                        ephemeral=True
                    )
                await player.set_volume(volume)
                return await interaction.response.send_message(
                    content=f'🔈 | Set to {player.volume}%',
                    ephemeral=True
                )
            else:
                return await interaction.response.send_message(
                    content="Nothing playing.",
                    ephemeral=True
                )

    @app_commands.command(name="shuffle")
    async def shuffle(self, interaction: discord.Interaction):
        """Enables or disabled the players shuffle."""
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            player = self.bot.lavalink.player_manager.get(
                interaction.guild.id)
            if player.is_playing:
                player.shuffle = not player.shuffle
                return await interaction.response.send_message(
                    content='🔀 | Shuffle ' +
                    ('enabled' if player.shuffle else 'disabled'),
                    ephemeral=True
                )
            else:
                return await interaction.response.send_message(
                    content="Nothing playing.",
                    ephemeral=True
                )

    @app_commands.command(name="disconnect")
    async def disconnect(self, interaction: discord.Interaction):
        """Disconnect the bot from the voice channel."""
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            player = self.bot.lavalink.player_manager.get(
                interaction.guild.id)
            if not interaction.guild.voice_client:
                return await interaction.response.send_message(
                    content="Not connected.",
                    ephemeral=True
                )
            if not interaction.user.voice or (player.is_connected and interaction.user.voice.channel.id != int(player.channel_id)):
                return await interaction.response.send_message(
                    content="You're not in my voice channel!",
                    ephemeral=True
                )
            player.queue.clear()
            await player.stop()
            await interaction.guild.voice_client.disconnect(force=True)
            return await interaction.response.send_message(
                content="*⃣ | Disconnected.",
                ephemeral=True
            )

    # @app_commands.command(name="lowpass")
    # @app_commands.describe(strength="The strength of the lowpass filter.")
    # async def lowpass(self, interaction: discord.Interaction, strength: float):
    #     """Sets the strength of the low pass filter."""
    #     player = self.bot.lavalink.player_manager.get(interaction.guild.id)

    #     strength = max(0.0, strength)
    #     strength = min(100, strength)

    #     if strength == 0.0:
    #         await player.remove_filter('lowpass')
    #         return await interaction.response.send_message('Disabled **Low Pass Filter**', ephemeral=True)

    #     low_pass = LowPass()
    #     low_pass.update(smoothing=strength)
    #     await player.set_filter(low_pass)

    #     return await interaction.response.send_message(f'Set **Low Pass Filter** strength to {strength}.', ephemeral=True)

    @app_commands.command(name="autoplay")
    async def autoplay(self, interaction: discord.Interaction):
        """Enables or disables ther autoplay feature."""
        inVoice = await self.ensure_voice(interaction)
        if inVoice:
            player = self.bot.lavalink.player_manager.get(interaction.guild.id)
            autoplay = player.fetch('autoplay')
            if not autoplay:
                player.store('autoplay', True)
                if not player.queue:
                    await interaction.response.send_message('Autoplay has been enabled!', ephemeral=True)
                    
                    api_token = await self.get_spotify_token('bf476164d2c84922b32e5f0af2a01f2d', 'bb4f8d3e303741fe95f8668f70098e20')
                    track_id, artist_id = await self.get_track_and_artist_ids(api_token, player.current.title, player.current.author)
                    artist_genres = await self.get_artist_genres(api_token, artist_id)
                    seed_genre = artist_genres[0] if artist_genres else None
                    recommendations = await self.get_recommendations(api_token, track_id, artist_id, seed_genre)

                    query = f"{recommendations[0]['artists'][0]['name']} - {recommendations[0]['name']}"
                    results = await player.node.get_tracks(f'spsearch:{query}')
                    track = results.tracks[0]
                    player.add(track=track, requester=interaction.guild.me.id)
                else:
                    return await interaction.response.send_message('Autoplay has been enabled!', ephemeral=True)
            else:
                player.store('autoplay', False)
                return await interaction.response.send_message('Autoplay has been disabled!', ephemeral=True)

    async def fetch_lyrics_from_musixmatch(self, interaction, song_title, artist_name):
        endpoint = 'matcher.lyrics.get'
        params = {
            'q_track': song_title,
            'q_artist': artist_name,
            'apikey': '35538fb48b771bd500c551b681406d29',
        }

        response = requests.get(f'https://api.musixmatch.com/ws/1.1/{endpoint}', params=params)
        data = response.json()

        if response.status_code == 200 and data['message']['header']['status_code'] == 200:
            lyrics = data['message']['body']['lyrics']['lyrics_body']

            # Remove the disclaimer from the lyrics
            lyrics = lyrics.replace('** This Lyrics is NOT for Commercial use **', '').strip()

            return lyrics if lyrics else 'Lyrics not available.'
        else:
            return 'Failed to fetch lyrics. Please try again later.'

    @app_commands.command(name="lyrics")
    async def lyrics(self, interaction: discord.Interaction):
        """Fetch the lyrics for the current song that is playing."""
        await interaction.response.defer()

        in_voice = await self.ensure_voice(interaction)
        if in_voice:
            player = self.bot.lavalink.player_manager.get(interaction.guild.id)
            if not player.current or not player.is_playing:
                return await interaction.followup.send("Nothing is playing at the moment, play a song and try again!")

            current_song = player.current.title
            current_artist = player.current.author

            lyrics = await self.fetch_lyrics_from_musixmatch(interaction, current_song, current_artist)

            e = discord.Embed(colour=discord.Colour.teal(), title=f"Lyrics for {current_song} by {current_artist}")

            if lyrics != 'Lyrics not available.':
                e.description = lyrics
            else:
                e.description = "No lyrics found for this song."

            e.set_footer(icon_url=interaction.user.display_avatar, text=f"Requested by: {interaction.user.display_name}")
            e.timestamp = datetime.datetime.now()

            await interaction.followup.send(embed=e)

    @app_commands.command(name="stats")
    async def stats(self, interaction: discord.Interaction, user: Optional[discord.Member]):
        """Shows music stats for a user."""
        await interaction.response.defer(thinking=True)

        if not user:
            user = interaction.user

        data = await self.bot.db.music_stats.find_one({"_id": user.id})
        
        if data:
            e = discord.Embed(colour=discord.Colour.teal())
            e.set_author(name=f"{user.display_name} | Music Stats")
            e.set_thumbnail(url=user.display_avatar)
            e.add_field(name="Songs Played", value=data['stats'].get('songsPlayed', 0), inline=False)
            e.add_field(name="Duration Listened", value=await formats.format_duration(data['stats'].get('timeListened', 0)), inline=False)
            e.timestamp = datetime.datetime.now()
            return await interaction.followup.send(embed=e)
        else:
            return await interaction.followup.send(f"{user.display_name} hasn't listened to any music yet!")

    @autoplay.error
    # @lowpass.error
    @disconnect.error
    @shuffle.error
    @volume.error
    @pause.error
    @queue.error
    @now.error
    @stop.error
    @skip.error
    @seek.error
    @play.error
    async def on_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        await self.bot.log_information("error", interaction, error)
        try:
            return await interaction.response.send_message("An error has occurred and has been logged, please try again!", ephemeral=True)
        except discord.InteractionResponded:
            return await interaction.followup.send(content="An error has occurred and has been logged, please try again!", embed=None, view=None)

    @lavalink.listener(lavalink.events.WebSocketClosedEvent)
    async def on_websocket_closed(self, event: lavalink.events.WebSocketClosedEvent):
        if event.code == 4014:
            await self.delete_npMsg(event)
            event.player.queue.clear()
            await event.player.stop()
            guild = self.bot.get_guild(event.player.guild_id)
            if guild.voice_client:
                await guild.voice_client.disconnect(force=True)
            await self.bot.lavalink.player_manager.destroy(event.player.guild_id)

    @lavalink.listener(lavalink.events.QueueEndEvent)
    async def on_queue_end(self, event: lavalink.events.QueueEndEvent):
        autoplay = event.player.fetch('autoplay')
        await self.delete_npMsg(event)
        if not autoplay:
            guild_id = event.player.guild_id
            guild = self.bot.get_guild(guild_id)
            await guild.voice_client.disconnect(force=True)

    @lavalink.listener(lavalink.events.TrackStartEvent)
    async def on_track_start(self, event: lavalink.events.TrackStartEvent):
        await self.send_controller(event)

        data = await self.bot.db.music_stats.find_one({"_id": event.track.requester})
        if data is None:
            return await self.bot.db.music_stats.insert_one({"_id": event.track.requester, "stats": {"songsPlayed": 1, "timeListened": 0}})
        else:
            data['stats']['songsPlayed'] += 1

        return await self.bot.db.music_stats.update_one({"_id": event.track.requester}, {"$set": {"stats": data['stats']}})

    @lavalink.listener(lavalink.events.TrackEndEvent)
    async def on_track_end(self, event: lavalink.events.TrackEndEvent):
        autoplay = event.player.fetch('autoplay')
        if autoplay:
            guild = self.bot.get_guild(event.player.guild_id)
            player = self.bot.lavalink.player_manager.get(guild.id)
            api_token = await self.get_spotify_token('bf476164d2c84922b32e5f0af2a01f2d', 'bb4f8d3e303741fe95f8668f70098e20')
            track_id, artist_id = await self.get_track_and_artist_ids(api_token, event.track.title, event.track.author)
            artist_genres = await self.get_artist_genres(api_token, artist_id)
            seed_genre = artist_genres[0] if artist_genres else None
            recommendations = await self.get_recommendations(api_token, track_id, artist_id, seed_genre)

            query = f"{recommendations[0]['artists'][0]['name']} - {recommendations[0]['name']}"
            results = await player.node.get_tracks(f'spsearch:{query}')
            track = results.tracks[0]
            player.add(track=track, requester=guild.me.id)

    async def get_spotify_token(self, client_id, client_secret):
        url = 'https://accounts.spotify.com/api/token'
        data = {'grant_type': 'client_credentials'}
        response = requests.post(url, data=data, auth=(client_id, client_secret))
        token = response.json()['access_token']
        return token

    async def get_track_and_artist_ids(self, api_token, title, artist):
        url = 'https://api.spotify.com/v1/search'
        headers = {'Authorization': f'Bearer {api_token}'}
        params = {
            'q': f'track:{title} artist:{artist}',
            'type': 'track',
            'limit': 1,
        }
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        track_id = data['tracks']['items'][0]['id']
        artist_id = data['tracks']['items'][0]['artists'][0]['id']
        return track_id, artist_id

    async def get_artist_genres(self, api_token, artist_id):
        url = f'https://api.spotify.com/v1/artists/{artist_id}'
        headers = {'Authorization': f'Bearer {api_token}'}
        response = requests.get(url, headers=headers)
        artist_data = response.json()
        genres = artist_data['genres']
        return genres

    async def get_recommendations(self, api_token, seed_tracks, seed_artists, seed_genres):
        url = 'https://api.spotify.com/v1/recommendations'
        headers = {'Authorization': f'Bearer {api_token}'}
        params = {
            'seed_tracks': seed_tracks,
            'seed_artists': seed_artists,
            'seed_genres': seed_genres,
        }
        response = requests.get(url, headers=headers, params=params)
        recommendations = response.json()['tracks']
        return recommendations

    async def autoplay_similar_songs(self, guild, player, current_track):
        api_token = await self.get_spotify_token('bf476164d2c84922b32e5f0af2a01f2d', 'bb4f8d3e303741fe95f8668f70098e20')
        track_id, artist_id = await self.get_track_and_artist_ids(api_token, current_track.title, current_track.artist)
        artist_genres = await self.get_artist_genres(api_token, artist_id)
        seed_genre = artist_genres[0] if artist_genres else None
        recommendations = await self.get_recommendations(api_token, track_id, artist_id, seed_genre)

        query = f"{recommendations[0]['artists'][0]['name']} - {recommendations[0]['name']}"
        results = await player.node.get_tracks(f'spsearch:{query}')
        track = results.tracks[0]
        player.add(track=track, requester=guild.me.id)

        channel = guild.get_channel(player.fetch('channel'))
        if channel:
            await channel.send('AutoPlay Queued: {} by {}'.format(track.title, track.author))

    async def delete_npMsg(self, event):
        if event.player.fetch('npMsg') != None:
            try:
                channel = self.bot.get_channel(event.player.fetch('channel'))
                msg = await channel.fetch_message(event.player.fetch('npMsg'))
                await msg.delete()
            except:
                pass

    async def send_controller(self, event):
        await self.delete_npMsg(event)
        if event.player.fetch('channel'):
            if event.track.stream:
                duration = '🔴 LIVE'
            else:
                duration = lavalink.utils.format_time(event.track.duration)
            fmt = f'{event.track.title} - {event.track.author}'
            song = f'**[{fmt}]({event.track.uri})**\n*Duration: {duration}*\n*Requested By: <@!{event.track.requester}>*'
            embed = discord.Embed(
                color=discord.Colour.teal(), title='Now Playing', description=song)
            embed.set_thumbnail(url=event.track.artwork_url)
            ch = self.bot.get_channel(event.player.fetch('channel'))
            npMsg = await ch.send(embed=embed, view=TrackStartEventButtons(self.bot, event.player.guild_id))
            event.player.store('npMsg', npMsg.id)

    async def ensure_voice(self, interaction: discord.Interaction):
        try:
            player = self.bot.lavalink.player_manager.create(
                interaction.guild.id)
            should_connect = interaction.command.name in ('play', 'playlist')
            if not interaction.user.voice or not interaction.user.voice.channel:
                return await interaction.response.send_message(
                    content='Join a voicechannel first.',
                    ephemeral=True
                )

            v_client = interaction.guild.voice_client
            if not v_client:
                if not should_connect:
                    return await interaction.response.send_message(
                        content="Not connected.",
                        ephemeral=True
                    )

                permissions = interaction.user.voice.channel.permissions_for(
                    interaction.guild.me)
                if not permissions.connect or not permissions.speak:
                    return await interaction.response.send_message(
                        content="I need the `CONNECT` and `SPEAK` permissions.",
                        ephemeral=True
                    )

                player.store('channel', interaction.channel.id)
                await interaction.user.voice.channel.connect(cls=LavalinkVoiceClient, self_deaf=True)
                return True
            else:
                if v_client.channel.id != interaction.user.voice.channel.id:
                    return await interaction.response.send_message(
                        content="You need to be in my voice channel.",
                        ephemeral=True
                    )
                else:
                    return True
        except Exception as e:
            print(f"[Music] Error during ensure_voice: {e}")

    def cog_unload(self):
        """ Cog unload handler. This removes any event hooks that were registered. """
        self.bot.lavalink._event_hooks.clear()


async def setup(bot: commands.AutoShardedBot):
    await bot.add_cog(Music(bot))

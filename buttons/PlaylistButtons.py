import discord
import lavalink
from aiohttp import request
from discord.ext import commands
from modules.music import LavalinkVoiceClient

class ConfirmationView(discord.ui.View):
    def __init__(self, playlist_view, message: discord.Message):
        super().__init__(timeout=30.0)
        self.playlist_view = playlist_view

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm_delete")
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        playlist = self.playlist_view.playlists[self.playlist_view.index]['name']
        playlist_to_delete = next((p for p in self.playlist_view.playlists if p['name'].lower() == playlist.lower()), None)

        if not playlist_to_delete:
            return await interaction.followup.send(f"Playlist '{playlist}' not found. Check the spelling and try again.")

        self.playlist_view.playlists.remove(playlist_to_delete)
        await self.playlist_view.user_playlists.update_one(
            {"_id": interaction.user.id},
            {"$set": {"playlists": self.playlist_view.playlists}},
        )
        await interaction.response.edit_message(content=f"Playlist **{playlist}** has been deleted.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel_delete")
    async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Deletion canceled.", view=None)

class PlaylistButtons(discord.ui.View):
    def __init__(self, bot: commands.AutoShardedBot, message: discord.Message, playlists: list, index: int):
        super().__init__(timeout=20.0)
        self.bot = bot
        self.playlists = playlists
        self.index = index
        self.message = message

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def update_display(self, interaction: discord.Interaction):
        current_playlist = self.playlists[self.index]
        playlist_type = self.get_playlist_type(current_playlist)
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

        await interaction.response.edit_message(embed=e)

    def get_playlist_type(self, playlist):
        if "creator_id" in playlist:
            return "Collaborative"
        else:
            return "Personal"

    @discord.ui.button(emoji="<:previous:1192214541443006574>", style=discord.ButtonStyle.gray)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.playlists)
        await self.update_display(interaction)

    @discord.ui.button(emoji="<:play:1010305312227606610>", style=discord.ButtonStyle.success)
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            for song in self.playlists[self.index]['songs']:
                results = await self.bot.lavalink.get_tracks(song, check_local=True)
                if not results or not results.tracks:
                    pass
                else:
                    track = results.tracks[0]
                    player.add(requester=interaction.user.id, track=track)

            player.store('channel', interaction.channel.id)
            if not player.is_playing:
                await player.play()

            return await interaction.response.edit_message(content=f"Added **{self.playlists[self.index]['name']}** to the queue!", embed=None, view=None)
        except lavalink.errors.LoadError:
            return await interaction.response.edit_message(content='Spotify API did not return a valid response!')

    @discord.ui.button(emoji="<:queue:1011747675491811458>", style=discord.ButtonStyle.grey)
    async def list_songs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await interaction.response.defer(thinking=True)
        playlist_name = self.get_current_playlist()["name"]
        songs = self.get_current_playlist().get("songs", [])
        songs_index = 0

        if not songs:
            return await interaction.followup.send(content="Playlist contains 0 songs.", view=None, embed=None)
        else:
            results = await self.bot.lavalink.get_tracks(songs[0], check_local=True)
            song_info = results.tracks[0]
            duration = '🔴 LIVE' if song_info.stream else lavalink.utils.format_time(song_info.duration)
            fmt = f'{song_info.title} - {song_info.author}'
            song = f'**[{fmt}]({song_info.uri})**\n*Duration: {duration}*'
            embed = discord.Embed(color=discord.Colour.teal(), title=f"Playlist song 1/{len(songs)}", description=song)
            embed.set_thumbnail(url=song_info.artwork_url)

            msg = await interaction.followup.send(embed=embed)
            return await msg.edit(view=PlaylistSongsButtons(self.bot, msg, playlist_name, songs, songs_index))


    @discord.ui.button(emoji="<:trashcan:1192213838880317501>", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        playlist_name = self.get_current_playlist()["name"]
        return await interaction.response.send_message(content="Being reworked since addition of collaborative playlists.", embed=None, view=None)

    @discord.ui.button(emoji="<:next:1192214542571290666>", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.playlists)
        await self.update_display(interaction)

    def get_current_playlist(self):
        return self.playlists[self.index]

class PlaylistSongsButtons(discord.ui.View):
    def __init__(self, bot: commands.AutoShardedBot, message: discord.Message, playlist_name: str, songs: list, index: int) -> None:
        super().__init__(timeout=20.0)
        self.bot = bot
        self.playlist_name = playlist_name
        self.songs = songs
        self.index = index
        self.song_info = None
        self.user_playlists = self.bot.db.playlists
        self.message = message

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def update_display(self, interaction: discord.Interaction):
        if not 0 <= self.index < len(self.songs):
            return

        results = await self.bot.lavalink.get_tracks(self.songs[self.index], check_local=True)
        self.song_info = results.tracks[0]
        duration = '🔴 LIVE' if self.song_info.stream else lavalink.utils.format_time(self.song_info.duration)
        fmt = f'{self.song_info.title} - {self.song_info.author}'
        song = f'**[{fmt}]({self.song_info.uri})**\n*Duration: {duration}*'

        embed = discord.Embed(color=discord.Colour.teal(), title=f'Playlist song {self.index+1}/{len(self.songs)}', description=song)
        embed.set_thumbnail(url=self.song_info.artwork_url)

        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.errors.NotFound:
            pass

    @discord.ui.button(emoji="<:previous:1192214541443006574>", style=discord.ButtonStyle.gray)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.songs)
        await self.update_display(interaction)

    @discord.ui.button(emoji="<:trashcan:1192213838880317501>", style=discord.ButtonStyle.red)
    async def delete_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        msg = await interaction.channel.send("<a:loading:697759686509985814> Hold on, let me work my magic...")
        playlist_data = await self.user_playlists.find_one({"_id": interaction.user.id})

        if not playlist_data or not playlist_data['playlists']:
            return await msg.edit(content="You don't have any playlists to delete from. Which is an issue, please report to dev.")

        playlist_to_update = next((p for p in playlist_data['playlists'] if p['name'].lower() == self.playlist_name.lower()), None)

        if not playlist_to_update:
            return await msg.edit(content=f"Playlist **{self.playlist_name}** not found. Which is an issue, please report to dev.")

        if self.song_info['uri'] in playlist_to_update['songs']:
            playlist_to_update['songs'].remove(self.song_info['uri'])
            await self.user_playlists.update_one({"_id": interaction.user.id, "playlists.name": self.playlist_name},
                                                  {"$set": {"playlists.$.songs": playlist_to_update['songs']}})
            return await msg.edit(content=f"Deleted the song **{self.song_info['title']}** from the playlist **{self.playlist_name}**.")
        else:
            return await msg.edit(content=f"Song **{self.song_info['title']}** not found in the playlist **{self.playlist_name}**. Which is an issue, please report to dev.")

    @discord.ui.button(emoji="<:next:1192214542571290666>", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.songs)
        await self.update_display(interaction)

    @discord.ui.button(emoji="<:stop:1010325505179918468>", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class LikedButtons(discord.ui.View):
    def __init__(self, bot: commands.AutoShardedBot, songs: dict, index: int) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.songs = songs
        self.index = index
        self.user_liked = self.bot.db.liked

    async def update_display(self, interaction: discord.Interaction):
        if not 0 <= self.index < len(self.songs):
            return

        song_info = self.songs[self.index]
        duration = '🔴 LIVE' if song_info.stream else lavalink.utils.format_time(song_info.duration)

        embed = discord.Embed(color=discord.Colour.teal())
        embed.add_field(name="Title:", value=song_info.title)
        embed.add_field(name="Duration:", value=duration)
        embed.add_field(name="Link:", value=f"[Click here to open..]({song_info.uri})", inline=False)
        embed.set_thumbnail(url=song_info.artwork_url)

        embed.set_footer(text=f"Showing song {self.index+1} of {len(self.songs)} liked song(s)...")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="<:previous:1192214541443006574>", style=discord.ButtonStyle.gray)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.songs)
        await self.update_display(interaction)

    @discord.ui.button(emoji="<:trashcan:1192213838880317501>", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await self.user_liked.find_one({"_id": interaction.user.id})
        if data and self.songs[self.index].uri in data['songs']:
            await self.user_liked.update_one({"_id": interaction.user.id}, {"$pull": {"songs": self.songs[self.index].uri}})
            await interaction.response.edit_message(content=f"**{self.songs[self.index].title}** has been removed from your liked!", embed=None, view=None)

    @discord.ui.button(emoji="<:next:1192214542571290666>", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.songs)
        await self.update_display(interaction)

    @discord.ui.button(emoji="<:stop:1010325505179918468>", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
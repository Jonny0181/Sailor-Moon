import discord
import lavalink
from aiohttp import request
from discord.ext import commands
from utils.formats import translate

class AddToPlaylist(discord.ui.Select):
    def __init__(self, bot: commands.AutoShardedBot, guild_id, song_link: str, data: dict):
        self.bot = bot
        self.song_link = song_link
        self.user_playlists = self.bot.db.playlists
        options = []

        if data and 'playlists' in data and data['playlists']:
            for playlist in data['playlists']:
                options.append(discord.SelectOption(label=playlist['name']))
        self.setup_options(guild_id, options)

        super().__init__(placeholder="Select a playlist...", max_values=1, min_values=1, options=options)

    async def setup_options(self, guild_id, options):
        options.append(discord.SelectOption(label=await translate(self, guild_id, "createNewPlaylist"), emoji="<:add:1191452405225771168>"))
        options.append(discord.SelectOption(label=await translate(self, guild_id, "cancel"), emoji="<:tickNo:697759586538749982>"))

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        user_id = interaction.user.id

        if choice == "Create new playlist":
            await interaction.response.edit_message(content=await translate(self, interaction.guild.id, "namePlaylist"), view=None)

            response = await self.bot.wait_for("message", check=lambda m: m.author.id == user_id, timeout=60)
            if response:
                playlist_name = response.content

                await self.user_playlists.update_one(
                    {"_id": user_id},
                    {"$push": {"playlists": {"name": playlist_name, "songs": [self.song_link]}}},
                    upsert=True
                )
                return await interaction.channel.send(str(await translate(self, interaction.guild.id, "playlistCreated")).format(playlist_name))
        elif choice == "Cancel":
            return await interaction.response.edit_message(content=await translate(self, interaction.guild.id, "canceling"), view=None)
        else:
            playlist_data = await self.user_playlists.find_one({"_id": user_id, "playlists.name": choice})
            if playlist_data and "songs" in playlist_data['playlists'][0]:
                songs = playlist_data['playlists'][0]['songs']
                if self.song_link in songs:
                    return await interaction.response.edit_message(content=str(await translate(self, interaction.guild.id, "songInPlaylist")).format(choice), view=None)

            await self.user_playlists.update_one(
                {"_id": user_id, "playlists.name": choice},
                {"$push": {"playlists.$.songs": self.song_link}}
            )
            return await interaction.response.edit_message(content=str(await translate(self, interaction.guild.id, "songAddedToPlaylist")).format(choice), view=None)

class AddToPlaylistView(discord.ui.View):
    def __init__(self, bot: commands.AutoShardedBot, guild_id, song_link: str, data: dict, timeout=60):
        super().__init__(timeout=timeout)
        self.add_item(AddToPlaylist(bot, guild_id, song_link, data))

class NowPlaying(discord.ui.View):
    def __init__(self, bot, guild_id) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.user_liked = self.bot.db.liked
        self.user_playlists = self.bot.db.playlists
        self.player = bot.lavalink.player_manager.get(guild_id)

    @discord.ui.button(emoji="<:add:1191452405225771168>", style=discord.ButtonStyle.green)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        data = await self.user_liked.find_one({"_id": interaction.user.id})
        playlists_data = await self.user_playlists.find_one({"_id": interaction.user.id})
        if data is None:
            await self.user_liked.insert_one({"_id": interaction.user.id})
            await self.user_liked.update_one({"_id": interaction.user.id}, {"$set": {"songs": [self.player.current.uri]}})
            return await interaction.followup.send(str(await translate(self, interaction.guild.id, "songAddedToLiked")).format(self.player.current.title), view=AddToPlaylistView(self.bot, interaction.guild.id, self.player.current.uri, playlists_data))
        else:
            if self.player.current.uri in data['songs']:
                return await interaction.followup.send(await translate(self, interaction.guild.id, "songAlreadyLiked"), view=AddToPlaylistView(self.bot, self.player.current.uri, playlists_data))
            else:
                await self.user_liked.update_one({"_id": interaction.user.id}, {"$push": {"songs": self.player.current.uri}})
                return await interaction.followup.send(str(await translate(self, interaction.guild.id, "songAddedToLiked")).format(self.player.current.title), view=AddToPlaylistView(self.bot, self.player.current.uri, playlists_data))

    @discord.ui.button(emoji="<:pause:1010305240672780348>", style=discord.ButtonStyle.gray)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.set_pause(not self.player.paused)
        if self.player.paused:
            title = await translate(self, interaction.guild.id, "paused")
            button.emoji = "<:play:1010305312227606610>"
        else:
            button.emoji = "<:pause:1010305240672780348>"
            title = await translate(self, interaction.guild.id, "nowPlaying")
        e = discord.Embed(colour=discord.Colour.teal(), title=title)
        if self.player.current.stream:
            duration = await translate(self, interaction.guild.id, "live")
        else:
            duration = lavalink.utils.format_time(self.player.current.duration)
        fmt = f'{self.player.current.title} - {self.player.current.author}'
        e.description = str(await translate(self, interaction.guild.id, "nowPlayingDescription")).format(fmt, self.player.current.uri, duration, self.player.current.requester)
        e.set_thumbnail(url=self.player.current.artwork_url)
        return await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(emoji="<:skip:1010321396301299742>", style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.is_playing:
            await self.player.skip()
            return await interaction.response.edit_message(content=await translate(self, interaction.guild.id, "skipped"), embed=None, view=None)
        else:
            return await interaction.response.edit_message(content=await translate(self, interaction.guild.id, "nothingPlaying"), view=None, embed=None)

    @discord.ui.button(emoji="<:shuffle:1033963011657977876>", style=discord.ButtonStyle.grey)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.shuffle = not self.player.shuffle
        return await interaction.response.send_message(content=await translate(self, interaction.guild.id, "shuffleEnabled") if self.player.shuffle else await translate(self, interaction.guild.id, "shuffleDisabled"))

    @discord.ui.button(emoji="<:stop:1010325505179918468>", style=discord.ButtonStyle.red)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.fetch('npMsg') != None:
            try:
                msg = await interaction.channel.fetch_message(self.player.fetch('npMsg'))
                await msg.delete()
            except:
                pass
        self.player.queue.clear()
        await self.player.stop()
        await interaction.response.send_message(content=await translate(self, interaction.guild.id, "stoppedMusic"), ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        e = discord.Embed(
            colour=discord.Colour.red(),
            title="An error has occurred!"
        )
        e.add_field(name="Error", value=error)
        e.set_thumbnail(self.bot.user.avatar)
        try:
            return await interaction.response.send_message(embed=e)
        except:
            print(f"[Now Playing Buttons] Error: {error}")

import discord
import lavalink
from aiohttp import request
from discord.ext import commands

class AddToPlaylist(discord.ui.Select):
    def __init__(self, bot: commands.AutoShardedBot, song_link: str, personal_playlists: dict, collaborative_playlists: dict):
        self.bot = bot
        self.song_link = song_link
        self.user_playlists = self.bot.db.playlists
        self.collaborative_playlists = self.bot.db.collaborative_playlists

        options = []

        if personal_playlists and 'playlists' in personal_playlists and personal_playlists['playlists']:
            for playlist in personal_playlists['playlists']:
                options.append(discord.SelectOption(label=playlist['name'], value=f"personal_{playlist['name']}"))
        
        if collaborative_playlists:
            for collab_playlist in collaborative_playlists:
                options.append(discord.SelectOption(label=f"[Collab] {collab_playlist['name']}", value=f"collab_{collab_playlist['_id']}"))

        options.append(discord.SelectOption(label="Create new playlist", emoji="<:add:1191452405225771168>"))
        options.append(discord.SelectOption(label="Cancel", emoji="<:tickNo:697759586538749982>"))

        super().__init__(placeholder="Select a playlist...", max_values=1, min_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        user_id = interaction.user.id

        if choice == "Create new playlist":
            await interaction.response.edit_message(content="Would you like this to be a collaborative playlist? Yes/No", view=None)

            response = await self.bot.wait_for("message", check=lambda m: m.author.id == user_id, timeout=60)
            if response.content.lower() in ('yes', 'no'):
                if response.content.lower() == 'yes':
                    await interaction.channel.send("Please enter a name for your new playlist.")
                    playlist_name = await self.bot.wait_for("message", check=lambda m: m.author.id == user_id, timeout=60)
                    if " " in playlist_name.content:
                        return await interaction.channel.send("Playlist name cannot contain any spaces, please try again.")
                    else:
                        playlist_id = f"{playlist_name.content}_{user_id}"
                        existing_playlist = await self.collaborative_playlists.find_one({"_id": playlist_id})
                        if existing_playlist:
                            return await interaction.channel.send(f'Playlist **{playlist_name.content}** already exists. Please try again.')
                        else:
                            playlist_data = {
                                "_id": playlist_id,
                                "name": playlist_name.content,
                                "creator_id": interaction.user.id,  # Add creator_id to the playlist data
                                "allowed_users": [interaction.user.id],
                                "songs": [self.song_link]
                            }
                            await self.collaborative_playlists.insert_one(playlist_data)
                            return await interaction.channel.send(f"Playlist **{playlist_name.content}** created and song added!")
                else:
                    await interaction.channel.send("Please enter a name for your new playlist.")
                    playlist_name = await self.bot.wait_for("message", check=lambda m: m.author.id == user_id, timeout=60)
                    if " " in playlist_name.content:
                        return await interaction.channel.send("Playlist name cannot contain any spaces, please try again.")
                    else:
                        await self.user_playlists.update_one(
                            {"_id": user_id},
                            {"$push": {"playlists": {"name": playlist_name.content, "songs": [self.song_link]}}},
                            upsert=True
                        )
                        return await interaction.channel.send(f"Playlist **{playlist_name.content}** created and song added!")
            else:
                return await interaction.channel.send("Invalid response, please try again but reply with only yes or no.")
        elif choice == "Cancel":
            return await interaction.response.edit_message(content="Cancelling..", view=None)
        elif choice.startswith('personal_'):
            playlists = await self.user_playlists.find_one({"_id": interaction.user.id})
            if playlists:
                playlist_name = choice.replace('personal_', '')
                found_personal_playlist = next((playlist for playlist in playlists['playlists'] if playlist['name'] == playlist_name), None)

                if found_personal_playlist and 'songs' in found_personal_playlist:
                    songs = found_personal_playlist['songs']
                    if self.song_link in songs:
                        return await interaction.response.edit_message(content=f"The song is already in the playlist **{playlist_name}**!", view=None)

                await self.user_playlists.update_one(
                    {"_id": interaction.user.id, "playlists.name": playlist_name},
                    {"$push": {"playlists.$.songs": self.song_link}}
                )
                return await interaction.response.edit_message(content=f"Song added to the playlist **{playlist_name}**!", view=None)
        elif choice.startswith('collab_'):
            playlist_name = choice.replace("collab_", "")
            playlist = await self.collaborative_playlists.find_one({"_id": playlist_name})
            
            if playlist and interaction.user.id in playlist["allowed_users"]:
                if "songs" in playlist:
                    if self.song_link in playlist["songs"]:
                        return await interaction.response.edit_message(content=f'The song is already in the playlist **{playlist_name.split("_")[0]}**!', view=None)

                try:
                    result = await self.collaborative_playlists.update_one(
                        {"_id": playlist_name},
                        {"$push": {"songs": self.song_link}}
                    )
                    
                    if result.modified_count > 0:
                        await interaction.response.edit_message(content=f'Song added to playlist **{playlist_name.split("_")[0]}**!', view=None)
                    else:
                        await interaction.response.edit_message(content='Failed to add the song to the playlist. Please try again.', view=None)

                except Exception as e:
                    print(f"Error adding song to collaborative playlist: {e}")
                    await interaction.response.edit_message(content='An error occurred while adding the song to the playlist. Please try again.', view=None)
            else:
                await interaction.response.edit_message(content=f'You are not allowed to manage or the playlist **{playlist_name}** not found.', view=None)

class AddToPlaylistView(discord.ui.View):
    def __init__(self, bot: commands.AutoShardedBot, song_link: str, personal_playlists: dict, collab_playlists: dict, timeout=60):
        super().__init__(timeout=timeout)
        self.add_item(AddToPlaylist(bot, song_link, personal_playlists, collab_playlists))

class TrackStartEventButtons(discord.ui.View):
    def __init__(self, bot, guild_id) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.user_liked = self.bot.db.liked
        self.user_playlists = self.bot.db.playlists
        self.collaborative_playlists = self.bot.db.collaborative_playlists
        self.player = bot.lavalink.player_manager.get(guild_id)

    @discord.ui.button(emoji="<:add:1191452405225771168>", style=discord.ButtonStyle.green)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        data = await self.user_liked.find_one({"_id": interaction.user.id})
        playlists_data = await self.user_playlists.find_one({"_id": interaction.user.id})
        collab_playlists = await self.collaborative_playlists.find({"$or": [{"creator_id": interaction.user.id}, {"allowed_users": interaction.user.id}]}).to_list(length=None)
        view = AddToPlaylistView(self.bot, self.player.current.uri, playlists_data, collab_playlists)
        if data is None:
            await self.user_liked.insert_one({"_id": interaction.user.id})
            await self.user_liked.update_one({"_id": interaction.user.id}, {"$set": {"songs": [self.player.current.uri]}})
            return await interaction.followup.send(f"**{self.player.current.title}** has been added to your liked! Would you like to add it to a playlist?", view=view)
        else:
            if self.player.current.uri in data['songs']:
                return await interaction.followup.send("You have already liked this song! Would you like to add it to a playlist?", view=view)
            else:
                await self.user_liked.update_one({"_id": interaction.user.id}, {"$push": {"songs": self.player.current.uri}})
                return await interaction.followup.send(f"**{self.player.current.title}** has been added to your liked! If you would like to add it to a playlist select one below!", view=view)

    @discord.ui.button(emoji="<:pause:1010305240672780348>", style=discord.ButtonStyle.gray)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.set_pause(not self.player.paused)
        if self.player.paused:
            title = "Paused"
            button.emoji = "<:play:1010305312227606610>"
        else:
            button.emoji = "<:pause:1010305240672780348>"
            title = "Now Playing"
        e = discord.Embed(colour=discord.Colour.teal(), title=title)
        if self.player.current.stream:
            duration = '🔴 LIVE'
        else:
            duration = lavalink.utils.format_time(self.player.current.duration)
        fmt = f'{self.player.current.title} - {self.player.current.author}'
        e.description = f'**[{fmt}]({self.player.current.uri})**\n*Duration: {duration}*\n*Requested By: <@!{self.player.current.requester}>*'
        e.set_thumbnail(url=self.player.current.artwork_url)
        return await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(emoji="<:skip:1010321396301299742>", style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.is_playing:
            await self.player.skip()
        else:
            return await interaction.response.send_message(
                content="Nothing playing.",
                ephemeral=True
            )

    @discord.ui.button(emoji="<:shuffle:1033963011657977876>", style=discord.ButtonStyle.grey)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.shuffle = not self.player.shuffle
        return await interaction.response.send_message(
            content='🔀 | Shuffle ' +
            ('enabled' if self.player.shuffle else 'disabled'),
            ephemeral=True
        )

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
        await interaction.response.send_message(content="⏹️ Stopped music and cleared queue.", ephemeral=True)

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
            self.bot.richConsole.print(
                f"[bold red][TrackStart Event Buttons][/] Error: {error}")

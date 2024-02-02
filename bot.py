import os
import json
import discord
import aiohttp
import subprocess
import asyncio
import datetime
import traceback
from discord.ext import commands
import motor.motor_asyncio as motor

with open("config.json", "r") as config:
    _config = json.load(config)

with open("languages.json", "r") as languages:
    _languages = json.load(languages)

class SailorMoon(commands.AutoShardedBot):
    def __init__(self, **options):
        super().__init__(**options)
        self.config = _config
        self.languages = _languages
        self.session = None
        self.statusIndex = 0
        self.member_join_times = {}

    async def on_ready(self):
        print(f'[Sailor Moon] Connected and logged in.')
        self.session = aiohttp.ClientSession()
        await self.init_db()
        await self.load_modules()
        self.loop.create_task(self.status_loop())

    async def status_loop(self):
        await self.wait_until_ready()

        while not self.is_closed():

            playing = 0
            for player in self.lavalink.player_manager.players:
                player = self.lavalink.player_manager.get(player)
                if player.current is not None:
                    playing += 1

            users = 0
            for guild in self.guilds:
                users += len(guild.members)

            statuses = [
                {"name": "guilds",
                    "value": f"/help | {len(self.guilds)} guilds.."},
                {"name": "music",
                    "value": f"music in {playing} guilds.."},
                {"name": "users", "value": f"/help | {users} users.."}
            ]
            if statuses[self.statusIndex]['name'] in ("guilds", "users"):
                await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(
                    type=discord.ActivityType.watching, name=statuses[self.statusIndex]['value']
                ))
            elif statuses[self.statusIndex]['name'] == "music":
                await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(
                    type=discord.ActivityType.listening, name=statuses[self.statusIndex]['value']
                ))

            await asyncio.sleep(60)
            self.statusIndex += 1
            if self.statusIndex == 3:
                self.statusIndex = 0

    async def init_db(self):
        if _config['database']['enabled'] is not False:
            collection = _config["database"]["collection"]
            self.db = motor.AsyncIOMotorClient(
                _config["database"]["uri"])[collection]
            print(f'[DB] Connected to {collection}!')

    async def load_modules(self):
        modulesLoaded = 0
        modules = [e for e in os.listdir('modules') if e.endswith('.py')]

        for module in modules:
            try:
                await self.load_extension(f'modules.{module[:-3]}')
                modulesLoaded += 1
            except commands.ExtensionAlreadyLoaded:
                pass
            except Exception as e:
                print(f'[Sailor Moon] Err: {e}')
        print(f'[Sailor Moon] Loaded {modulesLoaded} module(s).')

        try:
            await self.load_extension('jishaku')
            print('[Sailor Moon] Loaded Jishaku!')
        except Exception as e:
            print(f'[Sailor Moon] ERR loading Jishaku: {str(e)}')

        print('[Sailor Moon] Attempting to sync application commands...')
        try:
            synced = await self.tree.sync()
        except Exception as e:
            print(f'[Sailor Moon] Err: {e}')
        print(f'[Sailor Moon] Synced {len(synced)} application command(s).')

    #Listening time tracker
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        await asyncio.sleep(1)
        player = self.lavalink.player_manager.players.get(member.guild.id)

        if before.channel != after.channel:
            if after.channel is not None:
                if self.user in after.channel.members:
                    if player and player.is_playing:
                        users = [e for e in after.channel.members if e.id != self.user.id]
                        for user in users:
                            self.member_join_times[user.id] = datetime.datetime.now()
            elif before.channel is not None and after.channel is None:
                if not player and member.id == self.user.id:
                    users = [e for e in before.channel.members if e.id != self.user.id]
                    for user in users:
                        data = await self.db.music_stats.find_one({"_id": user.id})
                        join_time = self.member_join_times.get(user.id)
                        if join_time:
                            elapsed_time = datetime.datetime.now() - join_time
                            if data:
                                data['stats']['timeListened'] += elapsed_time.total_seconds()
                                await self.db.music_stats.update_one({"_id": user.id}, {"$set": {"stats": data['stats']}})
                            else:
                                data = {"_id": user.id, "stats": {"timeListened": elapsed_time.total_seconds(), "songsPlayed": 0}}
                                await self.db.music_stats.insert_one(data)
                elif player and player.is_playing:
                    data = await self.db.music_stats.find_one({"_id": member.id})
                    join_time = self.member_join_times.get(member.id)
                    if join_time:
                        elapsed_time = datetime.datetime.now() - join_time
                        if data:
                            data['stats']['timeListened'] += elapsed_time.total_seconds()
                            return await self.db.music_stats.update_one({"_id": member.id}, {"$set": {"stats": data['stats']}})
                        else:
                            data = {"_id": member.id, "stats": {"timeListened": elapsed_time.total_seconds(), "songsPlayed": 0}}
                            return await self.db.music_stats.insert_one(data)

    async def on_application_command_error(self, interaction: discord.Interaction, error):
        print(error)
        if isinstance(error, discord.errors.MissingPermissions):
            return
        elif isinstance(error, discord.errors.MissingRequiredArgument):
            return
        
        traceback_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        await self.log_error(error, traceback_str)

    async def log_error(self, error, traceback):
        error_message = f"An error occurred while processing the command: {error}"

        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url("https://discord.com/api/webhooks/1202877453081645116/hVP7DKCYpBVgkjizm39Xz5fRn8nYwtNpzuhMaryMJV1pqiF0eyfOJBZOr1xMS2DA0hHb", session=session)
            
            try:
                await webhook.send(error_message, username="Error Bot")
            except discord.errors.HTTPException as e:
                print(f"Error sending to webhook: {e}") 

if __name__ == '__main__':
    # Start the Flask website when the bot script is run
    subprocess.Popen(["python", "website/main.py"])

    # Initialize and run the Discord bot
    bot = SailorMoon(command_prefix=commands.when_mentioned_or(_config.get('prefix')), max_messages=None, intents=discord.Intents.all(), help_command=None)
    bot.run(_config.get('token'))
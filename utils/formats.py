async def translate(self, guild_id, key):
    guild_data = await self.bot.db.settings.find_one({"_id": guild_id})
    language = guild_data.get('language') if guild_data else None

    if language and language in self.bot.languages and key in self.bot.languages[language]:
        return self.bot.languages[language][key]
    elif 'English' in self.bot.languages and key in self.bot.languages['English']:
        return self.bot.languages['English'][key]
    else:
        return f"Translation not found for key: {key}"
    
async def format_duration(seconds):
    # Function to format seconds into a readable duration (hh:mm:ss)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
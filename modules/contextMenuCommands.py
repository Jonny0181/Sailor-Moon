import discord
import datetime
from utils import formats
from discord.ext import commands
from discord import app_commands

class ContextMenus(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot


        # ---------- MUSIC ----------
        @bot.tree.context_menu(name="Music Stats")
        async def music_stats(interaction: discord.Interaction, member: discord.Member):
            await interaction.response.defer(thinking=True)
            data = await self.bot.db.music_stats.find_one({"_id": member.id})
            if data:
                e = discord.Embed(colour=discord.Colour.teal())
                e.set_author(name=f"{member.display_name} | Music Stats")
                e.set_thumbnail(url=member.display_avatar)
                e.add_field(name="Songs Played", value=data['stats'].get('songsPlayed', 0), inline=False)
                e.add_field(name="Duration Listened", value=await formats.format_duration(data['stats'].get('timeListened', 0)), inline=False)
                e.timestamp = datetime.datetime.now()
                return await interaction.followup.send(embed=e)
            else:
                return await interaction.followup.send(f"{member.display_name} hasn't listened to any music yet!")
            
async def setup(bot: commands.AutoShardedBot):
    await bot.add_cog(ContextMenus(bot))

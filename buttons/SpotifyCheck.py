import discord
from discord.ext import commands

class Disconnect_Check(discord.ui.View):
    def __init__(self, bot: commands.AutoShardedBot, message: discord.Message) -> None:
        super().__init__(timeout=15.0)
        self.bot = bot
        self.db = self.bot.db.spotifyOauth
        self.message = message

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Yes", emoji="<:tickYes:697759553626046546>", style=discord.ButtonStyle.green)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.db.find_one_and_delete({"_id": interaction.user.id})
        return await interaction.response.edit_message(
            content="Your spotify account has been disconnected!", view=None, embed=None)

    @discord.ui.button(label="No", emoji="<:tickNo:697759586538749982>", style=discord.ButtonStyle.red)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        return await interaction.response.edit_message(
            content="Great, your account will stay connected!", view=None, embed=None)

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
            print(f"[Disconnect Check Buttons] Error: {error}")
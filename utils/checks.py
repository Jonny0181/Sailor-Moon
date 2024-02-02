import discord
import json
from discord import app_commands as Boog

with open("config.json", "r") as config_file:
    config_data = json.load(config_file)

def is_dev():
    def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in config_data["devIDS"]:
            return True
        else:
            return False
    return Boog.check(predicate)
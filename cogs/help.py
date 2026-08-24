from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

class HelpSelect(discord.ui.Select):
    def __init__(self, bot):
        options = [
            discord.SelectOption(label="Moderation", value="moderation", emoji="🛡️"),
            discord.SelectOption(label="Server Systems", value="systems", emoji="⚙️"),
            discord.SelectOption(label="Utility", value="utility", emoji="🧰"),
            discord.SelectOption(label="Fun / Media", value="media", emoji="🖼️"),
        ]
        super().__init__(placeholder="Choose a command category…", options=options)
        self.bot = bot

    async def callback(self, interaction):
        groups = {
            "moderation": ["ban","unban","kick","timeout","untimeout","warn","warnings","clearwarnings","purge","slowmode","lock","unlock","nick","hardban","unhardban","moddms","logging","role"],
            "systems": ["afk","greet","leave","embed","vanity","rank","leaderboard","levels","reactionrole","giveaway","ticket","autoresponse","j2c","tts"],
            "utility": ["userinfo","serverinfo","avatar","banner","roleinfo","channelinfo","membercount","botinfo","ping","timestamp","say","servericon","serverbanner"],
            "media": ["media"],
        }
        wanted = groups[self.values[0]]
        lines = []
        for cmd in self.bot.tree.walk_commands():
            top = cmd.qualified_name.split()[0]
            if top in wanted:
                lines.append(f"`/{cmd.qualified_name}` — {cmd.description or 'No description'}")
        e = discord.Embed(title=f"Help • {self.values[0].title()}", description="\n".join(lines[:35]) or "No commands found.", color=discord.Color.dark_gray())
        await interaction.response.edit_message(embed=e, view=self.view)

class HelpView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(bot))

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="View all bot commands by category.")
    async def help(self, interaction: discord.Interaction):
        e = discord.Embed(title="Lonely Help", description="Choose a category below to view commands.", color=discord.Color.dark_gray())
        await interaction.response.send_message(embed=e, view=HelpView(self.bot), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Help(bot))

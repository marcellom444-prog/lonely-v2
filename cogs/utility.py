from __future__ import annotations
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🏓 **{round(self.bot.latency*1000)}ms**")

    @app_commands.command(name="userinfo")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        e = discord.Embed(title=f"User Info • {member}", color=member.color)
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="ID", value=member.id)
        e.add_field(name="Created", value=f"<t:{int(member.created_at.timestamp())}:R>")
        e.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown")
        e.add_field(name="Top Role", value=member.top_role.mention)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="serverinfo")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        e = discord.Embed(title=g.name, color=discord.Color.dark_gray())
        if g.icon: e.set_thumbnail(url=g.icon.url)
        e.add_field(name="Members", value=g.member_count)
        e.add_field(name="Owner", value=f"<@{g.owner_id}>")
        e.add_field(name="Created", value=f"<t:{int(g.created_at.timestamp())}:R>")
        e.add_field(name="Roles", value=len(g.roles))
        e.add_field(name="Channels", value=len(g.channels))
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="avatar")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        e = discord.Embed(title=f"{member.display_name}'s avatar")
        e.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="banner")
    async def banner(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        user = await self.bot.fetch_user(member.id)
        if not user.banner:
            return await interaction.response.send_message("That user doesn't have a banner.", ephemeral=True)
        e = discord.Embed(title=f"{member.display_name}'s banner")
        e.set_image(url=user.banner.url)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="roleinfo")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        e = discord.Embed(title=f"Role Info • {role.name}", color=role.color)
        e.add_field(name="ID", value=role.id)
        e.add_field(name="Members", value=len(role.members))
        e.add_field(name="Position", value=role.position)
        e.add_field(name="Mentionable", value=role.mentionable)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="channelinfo")
    async def channelinfo(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        channel = channel or interaction.channel
        e = discord.Embed(title=f"Channel Info • #{channel.name}", color=discord.Color.dark_gray())
        e.add_field(name="ID", value=channel.id)
        e.add_field(name="Created", value=f"<t:{int(channel.created_at.timestamp())}:R>")
        e.add_field(name="NSFW", value=getattr(channel, "nsfw", False))
        e.add_field(name="Slowmode", value=f"{getattr(channel, 'slowmode_delay', 0)}s")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="membercount")
    async def membercount(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"👥 **{interaction.guild.member_count}** members")

    @app_commands.command(name="botinfo")
    async def botinfo(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🤖 **{self.bot.user}**\nGuilds: **{len(self.bot.guilds)}**\nLatency: **{round(self.bot.latency*1000)}ms**")

    @app_commands.command(name="timestamp")
    async def timestamp(self, interaction: discord.Interaction, unix: int | None = None):
        unix = unix or int(datetime.now(timezone.utc).timestamp())
        await interaction.response.send_message(f"`<t:{unix}:F>` → <t:{unix}:F>\n`<t:{unix}:R>` → <t:{unix}:R>")

    @app_commands.command(name="say")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def say(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message("Sent.", ephemeral=True)
        await interaction.channel.send(message)

    @app_commands.command(name="servericon")
    async def servericon(self, interaction: discord.Interaction):
        if not interaction.guild.icon:
            return await interaction.response.send_message("This server has no icon.", ephemeral=True)
        e = discord.Embed(title=f"{interaction.guild.name} icon")
        e.set_image(url=interaction.guild.icon.url)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="serverbanner")
    async def serverbanner(self, interaction: discord.Interaction):
        if not interaction.guild.banner:
            return await interaction.response.send_message("This server has no banner.", ephemeral=True)
        e = discord.Embed(title=f"{interaction.guild.name} banner")
        e.set_image(url=interaction.guild.banner.url)
        await interaction.response.send_message(embed=e)

async def setup(bot):
    await bot.add_cog(Utility(bot))

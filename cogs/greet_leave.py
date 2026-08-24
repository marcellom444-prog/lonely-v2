from __future__ import annotations

import json

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from config import DB_PATH
from db import get_settings, patch_settings


def render(template: str, member: discord.Member):
    return (
        template.replace("{user.mention}", member.mention)
        .replace("{user.name}", member.name)
        .replace("{user.id}", str(member.id))
        .replace("{user}", str(member))
        .replace("{server}", member.guild.name)
        .replace("{membercount}", str(member.guild.member_count or len(member.guild.members)))
    )


async def get_saved_embed(guild_id: int, name: str):
    if not name:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT data FROM embeds WHERE guild_id=? AND name=?", (guild_id, name.lower())) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return json.loads(row[0])


def render_embed(data: dict, member: discord.Member) -> discord.Embed:
    rendered = json.loads(json.dumps(data))
    for field in ("title", "description"):
        if isinstance(rendered.get(field), str):
            rendered[field] = render(rendered[field], member)
    if isinstance(rendered.get("footer"), dict) and isinstance(rendered["footer"].get("text"), str):
        rendered["footer"]["text"] = render(rendered["footer"]["text"], member)
    if isinstance(rendered.get("author"), dict) and isinstance(rendered["author"].get("name"), str):
        rendered["author"]["name"] = render(rendered["author"]["name"], member)
    for field in rendered.get("fields", []):
        if isinstance(field.get("name"), str):
            field["name"] = render(field["name"], member)
        if isinstance(field.get("value"), str):
            field["value"] = render(field["value"], member)
    return discord.Embed.from_dict(rendered)


class GreetLeave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    greet = app_commands.Group(name="greet", description="Configure welcome messages.")
    leave = app_commands.Group(name="leave", description="Configure leave messages.")

    @greet.command(name="setup", description="Choose the greeting channel.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def greet_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await patch_settings(interaction.guild.id, greet_channel=channel.id, greet_enabled=True)
        await interaction.response.send_message(f"✅ Greet messages enabled in {channel.mention}.", ephemeral=True)

    @greet.command(name="message", description="Set the greeting message.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def greet_message(self, interaction: discord.Interaction, message: str):
        await patch_settings(interaction.guild.id, greet_message=message)
<<<<<<< HEAD
        await interaction.response.send_message("✅ Greet message saved.", ephemeral=True)
=======
        await interaction.response.send_message("Greet message saved.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)

    @greet.command(name="embed", description="Use a saved embed for greetings.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def greet_embed(self, interaction: discord.Interaction, name: str):
        if not await get_saved_embed(interaction.guild.id, name):
<<<<<<< HEAD
            return await interaction.response.send_message("That saved embed doesn't exist.", ephemeral=True)
=======
            return await interaction.response.send_message("Embed not found.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)
        await patch_settings(interaction.guild.id, greet_embed=name.lower())
        await interaction.response.send_message(f"✅ Greet embed set to `{name}`.", ephemeral=True)

    @greet.command(name="test", description="Preview the greeting message.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def greet_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.send_greet(interaction.user, override_channel=interaction.channel)
<<<<<<< HEAD
        await interaction.followup.send("✅ Greet test sent.", ephemeral=True)
=======
        await interaction.followup.send("Greet test sent.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)

    @greet.command(name="disable", description="Disable greetings.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def greet_disable(self, interaction: discord.Interaction):
        await patch_settings(interaction.guild.id, greet_enabled=False)
<<<<<<< HEAD
        await interaction.response.send_message("✅ Greet disabled.", ephemeral=True)
=======
        await interaction.response.send_message("Greet disabled.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)

    @leave.command(name="setup", description="Choose the leave channel.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def leave_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await patch_settings(interaction.guild.id, leave_channel=channel.id, leave_enabled=True)
        await interaction.response.send_message(f"✅ Leave messages enabled in {channel.mention}.", ephemeral=True)

    @leave.command(name="message", description="Set the leave message.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def leave_message(self, interaction: discord.Interaction, message: str):
        await patch_settings(interaction.guild.id, leave_message=message)
<<<<<<< HEAD
        await interaction.response.send_message("✅ Leave message saved.", ephemeral=True)
=======
        await interaction.response.send_message("Leave message saved.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)

    @leave.command(name="embed", description="Use a saved embed for leave messages.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def leave_embed(self, interaction: discord.Interaction, name: str):
        if not await get_saved_embed(interaction.guild.id, name):
<<<<<<< HEAD
            return await interaction.response.send_message("That saved embed doesn't exist.", ephemeral=True)
=======
            return await interaction.response.send_message("Embed not found.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)
        await patch_settings(interaction.guild.id, leave_embed=name.lower())
        await interaction.response.send_message(f"✅ Leave embed set to `{name}`.", ephemeral=True)

    @leave.command(name="test", description="Preview the leave message.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def leave_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.send_leave(interaction.user, override_channel=interaction.channel)
<<<<<<< HEAD
        await interaction.followup.send("✅ Leave test sent.", ephemeral=True)
=======
        await interaction.followup.send("Leave test sent.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)

    @leave.command(name="disable", description="Disable leave messages.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def leave_disable(self, interaction: discord.Interaction):
        await patch_settings(interaction.guild.id, leave_enabled=False)
<<<<<<< HEAD
        await interaction.response.send_message("✅ Leave disabled.", ephemeral=True)
=======
        await interaction.response.send_message("Leave disabled.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)

    async def send_greet(self, member: discord.Member, override_channel=None):
        settings = await get_settings(member.guild.id)
        if not settings.get("greet_enabled", False) and not override_channel:
            return
        channel = override_channel or member.guild.get_channel(settings.get("greet_channel", 0))
        if not isinstance(channel, discord.TextChannel):
            return
        content = render(settings.get("greet_message", "Welcome {user.mention} to **{server}**!"), member)
        data = await get_saved_embed(member.guild.id, settings.get("greet_embed", ""))
        embed = render_embed(data, member) if data else None
        await channel.send(content=content or None, embed=embed)

    async def send_leave(self, member: discord.Member, override_channel=None):
        settings = await get_settings(member.guild.id)
        if not settings.get("leave_enabled", False) and not override_channel:
            return
        channel = override_channel or member.guild.get_channel(settings.get("leave_channel", 0))
        if not isinstance(channel, discord.TextChannel):
            return
        content = render(settings.get("leave_message", "**{user}** left **{server}**."), member)
        data = await get_saved_embed(member.guild.id, settings.get("leave_embed", ""))
        embed = render_embed(data, member) if data else None
        await channel.send(content=content or None, embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.send_greet(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.send_leave(member)


async def setup(bot):
    await bot.add_cog(GreetLeave(bot))

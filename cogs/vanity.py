from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from db import get_settings, patch_settings


def custom_status(member: discord.Member) -> str:
    for activity in member.activities:
        if isinstance(activity, discord.CustomActivity):
            return activity.state or activity.name or ""
    return ""


class Vanity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    vanity = app_commands.Group(name="vanity", description="Configure vanity status rewards.")

    @vanity.command(name="setup", description="Set the vanity keyword and reward role.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def setup_vanity(
        self,
        interaction: discord.Interaction,
        keyword: str,
        role: discord.Role,
        channel: discord.TextChannel | None = None,
    ):
        keyword = keyword.strip()
        if not keyword:
            return await interaction.response.send_message("The vanity keyword can't be empty.", ephemeral=True)
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("That role must be below Lonely's highest role.", ephemeral=True)
        await patch_settings(
            interaction.guild.id,
            vanity_keyword=keyword,
            vanity_role=role.id,
            vanity_channel=channel.id if channel else None,
            vanity_enabled=True,
        )
        await interaction.response.send_message(f"✅ Vanity reward configured for `{keyword}` → {role.mention}.", ephemeral=True)

    @vanity.command(name="message", description="Set the vanity reward message.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def message(self, interaction: discord.Interaction, message: str):
        await patch_settings(interaction.guild.id, vanity_message=message)
        await interaction.response.send_message("✅ Vanity message saved.", ephemeral=True)

    @vanity.command(name="check", description="Check whether a member matches the vanity keyword.")
    async def check(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        settings = await get_settings(interaction.guild.id)
        keyword = (settings.get("vanity_keyword") or "").casefold()
        matched = bool(keyword and keyword in custom_status(member).casefold())
        await interaction.response.send_message(f"{member.mention} vanity match: **{matched}**", ephemeral=True)

    @vanity.command(name="reset", description="Disable and clear vanity settings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction):
        await patch_settings(
            interaction.guild.id,
            vanity_enabled=False,
            vanity_keyword=None,
            vanity_role=None,
            vanity_channel=None,
        )
        await interaction.response.send_message("✅ Vanity system reset.", ephemeral=True)

    async def update_member(self, member: discord.Member):
        if member.bot:
            return
        settings = await get_settings(member.guild.id)
        if not settings.get("vanity_enabled"):
            return
        role = member.guild.get_role(settings.get("vanity_role", 0))
        if not role or role >= member.guild.me.top_role:
            return
        keyword = (settings.get("vanity_keyword") or "").casefold()
        matched = bool(keyword and keyword in custom_status(member).casefold())
        if matched and role not in member.roles:
            try:
                await member.add_roles(role, reason="Vanity status match")
                channel = member.guild.get_channel(settings.get("vanity_channel", 0))
                if isinstance(channel, discord.TextChannel):
                    message = settings.get("vanity_message", "{user.mention} earned the vanity role!")
                    await channel.send(message.replace("{user.mention}", member.mention))
            except discord.HTTPException:
                pass
        elif not matched and role in member.roles:
            try:
                await member.remove_roles(role, reason="Vanity status removed")
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        await self.update_member(after)


async def setup(bot):
    await bot.add_cog(Vanity(bot))

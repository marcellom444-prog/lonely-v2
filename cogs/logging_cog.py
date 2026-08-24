from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from db import get_settings, patch_settings


async def send_log(guild: discord.Guild, key: str, embed: discord.Embed):
    settings = await get_settings(guild.id)
    channel_id = settings.get(key)
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    logging = app_commands.Group(name="logging", description="Configure server logging.")

    @logging.command(name="setup", description="Create default private log channels.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_logs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        mapping = {}
        for key, name in [
            ("mod_log_channel", "mod-logs"),
            ("message_log_channel", "message-logs"),
            ("member_log_channel", "member-logs"),
            ("server_log_channel", "server-logs"),
        ]:
            channel = discord.utils.get(guild.text_channels, name=name)
            if not channel:
                channel = await guild.create_text_channel(name, overwrites=overwrites, reason="Logging setup")
            mapping[key] = channel.id
        await patch_settings(guild.id, **mapping)
        await interaction.followup.send("✅ Logging channels are configured.", ephemeral=True)

    @logging.command(name="channel", description="Set a log channel.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(
        kind=[
            app_commands.Choice(name="Moderation", value="mod_log_channel"),
            app_commands.Choice(name="Messages", value="message_log_channel"),
            app_commands.Choice(name="Members", value="member_log_channel"),
            app_commands.Choice(name="Server", value="server_log_channel"),
        ]
    )
    async def set_channel(
        self,
        interaction: discord.Interaction,
        kind: app_commands.Choice[str],
        channel: discord.TextChannel,
    ):
        await patch_settings(interaction.guild.id, **{kind.value: channel.id})
        await interaction.response.send_message(f"✅ {kind.name} logs → {channel.mention}", ephemeral=True)

    @logging.command(name="status", description="Show logging configuration.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status(self, interaction: discord.Interaction):
        settings = await get_settings(interaction.guild.id)
        text = "\n".join(
            [
                f"Moderation: <#{settings.get('mod_log_channel')}>" if settings.get("mod_log_channel") else "Moderation: Not set",
                f"Messages: <#{settings.get('message_log_channel')}>" if settings.get("message_log_channel") else "Messages: Not set",
                f"Members: <#{settings.get('member_log_channel')}>" if settings.get("member_log_channel") else "Members: Not set",
                f"Server: <#{settings.get('server_log_channel')}>" if settings.get("server_log_channel") else "Server: Not set",
            ]
        )
        await interaction.response.send_message(text, ephemeral=True)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        embed = discord.Embed(title="Message Deleted", color=discord.Color.red())
        embed.add_field(name="Author", value=f"{message.author} (`{message.author.id}`)", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=False)
        embed.add_field(name="Content", value=(message.content or "*No text*")[:1024], inline=False)
        await send_log(message.guild, "message_log_channel", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        embed = discord.Embed(title="Message Edited", color=discord.Color.orange(), url=after.jump_url)
        embed.add_field(name="Author", value=str(before.author), inline=False)
        embed.add_field(name="Before", value=(before.content or "*No text*")[:1024], inline=False)
        embed.add_field(name="After", value=(after.content or "*No text*")[:1024], inline=False)
        await send_log(before.guild, "message_log_channel", embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = discord.Embed(
            title="Member Joined",
            description=f"{member.mention}\n`{member.id}`",
            color=discord.Color.green(),
        )
        await send_log(member.guild, "member_log_channel", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = discord.Embed(
            title="Member Left",
            description=f"{member}\n`{member.id}`",
            color=discord.Color.red(),
        )
        await send_log(member.guild, "member_log_channel", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(title="Channel Created", description=f"{channel.mention} (`{channel.id}`)", color=discord.Color.green())
        await send_log(channel.guild, "server_log_channel", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(title="Channel Deleted", description=f"#{channel.name} (`{channel.id}`)", color=discord.Color.red())
        await send_log(channel.guild, "server_log_channel", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            embed = discord.Embed(title="Nickname Changed", color=discord.Color.dark_gray())
            embed.add_field(name="Member", value=f"{after.mention} (`{after.id}`)", inline=False)
            embed.add_field(name="Before", value=before.nick or "None", inline=False)
            embed.add_field(name="After", value=after.nick or "None", inline=False)
            await send_log(after.guild, "member_log_channel", embed)
        before_roles = set(before.roles)
        after_roles = set(after.roles)
        added = after_roles - before_roles
        removed = before_roles - after_roles
        if added or removed:
            embed = discord.Embed(title="Member Roles Changed", color=discord.Color.dark_gray())
            embed.add_field(name="Member", value=f"{after.mention} (`{after.id}`)", inline=False)
            if added:
                embed.add_field(name="Added", value=", ".join(r.mention for r in added), inline=False)
            if removed:
                embed.add_field(name="Removed", value=", ".join(r.mention for r in removed), inline=False)
            await send_log(after.guild, "member_log_channel", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = discord.Embed(title="Role Created", description=f"{role.mention} (`{role.id}`)", color=discord.Color.green())
        await send_log(role.guild, "server_log_channel", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = discord.Embed(title="Role Deleted", description=f"{role.name} (`{role.id}`)", color=discord.Color.red())
        await send_log(role.guild, "server_log_channel", embed)


async def setup(bot):
    await bot.add_cog(Logging(bot))

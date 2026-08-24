from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from config import DB_PATH
from db import get_settings, patch_settings


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def send_mod_log(
    guild: discord.Guild,
    action: str,
    target: discord.abc.User,
    moderator: discord.abc.User,
    reason: str | None = None,
    extra: str | None = None,
):
    settings = await get_settings(guild.id)
    channel = guild.get_channel(settings.get("mod_log_channel", 0))
    if not isinstance(channel, discord.TextChannel):
        return
    embed = discord.Embed(title=f"Moderation • {action}", color=discord.Color.dark_gray())
    embed.add_field(name="User", value=f"{target} (`{target.id}`)", inline=False)
    embed.add_field(name="Moderator", value=f"{moderator} (`{moderator.id}`)", inline=False)
<<<<<<< HEAD
    embed.add_field(name="Reason", value=reason or "No reason provided.", inline=False)
=======
    embed.add_field(name="Reason", value=reason or "No reason.", inline=False)
>>>>>>> be79980 (Update Lonely bot)
    if extra:
        embed.add_field(name="Details", value=extra, inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        pass


async def maybe_dm(
    member: discord.abc.User,
    guild: discord.Guild,
    action: str,
    reason: str | None = None,
    duration: str | None = None,
):
    settings = await get_settings(guild.id)
    if not settings.get("moderation_dms", True):
        return False
    text = f"You were **{action}** in **{guild.name}**."
    if duration:
        text += f"\nDuration: **{duration}**"
    if reason:
        text += f"\nReason: **{reason}**"
    try:
        await member.send(text)
        return True
    except discord.HTTPException:
        return False


def can_act(interaction: discord.Interaction, member: discord.Member) -> tuple[bool, str]:
    if interaction.user.id == member.id:
        return False, "You can't moderate yourself."
    if interaction.guild.owner_id == member.id:
<<<<<<< HEAD
        return False, "You can't moderate the server owner."
    actor = interaction.user
    bot_member = interaction.guild.me
    if actor != interaction.guild.owner and actor.top_role <= member.top_role:
        return False, "That member's highest role is equal to or above yours."
=======
        return False, "You can't moderate the owner."
    actor = interaction.user
    bot_member = interaction.guild.me
    if actor != interaction.guild.owner and actor.top_role <= member.top_role:
        return False, "That role is too high."
>>>>>>> be79980 (Update Lonely bot)
    if not bot_member or bot_member.top_role <= member.top_role:
        return False, "Lonely's role must be above that member's highest role."
    return True, ""


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    role = app_commands.Group(name="role", description="Role management tools.")

    @app_commands.command(name="ban", description="Ban a member.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None,
        delete_days: app_commands.Range[int, 0, 7] = 0,
    ):
        ok, message = can_act(interaction, member)
        if not ok:
            return await interaction.response.send_message(message, ephemeral=True)
        dm_sent = await maybe_dm(member, interaction.guild, "banned", reason)
        await interaction.guild.ban(member, reason=reason, delete_message_seconds=delete_days * 86400)
        await send_mod_log(interaction.guild, "Ban", member, interaction.user, reason, f"DM sent: {dm_sent}")
<<<<<<< HEAD
        await interaction.response.send_message(f"🔨 Banned **{member}**.\nReason: {reason or 'No reason provided.'}")
=======
        await interaction.response.send_message(f"**{member}** banned.\n{reason or 'No reason.'}")
>>>>>>> be79980 (Update Lonely bot)

    @app_commands.command(name="unban", description="Unban a user by ID.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str | None = None):
        try:
            uid = int(user_id)
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user, reason=reason)
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message(
<<<<<<< HEAD
                "I couldn't unban that user. Check the ID and whether they're banned.",
=======
                "Couldn't unban that user.",
>>>>>>> be79980 (Update Lonely bot)
                ephemeral=True,
            )
        await send_mod_log(interaction.guild, "Unban", user, interaction.user, reason)
        await interaction.response.send_message(f"✅ Unbanned **{user}**.")

    @app_commands.command(name="kick", description="Kick a member.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str | None = None):
        ok, message = can_act(interaction, member)
        if not ok:
            return await interaction.response.send_message(message, ephemeral=True)
        dm_sent = await maybe_dm(member, interaction.guild, "kicked", reason)
        await member.kick(reason=reason)
        await send_mod_log(interaction.guild, "Kick", member, interaction.user, reason, f"DM sent: {dm_sent}")
<<<<<<< HEAD
        await interaction.response.send_message(f"👢 Kicked **{member}**.\nReason: {reason or 'No reason provided.'}")
=======
        await interaction.response.send_message(f"**{member}** kicked.\n{reason or 'No reason.'}")
>>>>>>> be79980 (Update Lonely bot)

    @app_commands.command(name="timeout", description="Timeout a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, 40320],
        reason: str | None = None,
    ):
        ok, message = can_act(interaction, member)
        if not ok:
            return await interaction.response.send_message(message, ephemeral=True)
        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        dm_sent = await maybe_dm(member, interaction.guild, "timed out", reason, f"{minutes} minute(s)")
        await member.timeout(until, reason=reason)
        await send_mod_log(
            interaction.guild,
            "Timeout",
            member,
            interaction.user,
            reason,
            f"Duration: {minutes} minute(s)\nDM sent: {dm_sent}",
        )
<<<<<<< HEAD
        await interaction.response.send_message(f"⏳ Timed out **{member}** for **{minutes} minute(s)**.")
=======
        await interaction.response.send_message(f"**{member}** timed out for **{minutes}m**.")
>>>>>>> be79980 (Update Lonely bot)

    @app_commands.command(name="untimeout", description="Remove a timeout.")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member, reason: str | None = None):
        ok, message = can_act(interaction, member)
        if not ok:
            return await interaction.response.send_message(message, ephemeral=True)
        await member.timeout(None, reason=reason)
        await send_mod_log(interaction.guild, "Remove Timeout", member, interaction.user, reason)
<<<<<<< HEAD
        await interaction.response.send_message(f"✅ Removed timeout from **{member}**.")

    @app_commands.command(name="warn", description="Warn a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
=======
        await interaction.response.send_message(f"Timeout removed from **{member}**.")

    @app_commands.command(name="warn", description="Warn a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason."):
>>>>>>> be79980 (Update Lonely bot)
        ok, message = can_act(interaction, member)
        if not ok:
            return await interaction.response.send_message(message, ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "INSERT INTO warnings(guild_id,user_id,moderator_id,reason,created_at) VALUES(?,?,?,?,?)",
                (interaction.guild.id, member.id, interaction.user.id, reason, now_iso()),
            )
            await db.commit()
            case_id = cur.lastrowid
        dm_sent = await maybe_dm(member, interaction.guild, "warned", reason)
        await send_mod_log(interaction.guild, f"Warning #{case_id}", member, interaction.user, reason, f"DM sent: {dm_sent}")
<<<<<<< HEAD
        await interaction.response.send_message(f"⚠️ Warned **{member}** • Case **#{case_id}**\nReason: {reason}")
=======
        await interaction.response.send_message(f"**{member}** warned. `#{case_id}`\n{reason}")
>>>>>>> be79980 (Update Lonely bot)

    @app_commands.command(name="warnings", description="View a member's warnings.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id,moderator_id,reason,created_at FROM warnings WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 20",
                (interaction.guild.id, member.id),
            ) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await interaction.response.send_message(f"**{member}** has no warnings.", ephemeral=True)
        lines = [f"`#{row[0]}` • <@{row[1]}> • {row[2] or 'No reason'}" for row in rows]
        embed = discord.Embed(
            title=f"Warnings • {member}",
            description="\n".join(lines),
            color=discord.Color.dark_gray(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "DELETE FROM warnings WHERE guild_id=? AND user_id=?",
                (interaction.guild.id, member.id),
            )
            await db.commit()
        await send_mod_log(interaction.guild, "Clear Warnings", member, interaction.user, f"Cleared {cur.rowcount} warning(s).")
<<<<<<< HEAD
        await interaction.response.send_message(f"🧹 Cleared warnings for **{member}**.")
=======
        await interaction.response.send_message(f"Warnings cleared for **{member}**.")
>>>>>>> be79980 (Update Lonely bot)

    @app_commands.command(name="purge", description="Delete recent messages.")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 500]):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
<<<<<<< HEAD
        await interaction.followup.send(f"🧹 Deleted **{len(deleted)}** message(s).", ephemeral=True)
=======
        await interaction.followup.send(f"Deleted **{len(deleted)}** messages.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)

    @app_commands.command(name="slowmode", description="Set channel slowmode.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        await interaction.channel.edit(slowmode_delay=seconds)
<<<<<<< HEAD
        await interaction.response.send_message(f"🐢 Slowmode set to **{seconds}s**.")
=======
        await interaction.response.send_message(f"Slowmode: **{seconds}s**.")
>>>>>>> be79980 (Update Lonely bot)

    @app_commands.command(name="lock", description="Lock the current channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Locked by {interaction.user}")
<<<<<<< HEAD
        await interaction.response.send_message("🔒 Channel locked.")
=======
        await interaction.response.send_message("Channel locked.")
>>>>>>> be79980 (Update Lonely bot)

    @app_commands.command(name="unlock", description="Unlock the current channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Unlocked by {interaction.user}")
<<<<<<< HEAD
        await interaction.response.send_message("🔓 Channel unlocked.")
=======
        await interaction.response.send_message("Channel unlocked.")
>>>>>>> be79980 (Update Lonely bot)

    @app_commands.command(name="nick", description="Change a member's nickname.")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.checks.bot_has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, member: discord.Member, nickname: str | None = None):
        ok, message = can_act(interaction, member)
        if not ok:
            return await interaction.response.send_message(message, ephemeral=True)
        await member.edit(nick=nickname, reason=f"Changed by {interaction.user}")
<<<<<<< HEAD
        await interaction.response.send_message(f"✅ Updated nickname for **{member}**.")
=======
        await interaction.response.send_message(f"Nickname updated.")
>>>>>>> be79980 (Update Lonely bot)

    @role.command(name="add", description="Add a role to a member.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    async def role_add(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("You can't manage that role.", ephemeral=True)
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("Lonely's role must be above that role.", ephemeral=True)
        await member.add_roles(role, reason=f"Added by {interaction.user}")
        await interaction.response.send_message(f"✅ Added {role.mention} to {member.mention}.")

    @role.command(name="remove", description="Remove a role from a member.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    async def role_remove(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("You can't manage that role.", ephemeral=True)
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("Lonely's role must be above that role.", ephemeral=True)
        await member.remove_roles(role, reason=f"Removed by {interaction.user}")
        await interaction.response.send_message(f"✅ Removed {role.mention} from {member.mention}.")

    @role.command(name="members", description="Show members with a role.")
    async def role_members(self, interaction: discord.Interaction, role: discord.Role):
        mentions = [member.mention for member in role.members[:50]]
        extra = max(0, len(role.members) - 50)
        text = "\n".join(mentions) or "No members have this role."
        if extra:
            text += f"\n…and {extra} more."
        await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command(name="hardban", description="Persistently ban a user.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
<<<<<<< HEAD
    async def hardban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided."):
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message("Provide a valid user ID.", ephemeral=True)
=======
    async def hardban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason."):
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message("Invalid user ID.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)

        target = interaction.guild.get_member(uid)
        dm_sent = False
        if target:
            ok, message = can_act(interaction, target)
            if not ok:
                return await interaction.response.send_message(message, ephemeral=True)
            dm_sent = await maybe_dm(target, interaction.guild, "hardbanned", reason)
        try:
            user = target or await self.bot.fetch_user(uid)
        except discord.NotFound:
            return await interaction.response.send_message("I couldn't find a Discord user with that ID.", ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO hardbans(guild_id,user_id,moderator_id,reason,created_at) VALUES(?,?,?,?,?)",
                (interaction.guild.id, uid, interaction.user.id, reason, now_iso()),
            )
            await db.commit()
        await interaction.guild.ban(user, reason=f"Hardban: {reason}", delete_message_seconds=7 * 86400)
        await send_mod_log(interaction.guild, "Hardban", user, interaction.user, reason, f"DM sent: {dm_sent}")
<<<<<<< HEAD
        await interaction.response.send_message(f"⛔ Hardbanned **{user}** (`{uid}`).\nReason: {reason}")
=======
        await interaction.response.send_message(f"**{user}** hardbanned.\n{reason}")
>>>>>>> be79980 (Update Lonely bot)

    @app_commands.command(name="unhardban", description="Remove a persistent hardban and unban the user.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def unhardban(self, interaction: discord.Interaction, user_id: str):
        try:
            uid = int(user_id)
        except ValueError:
<<<<<<< HEAD
            return await interaction.response.send_message("Provide a valid user ID.", ephemeral=True)
=======
            return await interaction.response.send_message("Invalid user ID.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)
        try:
            user = await self.bot.fetch_user(uid)
        except discord.NotFound:
            user = discord.Object(id=uid)
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("DELETE FROM hardbans WHERE guild_id=? AND user_id=?", (interaction.guild.id, uid))
            await db.commit()
        try:
            await interaction.guild.unban(user, reason=f"Unhardbanned by {interaction.user}")
        except discord.NotFound:
            pass
        await interaction.response.send_message(
<<<<<<< HEAD
            f"✅ Removed hardban for `{uid}`." if cur.rowcount else f"`{uid}` wasn't on the hardban list, but I attempted to unban them.",
=======
            f"Hardban removed for `{uid}`." if cur.rowcount else f"`{uid}` wasn't on the hardban list, but I attempted to unban them.",
>>>>>>> be79980 (Update Lonely bot)
        )

    @app_commands.command(name="moddms", description="Enable or disable moderation DM notifications.")
    @app_commands.checks.has_permissions(administrator=True)
    async def moddms(self, interaction: discord.Interaction, enabled: bool):
        await patch_settings(interaction.guild.id, moderation_dms=enabled)
<<<<<<< HEAD
        await interaction.response.send_message(f"Moderation DMs are now **{'enabled' if enabled else 'disabled'}**.")
=======
        await interaction.response.send_message(f"Moderation DMs **{'on' if enabled else 'off'}**.")
>>>>>>> be79980 (Update Lonely bot)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT reason FROM hardbans WHERE guild_id=? AND user_id=?",
                (member.guild.id, member.id),
            ) as cur:
                row = await cur.fetchone()
        if row:
            try:
                await member.guild.ban(member, reason=f"Persistent hardban: {row[0] or 'No reason'}")
            except discord.HTTPException:
                pass


async def setup(bot):
    await bot.add_cog(Moderation(bot))

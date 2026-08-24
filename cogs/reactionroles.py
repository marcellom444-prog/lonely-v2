from __future__ import annotations

import re

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from config import DB_PATH

CUSTOM = re.compile(r"<a?:([A-Za-z0-9_]+):(\d+)>")


def emoji_key(value: str | discord.PartialEmoji) -> str:
    if isinstance(value, discord.PartialEmoji):
        return f"{value.name}:{value.id}" if value.id else value.name or ""
    match = CUSTOM.fullmatch(value.strip())
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    return value.strip()


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    rr = app_commands.Group(name="reactionrole", description="Reaction role tools.")

    @rr.command(name="add", description="Add a reaction role to a message in this channel.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def add(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("That role must be below Lonely's highest role.", ephemeral=True)
        try:
            mid = int(message_id)
            message = await interaction.channel.fetch_message(mid)
            await message.add_reaction(emoji)
        except (ValueError, discord.HTTPException):
            return await interaction.response.send_message("I couldn't find that message or use that emoji.", ephemeral=True)

        key = emoji_key(emoji)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO reaction_roles(guild_id,channel_id,message_id,emoji,role_id,mode) "
                "VALUES(?,?,?,?,?,'toggle')",
                (interaction.guild.id, interaction.channel.id, mid, key, role.id),
            )
            await db.commit()
<<<<<<< HEAD
        await interaction.response.send_message(f"✅ {emoji} → {role.mention}", ephemeral=True)
=======
        await interaction.response.send_message(f"{emoji} → {role.mention}", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)

    @rr.command(name="remove", description="Remove a reaction role mapping.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def remove(self, interaction: discord.Interaction, message_id: str, emoji: str):
        try:
            mid = int(message_id)
        except ValueError:
            return await interaction.response.send_message("Provide a valid message ID.", ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM reaction_roles WHERE guild_id=? AND message_id=? AND emoji=?",
                (interaction.guild.id, mid, emoji_key(emoji)),
            )
            await db.commit()
<<<<<<< HEAD
        await interaction.response.send_message("✅ Reaction role removed.", ephemeral=True)
=======
        await interaction.response.send_message("Reaction role removed.", ephemeral=True)
>>>>>>> be79980 (Update Lonely bot)

    @rr.command(name="list", description="List reaction roles in this server.")
    async def list_rr(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT channel_id,message_id,emoji,role_id FROM reaction_roles WHERE guild_id=? LIMIT 50",
                (interaction.guild.id,),
            ) as cur:
                rows = await cur.fetchall()
        text = "\n".join(f"<#{c}> • `{m}` • `{e}` → <@&{r}>" for c, m, e, r in rows) or "No reaction roles."
        await interaction.response.send_message(text, ephemeral=True)

    async def apply(self, payload: discord.RawReactionActionEvent, add: bool):
        if not payload.guild_id or payload.user_id == getattr(self.bot.user, "id", None):
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id FROM reaction_roles WHERE guild_id=? AND message_id=? AND emoji=?",
                (payload.guild_id, payload.message_id, emoji_key(payload.emoji)),
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.HTTPException:
                return
        role = guild.get_role(row[0])
        if not role or role >= guild.me.top_role:
            return
        try:
            if add:
                await member.add_roles(role, reason="Reaction role")
            else:
                await member.remove_roles(role, reason="Reaction role removed")
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self.apply(payload, True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self.apply(payload, False)


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))

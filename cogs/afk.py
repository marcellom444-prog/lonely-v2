from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from config import DB_PATH


def parse_iso(value: str):
    return datetime.fromisoformat(value)


def human_delta(dt: datetime):
    seconds = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {seconds % 3600 // 60}m"
    return f"{seconds // 86400}d {seconds % 86400 // 3600}h"


class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def set_afk(self, member: discord.Member, reason: str):
        reason = reason.strip()[:500] or "AFK"
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT old_nick FROM afk WHERE guild_id=? AND user_id=?",
                (member.guild.id, member.id),
            ) as cur:
                existing = await cur.fetchone()
            old_nick = existing[0] if existing else member.nick
            await db.execute(
                "INSERT OR REPLACE INTO afk(guild_id,user_id,reason,since,old_nick) VALUES(?,?,?,?,?)",
                (member.guild.id, member.id, reason, datetime.now(timezone.utc).isoformat(), old_nick),
            )
            await db.commit()
        try:
            if not member.display_name.startswith("[AFK]"):
                await member.edit(nick=f"[AFK] {member.display_name}"[:32], reason="AFK status")
        except discord.HTTPException:
            pass
        return reason

    @app_commands.command(name="afk", description="Set your AFK status.")
    async def afk_slash(self, interaction: discord.Interaction, reason: str = "AFK"):
        saved = await self.set_afk(interaction.user, reason)
        await interaction.response.send_message(f"💤 You're now AFK: **{saved}**")

    @commands.command(name="afk", aliases=["a"])
    @commands.guild_only()
    async def afk_prefix(self, ctx: commands.Context, *, reason: str = "AFK"):
        saved = await self.set_afk(ctx.author, reason)
        await ctx.send(f"💤 {ctx.author.mention}, you're now AFK: **{saved}**")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT reason,since,old_nick FROM afk WHERE guild_id=? AND user_id=?",
                (message.guild.id, message.author.id),
            ) as cur:
                own = await cur.fetchone()

        if own:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM afk WHERE guild_id=? AND user_id=?", (message.guild.id, message.author.id))
                await db.commit()
            if isinstance(message.author, discord.Member):
                try:
                    await message.author.edit(nick=own[2], reason="Returned from AFK")
                except discord.HTTPException:
                    pass
            try:
                await message.channel.send(
<<<<<<< HEAD
                    f"👋 Welcome back {message.author.mention}! I removed your AFK status.",
=======
                    f"Welcome back {message.author.mention}. AFK removed.",
>>>>>>> be79980 (Update Lonely bot)
                    delete_after=8,
                )
            except discord.HTTPException:
                pass

        if message.mentions:
            lines = []
            async with aiosqlite.connect(DB_PATH) as db:
                for user in message.mentions[:10]:
                    async with db.execute(
                        "SELECT reason,since FROM afk WHERE guild_id=? AND user_id=?",
                        (message.guild.id, user.id),
                    ) as cur:
                        row = await cur.fetchone()
                    if row:
                        lines.append(
                            f"💤 **{user.display_name}** is AFK: {row[0]} • {human_delta(parse_iso(row[1]))}"
                        )
            if lines:
                try:
                    await message.channel.send("\n".join(lines), delete_after=15)
                except discord.HTTPException:
                    pass


async def setup(bot):
    await bot.add_cog(AFK(bot))

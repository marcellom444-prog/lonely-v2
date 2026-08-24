from __future__ import annotations

import random
import time

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from config import DB_PATH
from db import get_settings, patch_settings


def needed(level: int):
    return 100 + level * 75


def add_and_normalize(xp: int, level: int, amount: int):
    xp = max(0, xp + amount)
    while xp >= needed(level):
        xp -= needed(level)
        level += 1
    return xp, level


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns: dict[tuple[int, int], float] = {}

    levels = app_commands.Group(name="levels", description="Leveling configuration.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or not message.content.strip():
            return
        settings = await get_settings(message.guild.id)
        if not settings.get("leveling_enabled", True):
            return
        key = (message.guild.id, message.author.id)
        now = time.monotonic()
        if now - self.cooldowns.get(key, 0.0) < int(settings.get("xp_cooldown", 60)):
            return
        self.cooldowns[key] = now
        xp_min = max(1, int(settings.get("xp_min", 15)))
        xp_max = max(xp_min, int(settings.get("xp_max", 25)))
        gain = random.randint(xp_min, xp_max)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT xp,level FROM xp WHERE guild_id=? AND user_id=?", key) as cur:
                row = await cur.fetchone()
            xp, level = row or (0, 0)
            old_level = level
            xp, level = add_and_normalize(xp, level, gain)
            await db.execute(
                "INSERT INTO xp(guild_id,user_id,xp,level) VALUES(?,?,?,?) "
                "ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=excluded.xp, level=excluded.level",
                (message.guild.id, message.author.id, xp, level),
            )
            await db.commit()

        if level > old_level:
            channel = message.guild.get_channel(settings.get("levelup_channel", 0)) or message.channel
            template = settings.get("levelup_message", "🎉 {user.mention} reached **level {level}**!")
            try:
                await channel.send(template.replace("{user.mention}", message.author.mention).replace("{level}", str(level)))
            except discord.HTTPException:
                pass

    @app_commands.command(name="rank", description="Show a member's level and XP.")
    async def rank(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT xp,level FROM xp WHERE guild_id=? AND user_id=?",
                (interaction.guild.id, member.id),
            ) as cur:
                row = await cur.fetchone()
        xp, level = row or (0, 0)
        embed = discord.Embed(title=f"Rank • {member.display_name}", color=discord.Color.dark_gray())
        embed.description = f"Level **{level}**\nXP **{xp}/{needed(level)}**"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show the server XP leaderboard.")
    async def leaderboard(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id,xp,level FROM xp WHERE guild_id=? ORDER BY level DESC,xp DESC LIMIT 10",
                (interaction.guild.id,),
            ) as cur:
                rows = await cur.fetchall()
        lines = [f"**{i}.** <@{uid}> — Level {level} ({xp} XP)" for i, (uid, xp, level) in enumerate(rows, 1)]
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Leaderboard",
                description="\n".join(lines) or "No XP yet.",
                color=discord.Color.dark_gray(),
            )
        )

    @levels.command(name="settings", description="Configure leveling.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settings(
        self,
        interaction: discord.Interaction,
        enabled: bool | None = None,
        cooldown: app_commands.Range[int, 5, 600] | None = None,
        levelup_channel: discord.TextChannel | None = None,
    ):
        updates = {}
        if enabled is not None:
            updates["leveling_enabled"] = enabled
        if cooldown is not None:
            updates["xp_cooldown"] = cooldown
        if levelup_channel is not None:
            updates["levelup_channel"] = levelup_channel.id
        await patch_settings(interaction.guild.id, **updates)
        await interaction.response.send_message("Leveling updated.", ephemeral=True)

    @levels.command(name="addxp", description="Add XP to a member.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def addxp(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1, 100000],
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT xp,level FROM xp WHERE guild_id=? AND user_id=?",
                (interaction.guild.id, member.id),
            ) as cur:
                row = await cur.fetchone()
            xp, level = row or (0, 0)
            xp, level = add_and_normalize(xp, level, amount)
            await db.execute(
                "INSERT INTO xp(guild_id,user_id,xp,level) VALUES(?,?,?,?) "
                "ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=excluded.xp,level=excluded.level",
                (interaction.guild.id, member.id, xp, level),
            )
            await db.commit()
        await interaction.response.send_message(f"Added **{amount} XP** to {member.mention}.", ephemeral=True)

    @levels.command(name="reset", description="Reset a member's XP and level.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reset(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM xp WHERE guild_id=? AND user_id=?", (interaction.guild.id, member.id))
            await db.commit()
        await interaction.response.send_message(f"XP reset for {member.mention}.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Leveling(bot))

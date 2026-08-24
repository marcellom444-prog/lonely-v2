from __future__ import annotations

import time

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from config import DB_PATH


class AutoResponse(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns: dict[tuple[int, int], float] = {}

    autoresponse = app_commands.Group(name="autoresponse", description="Automatic channel responses.")

    @autoresponse.command(name="create", description="Create an automatic channel response.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def create(
        self,
        interaction: discord.Interaction,
        trigger: str,
        response: str,
        exact: bool = False,
        cooldown_seconds: app_commands.Range[int, 0, 3600] = 0,
        case_sensitive: bool = False,
        delete_trigger: bool = False,
    ):
        if not trigger.strip():
            return await interaction.response.send_message("Trigger can't be empty.", ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "INSERT INTO autoresponses"
                "(guild_id,trigger,response,exact,case_sensitive,cooldown_seconds,delete_trigger) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    interaction.guild.id,
                    trigger,
                    response,
                    int(exact),
                    int(case_sensitive),
                    cooldown_seconds,
                    int(delete_trigger),
                ),
            )
            await db.commit()
            response_id = cur.lastrowid
        await interaction.response.send_message(f"✅ Auto response #{response_id} created.", ephemeral=True)

    @autoresponse.command(name="delete", description="Delete an automatic response.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete(self, interaction: discord.Interaction, id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "DELETE FROM autoresponses WHERE guild_id=? AND id=?",
                (interaction.guild.id, id),
            )
            await db.commit()
        await interaction.response.send_message(
            "Auto response deleted." if cur.rowcount else "That auto response wasn't found.",
            ephemeral=True,
        )

    @autoresponse.command(name="enable", description="Enable an automatic response.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def enable(self, interaction: discord.Interaction, id: int):
        await self.set_enabled(interaction, id, True)

    @autoresponse.command(name="disable", description="Disable an automatic response.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def disable(self, interaction: discord.Interaction, id: int):
        await self.set_enabled(interaction, id, False)

    async def set_enabled(self, interaction: discord.Interaction, response_id: int, enabled: bool):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "UPDATE autoresponses SET enabled=? WHERE guild_id=? AND id=?",
                (int(enabled), interaction.guild.id, response_id),
            )
            await db.commit()
        await interaction.response.send_message(
            f"✅ Auto response {'enabled' if enabled else 'disabled'}." if cur.rowcount else "That auto response wasn't found.",
            ephemeral=True,
        )

    @autoresponse.command(name="list", description="List automatic responses.")
    async def list_ar(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id,trigger,response,enabled FROM autoresponses WHERE guild_id=? ORDER BY id LIMIT 50",
                (interaction.guild.id,),
            ) as cur:
                rows = await cur.fetchall()
        text = "\n".join(
            f"`#{i}` `{t[:40]}` → {r[:80]} {'✅' if enabled else '❌'}"
            for i, t, r, enabled in rows
        ) or "No auto responses."
        await interaction.response.send_message(text[:1900], ephemeral=True)

    @autoresponse.command(name="test", description="Test a trigger without posting publicly.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def test(self, interaction: discord.Interaction, text: str):
        row = await self.find_match(interaction.guild.id, text)
        if not row:
            return await interaction.response.send_message("No auto response matched that text.", ephemeral=True)
        await interaction.response.send_message(f"Matched `#{row[0]}` → {row[2]}", ephemeral=True)

    async def find_match(self, guild_id: int, content_text: str):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id,trigger,response,exact,case_sensitive,cooldown_seconds,delete_trigger "
                "FROM autoresponses WHERE guild_id=? AND enabled=1 ORDER BY id",
                (guild_id,),
            ) as cur:
                rows = await cur.fetchall()
        for row in rows:
            rid, trigger, response, exact, case_sensitive, cooldown, delete_trigger = row
            content = content_text if case_sensitive else content_text.casefold()
            target = trigger if case_sensitive else trigger.casefold()
            if (content == target) if exact else (target in content):
                return row
        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or not message.content:
            return
        row = await self.find_match(message.guild.id, message.content)
        if not row:
            return
        rid, _, response, _, _, cooldown, delete_trigger = row
        key = (message.guild.id, rid)
        now = time.monotonic()
        if cooldown and now - self.cooldowns.get(key, 0.0) < cooldown:
            return
        self.cooldowns[key] = now
        if delete_trigger:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
        try:
            await message.channel.send(response)
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(AutoResponse(bot))

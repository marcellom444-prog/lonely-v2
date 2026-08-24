from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from config import DB_PATH


class GiveawayView(discord.ui.View):
    def __init__(self, cog: "Giveaways"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Enter Giveaway",
        emoji="🎉",
        style=discord.ButtonStyle.secondary,
        custom_id="lonely:giveaway:enter",
    )
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.message or not interaction.guild:
            return await interaction.response.send_message("This giveaway is unavailable.", ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT ended,cancelled FROM giveaway_history WHERE message_id=? AND guild_id=?",
                (interaction.message.id, interaction.guild.id),
            ) as cur:
                row = await cur.fetchone()
            if not row or row[0] or row[1]:
                return await interaction.response.send_message("This giveaway has already ended.", ephemeral=True)
            await db.execute(
                "INSERT OR IGNORE INTO giveaway_entries(message_id,user_id) VALUES(?,?)",
                (interaction.message.id, interaction.user.id),
            )
            await db.commit()

        await interaction.response.send_message("🎉 You're entered!", ephemeral=True)


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tasks: dict[int, asyncio.Task] = {}
        self.resume_task: asyncio.Task | None = None

    giveaway = app_commands.Group(name="giveaway", description="Giveaway tools.")

    async def cog_load(self):
        self.bot.add_view(GiveawayView(self))
        if not getattr(self.bot, "preflight_mode", False):
            self.resume_task = asyncio.create_task(self.resume_active_giveaways())

    def cog_unload(self):
        if self.resume_task:
            self.resume_task.cancel()
        for task in self.tasks.values():
            task.cancel()
        self.tasks.clear()

    async def resume_active_giveaways(self):
        await self.bot.wait_until_ready()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT message_id,ends_at FROM giveaway_history WHERE ended=0 AND cancelled=0"
            ) as cur:
                rows = await cur.fetchall()
        for message_id, ends_at in rows:
            try:
                end = datetime.fromisoformat(ends_at)
                delay = max(0.0, (end - datetime.now(timezone.utc)).total_seconds())
                self.schedule_finish(message_id, delay)
            except (TypeError, ValueError):
                continue

    def schedule_finish(self, message_id: int, delay: float):
        old = self.tasks.pop(message_id, None)
        if old:
            old.cancel()
        self.tasks[message_id] = asyncio.create_task(self.finish_after(message_id, delay))

    @giveaway.command(name="create", description="Create a giveaway.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create(
        self,
        interaction: discord.Interaction,
        prize: str,
        minutes: app_commands.Range[int, 1, 10080],
        winners: app_commands.Range[int, 1, 20] = 1,
    ):
        ends = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        embed = discord.Embed(
            title="🎉 Giveaway",
            description=(
                f"**Prize:** {prize}\n"
                f"**Winners:** {winners}\n"
                f"**Ends:** <t:{int(ends.timestamp())}:R>\n"
                f"**Host:** {interaction.user.mention}"
            ),
            color=discord.Color.dark_gray(),
        )
        await interaction.response.send_message(embed=embed, view=GiveawayView(self))
        message = await interaction.original_response()

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO giveaway_history"
                "(guild_id,message_id,channel_id,host_id,prize,winners,ends_at,ended,cancelled) "
                "VALUES(?,?,?,?,?,?,?,0,0)",
                (
                    interaction.guild.id,
                    message.id,
                    interaction.channel.id,
                    interaction.user.id,
                    prize,
                    winners,
                    ends.isoformat(),
                ),
            )
            await db.commit()
        self.schedule_finish(message.id, minutes * 60)

    async def finish_after(self, message_id: int, delay: float):
        try:
            await asyncio.sleep(delay)
            await self.finish_giveaway(message_id)
        except asyncio.CancelledError:
            return
        finally:
            self.tasks.pop(message_id, None)

    async def finish_giveaway(self, message_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT guild_id,channel_id,prize,winners,ended,cancelled FROM giveaway_history WHERE message_id=?",
                (message_id,),
            ) as cur:
                row = await cur.fetchone()
            if not row or row[4] or row[5]:
                return False
            guild_id, channel_id, prize, winner_count, _, _ = row
            async with db.execute(
                "SELECT user_id FROM giveaway_entries WHERE message_id=?",
                (message_id,),
            ) as cur:
                entrants = [r[0] for r in await cur.fetchall()]
            await db.execute("UPDATE giveaway_history SET ended=1 WHERE message_id=?", (message_id,))
            await db.commit()

        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return True

        chosen = random.sample(entrants, k=min(winner_count, len(entrants))) if entrants else []
        if chosen:
            mentions = ", ".join(f"<@{uid}>" for uid in chosen)
            await channel.send(f"🎉 Congratulations {mentions}! You won **{prize}**.")
        else:
            await channel.send(f"The giveaway for **{prize}** ended with no entries.")
        return True

    @giveaway.command(name="end", description="End a giveaway now.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def end(self, interaction: discord.Interaction, message_id: str):
        try:
            mid = int(message_id)
        except ValueError:
            return await interaction.response.send_message("Provide a valid giveaway message ID.", ephemeral=True)
        task = self.tasks.pop(mid, None)
        if task:
            task.cancel()
        ended = await self.finish_giveaway(mid)
        await interaction.response.send_message(
            "✅ Giveaway ended." if ended else "That giveaway wasn't found or already ended.",
            ephemeral=True,
        )

    @giveaway.command(name="cancel", description="Cancel a giveaway without choosing winners.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cancel(self, interaction: discord.Interaction, message_id: str):
        try:
            mid = int(message_id)
        except ValueError:
            return await interaction.response.send_message("Provide a valid giveaway message ID.", ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "UPDATE giveaway_history SET cancelled=1,ended=1 WHERE guild_id=? AND message_id=? AND ended=0",
                (interaction.guild.id, mid),
            )
            await db.commit()
        task = self.tasks.pop(mid, None)
        if task:
            task.cancel()
        await interaction.response.send_message(
            "✅ Giveaway cancelled." if cur.rowcount else "That active giveaway wasn't found.",
            ephemeral=True,
        )

    @giveaway.command(name="reroll", description="Pick a new winner from a finished giveaway.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reroll(self, interaction: discord.Interaction, message_id: str):
        try:
            mid = int(message_id)
        except ValueError:
            return await interaction.response.send_message("Provide a valid giveaway message ID.", ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id FROM giveaway_entries WHERE message_id=?",
                (mid,),
            ) as cur:
                entrants = [r[0] for r in await cur.fetchall()]
        if not entrants:
            return await interaction.response.send_message("No entrants were saved for that giveaway.", ephemeral=True)
        await interaction.response.send_message(f"🎉 New winner: <@{random.choice(entrants)}>")

    @giveaway.command(name="list", description="List recent giveaways.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def list_giveaways(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT message_id,prize,ends_at,ended,cancelled FROM giveaway_history "
                "WHERE guild_id=? ORDER BY message_id DESC LIMIT 15",
                (interaction.guild.id,),
            ) as cur:
                rows = await cur.fetchall()
        lines = []
        for mid, prize, ends_at, ended, cancelled in rows:
            status = "cancelled" if cancelled else ("ended" if ended else "active")
            lines.append(f"`{mid}` • **{prize[:60]}** • {status}")
        await interaction.response.send_message("\n".join(lines) or "No giveaways found.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Giveaways(bot))

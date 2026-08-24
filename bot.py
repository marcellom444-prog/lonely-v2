from __future__ import annotations

import asyncio
import traceback

import discord
from discord import app_commands
from discord.ext import commands

from config import DEFAULT_PREFIX, TOKEN
from db import init_db

INTENTS = discord.Intents.default()
INTENTS.guilds = True
INTENTS.members = True
INTENTS.message_content = True
INTENTS.presences = True
INTENTS.reactions = True
INTENTS.moderation = True

EXTENSIONS = [
    "cogs.moderation",
    "cogs.afk",
    "cogs.logging_cog",
    "cogs.greet_leave",
    "cogs.embeds",
    "cogs.vanity",
    "cogs.leveling",
    "cogs.booster_roles",
    "cogs.steal",
    "cogs.reactionroles",
    "cogs.giveaways",
    "cogs.media",
    "cogs.utility",
    "cogs.tickets",
    "cogs.autoresponse",
    "cogs.voice_system",
<<<<<<< HEAD
    "cogs.help",
=======
    "cogs.snipe",
            "cogs.help",
>>>>>>> be79980 (Update Lonely bot)
]


class LonelyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(DEFAULT_PREFIX),
            intents=INTENTS,
            help_command=None,
            case_insensitive=True,
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                roles=False,
                users=True,
                replied_user=False,
            ),
        )

    async def setup_hook(self):
        await init_db()
        failures: list[tuple[str, str]] = []

        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                print(f"✅ Loaded {ext}")
            except Exception as exc:
                failures.append((ext, f"{type(exc).__name__}: {exc}"))
                print(f"❌ Failed to load {ext}: {exc!r}")
                traceback.print_exc()

        if failures:
            print("\n⚠️ One or more extensions failed. Slash sync skipped so the error is easier to fix.")
            for ext, error in failures:
                print(f"   - {ext}: {error}")
            return

        try:
            synced = await self.tree.sync()
            print(f"✅ Synced {len(synced)} slash commands")
        except Exception as exc:
            print(f"❌ Slash sync failed: {exc!r}")
            traceback.print_exc()

    async def on_ready(self):
        print("=" * 60)
        print(f"✅ Lonely is online as {self.user}")
        print(f"🤖 Connected to {len(self.guilds)} guild(s)")
        print("=" * 60)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        error = getattr(error, "original", error)
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("You don't have permission to use that command.")
        if isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            return await ctx.send(f"Lonely is missing these permissions: `{missing}`")
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"Missing required argument: `{error.param.name}`")
        if isinstance(error, commands.BadArgument):
            return await ctx.send("I couldn't understand one of those arguments.")
        print(f"Prefix command error: {error!r}")
        traceback.print_exception(type(error), error, error.__traceback__)
        await ctx.send("Something went wrong while running that command. Check the console for the error.")


async def tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    original = getattr(error, "original", error)
    if isinstance(error, app_commands.MissingPermissions):
        message = "You don't have permission to use that command."
    elif isinstance(error, app_commands.BotMissingPermissions):
        message = f"Lonely is missing these permissions: `{', '.join(error.missing_permissions)}`"
    elif isinstance(error, app_commands.CommandOnCooldown):
        message = f"That command is on cooldown. Try again in **{error.retry_after:.1f}s**."
    elif isinstance(error, app_commands.TransformerError):
        message = "I couldn't understand one of the command options."
    else:
        print(f"Slash command error: {original!r}")
        traceback.print_exception(type(original), original, original.__traceback__)
        message = "Something went wrong while running that command. Check the console for the error."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass


async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is missing. Copy .env.example to .env and add your bot token.")

    async with LonelyBot() as bot:
        bot.tree.on_error = tree_error
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import io
import re

import aiohttp
import discord
from discord.ext import commands

CUSTOM_EMOJI = re.compile(r"<(a?):([A-Za-z0-9_]+):(\d+)>")


class Steal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def source_message(self, ctx: commands.Context):
        if ctx.message.reference and ctx.message.reference.message_id:
            try:
                return await ctx.channel.fetch_message(ctx.message.reference.message_id)
            except discord.HTTPException:
                return None
        return None

    async def add_emoji(self, guild: discord.Guild, animated: str, name: str, emoji_id: str, actor) -> discord.Emoji:
        ext = "gif" if animated else "png"
        url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}?quality=lossless"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise RuntimeError(f"download returned HTTP {response.status}")
                data = await response.read()
        return await guild.create_custom_emoji(name=name[:32], image=data, reason=f"Added by {actor}")

    @commands.group(name="steal", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_emojis_and_stickers=True)
    async def steal(self, ctx: commands.Context, new_name: str | None = None):
        source = await self.source_message(ctx)
        text = source.content if source else ""
        match = CUSTOM_EMOJI.search(text)
        if match:
            animated, name, emoji_id = match.groups()
            try:
                emoji = await self.add_emoji(ctx.guild, animated, new_name or name, emoji_id, ctx.author)
                return await ctx.send(f"✅ Added {emoji}.")
            except (discord.HTTPException, RuntimeError) as exc:
                return await ctx.send(f"I couldn't add that emoji: {exc}")

        if source and source.stickers:
            sticker = source.stickers[0]
            try:
                raw = await sticker.read()
                suffix = ".json" if sticker.format is discord.StickerFormatType.lottie else ".png"
                created = await ctx.guild.create_sticker(
                    name=(new_name or sticker.name)[:30],
                    description=(getattr(sticker, "description", None) or "Added with Lonely")[:100],
                    emoji="⭐",
                    file=discord.File(io.BytesIO(raw), filename=f"sticker{suffix}"),
                    reason=f"Added by {ctx.author}",
                )
                return await ctx.send(f"✅ Added sticker **{created.name}**.")
            except discord.HTTPException as exc:
                return await ctx.send(f"I couldn't add that sticker: {exc}")

        await ctx.send("Reply to a message containing a custom emoji or sticker.")

    @steal.command(name="bulk")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_emojis_and_stickers=True)
    async def bulk(self, ctx: commands.Context):
        source = await self.source_message(ctx)
        if not source:
            return await ctx.send("Reply to the message you want to bulk-steal from.")

        added, skipped = [], []
        found = []
        seen_ids = set()
        for match in CUSTOM_EMOJI.finditer(source.content):
            animated, name, emoji_id = match.groups()
            if emoji_id not in seen_ids:
                found.append((animated, name, emoji_id))
                seen_ids.add(emoji_id)

        for animated, name, emoji_id in found:
            try:
                emoji = await self.add_emoji(ctx.guild, animated, name, emoji_id, ctx.author)
                added.append(emoji.name)
            except discord.HTTPException:
                skipped.append(name)
            except RuntimeError:
                skipped.append(name)

        for sticker in source.stickers:
            try:
                raw = await sticker.read()
                suffix = ".json" if sticker.format is discord.StickerFormatType.lottie else ".png"
                created = await ctx.guild.create_sticker(
                    name=sticker.name[:30],
                    description=(getattr(sticker, "description", None) or "Added with Lonely")[:100],
                    emoji="⭐",
                    file=discord.File(io.BytesIO(raw), filename=f"sticker{suffix}"),
                    reason=f"Bulk added by {ctx.author}",
                )
                added.append(created.name)
            except discord.HTTPException:
                skipped.append(sticker.name)

        await ctx.send(
            f"✅ Added: {', '.join(added) or 'None'}\n"
            f"⏭️ Skipped/failed: {', '.join(skipped) or 'None'}"
        )


async def setup(bot):
    await bot.add_cog(Steal(bot))

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone

import discord
from discord.ext import commands


@dataclass
class SnipedMessage:
    author_id: int
    author_name: str
    author_avatar: str | None
    content: str
    channel_id: int
    created_at: datetime
    deleted_at: datetime
    attachments: list[str]


class Snipe(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Keep up to 10 deleted messages per channel.
        self.snipes: dict[int, deque[SnipedMessage]] = defaultdict(
            lambda: deque(maxlen=10)
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        attachments = [a.url for a in message.attachments]

        # Don't store completely empty messages.
        if not message.content and not attachments:
            return

        self.snipes[message.channel.id].appendleft(
            SnipedMessage(
                author_id=message.author.id,
                author_name=str(message.author),
                author_avatar=(
                    message.author.display_avatar.url
                    if getattr(message.author, "display_avatar", None)
                    else None
                ),
                content=message.content or "",
                channel_id=message.channel.id,
                created_at=message.created_at,
                deleted_at=datetime.now(timezone.utc),
                attachments=attachments,
            )
        )

    @commands.command(name="s", aliases=["snipe"])
    @commands.guild_only()
    async def snipe(self, ctx: commands.Context, index: int = 1):
        """Show a recently deleted message from this channel."""
        if index < 1 or index > 10:
            return await ctx.send("Use a snipe number from **1 to 10**.")

        entries = self.snipes.get(ctx.channel.id)
        if not entries:
            return await ctx.send("Nothing to snipe.")

        if index > len(entries):
            return await ctx.send(
                f"I only have **{len(entries)}** deleted message(s) saved here."
            )

        item = entries[index - 1]

        description = item.content.strip() or "*No text content.*"
        embed = discord.Embed(
            description=description[:4096],
            color=discord.Color(0x000000),
            timestamp=item.deleted_at,
        )
        embed.set_author(
            name=item.author_name,
            icon_url=item.author_avatar or discord.Embed.Empty,
        )
        embed.set_footer(
            text=f"Snipe {index}/{len(entries)} • User ID: {item.author_id}"
        )

        if item.attachments:
            first = item.attachments[0]
            lower = first.lower()
            if any(lower.split("?")[0].endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                embed.set_image(url=first)

            if len(item.attachments) > 1 or not embed.image.url:
                embed.add_field(
                    name="Attachments",
                    value="\n".join(item.attachments[:5])[:1024],
                    inline=False,
                )

        await ctx.send(embed=embed)

    @commands.command(name="cs", aliases=["clearsnipe"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def clear_snipe(self, ctx: commands.Context):
        """Clear stored deleted messages for the current channel."""
        count = len(self.snipes.get(ctx.channel.id, ()))
        self.snipes.pop(ctx.channel.id, None)
        await ctx.send(
            f"✅ Cleared **{count}** saved snipe{'s' if count != 1 else ''} "
            f"for {ctx.channel.mention}."
        )

    @clear_snipe.error
    async def clear_snipe_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need **Manage Messages**.")
            return
        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Snipe(bot))

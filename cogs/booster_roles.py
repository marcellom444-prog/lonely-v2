from __future__ import annotations

import discord
from discord.ext import commands
import aiosqlite

from config import DB_PATH


def parse_color(value: str | None):
    if not value:
        return discord.Color.default()
    try:
        return discord.Color(int(value.lstrip("#"), 16))
    except ValueError:
        return discord.Color.default()


class BoosterRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_role(self, ctx: commands.Context):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id FROM booster_roles WHERE guild_id=? AND owner_id=?",
                (ctx.guild.id, ctx.author.id),
            ) as cur:
                row = await cur.fetchone()

        role = ctx.guild.get_role(row[0]) if row else None
        if not role:
            await ctx.send("No booster role found.")
            return None
        return role

    @commands.group(name="br", invoke_without_command=True)
    @commands.guild_only()
    async def br(self, ctx: commands.Context):
        """Manage your booster role."""
        await ctx.send(
            "Booster role commands: `,br create`, `,br name`, `,br color`, "
            "`,br share`, `,br unshare`, `,br delete`"
        )

    @br.command(name="create")
    @commands.guild_only()
    async def br_create(self, ctx: commands.Context, name: str, color: str | None = None):
        if not isinstance(ctx.author, discord.Member) or ctx.author.premium_since is None:
            return await ctx.send("You need to boost this server first.")

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id FROM booster_roles WHERE guild_id=? AND owner_id=?",
                (ctx.guild.id, ctx.author.id),
            ) as cur:
                row = await cur.fetchone()

        if row and ctx.guild.get_role(row[0]):
            return await ctx.send("You already have a booster role.")

        try:
            role = await ctx.guild.create_role(
                name=name[:100],
                color=parse_color(color),
                reason=f"Booster role for {ctx.author}",
            )
        except discord.Forbidden:
            return await ctx.send("I don't have permission to create roles.")
        except discord.HTTPException as exc:
            return await ctx.send(f"I couldn't create that role: {exc}")

        try:
            await ctx.author.add_roles(role, reason="Booster role")
        except discord.Forbidden:
            try:
                await role.delete(reason="Could not assign booster role")
            except discord.HTTPException:
                pass
            return await ctx.send(
                "I created the role but couldn't assign it. Move Lonely's role higher and try again."
            )

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO booster_roles(guild_id,owner_id,role_id) VALUES(?,?,?)",
                (ctx.guild.id, ctx.author.id, role.id),
            )
            await db.commit()

        await ctx.send(f"Booster role created: {role.mention}")

    @br.command(name="delete")
    @commands.guild_only()
    async def br_delete(self, ctx: commands.Context):
        role = await self.get_role(ctx)
        if not role:
            return

        try:
            await role.delete(reason=f"Booster role deleted by {ctx.author}")
        except discord.Forbidden:
            return await ctx.send("I can't delete that role. Move Lonely's role above it.")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM booster_roles WHERE guild_id=? AND owner_id=?",
                (ctx.guild.id, ctx.author.id),
            )
            await db.commit()

        await ctx.send("Booster role deleted.")

    @br.command(name="color")
    @commands.guild_only()
    async def br_color(self, ctx: commands.Context, color: str):
        role = await self.get_role(ctx)
        if not role:
            return
        try:
            await role.edit(color=parse_color(color), reason=f"Updated by {ctx.author}")
        except discord.Forbidden:
            return await ctx.send("I can't edit that role. Move Lonely's role above it.")
        await ctx.send("Color updated.")

    @br.command(name="name")
    @commands.guild_only()
    async def br_name(self, ctx: commands.Context, *, name: str):
        role = await self.get_role(ctx)
        if not role:
            return
        try:
            await role.edit(name=name[:100], reason=f"Updated by {ctx.author}")
        except discord.Forbidden:
            return await ctx.send("I can't edit that role. Move Lonely's role above it.")
        await ctx.send("Name updated.")

    @br.command(name="share")
    @commands.guild_only()
    async def br_share(self, ctx: commands.Context, member: discord.Member):
        role = await self.get_role(ctx)
        if not role:
            return
        try:
            await member.add_roles(role, reason=f"Booster role shared by {ctx.author}")
        except discord.Forbidden:
            return await ctx.send("I can't assign that role. Move Lonely's role higher.")
        await ctx.send(f"Shared with {member.mention}.")

    @br.command(name="unshare")
    @commands.guild_only()
    async def br_unshare(self, ctx: commands.Context, member: discord.Member):
        role = await self.get_role(ctx)
        if not role:
            return
        try:
            await member.remove_roles(role, reason=f"Booster role unshared by {ctx.author}")
        except discord.Forbidden:
            return await ctx.send("I can't remove that role. Move Lonely's role higher.")
        await ctx.send(f"Removed from {member.mention}.")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since is not None and after.premium_since is None:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT role_id FROM booster_roles WHERE guild_id=? AND owner_id=?",
                    (after.guild.id, after.id),
                ) as cur:
                    row = await cur.fetchone()
                if not row:
                    return
                await db.execute(
                    "DELETE FROM booster_roles WHERE guild_id=? AND owner_id=?",
                    (after.guild.id, after.id),
                )
                await db.commit()
            role = after.guild.get_role(row[0])
            if role:
                try:
                    await role.delete(reason="Member stopped boosting")
                except discord.HTTPException:
                    pass


async def setup(bot):
    await bot.add_cog(BoosterRoles(bot))

from __future__ import annotations
import json
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from config import DB_PATH

async def load_embed(guild_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT data FROM embeds WHERE guild_id=? AND name=?", (guild_id, name.lower())) as cur:
            row = await cur.fetchone()
    return json.loads(row[0]) if row else None

async def save_embed(guild_id: int, name: str, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO embeds(guild_id,name,data) VALUES(?,?,?)",
            (guild_id, name.lower(), json.dumps(data))
        )
        await db.commit()

class EmbedAllModal(discord.ui.Modal, title="Edit Embed"):
    embed_title = discord.ui.TextInput(label="Title", required=False, max_length=256)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=False, max_length=4000)
    color = discord.ui.TextInput(label="Color hex", placeholder="#000000", required=False, max_length=7)
    footer = discord.ui.TextInput(label="Footer", required=False, max_length=2048)
    image = discord.ui.TextInput(label="Image URL", required=False)

    def __init__(self, guild_id: int, name: str, existing: dict):
        super().__init__()
        self.guild_id = guild_id
        self.name = name
        self.existing = existing
        self.embed_title.default = existing.get("title", "")
        self.description.default = existing.get("description", "")
        if existing.get("color") is not None:
            self.color.default = f"#{existing['color']:06x}"
        self.footer.default = (existing.get("footer") or {}).get("text", "")
        self.image.default = (existing.get("image") or {}).get("url", "")

    async def on_submit(self, interaction: discord.Interaction):
        d = dict(self.existing)
        d["title"] = str(self.embed_title) or None
        d["description"] = str(self.description) or None
        if str(self.color):
            value = str(self.color).lstrip("#")
            try:
                color = int(value, 16)
            except ValueError:
                return await interaction.response.send_message("Invalid color.", ephemeral=True)
            if not 0 <= color <= 0xFFFFFF:
                return await interaction.response.send_message("Color must be between #000000 and #FFFFFF.", ephemeral=True)
            d["color"] = color
        if str(self.footer):
            d["footer"] = {"text": str(self.footer)}
        else:
            d.pop("footer", None)
        if str(self.image):
            d["image"] = {"url": str(self.image)}
        else:
            d.pop("image", None)
        await save_embed(self.guild_id, self.name, d)
        await interaction.response.send_message(embed=discord.Embed.from_dict(d), ephemeral=True)

class Embeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    embed = app_commands.Group(name="embed", description="Create and manage saved embeds.")
    edit = app_commands.Group(name="edit", description="Edit an embed.", parent=embed)

    @embed.command(name="create")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def create(self, interaction: discord.Interaction, name: str):
        if await load_embed(interaction.guild.id, name):
            return await interaction.response.send_message("An embed with that name already exists.", ephemeral=True)
        data = {"title": name, "description": "Use `/embed edit all` or the field edit commands to customize me.", "color": 0x000000}
        await save_embed(interaction.guild.id, name, data)
        await interaction.response.send_message(f"Embed `{name}` created.", embed=discord.Embed.from_dict(data), ephemeral=True)

    @embed.command(name="delete")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete(self, interaction: discord.Interaction, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM embeds WHERE guild_id=? AND name=?", (interaction.guild.id, name.lower()))
            await db.commit()
        await interaction.response.send_message(f"Embed `{name}` deleted.", ephemeral=True)

    @embed.command(name="list")
    async def list_embeds(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name FROM embeds WHERE guild_id=? ORDER BY name", (interaction.guild.id,)) as cur:
                rows = await cur.fetchall()
        await interaction.response.send_message("Saved embeds: " + (", ".join(f"`{r[0]}`" for r in rows) if rows else "None"), ephemeral=True)

    @embed.command(name="show")
    async def show(self, interaction: discord.Interaction, name: str):
        d = await load_embed(interaction.guild.id, name)
        if not d:
            return await interaction.response.send_message("Embed not found.", ephemeral=True)
        await interaction.response.send_message(embed=discord.Embed.from_dict(d))

    @edit.command(name="all")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_all(self, interaction: discord.Interaction, name: str):
        d = await load_embed(interaction.guild.id, name)
        if not d:
            return await interaction.response.send_message("Embed not found.", ephemeral=True)
        await interaction.response.send_modal(EmbedAllModal(interaction.guild.id, name.lower(), d))

    async def edit_field(self, interaction, name, updater):
        d = await load_embed(interaction.guild.id, name)
        if not d:
            return await interaction.response.send_message("Embed not found.", ephemeral=True)
        updater(d)
        await save_embed(interaction.guild.id, name, d)
        await interaction.response.send_message(embed=discord.Embed.from_dict(d), ephemeral=True)

    @edit.command(name="title")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_title(self, interaction: discord.Interaction, name: str, value: str):
        await self.edit_field(interaction, name, lambda d: d.__setitem__("title", value))

    @edit.command(name="description")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_description(self, interaction: discord.Interaction, name: str, value: str):
        await self.edit_field(interaction, name, lambda d: d.__setitem__("description", value))

    @edit.command(name="color")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_color(self, interaction: discord.Interaction, name: str, hex: str):
        try:
            color = int(hex.lstrip("#"), 16)
        except ValueError:
            return await interaction.response.send_message("Invalid color.", ephemeral=True)
        if not 0 <= color <= 0xFFFFFF:
            return await interaction.response.send_message("Color must be between #000000 and #FFFFFF.", ephemeral=True)
        await self.edit_field(interaction, name, lambda d: d.__setitem__("color", color))

    @edit.command(name="author")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_author(self, interaction: discord.Interaction, name: str, author: str, icon_url: str | None = None):
        await self.edit_field(interaction, name, lambda d: d.__setitem__("author", {"name": author, **({"icon_url": icon_url} if icon_url else {})}))

    @edit.command(name="footer")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_footer(self, interaction: discord.Interaction, name: str, footer: str, icon_url: str | None = None):
        await self.edit_field(interaction, name, lambda d: d.__setitem__("footer", {"text": footer, **({"icon_url": icon_url} if icon_url else {})}))

    @edit.command(name="image")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_image(self, interaction: discord.Interaction, name: str, url: str):
        await self.edit_field(interaction, name, lambda d: d.__setitem__("image", {"url": url}))

    @edit.command(name="thumbnail")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_thumbnail(self, interaction: discord.Interaction, name: str, url: str):
        await self.edit_field(interaction, name, lambda d: d.__setitem__("thumbnail", {"url": url}))

    @edit.command(name="timestamp")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_timestamp(self, interaction: discord.Interaction, name: str, enabled: bool = True):
        from datetime import datetime, timezone
        def upd(d):
            if enabled:
                d["timestamp"] = datetime.now(timezone.utc).isoformat()
            else:
                d.pop("timestamp", None)
        await self.edit_field(interaction, name, upd)

async def setup(bot):
    await bot.add_cog(Embeds(bot))

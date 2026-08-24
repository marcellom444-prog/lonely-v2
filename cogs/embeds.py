from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from config import DB_PATH


def valid_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def clean_embed_data(data: dict) -> dict:
    """Remove malformed values that can make Discord reject an embed."""
    d = dict(data or {})

    for key in ("image", "thumbnail"):
        obj = d.get(key)
        if not isinstance(obj, dict) or not valid_url(obj.get("url")):
            d.pop(key, None)

    for key in ("author", "footer"):
        obj = d.get(key)
        if isinstance(obj, dict):
            icon = obj.get("icon_url")
            if icon and not valid_url(icon):
                obj = dict(obj)
                obj.pop("icon_url", None)
                d[key] = obj

    if d.get("url") and not valid_url(d.get("url")):
        d.pop("url", None)

    # Discord does not like explicit None values in several embed fields.
    for key in ("title", "description"):
        if d.get(key) is None:
            d.pop(key, None)

    return d


async def load_embed(guild_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT data FROM embeds WHERE guild_id=? AND name=?",
            (guild_id, name.lower()),
        ) as cur:
            row = await cur.fetchone()

    if not row:
        return None

    try:
        data = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return None

    cleaned = clean_embed_data(data)

    # Repair old saved embeds automatically if they contain bad URL data.
    if cleaned != data:
        await save_embed(guild_id, name, cleaned)

    return cleaned


async def save_embed(guild_id: int, name: str, data: dict):
    data = clean_embed_data(data)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO embeds(guild_id,name,data) VALUES(?,?,?)",
            (guild_id, name.lower(), json.dumps(data)),
        )
        await db.commit()


async def send_preview(interaction: discord.Interaction, data: dict, message: str = "Updated."):
    try:
        embed = discord.Embed.from_dict(clean_embed_data(data))
        if interaction.response.is_done():
            await interaction.followup.send(message, embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(message, embed=embed, ephemeral=True)
    except discord.HTTPException as exc:
        error = f"{type(exc).__name__}: {exc}"
        if len(error) > 1500:
            error = error[:1500] + "..."
        if interaction.response.is_done():
            await interaction.followup.send(f"Embed error:\n```py\n{error}\n```", ephemeral=True)
        else:
            await interaction.response.send_message(f"Embed error:\n```py\n{error}\n```", ephemeral=True)


class EmbedAllModal(discord.ui.Modal, title="Edit Embed"):
    embed_title = discord.ui.TextInput(label="Title", required=False, max_length=256)
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=4000,
    )
    color = discord.ui.TextInput(
        label="Color hex",
        placeholder="#000000",
        required=False,
        max_length=7,
    )
    footer = discord.ui.TextInput(label="Footer", required=False, max_length=2048)
    image = discord.ui.TextInput(label="Image URL", required=False)

    def __init__(self, guild_id: int, name: str, existing: dict):
        super().__init__()
        self.guild_id = guild_id
        self.name = name
        self.existing = clean_embed_data(existing)

        self.embed_title.default = self.existing.get("title", "")
        self.description.default = self.existing.get("description", "")

        if self.existing.get("color") is not None:
            self.color.default = f"#{self.existing['color']:06x}"

        self.footer.default = (self.existing.get("footer") or {}).get("text", "")
        self.image.default = (self.existing.get("image") or {}).get("url", "")

    async def on_submit(self, interaction: discord.Interaction):
        d = dict(self.existing)

        title = str(self.embed_title).strip()
        description = str(self.description).strip()
        footer = str(self.footer).strip()
        image = str(self.image).strip()
        color_text = str(self.color).strip()

        if title:
            d["title"] = title
        else:
            d.pop("title", None)

        if description:
            d["description"] = description
        else:
            d.pop("description", None)

        if color_text:
            try:
                color = int(color_text.lstrip("#"), 16)
            except ValueError:
                return await interaction.response.send_message("Invalid color.", ephemeral=True)

            if not 0 <= color <= 0xFFFFFF:
                return await interaction.response.send_message(
                    "Color must be between #000000 and #FFFFFF.",
                    ephemeral=True,
                )
            d["color"] = color

        if footer:
            d["footer"] = {"text": footer}
        else:
            d.pop("footer", None)

        if image:
            if not valid_url(image):
                return await interaction.response.send_message(
                    "Invalid image URL. Use a full http:// or https:// link.",
                    ephemeral=True,
                )
            d["image"] = {"url": image}
        else:
            d.pop("image", None)

        await save_embed(self.guild_id, self.name, d)
        await send_preview(interaction, d)


class Embeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    embed = app_commands.Group(
        name="embed",
        description="Create and manage saved embeds.",
    )
    edit = app_commands.Group(
        name="edit",
        description="Edit an embed.",
        parent=embed,
    )

    @embed.command(name="create", description="Create a saved embed.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def create(self, interaction: discord.Interaction, name: str):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )

        name = name.strip()
        if not name:
            return await interaction.response.send_message(
                "Enter an embed name.",
                ephemeral=True,
            )

        if await load_embed(interaction.guild.id, name):
            return await interaction.response.send_message(
                "An embed with that name already exists.",
                ephemeral=True,
            )

        data = {
            "title": name,
            "description": "Use the embed edit commands to customize this embed.",
            "color": 0x000000,
        }
        await save_embed(interaction.guild.id, name, data)
        await send_preview(interaction, data, f"Embed `{name}` created.")

    @embed.command(name="delete", description="Delete a saved embed.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete(self, interaction: discord.Interaction, name: str):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )

        if not await load_embed(interaction.guild.id, name):
            return await interaction.response.send_message("Embed not found.", ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM embeds WHERE guild_id=? AND name=?",
                (interaction.guild.id, name.lower()),
            )
            await db.commit()

        await interaction.response.send_message(
            f"Embed `{name}` deleted.",
            ephemeral=True,
        )

    @embed.command(name="list", description="List saved embeds.")
    async def list_embeds(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT name FROM embeds WHERE guild_id=? ORDER BY name",
                (interaction.guild.id,),
            ) as cur:
                rows = await cur.fetchall()

        content = ", ".join(f"`{row[0]}`" for row in rows) if rows else "None"
        await interaction.response.send_message(
            f"Saved embeds: {content}",
            ephemeral=True,
        )

    @embed.command(name="show", description="Send a saved embed.")
    @app_commands.describe(
        name="Saved embed name",
        channel="Channel to send the embed to",
    )
    async def show(
        self,
        interaction: discord.Interaction,
        name: str,
        channel: discord.TextChannel | None = None,
    ):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )

        data = await load_embed(interaction.guild.id, name)
        if not data:
            return await interaction.response.send_message(
                "Embed not found.",
                ephemeral=True,
            )

        target = channel or interaction.channel
        if not isinstance(target, discord.abc.Messageable):
            return await interaction.response.send_message(
                "Choose a text channel.",
                ephemeral=True,
            )

        if channel is not None:
            user_perms = channel.permissions_for(interaction.user)
            if not user_perms.send_messages:
                return await interaction.response.send_message(
                    "You can't send messages in that channel.",
                    ephemeral=True,
                )

            me = interaction.guild.me
            bot_perms = channel.permissions_for(me)
            if not bot_perms.send_messages or not bot_perms.embed_links:
                return await interaction.response.send_message(
                    "I need Send Messages and Embed Links in that channel.",
                    ephemeral=True,
                )

        try:
            await target.send(embed=discord.Embed.from_dict(clean_embed_data(data)))
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I can't send embeds in that channel.",
                ephemeral=True,
            )
        except discord.HTTPException as exc:
            error = f"{type(exc).__name__}: {exc}"
            if len(error) > 1500:
                error = error[:1500] + "..."
            return await interaction.response.send_message(
                f"Embed error:\n```py\n{error}\n```",
                ephemeral=True,
            )

        if channel is None:
            await interaction.response.send_message("Embed sent.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"Embed sent to {channel.mention}.",
                ephemeral=True,
            )

    @edit.command(name="all", description="Edit the main embed fields.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_all(self, interaction: discord.Interaction, name: str):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )

        data = await load_embed(interaction.guild.id, name)
        if not data:
            return await interaction.response.send_message("Embed not found.", ephemeral=True)

        await interaction.response.send_modal(
            EmbedAllModal(interaction.guild.id, name.lower(), data)
        )

    async def edit_field(self, interaction: discord.Interaction, name: str, updater):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )

        data = await load_embed(interaction.guild.id, name)
        if not data:
            return await interaction.response.send_message("Embed not found.", ephemeral=True)

        updater(data)
        data = clean_embed_data(data)
        await save_embed(interaction.guild.id, name, data)
        await send_preview(interaction, data)

    @edit.command(name="title", description="Edit the embed title.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_title(self, interaction: discord.Interaction, name: str, value: str):
        await self.edit_field(
            interaction,
            name,
            lambda d: d.__setitem__("title", value[:256]),
        )

    @edit.command(name="description", description="Edit the embed description.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_description(self, interaction: discord.Interaction, name: str, value: str):
        await self.edit_field(
            interaction,
            name,
            lambda d: d.__setitem__("description", value[:4096]),
        )

    @edit.command(name="color", description="Edit the embed color.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_color(self, interaction: discord.Interaction, name: str, hex: str):
        value = hex.strip().lstrip("#")
        if len(value) not in {3, 6}:
            return await interaction.response.send_message(
                "Invalid color. Use a hex color like #000000.",
                ephemeral=True,
            )

        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)

        try:
            color = int(value, 16)
        except ValueError:
            return await interaction.response.send_message(
                "Invalid color. Use a hex color like #000000.",
                ephemeral=True,
            )

        await self.edit_field(
            interaction,
            name,
            lambda d: d.__setitem__("color", color),
        )

    @edit.command(name="author", description="Edit the embed author.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_author(
        self,
        interaction: discord.Interaction,
        name: str,
        author: str,
        icon_url: str | None = None,
    ):
        if icon_url and not valid_url(icon_url):
            return await interaction.response.send_message(
                "Invalid icon URL. Use a full http:// or https:// link.",
                ephemeral=True,
            )

        author_data = {"name": author[:256]}
        if icon_url:
            author_data["icon_url"] = icon_url.strip()

        await self.edit_field(
            interaction,
            name,
            lambda d: d.__setitem__("author", author_data),
        )

    @edit.command(name="footer", description="Edit the embed footer.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_footer(
        self,
        interaction: discord.Interaction,
        name: str,
        footer: str,
        icon_url: str | None = None,
    ):
        if icon_url and not valid_url(icon_url):
            return await interaction.response.send_message(
                "Invalid icon URL. Use a full http:// or https:// link.",
                ephemeral=True,
            )

        footer_data = {"text": footer[:2048]}
        if icon_url:
            footer_data["icon_url"] = icon_url.strip()

        await self.edit_field(
            interaction,
            name,
            lambda d: d.__setitem__("footer", footer_data),
        )

    @edit.command(name="image", description="Set the embed image.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_image(self, interaction: discord.Interaction, name: str, url: str):
        url = url.strip()

        if url.lower() in {"none", "remove", "clear"}:
            await self.edit_field(interaction, name, lambda d: d.pop("image", None))
            return

        if not valid_url(url):
            return await interaction.response.send_message(
                "Invalid image URL. Use a full http:// or https:// link.",
                ephemeral=True,
            )

        await self.edit_field(
            interaction,
            name,
            lambda d: d.__setitem__("image", {"url": url}),
        )

    @edit.command(name="thumbnail", description="Set the embed thumbnail.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_thumbnail(self, interaction: discord.Interaction, name: str, url: str):
        url = url.strip()

        if url.lower() in {"none", "remove", "clear"}:
            await self.edit_field(interaction, name, lambda d: d.pop("thumbnail", None))
            return

        if not valid_url(url):
            return await interaction.response.send_message(
                "Invalid thumbnail URL. Use a full http:// or https:// link.",
                ephemeral=True,
            )

        await self.edit_field(
            interaction,
            name,
            lambda d: d.__setitem__("thumbnail", {"url": url}),
        )

    @edit.command(name="timestamp", description="Turn the embed timestamp on or off.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_timestamp(
        self,
        interaction: discord.Interaction,
        name: str,
        enabled: bool = True,
    ):
        def update(data: dict):
            if enabled:
                data["timestamp"] = datetime.now(timezone.utc).isoformat()
            else:
                data.pop("timestamp", None)

        await self.edit_field(interaction, name, update)


async def setup(bot):
    await bot.add_cog(Embeds(bot))

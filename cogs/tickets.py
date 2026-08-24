from __future__ import annotations

import io
import json
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

from config import DB_PATH
from db import get_settings, patch_settings


def build_ticket_embed(settings: dict, panel: bool = True) -> discord.Embed:
    prefix = "ticket_panel_" if panel else "ticket_open_"

    title = settings.get(prefix + "title")
    description = settings.get(prefix + "description")
    color_value = settings.get(prefix + "color", 0x000000)

    if not title:
        title = "Support Tickets" if panel else "Ticket"
    if not description:
        description = (
            "Click the button below to open a private ticket."
            if panel
            else "A staff member will be with you shortly."
        )

    try:
        color = discord.Color(int(color_value))
    except Exception:
        color = discord.Color(0x000000)

    embed = discord.Embed(title=title, description=description, color=color)

    thumbnail = settings.get(prefix + "thumbnail")
    image = settings.get(prefix + "image")
    footer = settings.get(prefix + "footer")

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
    if footer:
        embed.set_footer(text=footer)

    return embed


class TicketEmbedModal(discord.ui.Modal, title="Customize Ticket Embed"):
    embed_title = discord.ui.TextInput(
        label="Title",
        required=False,
        max_length=256,
        placeholder="Support Tickets",
    )
    description = discord.ui.TextInput(
        label="Description",
        required=False,
        max_length=4000,
        style=discord.TextStyle.paragraph,
        placeholder="Click the button below to open a ticket.",
    )
    color = discord.ui.TextInput(
        label="Color",
        required=False,
        max_length=7,
        placeholder="#000000",
    )
    footer = discord.ui.TextInput(
        label="Footer",
        required=False,
        max_length=2048,
    )
    image = discord.ui.TextInput(
        label="Image URL",
        required=False,
        max_length=1000,
    )

    def __init__(self, guild_id: int, panel: bool, settings: dict):
        super().__init__()
        self.guild_id = guild_id
        self.panel = panel
        prefix = "ticket_panel_" if panel else "ticket_open_"

        self.embed_title.default = settings.get(prefix + "title") or ""
        self.description.default = settings.get(prefix + "description") or ""

        color_value = settings.get(prefix + "color")
        if color_value is not None:
            try:
                self.color.default = f"#{int(color_value):06x}"
            except Exception:
                pass

        self.footer.default = settings.get(prefix + "footer") or ""
        self.image.default = settings.get(prefix + "image") or ""

    async def on_submit(self, interaction: discord.Interaction):
        prefix = "ticket_panel_" if self.panel else "ticket_open_"

        color_value = 0x000000
        if str(self.color).strip():
            try:
                color_value = int(str(self.color).strip().lstrip("#"), 16)
            except ValueError:
                return await interaction.response.send_message(
                    "That color isn't valid. Use a hex color like `#000000`.",
                    ephemeral=True,
                )

        updates = {
            prefix + "title": str(self.embed_title).strip() or None,
            prefix + "description": str(self.description).strip() or None,
            prefix + "color": color_value,
            prefix + "footer": str(self.footer).strip() or None,
            prefix + "image": str(self.image).strip() or None,
        }

        await patch_settings(self.guild_id, **updates)
        settings = await get_settings(self.guild_id)

        embed = build_ticket_embed(settings, panel=self.panel)
        await interaction.response.send_message(
            "Ticket embed updated.",
            embed=embed,
            ephemeral=True,
        )


class TicketPanel(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Open Ticket",
        emoji="🎫",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:open",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog.create_ticket(interaction)


class TicketControls(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:claim",
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE tickets SET claimed_by=? WHERE channel_id=?",
                (interaction.user.id, interaction.channel.id),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Ticket claimed by {interaction.user.mention}."
        )

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:close",
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.cog.close_ticket(interaction.channel, interaction.user)
        except RuntimeError as exc:
            return await interaction.followup.send(
                f"❌ {exc}",
                ephemeral=True,
            )


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ticket = app_commands.Group(
        name="ticket",
        description="Ticket system.",
    )

    async def cog_load(self):
        self.bot.add_view(TicketPanel(self))
        self.bot.add_view(TicketControls(self))

    @ticket.command(name="setup", description="Set up the ticket system.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_ticket(
        self,
        interaction: discord.Interaction,
        panel_channel: discord.TextChannel,
        staff_role: discord.Role,
        auto_transcripts: bool = False,
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category(
                "Tickets",
                reason="Ticket setup",
            )

        transcript_channel = None
        if auto_transcripts:
            transcript_channel = discord.utils.get(
                guild.text_channels,
                name="ticket-transcripts",
            )
            if not transcript_channel:
                transcript_channel = await guild.create_text_channel(
                    "ticket-transcripts",
                    reason="Automatic ticket transcript storage",
                )

        await patch_settings(
            guild.id,
            ticket_category=category.id,
            ticket_staff_role=staff_role.id,
            ticket_panel_channel=panel_channel.id,
            ticket_transcripts_enabled=auto_transcripts,
            ticket_transcript_channel=(
                transcript_channel.id if transcript_channel else None
            ),
        )

        settings = await get_settings(guild.id)
        embed = build_ticket_embed(settings, panel=True)

        await panel_channel.send(
            embed=embed,
            view=TicketPanel(self),
        )

        await interaction.followup.send(
            "Ticket system ready.",
            ephemeral=True,
        )

    @ticket.command(
        name="panel",
        description="Customize the public ticket panel embed.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        settings = await get_settings(interaction.guild.id)
        await interaction.response.send_modal(
            TicketEmbedModal(
                interaction.guild.id,
                panel=True,
                settings=settings,
            )
        )

    @ticket.command(
        name="message",
        description="Customize the embed shown inside new tickets.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_message(self, interaction: discord.Interaction):
        settings = await get_settings(interaction.guild.id)
        await interaction.response.send_modal(
            TicketEmbedModal(
                interaction.guild.id,
                panel=False,
                settings=settings,
            )
        )

    @ticket.command(
        name="thumbnail",
        description="Set or clear the ticket panel thumbnail.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_thumbnail(
        self,
        interaction: discord.Interaction,
        url: str | None = None,
    ):
        await patch_settings(
            interaction.guild.id,
            ticket_panel_thumbnail=url,
        )
        await interaction.response.send_message(
            "Thumbnail updated.",
            ephemeral=True,
        )

    @ticket.command(
        name="preview",
        description="Preview the current ticket embeds.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_preview(
        self,
        interaction: discord.Interaction,
    ):
        settings = await get_settings(interaction.guild.id)
        panel_embed = build_ticket_embed(settings, panel=True)
        open_embed = build_ticket_embed(settings, panel=False)

        await interaction.response.send_message(
            content="**Panel preview:**",
            embed=panel_embed,
            ephemeral=True,
        )
        await interaction.followup.send(
            content="**New ticket preview:**",
            embed=open_embed,
            ephemeral=True,
        )

    async def create_ticket(self, interaction: discord.Interaction):
        settings = await get_settings(interaction.guild.id)
        category = interaction.guild.get_channel(
            settings.get("ticket_category", 0)
        )
        staff = interaction.guild.get_role(
            settings.get("ticket_staff_role", 0)
        )

        if not category or not staff:
            return await interaction.response.send_message(
                "Ticket system isn't set up.",
                ephemeral=True,
            )

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COALESCE(MAX(number), 0) FROM tickets WHERE guild_id=?",
                (interaction.guild.id,),
            ) as cur:
                current = (await cur.fetchone())[0]
                number = current + 1

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
            staff: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
        }

        channel = await interaction.guild.create_text_channel(
            f"ticket-{number:04d}",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket for {interaction.user}",
        )

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO tickets(guild_id,channel_id,opener_id,number,status) "
                "VALUES(?,?,?,?, 'open')",
                (
                    interaction.guild.id,
                    channel.id,
                    interaction.user.id,
                    number,
                ),
            )
            await db.commit()

        embed = build_ticket_embed(settings, panel=False)
        if embed.title == "Ticket":
            embed.title = f"Ticket #{number:04d}"

        if embed.description:
            embed.description = (
                embed.description
                .replace("{user}", str(interaction.user))
                .replace("{user.mention}", interaction.user.mention)
                .replace("{ticket}", channel.name)
                .replace("{ticket.number}", str(number))
                .replace("{server}", interaction.guild.name)
            )

        await channel.send(
            content=f"{interaction.user.mention} {staff.mention}",
            embed=embed,
            view=TicketControls(self),
        )

        await interaction.response.send_message(
            f"Ticket: {channel.mention}",
            ephemeral=True,
        )

    async def close_ticket(
        self,
        channel: discord.TextChannel,
        closer: discord.Member,
    ):
        settings = await get_settings(channel.guild.id)
        transcript = []

        async for msg in channel.history(limit=None, oldest_first=True):
            transcript.append(
                f"[{msg.created_at.isoformat()}] "
                f"{msg.author} ({msg.author.id}): {msg.clean_content}"
            )

        data = "\n".join(transcript).encode("utf-8")

        # If automatic transcripts are enabled, save the transcript first.
        # The ticket is only deleted after the transcript is safely posted.
        if settings.get("ticket_transcripts_enabled"):
            out = channel.guild.get_channel(
                settings.get("ticket_transcript_channel", 0)
            )

            # Recover automatically if the configured transcript channel
            # was deleted after ticket setup.
            if out is None:
                out = discord.utils.get(
                    channel.guild.text_channels,
                    name="ticket-transcripts",
                )
                if out is None:
                    out = await channel.guild.create_text_channel(
                        "ticket-transcripts",
                        reason="Restore automatic ticket transcript storage",
                    )
                await patch_settings(
                    channel.guild.id,
                    ticket_transcript_channel=out.id,
                )

            try:
                await out.send(
                    f"Transcript for **#{channel.name}** • closed by {closer.mention}",
                    file=discord.File(
                        io.BytesIO(data),
                        filename=f"{channel.name}.txt",
                    ),
                )
            except discord.HTTPException as exc:
                # Do not delete the ticket if its requested transcript
                # could not be saved.
                raise RuntimeError(
                    f"I couldn't save the transcript, so I did not delete the ticket: {exc}"
                ) from exc

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE tickets SET status='closed' WHERE channel_id=?",
                (channel.id,),
            )
            await db.commit()

        # Closing a ticket now removes the channel automatically.
        try:
            await channel.delete(
                reason=f"Ticket closed by {closer}",
            )
        except discord.Forbidden as exc:
            raise RuntimeError(
                "I couldn't delete the ticket channel. Make sure Lonely has Manage Channels."
            ) from exc

    @ticket.command(name="close", description="Close the current ticket.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def close_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.close_ticket(
                interaction.channel,
                interaction.user,
            )
        except RuntimeError as exc:
            return await interaction.followup.send(
                f"❌ {exc}",
                ephemeral=True,
            )

    @ticket.command(
        name="adduser",
        description="Add a member to the current ticket.",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def adduser(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        await interaction.channel.set_permissions(
            member,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        )
        await interaction.response.send_message(
            f"Added {member.mention}.",
            ephemeral=True,
        )

    @ticket.command(
        name="removeuser",
        description="Remove a member from the current ticket.",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def removeuser(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        await interaction.channel.set_permissions(
            member,
            overwrite=None,
        )
        await interaction.response.send_message(
            f"Removed {member.mention}.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Tickets(bot))

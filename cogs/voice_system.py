from __future__ import annotations

import asyncio
import os
import tempfile
import time
from collections import defaultdict, deque
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

from config import DB_PATH
from db import get_settings, patch_settings


async def ensure_voice_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS j2c_channels (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                control_message_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS tts_settings (
                guild_id INTEGER PRIMARY KEY,
                text_channel_id INTEGER,
                auto_read INTEGER NOT NULL DEFAULT 0,
                voice TEXT NOT NULL DEFAULT 'en-US-GuyNeural',
                rate TEXT NOT NULL DEFAULT '+0%'
            );
            """
        )
        await db.commit()


class RenameVoiceModal(discord.ui.Modal, title="Rename Voice Channel"):
    name_input = discord.ui.TextInput(
        label="New channel name",
        max_length=100,
        placeholder="gaming",
    )

    def __init__(self, cog: "VoiceSystem", channel_id: int):
        super().__init__()
        self.cog = cog
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return await interaction.response.send_message(
                "That temporary voice channel no longer exists.",
                ephemeral=True,
            )
        if not await self.cog.is_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "Only the voice channel owner can rename it.",
                ephemeral=True,
            )
        await channel.edit(name=str(self.name_input).strip()[:100])
        await self.cog.refresh_control_panel(channel)
        await interaction.response.send_message(
            f"✅ Renamed the channel to **{channel.name}**.",
            ephemeral=True,
        )


class LimitVoiceModal(discord.ui.Modal, title="Set User Limit"):
    limit_input = discord.ui.TextInput(
        label="User limit",
        placeholder="0 = unlimited",
        max_length=2,
    )

    def __init__(self, cog: "VoiceSystem", channel_id: int):
        super().__init__()
        self.cog = cog
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return await interaction.response.send_message(
                "That temporary voice channel no longer exists.",
                ephemeral=True,
            )
        if not await self.cog.is_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "Only the voice channel owner can change the limit.",
                ephemeral=True,
            )
        try:
            limit = int(str(self.limit_input).strip())
        except ValueError:
            return await interaction.response.send_message(
                "Enter a number from 0 to 99.",
                ephemeral=True,
            )
        if not 0 <= limit <= 99:
            return await interaction.response.send_message(
                "Enter a number from 0 to 99.",
                ephemeral=True,
            )
        await channel.edit(user_limit=limit)
        await self.cog.refresh_control_panel(channel)
        await interaction.response.send_message(
            f"✅ User limit set to **{limit or 'unlimited'}**.",
            ephemeral=True,
        )


class VoiceAccessSelect(discord.ui.Select):
    def __init__(self, cog: "VoiceSystem", channel_id: int):
        self.cog = cog
        self.channel_id = channel_id
        options = [
            discord.SelectOption(
                label="Lock Channel",
                value="lock",
                emoji="🔒",
                description="Prevent new members from joining.",
            ),
            discord.SelectOption(
                label="Unlock Channel",
                value="unlock",
                emoji="🔓",
                description="Allow members to join again.",
            ),
            discord.SelectOption(
                label="Hide Channel",
                value="hide",
                emoji="🙈",
                description="Hide the voice channel from everyone else.",
            ),
            discord.SelectOption(
                label="Reveal Channel",
                value="reveal",
                emoji="👁️",
                description="Make the voice channel visible again.",
            ),
        ]
        super().__init__(
            placeholder="Access controls",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"lonely:j2c:access:{channel_id}",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return await interaction.response.send_message(
                "This temporary voice channel no longer exists.",
                ephemeral=True,
            )
        if not await self.cog.is_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "Only the voice channel owner can use these controls.",
                ephemeral=True,
            )

        overwrite = channel.overwrites_for(interaction.guild.default_role)
        action = self.values[0]

        if action == "lock":
            overwrite.connect = False
            await channel.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite,
                reason=f"J2C locked by {interaction.user}",
            )
            message = "🔒 Voice channel locked."
        elif action == "unlock":
            overwrite.connect = None
            await channel.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite,
                reason=f"J2C unlocked by {interaction.user}",
            )
            message = "🔓 Voice channel unlocked."
        elif action == "hide":
            overwrite.view_channel = False
            await channel.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite,
                reason=f"J2C hidden by {interaction.user}",
            )
            message = "🙈 Voice channel hidden."
        else:
            overwrite.view_channel = None
            await channel.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite,
                reason=f"J2C revealed by {interaction.user}",
            )
            message = "👁️ Voice channel revealed."

        await self.cog.refresh_control_panel(channel)
        await interaction.response.send_message(message, ephemeral=True)


class VoiceManageSelect(discord.ui.Select):
    def __init__(self, cog: "VoiceSystem", channel_id: int):
        self.cog = cog
        self.channel_id = channel_id
        options = [
            discord.SelectOption(
                label="Rename",
                value="rename",
                emoji="✏️",
                description="Change the temporary channel name.",
            ),
            discord.SelectOption(
                label="User Limit",
                value="limit",
                emoji="👥",
                description="Set how many users can join.",
            ),
            discord.SelectOption(
                label="Claim Ownership",
                value="claim",
                emoji="👑",
                description="Claim the channel if its owner left.",
            ),
        ]
        super().__init__(
            placeholder="Channel management",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"lonely:j2c:manage:{channel_id}",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return await interaction.response.send_message(
                "This temporary voice channel no longer exists.",
                ephemeral=True,
            )

        action = self.values[0]

        if action == "claim":
            owner_id = await self.cog.get_owner_id(channel.id)
            owner = interaction.guild.get_member(owner_id) if owner_id else None

            if owner and owner in channel.members:
                return await interaction.response.send_message(
                    "The current owner is still in the voice channel.",
                    ephemeral=True,
                )
            if interaction.user not in channel.members:
                return await interaction.response.send_message(
                    "Join the voice channel before claiming it.",
                    ephemeral=True,
                )

            await self.cog.set_owner(channel, interaction.user)
            await self.cog.refresh_control_panel(channel)
            return await interaction.response.send_message(
                f"👑 {interaction.user.mention} now owns this voice channel.",
                ephemeral=True,
            )

        if not await self.cog.is_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "Only the voice channel owner can use this control.",
                ephemeral=True,
            )

        if action == "rename":
            return await interaction.response.send_modal(
                RenameVoiceModal(self.cog, self.channel_id)
            )

        if action == "limit":
            return await interaction.response.send_modal(
                LimitVoiceModal(self.cog, self.channel_id)
            )


class VoiceControlView(discord.ui.View):
    def __init__(self, cog: "VoiceSystem", channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id
        self.add_item(VoiceAccessSelect(cog, channel_id))
        self.add_item(VoiceManageSelect(cog, channel_id))

    @discord.ui.button(
        label="Refresh",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="lonely:j2c:refresh",
        row=2,
    )
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.guild.get_channel(self.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return await interaction.response.send_message(
                "This temporary voice channel no longer exists.",
                ephemeral=True,
            )
        await self.cog.refresh_control_panel(channel)
        await interaction.response.send_message(
            "✅ Voice panel refreshed.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Delete Channel",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="lonely:j2c:delete",
        row=2,
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.guild.get_channel(self.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return await interaction.response.send_message(
                "This temporary voice channel no longer exists.",
                ephemeral=True,
            )
        if not await self.cog.is_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "Only the voice channel owner can delete it.",
                ephemeral=True,
            )
        await interaction.response.send_message(
            "🗑️ Deleting voice channel…",
            ephemeral=True,
        )
        await self.cog.delete_temp_channel(channel)


class VoiceSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tts_queues: dict[int, deque[str]] = defaultdict(deque)
        self.tts_workers: dict[int, asyncio.Task] = {}
        self.tts_last_use: dict[tuple[int, int], float] = {}

    def build_control_embed(self, channel: discord.VoiceChannel, owner: Optional[discord.Member]) -> discord.Embed:
        default_overwrite = channel.overwrites_for(channel.guild.default_role)

        locked = default_overwrite.connect is False
        hidden = default_overwrite.view_channel is False
        limit = channel.user_limit if channel.user_limit else "Unlimited"

        owner_text = owner.mention if owner else "Owner left — channel can be claimed"
        members_text = f"{len(channel.members)} connected"

        embed = discord.Embed(
            title="Voice Channel Control",
            description=(
                "Manage your temporary voice channel from the menus below.\n"
                "Only the current owner can change channel settings."
            ),
            color=discord.Color(0x000000),
        )
        embed.add_field(name="Owner", value=owner_text, inline=True)
        embed.add_field(name="Members", value=members_text, inline=True)
        embed.add_field(name="User Limit", value=str(limit), inline=True)
        embed.add_field(
            name="Access",
            value="🔒 Locked" if locked else "🔓 Unlocked",
            inline=True,
        )
        embed.add_field(
            name="Visibility",
            value="🙈 Hidden" if hidden else "👁️ Visible",
            inline=True,
        )
        embed.add_field(
            name="Channel",
            value=channel.mention,
            inline=True,
        )
        embed.set_footer(text="Use Refresh after making changes if you want the latest status.")
        return embed

    async def get_control_message_id(self, channel_id: int) -> Optional[int]:
        async with aiosqlite.connect(DB_PATH) as db:
            try:
                async with db.execute(
                    "SELECT control_message_id FROM j2c_channels WHERE channel_id=?",
                    (channel_id,),
                ) as cur:
                    row = await cur.fetchone()
            except aiosqlite.OperationalError:
                return None
        return row[0] if row and row[0] else None

    async def set_control_message_id(self, channel_id: int, message_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            try:
                await db.execute(
                    "ALTER TABLE j2c_channels ADD COLUMN control_message_id INTEGER"
                )
                await db.commit()
            except aiosqlite.OperationalError:
                pass

            await db.execute(
                "UPDATE j2c_channels SET control_message_id=? WHERE channel_id=?",
                (message_id, channel_id),
            )
            await db.commit()

    async def refresh_control_panel(self, channel: discord.VoiceChannel):
        owner_id = await self.get_owner_id(channel.id)
        owner = channel.guild.get_member(owner_id) if owner_id else None
        embed = self.build_control_embed(channel, owner)
        message_id = await self.get_control_message_id(channel.id)

        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(
                    embed=embed,
                    view=VoiceControlView(self, channel.id),
                )
                return
            except discord.HTTPException:
                pass

        try:
            message = await channel.send(
                embed=embed,
                view=VoiceControlView(self, channel.id),
            )
            await self.set_control_message_id(channel.id, message.id)
        except discord.HTTPException:
            pass

    j2c = app_commands.Group(name="j2c", description="Join-to-create voice system.")
    tts = app_commands.Group(name="tts", description="Text-to-speech voice commands.")

    async def cog_load(self):
        await ensure_voice_tables()

    async def get_owner_id(self, channel_id: int) -> Optional[int]:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT owner_id FROM j2c_channels WHERE channel_id=?",
                (channel_id,),
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row else None

    async def is_owner(self, member: discord.Member, channel: discord.VoiceChannel) -> bool:
        owner_id = await self.get_owner_id(channel.id)
        return owner_id == member.id or member.guild_permissions.administrator

    async def set_owner(self, channel: discord.VoiceChannel, member: discord.Member):
        old_owner_id = await self.get_owner_id(channel.id)
        old_owner = channel.guild.get_member(old_owner_id) if old_owner_id else None

        if old_owner:
            old_overwrite = channel.overwrites_for(old_owner)
            old_overwrite.manage_channels = None
            old_overwrite.move_members = None
            await channel.set_permissions(old_owner, overwrite=old_overwrite)

        new_overwrite = channel.overwrites_for(member)
        new_overwrite.view_channel = True
        new_overwrite.connect = True
        new_overwrite.speak = True
        new_overwrite.manage_channels = True
        new_overwrite.move_members = True
        await channel.set_permissions(member, overwrite=new_overwrite)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE j2c_channels SET owner_id=? WHERE channel_id=?",
                (member.id, channel.id),
            )
            await db.commit()

    async def delete_temp_channel(self, channel: discord.VoiceChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM j2c_channels WHERE channel_id=?",
                (channel.id,),
            )
            await db.commit()
        try:
            await channel.delete(reason="Temporary voice channel removed")
        except discord.HTTPException:
            pass

    @j2c.command(name="setup", description="Create or configure the join-to-create lobby.")
    @app_commands.checks.has_permissions(administrator=True)
    async def j2c_setup(
        self,
        interaction: discord.Interaction,
        lobby_name: str = "Join to Create",
        category_name: str = "Voice Channels",
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        settings = await get_settings(guild.id)
        old_category = guild.get_channel(settings.get("j2c_category", 0))
        category = old_category if isinstance(old_category, discord.CategoryChannel) else None
        if category is None:
            category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            category = await guild.create_category(category_name, reason="J2C setup")

        old_lobby = guild.get_channel(settings.get("j2c_lobby", 0))
        lobby = old_lobby if isinstance(old_lobby, discord.VoiceChannel) else None
        if lobby is None:
            lobby = discord.utils.get(category.voice_channels, name=lobby_name)
        if lobby is None:
            lobby = await guild.create_voice_channel(
                lobby_name,
                category=category,
                reason="J2C setup",
            )

        await patch_settings(
            guild.id,
            j2c_enabled=True,
            j2c_category=category.id,
            j2c_lobby=lobby.id,
        )
        await interaction.followup.send(
            f"✅ J2C is ready.\nJoin **{lobby.name}** to create a temporary voice channel.",
            ephemeral=True,
        )

    @j2c.command(name="disable", description="Disable join-to-create.")
    @app_commands.checks.has_permissions(administrator=True)
    async def j2c_disable(self, interaction: discord.Interaction):
        await patch_settings(interaction.guild.id, j2c_enabled=False)
        await interaction.response.send_message("✅ J2C disabled.", ephemeral=True)

    @j2c.command(name="status", description="Show join-to-create settings.")
    async def j2c_status(self, interaction: discord.Interaction):
        settings = await get_settings(interaction.guild.id)
        lobby = interaction.guild.get_channel(settings.get("j2c_lobby", 0))
        category = interaction.guild.get_channel(settings.get("j2c_category", 0))
        await interaction.response.send_message(
            f"Enabled: **{bool(settings.get('j2c_enabled'))}**\n"
            f"Lobby: **{getattr(lobby, 'name', 'Not set')}**\n"
            f"Category: **{getattr(category, 'name', 'Not set')}**",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        settings = await get_settings(member.guild.id)
        lobby_id = settings.get("j2c_lobby")

        if (
            settings.get("j2c_enabled")
            and after.channel
            and after.channel.id == lobby_id
        ):
            category = member.guild.get_channel(settings.get("j2c_category", 0))
            if not isinstance(category, discord.CategoryChannel):
                category = after.channel.category

            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                ),
                member: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    manage_channels=True,
                    move_members=True,
                ),
                member.guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    manage_channels=True,
                    move_members=True,
                ),
            }

            try:
                temp = await member.guild.create_voice_channel(
                    f"{member.display_name}'s channel",
                    category=category,
                    overwrites=overwrites,
                    reason=f"J2C channel for {member}",
                )
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "INSERT OR REPLACE INTO j2c_channels(guild_id,channel_id,owner_id,created_at) "
                        "VALUES(?,?,?,?)",
                        (member.guild.id, temp.id, member.id, int(time.time())),
                    )
                    await db.commit()

                await member.move_to(temp, reason="J2C channel created")

                await self.refresh_control_panel(temp)
            except discord.HTTPException:
                pass

        # Delete temporary J2C channels when empty.
        candidate = before.channel
        if candidate and candidate.id != lobby_id:
            owner_id = await self.get_owner_id(candidate.id)
            if owner_id and len(candidate.members) == 0:
                await self.delete_temp_channel(candidate)
            elif owner_id:
                owner = member.guild.get_member(owner_id)
                if owner and owner not in candidate.members and candidate.members:
                    # Ownership remains claimable; do not force-transfer.
                    pass

    # -------------------------
    # TTS
    # -------------------------

    async def get_tts_row(self, guild_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT text_channel_id,auto_read,voice,rate FROM tts_settings WHERE guild_id=?",
                (guild_id,),
            ) as cur:
                return await cur.fetchone()

    async def save_tts_settings(
        self,
        guild_id: int,
        text_channel_id: Optional[int] = None,
        auto_read: Optional[bool] = None,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
    ):
        row = await self.get_tts_row(guild_id)
        current = {
            "text_channel_id": row[0] if row else None,
            "auto_read": bool(row[1]) if row else False,
            "voice": row[2] if row else "en-US-GuyNeural",
            "rate": row[3] if row else "+0%",
        }
        if text_channel_id is not None:
            current["text_channel_id"] = text_channel_id
        if auto_read is not None:
            current["auto_read"] = bool(auto_read)
        if voice is not None:
            current["voice"] = voice
        if rate is not None:
            current["rate"] = rate

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO tts_settings(guild_id,text_channel_id,auto_read,voice,rate) "
                "VALUES(?,?,?,?,?) "
                "ON CONFLICT(guild_id) DO UPDATE SET "
                "text_channel_id=excluded.text_channel_id, "
                "auto_read=excluded.auto_read, "
                "voice=excluded.voice, "
                "rate=excluded.rate",
                (
                    guild_id,
                    current["text_channel_id"],
                    int(current["auto_read"]),
                    current["voice"],
                    current["rate"],
                ),
            )
            await db.commit()

    async def ensure_connected(self, member: discord.Member) -> discord.VoiceClient:
        if not member.voice or not member.voice.channel:
            raise RuntimeError("Join a voice channel first.")

        target = member.voice.channel
        vc = member.guild.voice_client

        if vc and vc.is_connected():
            if vc.channel.id != target.id:
                await vc.move_to(target)
            return vc

        return await target.connect(reconnect=True)

    async def synthesize(self, guild_id: int, text: str) -> str:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "The `edge-tts` package is missing. Run `python3 -m pip install -r requirements.txt`."
            ) from exc

        row = await self.get_tts_row(guild_id)
        voice = row[2] if row else "en-US-GuyNeural"
        rate = row[3] if row else "+0%"

        fd, path = tempfile.mkstemp(prefix="lonely_tts_", suffix=".mp3")
        os.close(fd)

        communicate = edge_tts.Communicate(
            text=text[:500],
            voice=voice,
            rate=rate,
        )
        await communicate.save(path)
        return path

    async def queue_tts(self, guild: discord.Guild, text: str):
        self.tts_queues[guild.id].append(text[:500])
        task = self.tts_workers.get(guild.id)
        if task is None or task.done():
            self.tts_workers[guild.id] = asyncio.create_task(
                self.tts_worker(guild)
            )

    async def tts_worker(self, guild: discord.Guild):
        queue = self.tts_queues[guild.id]
        while queue:
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                queue.clear()
                return

            text = queue.popleft()
            path = None
            try:
                path = await self.synthesize(guild.id, text)

                while vc.is_playing() or vc.is_paused():
                    await asyncio.sleep(0.1)

                done = asyncio.Event()

                def after(error):
                    self.bot.loop.call_soon_threadsafe(done.set)

                source = discord.FFmpegPCMAudio(
                    path,
                    options="-vn",
                )
                vc.play(source, after=after)
                await done.wait()
            except Exception:
                pass
            finally:
                if path:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    @tts.command(name="join", description="Join your voice channel and link TTS to this text channel.")
    async def tts_join(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            vc = await self.ensure_connected(interaction.user)
            await self.save_tts_settings(
                interaction.guild.id,
                text_channel_id=interaction.channel.id,
                auto_read=True,
            )
            await interaction.followup.send(
                f"✅ TTS joined **{vc.channel.name}**.\n"
                f"Messages sent in {interaction.channel.mention} will now be read aloud automatically.",
                ephemeral=True,
            )
        except RuntimeError as exc:
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @tts.command(name="say", description="Speak text in your current voice channel.")
    async def tts_say(
        self,
        interaction: discord.Interaction,
        text: app_commands.Range[str, 1, 500],
    ):
        key = (interaction.guild.id, interaction.user.id)
        now = time.monotonic()
        if now - self.tts_last_use.get(key, 0) < 2.0:
            return await interaction.response.send_message(
                "You're using TTS too quickly. Try again in a moment.",
                ephemeral=True,
            )
        self.tts_last_use[key] = now

        try:
            await interaction.response.defer(ephemeral=True)
            await self.ensure_connected(interaction.user)
            await self.queue_tts(interaction.guild, text)
            await interaction.followup.send("🔊 Added to the TTS queue.", ephemeral=True)
        except RuntimeError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)

    @tts.command(name="auto", description="Automatically read messages from the linked text channel.")
    async def tts_auto(self, interaction: discord.Interaction, enabled: bool):
        if enabled:
            try:
                await self.ensure_connected(interaction.user)
            except RuntimeError as exc:
                return await interaction.response.send_message(
                    f"❌ {exc}",
                    ephemeral=True,
                )
            await self.save_tts_settings(
                interaction.guild.id,
                text_channel_id=interaction.channel.id,
                auto_read=True,
            )
            await interaction.response.send_message(
                "✅ Auto TTS enabled. Messages sent in this channel will be read in voice.",
                ephemeral=True,
            )
        else:
            await self.save_tts_settings(
                interaction.guild.id,
                auto_read=False,
            )
            await interaction.response.send_message(
                "✅ Auto TTS disabled.",
                ephemeral=True,
            )

    @tts.command(name="voice", description="Choose a built-in TTS voice.")
    @app_commands.choices(
        voice=[
            app_commands.Choice(name="Male 1", value="en-US-GuyNeural"),
            app_commands.Choice(name="Male 2", value="en-US-ChristopherNeural"),
            app_commands.Choice(name="Female 1", value="en-US-JennyNeural"),
            app_commands.Choice(name="Female 2", value="en-US-AriaNeural"),
            app_commands.Choice(name="British Male", value="en-GB-RyanNeural"),
            app_commands.Choice(name="British Female", value="en-GB-SoniaNeural"),
        ]
    )
    async def tts_voice(
        self,
        interaction: discord.Interaction,
        voice: app_commands.Choice[str],
    ):
        await self.save_tts_settings(
            interaction.guild.id,
            voice=voice.value,
        )
        await interaction.response.send_message(
            f"✅ TTS voice set to **{voice.name}**.",
            ephemeral=True,
        )

    @tts.command(name="speed", description="Set TTS speaking speed.")
    @app_commands.choices(
        speed=[
            app_commands.Choice(name="Slow", value="-20%"),
            app_commands.Choice(name="Normal", value="+0%"),
            app_commands.Choice(name="Fast", value="+20%"),
            app_commands.Choice(name="Very Fast", value="+40%"),
        ]
    )
    async def tts_speed(
        self,
        interaction: discord.Interaction,
        speed: app_commands.Choice[str],
    ):
        await self.save_tts_settings(
            interaction.guild.id,
            rate=speed.value,
        )
        await interaction.response.send_message(
            f"✅ TTS speed set to **{speed.name}**.",
            ephemeral=True,
        )

    @tts.command(name="skip", description="Skip the current TTS message.")
    async def tts_skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped the current TTS message.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)

    @tts.command(name="stop", description="Stop the current TTS audio and clear the queue.")
    async def tts_stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        self.tts_queues[interaction.guild.id].clear()
        if vc and vc.is_playing():
            vc.stop()
        await interaction.response.send_message(
            "⏹️ TTS stopped and the queue was cleared.",
            ephemeral=True,
        )

    @tts.command(name="clear", description="Clear waiting TTS messages without disconnecting.")
    async def tts_clear(self, interaction: discord.Interaction):
        self.tts_queues[interaction.guild.id].clear()
        await interaction.response.send_message("🧹 Cleared the TTS queue.", ephemeral=True)

    @tts.command(name="leave", description="Disconnect TTS from voice.")
    async def tts_leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        self.tts_queues[interaction.guild.id].clear()
        await self.save_tts_settings(
            interaction.guild.id,
            text_channel_id=interaction.channel.id,
            auto_read=False,
        )
        if not vc or not vc.is_connected():
            return await interaction.response.send_message(
                "I'm not connected to voice.",
                ephemeral=True,
            )
        await vc.disconnect(force=True)
        await interaction.response.send_message(
            "👋 TTS left the voice channel.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            not message.guild
            or message.author.bot
            or not message.content.strip()
        ):
            return

        row = await self.get_tts_row(message.guild.id)
        if not row:
            return

        text_channel_id, auto_read, _, _ = row
        if not auto_read or message.channel.id != text_channel_id:
            return

        vc = message.guild.voice_client
        if not vc or not vc.is_connected():
            return

        member = message.guild.get_member(message.author.id)
        if not member or not member.voice or member.voice.channel != vc.channel:
            return

        key = (message.guild.id, message.author.id)
        now = time.monotonic()
        if now - self.tts_last_use.get(key, 0) < 1.5:
            return
        self.tts_last_use[key] = now

        clean = message.clean_content.strip()

        # Don't read commands or obvious bot-control messages aloud.
        if clean.startswith((",", "/", "!", ".", "?")):
            return

        # Keep the voice queue responsive if chat suddenly gets spammy.
        queue = self.tts_queues[message.guild.id]
        if len(queue) >= 8:
            return

        # Avoid reading a bare URL character-by-character style.
        lowered = clean.lower()
        if lowered.startswith(("http://", "https://")) and " " not in clean:
            clean = "sent a link"

        await self.queue_tts(message.guild, clean)


async def setup(bot):
    await bot.add_cog(VoiceSystem(bot))

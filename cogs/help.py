from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


SLASH_CATEGORIES = {
    "Moderation": {
        "emoji": "🛡️",
        "commands": [
            "ban", "unban", "kick", "timeout", "untimeout", "warn", "warnings",
            "clearwarnings", "purge", "slowmode", "lock", "unlock", "nick",
            "hardban", "unhardban", "moddms", "logging",
        ],
    },
    "Server Systems": {
        "emoji": "⚙️",
        "commands": [
            "afk", "greet", "leave", "embed", "vanity", "rank", "leaderboard",
            "levels", "reactionrole", "giveaway", "ticket", "autoresponse",
            "j2c", "tts",
        ],
    },
    "Utility": {
        "emoji": "🧰",
        "commands": [
            "userinfo", "serverinfo", "avatar", "banner", "roleinfo",
            "channelinfo", "membercount", "botinfo", "ping", "timestamp",
            "say", "servericon", "serverbanner",
        ],
    },
    "Media": {
        "emoji": "🖼️",
        "commands": ["media"],
    },
}

PREFIX_COMMANDS = [
    ("`,afk [reason]`", "Set AFK."),
    ("`,a [reason]`", "Short AFK alias."),
    ("`,br create <name> [color]`", "Create a booster role."),
    ("`,br name <name>`", "Rename your booster role."),
    ("`,br color <hex>`", "Change booster role color."),
    ("`,br share @user`", "Share your booster role."),
    ("`,br unshare @user`", "Remove your booster role from someone."),
    ("`,br delete`", "Delete your booster role."),
    ("`,steal`", "Steal an emoji or sticker from a replied message."),
    ("`,steal bulk`", "Bulk steal supported emojis from a replied message."),
    ("`,s`", "Show the latest deleted message."),
    ("`,s 2` - `,s 10`", "Show older deleted messages."),
    ("`,cs`", "Clear saved snipes in the channel."),
]


def slash_lines(bot: commands.Bot, names: list[str]) -> list[str]:
    lines = []
    seen = set()

    for cmd in bot.tree.walk_commands():
        if isinstance(cmd, app_commands.Group):
            continue

        top = cmd.qualified_name.split()[0]
        if top not in names:
            continue

        label = f"/{cmd.qualified_name}"
        if label in seen:
            continue
        seen.add(label)

        description = (cmd.description or "No description.").strip()
        lines.append(f"`{label}` — {description}")

    return lines


class HelpSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label=name,
                value=name,
                emoji=data["emoji"],
            )
            for name, data in SLASH_CATEGORIES.items()
        ]
        options.append(
            discord.SelectOption(
                label="Prefix Commands",
                value="Prefix Commands",
                emoji="⌨️",
            )
        )

        super().__init__(
            placeholder="Pick a category",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]

        if selected == "Prefix Commands":
            description = "\n".join(
                f"{name} — {desc}"
                for name, desc in PREFIX_COMMANDS
            )
            embed = discord.Embed(
                title="Help • Prefix Commands",
                description=description,
                color=discord.Color(0x000000),
            )
            embed.set_footer(text="Default prefix: ,")
            return await interaction.response.edit_message(
                embed=embed,
                view=self.view,
            )

        data = SLASH_CATEGORIES[selected]
        lines = slash_lines(self.bot, data["commands"])

        embed = discord.Embed(
            title=f"Help • {selected}",
            description="\n".join(lines) if lines else "No commands found.",
            color=discord.Color(0x000000),
        )
        embed.set_footer(text="Use the menu to switch categories.")

        await interaction.response.edit_message(
            embed=embed,
            view=self.view,
        )


class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(bot))


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="View Lonely commands.",
    )
    async def help(self, interaction: discord.Interaction):
        slash_count = sum(
            1
            for cmd in self.bot.tree.walk_commands()
            if not isinstance(cmd, app_commands.Group)
        )

        embed = discord.Embed(
            title="Lonely Help",
            description=(
                f"Pick a category below.\n"
                f"**{slash_count} slash commands** + **{len(PREFIX_COMMANDS)} prefix entries**"
            ),
            color=discord.Color(0x000000),
        )
        embed.add_field(
            name="Categories",
            value="Moderation • Server Systems • Utility • Media • Prefix Commands",
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed,
            view=HelpView(self.bot),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))

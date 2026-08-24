from __future__ import annotations
import discord

COLOR = discord.Color(0x000000)

def embed(text: str, *, title: str | None = None) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=text,
        color=COLOR,
    )

async def send_interaction(interaction: discord.Interaction, text: str, *, ephemeral: bool = False):
    payload = {"embed": embed(text), "ephemeral": ephemeral}
    if interaction.response.is_done():
        return await interaction.followup.send(**payload)
    return await interaction.response.send_message(**payload)

async def send_ctx(ctx, text: str):
    return await ctx.send(embed=embed(text))

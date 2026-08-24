from __future__ import annotations

import io
import os

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageSequence

FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def get_font(size: int):
    for path in FONT_PATHS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrapped_lines(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= width - 40:
            current = test
        else:
            if current:
                lines.append(current)
            # Break extremely long single words rather than overflowing.
            if draw.textbbox((0, 0), word, font=font)[2] > width - 40:
                chunk = ""
                for char in word:
                    trial = chunk + char
                    if draw.textbbox((0, 0), trial, font=font)[2] <= width - 40:
                        chunk = trial
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = char
                current = chunk
            else:
                current = word
    if current:
        lines.append(current)
    return lines


def fit_text(text: str, width: int):
    test_image = Image.new("RGB", (max(width, 1), 100), "white")
    draw = ImageDraw.Draw(test_image)
    size = max(28, min(64, width // 10))
    while size >= 18:
        font = get_font(size)
        lines = wrapped_lines(draw, text, font, width)
        if len(lines) <= 6:
            return font, lines
        size -= 4
    font = get_font(18)
    return font, wrapped_lines(draw, text, font, width)[:8]


def prepare_frame(frame: Image.Image, max_width: int = 1280) -> Image.Image:
    base = frame.convert("RGBA")
    if base.width > max_width:
        ratio = max_width / base.width
        base = base.resize((max_width, max(1, int(base.height * ratio))), Image.Resampling.LANCZOS)
    return base


def caption_gif(raw: bytes, caption: str) -> bytes:
    src = Image.open(io.BytesIO(raw))
    animated = bool(getattr(src, "is_animated", False))
    frame_count = int(getattr(src, "n_frames", 1))
    # Limit extremely long animations to keep memory and Discord upload size reasonable.
    step = max(1, frame_count // 120) if animated else 1

    frames: list[Image.Image] = []
    durations: list[int] = []
    for index, frame in enumerate(ImageSequence.Iterator(src)):
        if index % step:
            continue
        base = prepare_frame(frame)
        width, height = base.size
        font, lines = fit_text(caption, width)
        font_size = getattr(font, "size", 24)
        line_height = max(30, font_size + 8)
        banner_height = max(56, 28 + line_height * len(lines))

        canvas = Image.new("RGBA", (width, height + banner_height), "white")
        draw = ImageDraw.Draw(canvas)
        y = 14
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = max(10, (width - text_width) // 2)
            draw.text((x, y), line, fill="black", font=font)
            y += line_height
        canvas.alpha_composite(base, (0, banner_height))
        frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE))
        duration = int(frame.info.get("duration", 80 if animated else 1000)) * step
        durations.append(max(20, duration))

    if not frames:
        raise ValueError("No readable image frames were found.")

    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        optimize=True,
    )
    return output.getvalue()


class Media(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    media = app_commands.Group(name="media", description="Media tools.")

    @media.command(name="caption", description="Add a white top caption with bold black text and output a GIF.")
    async def caption(
        self,
        interaction: discord.Interaction,
        caption: str,
        attachment: discord.Attachment,
    ):
        await interaction.response.defer()
        if attachment.size > 25 * 1024 * 1024:
            return await interaction.followup.send("That file is too large to process. Please use a file under 25 MB.")
        if not caption.strip():
            return await interaction.followup.send("Caption text can't be empty.")
        raw = await attachment.read()
        try:
            result = caption_gif(raw, caption.strip())
        except Exception as exc:
            return await interaction.followup.send(f"I couldn't process that image or GIF: {exc}")

        # Keep a little safety room for servers with lower upload limits.
        if len(result) > 10 * 1024 * 1024:
            return await interaction.followup.send(
                "The finished GIF is too large to upload. Try a shorter or smaller source GIF."
            )
        await interaction.followup.send(file=discord.File(io.BytesIO(result), filename="caption.gif"))


async def setup(bot):
    await bot.add_cog(Media(bot))

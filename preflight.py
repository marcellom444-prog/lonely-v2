from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


async def main():
    print("Lonely preflight check")
    print("=" * 60)

    required = ["discord", "aiosqlite", "dotenv", "PIL", "aiohttp"]
    missing = []
    for module in required:
        try:
            importlib.import_module(module)
            print(f"✅ Import: {module}")
        except Exception as exc:
            missing.append(module)
            print(f"❌ Import: {module} — {exc}")

    if missing:
        print("\nInstall requirements first:")
        print("python3 -m pip install -r requirements.txt")
        raise SystemExit(1)

    import discord
    from discord.ext import commands
    from db import init_db
    from bot import EXTENSIONS, INTENTS

    await init_db()
    print("✅ Database schema/migrations")

    bot = commands.Bot(command_prefix=",", intents=INTENTS, help_command=None)
    bot.preflight_mode = True
    failures = []
    try:
        async with bot:
            for extension in EXTENSIONS:
                try:
                    await bot.load_extension(extension)
                    print(f"✅ Extension: {extension}")
                except Exception as exc:
                    failures.append((extension, exc))
                    print(f"❌ Extension: {extension} — {type(exc).__name__}: {exc}")

            slash = list(bot.tree.walk_commands())
            prefix = list(bot.walk_commands())
            print(f"✅ Registered slash/group commands: {len(slash)}")
            print(f"✅ Registered prefix/group commands: {len(prefix)}")
    finally:
        try:
            await bot.close()
        except Exception:
            pass

    if failures:
        print("\n❌ Preflight failed. Fix the extension errors above before starting Lonely.")
        raise SystemExit(1)

    print("\n✅ Preflight passed. You can run: python3 bot.py")


if __name__ == "__main__":
    asyncio.run(main())

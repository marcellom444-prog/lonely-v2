from __future__ import annotations

import json
import aiosqlite

from config import DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    data TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hardbans (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS afk (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT,
    since TEXT NOT NULL,
    old_nick TEXT,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS embeds (
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (guild_id, name)
);

CREATE TABLE IF NOT EXISTS xp (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS reaction_roles (
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    emoji TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'toggle',
    PRIMARY KEY (guild_id, message_id, emoji)
);

CREATE TABLE IF NOT EXISTS autoresponses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    trigger TEXT NOT NULL,
    response TEXT NOT NULL,
    exact INTEGER NOT NULL DEFAULT 0,
    case_sensitive INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    cooldown_seconds INTEGER NOT NULL DEFAULT 0,
    delete_trigger INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS booster_roles (
    guild_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, owner_id)
);

CREATE TABLE IF NOT EXISTS tickets (
    guild_id INTEGER NOT NULL,
    channel_id INTEGER PRIMARY KEY,
    opener_id INTEGER NOT NULL,
    number INTEGER NOT NULL,
    claimed_by INTEGER,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS giveaway_history (
    guild_id INTEGER NOT NULL,
    message_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    host_id INTEGER NOT NULL,
    prize TEXT NOT NULL,
    winners INTEGER NOT NULL,
    ends_at TEXT NOT NULL,
    ended INTEGER NOT NULL DEFAULT 0,
    cancelled INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS giveaway_entries (
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_warnings_guild_user ON warnings(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_xp_guild_rank ON xp(guild_id, level DESC, xp DESC);
CREATE INDEX IF NOT EXISTS idx_autoresponses_guild ON autoresponses(guild_id, enabled);
CREATE INDEX IF NOT EXISTS idx_tickets_guild_opener ON tickets(guild_id, opener_id, status);
"""


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, declaration: str):
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        columns = {row[1] for row in await cur.fetchall()}
    if column not in columns:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        # Safe migrations for databases created by earlier Lonely builds.
        await _ensure_column(db, "tickets", "created_at", "TEXT")
        await _ensure_column(db, "giveaway_history", "cancelled", "INTEGER NOT NULL DEFAULT 0")
        await db.commit()


async def get_settings(guild_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT data FROM guild_settings WHERE guild_id=?", (guild_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        return {}
    try:
        value = json.loads(row[0])
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


async def save_settings(guild_id: int, data: dict):
    payload = json.dumps(data)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO guild_settings(guild_id,data) VALUES(?,?) "
            "ON CONFLICT(guild_id) DO UPDATE SET data=excluded.data",
            (guild_id, payload),
        )
        await db.commit()


async def patch_settings(guild_id: int, **updates):
    data = await get_settings(guild_id)
    data.update(updates)
    await save_settings(guild_id, data)
    return data

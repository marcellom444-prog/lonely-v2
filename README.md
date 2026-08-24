# Lonely

Lonely is a modular all-in-one Discord bot built with Python and discord.py.

## Included systems

- Moderation: ban, unban, kick, timeout, warnings, purge, slowmode, lock/unlock, nickname tools, and role tools
- Persistent hardban system
- Optional moderation DM notifications
- AFK: `/afk`, `,afk`, `,a`, mention notices, automatic return handling, and nickname restoration
- Logging for moderation, messages, members, channels, and roles
- Greet and leave systems with placeholders and saved embeds
- Saved embed system with `/embed create`, `/embed delete`, `/embed edit ...`, `/embed list`, and `/embed show`
- Vanity status reward system
- Leveling and leaderboard
- Booster roles
- Emoji and sticker stealing with bulk support
- Reaction roles
- Persistent giveaways with saved entries and restart recovery
- Media captioning with a white top banner, bold black text, and GIF-only output
- Utility commands
- Ticket system with private ticket channels and optional automatic transcript channel creation
- Auto responses that post directly into the channel
- `/help` category menu

## 1. Install packages

Open Terminal inside the Lonely folder and run:

```bash
python3 -m pip install -r requirements.txt
```

## 2. Create `.env`

```bash
cp .env.example .env
```

Then put your token inside `.env`:

```env
DISCORD_TOKEN=YOUR_TOKEN_HERE
DEFAULT_PREFIX=,
```

Do not share your bot token.

## 3. Discord Developer Portal

Enable these Privileged Gateway Intents:

- Server Members Intent
- Message Content Intent
- Presence Intent

Presence Intent is required for the vanity system.

## 4. Bot permissions

Lonely needs the permissions required by the systems you use, including:

- Manage Roles
- Manage Channels
- Manage Messages
- Kick Members
- Ban Members
- Moderate Members
- Manage Emojis and Stickers
- Read Message History
- Send Messages
- Embed Links
- Attach Files
- Add Reactions

Place Lonely's role above any roles and members it needs to manage.

## 5. Run the preflight check first

Before starting the bot, run:

```bash
python3 preflight.py
```

The preflight checker loads the database and every cog without logging into Discord. If every line passes, it ends with:

```text
✅ Preflight passed. You can run: python3 bot.py
```

If a cog has a load-time problem, preflight tells you which one before the bot starts.

## 6. Start Lonely

```bash
python3 bot.py
```

A healthy startup should show every cog loading, slash commands syncing, and Lonely coming online.


## Voice system

Lonely includes a join-to-create voice system.

### J2C commands

- `/j2c setup` — creates/configures the join-to-create lobby and category
- `/j2c status` — shows the current J2C setup
- `/j2c disable` — disables automatic temporary channel creation

When a member joins the J2C lobby, Lonely creates a temporary voice channel, moves the member into it, and posts a control panel in that voice channel's chat. The owner can lock/unlock, hide/reveal, rename, set a user limit, claim, or delete the channel. Empty temporary channels are deleted automatically.

### TTS commands

- `/tts join` — joins your voice channel, links the current text channel, and immediately enables normal-message TTS
- `/tts say` — speaks one message
- `/tts auto` — turns automatic reading of linked-channel messages on/off
- `/tts voice` — chooses a built-in voice
- `/tts speed` — changes speaking speed
- `/tts skip` — skips the current spoken message
- `/tts clear` — clears waiting messages
- `/tts stop` — stops audio and clears the queue
- `/tts status` — shows the connection and current TTS settings
- `/tts leave` — disconnects from voice

Auto TTS only reads a member's message when that member is in the same voice channel as Lonely.

### FFmpeg

TTS playback requires FFmpeg. On macOS with Homebrew:

```bash
brew install ffmpeg
```

Then install/update Python packages:

```bash
python3 -m pip install -r requirements.txt
```


### J2C control panel

Each temporary voice channel gets a polished control panel in its built-in text chat. The panel shows the current owner, member count, user limit, lock state, visibility state, and channel mention.

Controls are grouped into dropdown menus:
- Access controls: Lock, Unlock, Hide, Reveal
- Channel management: Rename, User Limit, Claim Ownership

It also includes Refresh and Delete Channel buttons.
<<<<<<< HEAD
=======


## Snipe commands

- `,s` — show the most recently deleted message in the current channel
- `,s 2` through `,s 10` — show older deleted messages
- `,cs` — clear the saved snipes for the current channel
- `,cs` requires Manage Messages


## Help menu

`/help` now includes all current slash-command categories plus a Prefix Commands page for:
`,afk`, `,a`, booster role commands, `,steal`, `,steal bulk`, `,s`, and `,cs`.
>>>>>>> be79980 (Update Lonely bot)

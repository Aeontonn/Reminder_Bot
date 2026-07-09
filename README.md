# Reminder Bot

A Discord bot that sends daily routine and medicine reminders to multiple
users, each in their own timezone and at their own chosen times. Built
with [discord.py](https://discordpy.readthedocs.io/).

Every user gets:

- A **morning checklist** DM with interactive checkboxes for today's
  recurring tasks (e.g. medicine) and any one-time tasks added the
  evening before.
- An **evening checklist** DM for any tasks specifically flagged to show
  up at night, plus a simple "did you get everything done?" check-in.
- A **streak counter** that goes up once a full day's tasks are all
  checked off.
- Full control over their own **timezone** and **reminder times** —
  handy when travelling, since it's just a chat command to switch and
  switch back.

All data (user IDs, timezones, tasks, streaks) is stored locally in
`data.json`, written atomically so a restart mid-write can't corrupt it.

## Commands

| Command | What it does |
|---|---|
| `!add [task]` | Add a one-time task, shown once on tomorrow's morning checklist, then cleared automatically. |
| `!add recurring [task]` | Add a task that stays on the checklist every day until removed with `!remove`. |
| `!add evening-only [task]` | Add a task that only shows up on the evening checklist. |
| `!add both-times [task]` | Add a task that shows up on both the morning and evening checklists (checking it off on one marks it done on the other too). |
| `!tasks` | List your current tasks, numbered, with checked status and tags for recurring / evening / both. |
| `!remove [number]` | Remove a task by the number shown in `!tasks`. |
| `!timezone [zone]` | Set or change your timezone, e.g. `!timezone Europe/Stockholm` or `!timezone Asia/Seoul`. |
| `!morningtime [HH:MM]` | Set what local time your morning checklist is sent (default `08:00`). |
| `!eveningtime [HH:MM]` | Set what local time your evening checklist/check-in is sent (default `20:00`). |
| `!settings` | Show everything saved for you: timezone, reminder times, task counts, streak. |
| `!help` | List all commands in Discord. |

`recurring`, `evening-only`/`both-times`, and an optional emoji can all
be combined in `!add`, in any order, e.g.:

```
!add recurring both-times 🚰 Drink water
```

## Project structure

```
bot.py                    # entry point: creates the bot, loads cogs, starts a tiny web server
storage.py                 # atomic read/write for data.json, per-user defaults and migration
views.py                    # interactive discord.ui checklist buttons (morning + evening)
data.json                   # local data store (gitignored)
requirements.txt
cogs/
    settings_cog.py         # !timezone, !morningtime, !eveningtime, !settings
    tasks_cog.py             # !add, !tasks, !remove
    reminders_cog.py         # the minute-by-minute background loop
    help_cog.py               # !help
```

## Running locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a bot application at the
   [Discord Developer Portal](https://discord.com/developers/applications),
   copy its token, and enable the **Message Content** privileged intent.
3. Copy `.env.example` to `.env` and fill in your token:
   ```bash
   cp .env.example .env
   ```
4. Run it:
   ```bash
   python bot.py
   ```

## Deploying for free (24/7, no local machine required)

The bot includes a minimal `aiohttp` web server (see `bot.py`) purely so
it can run as a **Render Web Service** on the free tier, which requires
binding to a port — unlike Render's Background Workers, which are paid
only.

1. Push this repo to GitHub.
2. On [Render](https://render.com): **New +** → **Web Service** → connect
   the repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `python bot.py`
   - Add an environment variable `DISCORD_TOKEN` with your bot token.
3. Free Render web services spin down after 15 minutes of inactivity.
   Use a free uptime pinger (e.g. [UptimeRobot](https://uptimerobot.com))
   to hit the deployed URL every 5 minutes and keep it awake.

This is an unofficial workaround, not a guarantee — for a fully reliable
always-on deployment, Render's paid Starter plan or a free-forever VM
(e.g. Oracle Cloud's Always Free tier) is more robust.

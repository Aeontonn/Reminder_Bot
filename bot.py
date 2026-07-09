"""
bot.py

Entry point. Creates the Bot instance, loads every cog, re-registers the
persistent checklist views (so buttons on already-sent messages survive a
restart), and logs in using the token from the .env file.
"""

import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import storage
import views

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# message_content is required to read !command text, and is a privileged
# intent that must also be enabled in the Discord Developer Portal for
# this bot application.
intents = discord.Intents.default()
intents.message_content = True

# help_command=None disables discord.py's built-in !help so our own
# custom one in cogs/help_cog.py can use that name instead.
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

EXTENSIONS = [
    "cogs.settings_cog",
    "cogs.tasks_cog",
    "cogs.reminders_cog",
    "cogs.help_cog",
]


@bot.event
async def setup_hook():
    for extension in EXTENSIONS:
        await bot.load_extension(extension)

    # Re-register one persistent ChecklistView per user with an active
    # checklist, so buttons sent before a restart keep working.
    data = storage.load_data()
    for view in views.build_registered_views(data):
        bot.add_view(view)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN is missing. Copy .env.example to .env and fill in your bot token."
        )
    asyncio.run(bot.start(TOKEN))

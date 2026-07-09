"""
settings_cog.py

Commands for managing a user's bot-wide settings: !timezone, !settings.

Timezone is validated against Python's zoneinfo database, so users can
switch freely between e.g. "Europe/Stockholm" and "Asia/Seoul" when
travelling, and switch back just as easily.
"""

from datetime import datetime

import discord
from discord.ext import commands
from zoneinfo import available_timezones, ZoneInfo

import storage

# Computed once at import time — available_timezones() reads the system's
# tz database, which doesn't change while the bot is running.
VALID_TIMEZONES = available_timezones()


def parse_hhmm(text: str) -> str:
    """
    Validate a "HH:MM" 24-hour time string and return it normalized
    (e.g. "8:5" -> "08:05"). Raises ValueError if the format is invalid.
    """
    parsed = datetime.strptime(text, "%H:%M")
    return parsed.strftime("%H:%M")


class SettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="timezone")
    async def set_timezone(self, ctx: commands.Context, tz_name: str = None):
        """Set or update the user's timezone, e.g. !timezone Europe/Stockholm"""
        if tz_name is None:
            await ctx.send(
                "Please provide a timezone, e.g. `!timezone Europe/Stockholm` or "
                "`!timezone Asia/Seoul`. Full list: "
                "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
            )
            return

        if tz_name not in VALID_TIMEZONES:
            await ctx.send(
                f"`{tz_name}` is not a valid timezone. Examples of valid "
                "formats: `Europe/Stockholm`, `Asia/Seoul`, `America/New_York`."
            )
            return

        data = storage.load_data()
        user = storage.get_user(data, ctx.author.id)
        user["timezone"] = tz_name
        storage.save_data(data)

        await ctx.send(f"Your timezone is now set to `{tz_name}`.")

    @commands.command(name="morningtime")
    async def set_morning_time(self, ctx: commands.Context, time_str: str = None):
        """Set what local time the morning checklist should be sent, e.g. !morningtime 07:30"""
        if time_str is None:
            await ctx.send("Please provide a time in HH:MM format, e.g. `!morningtime 07:30`.")
            return

        try:
            normalized = parse_hhmm(time_str)
        except ValueError:
            await ctx.send(f"`{time_str}` is not a valid time. Use HH:MM format, e.g. `07:30`.")
            return

        data = storage.load_data()
        user = storage.get_user(data, ctx.author.id)
        user["morning_time"] = normalized
        storage.save_data(data)

        await ctx.send(f"Your morning reminder will now be sent at `{normalized}` (your local time).")

    @commands.command(name="eveningtime")
    async def set_evening_time(self, ctx: commands.Context, time_str: str = None):
        """Set what local time the evening check-in should be sent, e.g. !eveningtime 21:30"""
        if time_str is None:
            await ctx.send("Please provide a time in HH:MM format, e.g. `!eveningtime 21:30`.")
            return

        try:
            normalized = parse_hhmm(time_str)
        except ValueError:
            await ctx.send(f"`{time_str}` is not a valid time. Use HH:MM format, e.g. `21:30`.")
            return

        data = storage.load_data()
        user = storage.get_user(data, ctx.author.id)
        user["evening_time"] = normalized
        storage.save_data(data)

        await ctx.send(f"Your evening reminder will now be sent at `{normalized}` (your local time).")

    @commands.command(name="settings")
    async def show_settings(self, ctx: commands.Context):
        """Show everything the bot has saved for the user."""
        data = storage.load_data()
        user = storage.get_user(data, ctx.author.id)
        storage.save_data(data)  # persist in case this created a new user

        tz_name = user["timezone"]
        try:
            local_now = discord.utils.utcnow().astimezone(ZoneInfo(tz_name))
            local_time_str = local_now.strftime("%Y-%m-%d %H:%M")
        except Exception:
            local_time_str = "unknown"

        recurring_count = sum(1 for t in user["tasks"] if t["recurring"])
        one_time_count = sum(1 for t in user["tasks"] if not t["recurring"])

        embed = discord.Embed(title="Your settings", color=discord.Color.green())
        embed.add_field(name="Timezone", value=f"`{tz_name}`", inline=False)
        embed.add_field(name="Current local time", value=local_time_str, inline=False)
        embed.add_field(name="Morning reminder", value=f"`{user['morning_time']}`", inline=True)
        embed.add_field(name="Evening reminder", value=f"`{user['evening_time']}`", inline=True)
        embed.add_field(name="Recurring tasks", value=str(recurring_count), inline=True)
        embed.add_field(name="One-time tasks", value=str(one_time_count), inline=True)
        embed.add_field(name="Streak", value=f"{user['streak']} days", inline=True)

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCog(bot))

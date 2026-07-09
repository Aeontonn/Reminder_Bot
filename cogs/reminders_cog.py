"""
reminders_cog.py

The background loop that drives everything time-based: runs once every
minute (required because the host server's clock is UTC, so we can't
rely on any single fixed-time schedule — each user's local reminder time
happens at a different UTC minute depending on their timezone, and each
user can also set their own custom time via !morningtime / !eveningtime).

For every registered user it converts the current UTC time to their
local timezone via zoneinfo, and:
  - at the user's configured morning_time (default 08:00): sends the
    interactive morning checklist DM
  - at the user's configured evening_time (default 20:00): sends the
    evening check-in DM

Duplicate sends (e.g. if the loop is delayed and "catches" the same
local time twice) are prevented by recording the local date the
reminder was last sent and comparing against it.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

import storage
import views

DEFAULT_MORNING_TIME = "08:00"
DEFAULT_EVENING_TIME = "20:00"


def _parse_hhmm(time_str: str) -> tuple[int, int]:
    """Parse a "HH:MM" string into (hour, minute). Raises ValueError if malformed."""
    hour_str, minute_str = time_str.split(":")
    return int(hour_str), int(minute_str)


class RemindersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @tasks.loop(minutes=1)
    async def reminder_loop(self):
        utc_now = datetime.now(timezone.utc)
        data = storage.load_data()
        changed = False

        for user_id_str, user in data.items():
            try:
                local_now = utc_now.astimezone(ZoneInfo(user["timezone"]))
            except Exception:
                # Invalid/unknown timezone string somehow ended up stored;
                # skip this user rather than crashing the whole loop.
                continue

            today_str = local_now.strftime("%Y-%m-%d")

            try:
                morning_hour, morning_minute = _parse_hhmm(
                    user.get("morning_time", DEFAULT_MORNING_TIME)
                )
                evening_hour, evening_minute = _parse_hhmm(
                    user.get("evening_time", DEFAULT_EVENING_TIME)
                )
            except ValueError:
                # Malformed stored time string; skip this user's reminders
                # rather than crashing the whole loop.
                continue

            if (
                local_now.hour == morning_hour
                and local_now.minute == morning_minute
                and user.get("last_morning_sent") != today_str
            ):
                await self._send_morning_reminder(int(user_id_str), user)
                user["last_morning_sent"] = today_str
                changed = True

            if (
                local_now.hour == evening_hour
                and local_now.minute == evening_minute
                and user.get("last_evening_sent") != today_str
            ):
                await self._send_evening_reminder(int(user_id_str))
                user["last_evening_sent"] = today_str
                changed = True

        if changed:
            storage.save_data(data)

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        # Avoid hitting the Discord API before the bot has finished logging
        # in and caching is ready.
        await self.bot.wait_until_ready()

    async def _send_morning_reminder(self, user_id: int, user: dict):
        # Purge one-time tasks that were already shown in a previous
        # morning's checklist (they get cleared after use), reset every
        # recurring task to unchecked, and mark the remaining one-time
        # tasks (added since yesterday) as shown for today.
        tasks_list = user["tasks"]
        tasks_list = [t for t in tasks_list if t["recurring"] or not t.get("shown", False)]
        for t in tasks_list:
            t["checked"] = False
            if not t["recurring"]:
                t["shown"] = True
        user["tasks"] = tasks_list
        user["checklist_completed_today"] = False

        todays_tasks = views.get_todays_tasks(user)

        discord_user = await self._fetch_user_safely(user_id)
        if discord_user is None:
            return

        embed = views.build_checklist_embed(todays_tasks, user["streak"])
        view = views.ChecklistView(user_id, todays_tasks) if todays_tasks else None

        try:
            if todays_tasks:
                await discord_user.send(embed=embed, view=view)
            else:
                await discord_user.send(
                    "Good morning! ☀️ You don't have any saved tasks for today. "
                    "Add some with `!add [task]` ahead of tomorrow."
                )
        except discord.Forbidden:
            # User has DMs disabled / blocked the bot; nothing more we can do.
            pass

    async def _send_evening_reminder(self, user_id: int):
        discord_user = await self._fetch_user_safely(user_id)
        if discord_user is None:
            return

        try:
            await discord_user.send(
                "Evening check-in! 🌙 Have you done everything you needed to today?\n"
                "Don't forget to add tomorrow's tasks with "
                "`!add [task]` (or `!add recurring [task]` for "
                "something that should repeat every day).\n"
                "Want to change when your reminders are sent? Use "
                "`!morningtime HH:MM` and `!eveningtime HH:MM`."
            )
        except discord.Forbidden:
            pass

    async def _fetch_user_safely(self, user_id: int):
        try:
            return await self.bot.fetch_user(user_id)
        except discord.NotFound:
            return None


async def setup(bot: commands.Bot):
    await bot.add_cog(RemindersCog(bot))

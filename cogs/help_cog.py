"""
help_cog.py

A single !help command that lists every command the bot supports and
explains what it does. Replaces discord.py's built-in help command
(disabled in bot.py via help_command=None) with a custom embed so the
formatting matches the rest of the bot.
"""

import discord
from discord.ext import commands


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help")
    async def show_help(self, ctx: commands.Context):
        """List all available commands and what they do."""
        embed = discord.Embed(
            title="Reminder Bot — commands",
            description=(
                "A daily routine and medicine reminder bot. Sends you a "
                "morning checklist and an evening check-in DM every day, "
                "in your own timezone and at your own chosen times."
            ),
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="!add [task]",
            value=(
                "Add a one-time task for tomorrow's morning checklist. "
                "It's shown once, then automatically cleared.\n"
                "Example: `!add Do laundry`"
            ),
            inline=False,
        )
        embed.add_field(
            name="!add recurring [task]",
            value=(
                "Add a recurring task (e.g. medicine) that stays on your "
                "checklist every day until you remove it manually.\n"
                "Example: `!add recurring 💊 Take medicine`"
            ),
            inline=False,
        )
        embed.add_field(
            name="!add evening [task] / !add both [task]",
            value=(
                "Control which checklist a task appears on. By default "
                "tasks only show up on the morning checklist. Use "
                "`evening` (or `evening-only`) to show it only at night, "
                "or `both` (or `both-times`) to show it on both. These can "
                "be combined with `recurring`, in any order, followed by "
                "an optional emoji.\n"
                "Examples: `!add evening Read before bed`, "
                "`!add recurring both 🚰 Drink water`"
            ),
            inline=False,
        )
        embed.add_field(
            name="!add [HH:MM] [text] / !add recurring [HH:MM] [text]",
            value=(
                "Add a one-off timed reminder — a plain DM ping at an exact "
                "clock time, separate from the morning/evening checklists. "
                "Without `recurring` it fires once (next time that clock "
                "time comes around) and then deletes itself. With "
                "`recurring` it fires every day at that time.\n"
                "Examples: `!add 15:30 Call to book a meeting`, "
                "`!add recurring 07:00 Take out the trash`"
            ),
            inline=False,
        )
        embed.add_field(
            name="!tasks",
            value=(
                "Show your current task list AND timed reminders, numbered "
                "together, with checked status, 🔁 for recurring items, and "
                "a tag showing which checklist(s) each task appears on. "
                "Also shows your current morning/evening reminder times at "
                "the bottom."
            ),
            inline=False,
        )
        embed.add_field(
            name="!remove [number]",
            value="Remove a task or timed reminder by its number as shown in `!tasks`.\nExample: `!remove 2`",
            inline=False,
        )
        embed.add_field(
            name="!timezone [zone]",
            value=(
                "Set or update your timezone, using a name from the IANA "
                "tz database (e.g. `Europe/Stockholm`, `Asia/Seoul`). "
                "Change it any time — handy when travelling.\n"
                "Example: `!timezone Europe/Stockholm`"
            ),
            inline=False,
        )
        embed.add_field(
            name="!morningtime [HH:MM]",
            value="Set what local time your morning checklist is sent (default 08:00).\nExample: `!morningtime 07:30`",
            inline=False,
        )
        embed.add_field(
            name="!eveningtime [HH:MM]",
            value="Set what local time your evening check-in is sent (default 20:00).\nExample: `!eveningtime 21:30`",
            inline=False,
        )
        embed.add_field(
            name="!settings",
            value="Show everything the bot has saved for you: timezone, reminder times, task counts and streak.",
            inline=False,
        )
        embed.add_field(
            name="!help",
            value="Show this message.",
            inline=False,
        )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))

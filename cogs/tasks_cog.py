"""
tasks_cog.py

Commands for managing a user's task list: !add, !tasks, !remove.

Tasks are unified — there's no separate "medicine" list. Any task can be
marked recurring (stays every day until removed with !remove) or one-time
(added the evening before, cleared automatically after the morning
checklist is sent).

Each task also has a "show_when" setting controlling which checklist(s)
it appears on: morning (default), evening, or both. Accepts either the
short form ("morning"/"evening"/"both") or the long form
("morning-only"/"evening-only"/"both-times") — both work the same.

!add also supports a completely separate kind of reminder: a custom
exact-time ping (e.g. "!add 15:30 call to book a meeting"), unrelated to
the morning/evening checklist. By default it fires once, next time that
clock time comes around, then deletes itself. Add "recurring" to make it
fire every day at that time instead.

Usage:
    !add Do laundry                        -> one-time, morning checklist, default emoji
    !add 🏋️ Train for 30 min                -> one-time, morning checklist, custom emoji
    !add recurring 💊 Take medicine         -> recurring, morning checklist, custom emoji
    !add evening Read before bed            -> one-time, evening checklist only
    !add recurring both 🚰 Drink water       -> recurring, shown on both checklists
    !add 15:30 Call to book a meeting       -> one-off ping at 15:30, not part of any checklist
    !add recurring 07:00 Take out the trash -> ping at 07:00 every day
    !tasks                                  -> list all tasks and timed reminders with their status
    !remove 2                               -> remove item number 2 from !tasks
"""

import re
import uuid

import discord
from discord.ext import commands

import storage

DEFAULT_EMOJI = "📌"

# Matches a 24-hour "HH:MM" clock time, e.g. "9:05" or "23:59".
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

# Recognized leading keywords for !add, checked case-insensitively and
# consumed in any order before the optional emoji + task text. Both the
# short and "-only"/"-times" long form are accepted so a natural first
# guess like "!add morning ..." works the same as "!add morning-only ...".
WHEN_KEYWORDS = {
    "morning": "morning",
    "morning-only": "morning",
    "evening": "evening",
    "evening-only": "evening",
    "both": "both",
    "both-times": "both",
}


def parse_add_arguments(argument: str) -> tuple:
    """
    Parse the raw text after !add. Returns a tagged tuple:
        ("checklist", recurring, show_when, emoji, label)
        ("timed", recurring, time_str, label)

    "recurring" is always an optional leading word. What follows decides
    the kind: a "HH:MM" token means a custom-time reminder ("timed");
    otherwise the normal checklist-task format applies:
        [morning-only|evening-only|both-times] [emoji] <label text>
    show_when defaults to "morning" if not given.

    An "emoji" is detected heuristically: a single word made up entirely
    of non-ASCII characters (covers standard emoji without pulling in an
    extra dependency).
    """
    words = argument.split()
    if not words:
        raise ValueError("No task text provided.")

    recurring = False
    if words[0].lower() == "recurring":
        recurring = True
        words = words[1:]

    if not words:
        raise ValueError("No task text provided after 'recurring'.")

    time_match = TIME_RE.match(words[0])
    if time_match:
        hour, minute = int(time_match.group(1)), time_match.group(2)
        time_str = f"{hour:02d}:{minute}"
        label = " ".join(words[1:]).strip()
        if not label:
            raise ValueError("No reminder text provided after the time.")
        return "timed", recurring, time_str, label

    show_when = "morning"
    while words:
        lowered = words[0].lower()
        if lowered in WHEN_KEYWORDS:
            show_when = WHEN_KEYWORDS[lowered]
            words = words[1:]
        else:
            break

    if not words:
        raise ValueError("No task text provided after the flags.")

    emoji = DEFAULT_EMOJI
    looks_like_emoji = words and all(ord(ch) > 127 for ch in words[0])
    if looks_like_emoji:
        emoji = words[0]
        words = words[1:]

    label = " ".join(words).strip()
    if not label:
        raise ValueError("No task text provided.")

    return "checklist", recurring, show_when, emoji, label


def _combined_items(user: dict) -> list[tuple[str, int, dict]]:
    """
    Build a single numbered view over both checklist tasks and custom-time
    reminders, as ("task"|"reminder", index-within-its-own-list, item)
    tuples — used by both !tasks (display) and !remove (lookup by number)
    so they always agree on the numbering.
    """
    items = [("task", i, t) for i, t in enumerate(user["tasks"])]
    items += [("reminder", i, r) for i, r in enumerate(user["custom_reminders"])]
    return items


class TasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="add")
    async def add_task(self, ctx: commands.Context, *, argument: str = ""):
        """Add a new task or timed reminder. See module docstring for the argument format."""
        try:
            parsed = parse_add_arguments(argument)
        except ValueError:
            await ctx.send(
                "Please provide a task, e.g. `!add Train`, "
                "`!add recurring 💊 Take medicine`, `!add evening-only Read before bed`, "
                "or `!add 15:30 Call to book a meeting`."
            )
            return

        data = storage.load_data()
        user = storage.get_user(data, ctx.author.id)

        if parsed[0] == "timed":
            _, recurring, time_str, label = parsed
            user["custom_reminders"].append(
                {
                    "id": uuid.uuid4().hex[:8],
                    "time": time_str,
                    "label": label,
                    "recurring": recurring,
                    "last_sent": None,
                }
            )
            storage.save_data(data)

            kind = "Recurring reminder" if recurring else "One-off reminder"
            await ctx.send(f"{kind} set for `{time_str}`: {label}")
            return

        _, recurring, show_when, emoji, label = parsed
        user["tasks"].append(
            {
                "id": uuid.uuid4().hex[:8],
                "label": label,
                "emoji": emoji,
                "checked": False,
                "recurring": recurring,
                "shown": False,
                "show_when": show_when,
            }
        )
        storage.save_data(data)

        kind = "recurring task" if recurring else "task"
        when_note = {"morning": "morning checklist", "evening": "evening checklist", "both": "both checklists"}[show_when]
        await ctx.send(f"Added {kind} ({when_note}): {emoji} {label}")

    @commands.command(name="tasks")
    async def list_tasks(self, ctx: commands.Context):
        """Show the user's current task list with numbering and status."""
        data = storage.load_data()
        user = storage.get_user(data, ctx.author.id)
        storage.save_data(data)  # persist in case this created a new user

        footer = (
            f"Morning reminder: {user['morning_time']}  •  "
            f"Evening reminder: {user['evening_time']}"
        )

        combined = _combined_items(user)
        if not combined:
            embed = discord.Embed(
                title="Your tasks",
                description="You don't have any saved tasks or reminders right now.",
                color=discord.Color.blurple(),
            )
            embed.set_footer(text=footer)
            await ctx.send(embed=embed)
            return

        when_tags = {
            "morning": " (☀️ morning only)",
            "evening": " (🌙 evening only)",
            "both": " (☀️🌙 both)",
        }

        lines = []
        for i, (kind, _, item) in enumerate(combined, start=1):
            if kind == "task":
                status = "✅" if item["checked"] else "⬜"
                recurring_tag = " (🔁 recurring)" if item["recurring"] else ""
                when_tag = when_tags[item.get("show_when", "morning")]
                lines.append(f"{i}. {status} {item['emoji']} {item['label']}{recurring_tag}{when_tag}")
            else:
                recurring_tag = " (🔁 recurring)" if item["recurring"] else " (one-off)"
                lines.append(f"{i}. ⏰ {item['time']} — {item['label']}{recurring_tag}")

        embed = discord.Embed(
            title="Your tasks",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=footer)
        await ctx.send(embed=embed)

    @commands.command(name="remove")
    async def remove_task(self, ctx: commands.Context, number: int = None):
        """Remove a task or timed reminder by its number as shown in !tasks."""
        if number is None:
            await ctx.send("Please provide the number of the item to remove, e.g. `!remove 2`.")
            return

        data = storage.load_data()
        user = storage.get_user(data, ctx.author.id)
        combined = _combined_items(user)

        display_index = number - 1  # displayed list is 1-indexed
        if display_index < 0 or display_index >= len(combined):
            await ctx.send(f"No item found with number {number}. Run `!tasks` to see the list.")
            return

        kind, list_index, item = combined[display_index]
        if kind == "task":
            removed = user["tasks"].pop(list_index)
            storage.save_data(data)
            await ctx.send(f"Removed: {removed['emoji']} {removed['label']}")
        else:
            removed = user["custom_reminders"].pop(list_index)
            storage.save_data(data)
            await ctx.send(f"Removed reminder: ⏰ {removed['time']} — {removed['label']}")


async def setup(bot: commands.Bot):
    await bot.add_cog(TasksCog(bot))

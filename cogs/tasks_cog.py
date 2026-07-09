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

Usage:
    !add Do laundry                        -> one-time, morning checklist, default emoji
    !add 🏋️ Train for 30 min                -> one-time, morning checklist, custom emoji
    !add recurring 💊 Take medicine         -> recurring, morning checklist, custom emoji
    !add evening Read before bed            -> one-time, evening checklist only
    !add recurring both 🚰 Drink water       -> recurring, shown on both checklists
    !tasks                                  -> list all tasks with their status
    !remove 2                               -> remove task number 2 from !tasks
"""

import uuid

import discord
from discord.ext import commands

import storage

DEFAULT_EMOJI = "📌"

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


def parse_add_arguments(argument: str) -> tuple[bool, str, str, str]:
    """
    Parse the raw text after !add into (recurring, show_when, emoji, label).

    The expected format is:
        [recurring] [morning-only|evening-only|both-times] [emoji] <label text>
    where the flags and the emoji are all optional, and the two flags can
    appear in either order. show_when defaults to "morning" if not given.

    An "emoji" is detected heuristically: a single word made up entirely
    of non-ASCII characters (covers standard emoji without pulling in an
    extra dependency).
    """
    words = argument.split()
    if not words:
        raise ValueError("No task text provided.")

    recurring = False
    show_when = "morning"

    while words:
        lowered = words[0].lower()
        if lowered == "recurring" and not recurring:
            recurring = True
            words = words[1:]
        elif lowered in WHEN_KEYWORDS:
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

    return recurring, show_when, emoji, label


class TasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="add")
    async def add_task(self, ctx: commands.Context, *, argument: str = ""):
        """Add a new task. See module docstring for the argument format."""
        try:
            recurring, show_when, emoji, label = parse_add_arguments(argument)
        except ValueError:
            await ctx.send(
                "Please provide a task, e.g. `!add Train`, "
                "`!add recurring 💊 Take medicine`, or "
                "`!add evening-only Read before bed`."
            )
            return

        data = storage.load_data()
        user = storage.get_user(data, ctx.author.id)
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

        tasks = user["tasks"]
        if not tasks:
            await ctx.send("You don't have any saved tasks right now.")
            return

        when_tags = {
            "morning": " (☀️ morning only)",
            "evening": " (🌙 evening only)",
            "both": " (☀️🌙 both)",
        }

        lines = []
        for i, task in enumerate(tasks, start=1):
            status = "✅" if task["checked"] else "⬜"
            recurring_tag = " (🔁 recurring)" if task["recurring"] else ""
            when_tag = when_tags[task.get("show_when", "morning")]
            lines.append(f"{i}. {status} {task['emoji']} {task['label']}{recurring_tag}{when_tag}")

        embed = discord.Embed(
            title="Your tasks",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="remove")
    async def remove_task(self, ctx: commands.Context, number: int = None):
        """Remove a task by its number as shown in !tasks."""
        if number is None:
            await ctx.send("Please provide the number of the task to remove, e.g. `!remove 2`.")
            return

        data = storage.load_data()
        user = storage.get_user(data, ctx.author.id)
        tasks = user["tasks"]

        index = number - 1  # displayed list is 1-indexed
        if index < 0 or index >= len(tasks):
            await ctx.send(f"No task found with number {number}. Run `!tasks` to see the list.")
            return

        removed = tasks.pop(index)
        storage.save_data(data)
        await ctx.send(f"Removed: {removed['emoji']} {removed['label']}")


async def setup(bot: commands.Bot):
    await bot.add_cog(TasksCog(bot))

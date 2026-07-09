"""
tasks_cog.py

Commands for managing a user's task list: !add, !tasks, !remove.

Tasks are unified — there's no separate "medicine" list. Any task can be
marked recurring (stays every day until removed with !remove) or one-time
(added the evening before, cleared automatically after the morning
checklist is sent).

Usage:
    !add Do laundry                  -> one-time task, default emoji
    !add 🏋️ Train for 30 min          -> one-time task, custom emoji
    !add recurring 💊 Take medicine   -> recurring task, custom emoji
    !add recurring Water the plants   -> recurring task, default emoji
    !tasks                            -> list all tasks with their status
    !remove 2                         -> remove task number 2 from !tasks
"""

import uuid

import discord
from discord.ext import commands

import storage

DEFAULT_EMOJI = "📌"


def parse_add_arguments(argument: str) -> tuple[bool, str, str]:
    """
    Parse the raw text after !add into (recurring, emoji, label).

    The expected format is:
        [recurring] [emoji] <label text>
    where "recurring" and the emoji are both optional, in that order.

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

    emoji = DEFAULT_EMOJI
    looks_like_emoji = words and all(ord(ch) > 127 for ch in words[0])
    if looks_like_emoji:
        emoji = words[0]
        words = words[1:]

    label = " ".join(words).strip()
    if not label:
        raise ValueError("No task text provided.")

    return recurring, emoji, label


class TasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="add")
    async def add_task(self, ctx: commands.Context, *, argument: str = ""):
        """Add a new task. See module docstring for the argument format."""
        try:
            recurring, emoji, label = parse_add_arguments(argument)
        except ValueError:
            await ctx.send(
                "Please provide a task, e.g. `!add Train` or "
                "`!add recurring 💊 Take medicine`."
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
            }
        )
        storage.save_data(data)

        kind = "recurring task" if recurring else "task"
        await ctx.send(f"Added {kind}: {emoji} {label}")

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

        lines = []
        for i, task in enumerate(tasks, start=1):
            status = "✅" if task["checked"] else "⬜"
            recurring_tag = " (🔁 recurring)" if task["recurring"] else ""
            lines.append(f"{i}. {status} {task['emoji']} {task['label']}{recurring_tag}")

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

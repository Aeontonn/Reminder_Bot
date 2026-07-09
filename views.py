"""
views.py

The interactive discord.ui.View used for the morning checklist DM. Each
task gets its own button; clicking it toggles that task's checked state,
edits the message in place, and — once every task in today's checklist is
checked — sends a "Great job, you're done for today!" follow-up message
and bumps the user's streak.

Buttons reference tasks by their stable "id" field (not their list
position), so the checklist keeps working correctly even if the user
adds or removes other tasks later the same day.

These views are persistent (timeout=None, explicit custom_id per button),
which means they keep working after the bot process restarts — as long
as bot.py re-registers one view per user with an active checklist in its
setup_hook (see build_and_register_persistent_views below).
"""

import discord

import storage


def get_todays_tasks(user: dict) -> list[dict]:
    """
    Return the subset of a user's tasks that belong to today's checklist:
    all recurring tasks, plus one-time tasks that have been marked as
    shown (i.e. included in this morning's checklist).
    """
    return [t for t in user["tasks"] if t["recurring"] or t.get("shown")]


def build_checklist_embed(tasks: list[dict], streak: int) -> discord.Embed:
    """Build the embed shown alongside the checklist buttons."""
    if not tasks:
        description = "No tasks to check off today."
    else:
        lines = []
        for task in tasks:
            status = "✅" if task["checked"] else "⬜"
            lines.append(f"{status} {task['emoji']} {task['label']}")
        description = "\n".join(lines)

    all_checked = bool(tasks) and all(t["checked"] for t in tasks)
    color = discord.Color.green() if all_checked else discord.Color.blurple()

    embed = discord.Embed(title="Your morning checklist", description=description, color=color)
    embed.set_footer(text=f"Streak: {streak} days")
    return embed


class TaskToggleButton(discord.ui.Button):
    """A single checklist button bound to one specific task (by id)."""

    def __init__(self, user_id: int, task: dict):
        style = discord.ButtonStyle.success if task["checked"] else discord.ButtonStyle.secondary
        super().__init__(
            label=f"{task['emoji']} {task['label']}"[:80],
            style=style,
            custom_id=f"task_toggle:{user_id}:{task['id']}",
        )
        self.user_id = user_id
        self.task_id = task["id"]

    async def callback(self, interaction: discord.Interaction):
        # Only the owner of this checklist can toggle its buttons, even
        # though DMs are 1-on-1 this also protects the (optional) case of
        # the bot being used in a shared server channel.
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your checklist.", ephemeral=True
            )
            return

        data = storage.load_data()
        user = storage.get_user(data, self.user_id)
        task = next((t for t in user["tasks"] if t["id"] == self.task_id), None)

        if task is None:
            # The task was removed (e.g. via !remove) since this checklist
            # was sent. Just acknowledge; the stale button will disappear
            # next time the view is rebuilt.
            await interaction.response.send_message(
                "This task no longer exists.", ephemeral=True
            )
            return

        task["checked"] = not task["checked"]

        todays_tasks = get_todays_tasks(user)
        all_checked = bool(todays_tasks) and all(t["checked"] for t in todays_tasks)
        newly_completed = all_checked and not user["checklist_completed_today"]

        if newly_completed:
            user["streak"] += 1
            user["checklist_completed_today"] = True
        elif not all_checked:
            # If they uncheck something after completing, they need to
            # fully recheck everything to be "done" again, but that will
            # NOT grant a second streak point today (see newly_completed
            # check above, which only fires on the False -> True edge).
            user["checklist_completed_today"] = False

        storage.save_data(data)

        new_view = ChecklistView(self.user_id, todays_tasks)
        new_embed = build_checklist_embed(todays_tasks, user["streak"])
        await interaction.response.edit_message(embed=new_embed, view=new_view)

        if newly_completed:
            await interaction.followup.send("Great job, you're done for today! 🎉")


class ChecklistView(discord.ui.View):
    """Persistent view holding one TaskToggleButton per task in the checklist."""

    def __init__(self, user_id: int, tasks: list[dict]):
        super().__init__(timeout=None)
        for task in tasks:
            self.add_item(TaskToggleButton(user_id, task))


def build_registered_views(all_data: dict) -> list[discord.ui.View]:
    """
    Reconstruct one ChecklistView per user with an active (non-empty)
    checklist. Called once at bot startup so that buttons on checklists
    sent before a restart keep working afterwards — discord.py requires
    persistent views to be re-registered with bot.add_view() every time
    the process starts.
    """
    views = []
    for user_id_str, user in all_data.items():
        todays_tasks = get_todays_tasks(user)
        if todays_tasks:
            views.append(ChecklistView(int(user_id_str), todays_tasks))
    return views

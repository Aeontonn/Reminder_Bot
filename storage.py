"""
storage.py

Handles all reading and writing to data.json, the local file that stores
every user's timezone, tasks and streak count.

Uses an atomic write (write to a temp file, then rename) so that if the
process or server crashes mid-write, data.json is never left half-written
or corrupted.
"""

import copy
import json
import os
import tempfile

DATA_FILE = "data.json"

# Default structure given to a brand-new user the first time they interact
# with the bot (e.g. the first time they run !timezone or !add).
#
# Tasks are unified: there is no separate "medicine" list anymore. Any
# task (medicine or otherwise) can be marked recurring=True by the user
# when they add it, meaning it stays in the list forever (reset to
# unchecked every morning) until removed manually with !remove.
# recurring=False tasks are one-time: added the evening before, included
# in exactly one morning checklist, then purged the following morning.
#
# Each task also has:
#   - "id": a short random hex string. Checklist buttons reference tasks
#     by this id (not their position in the list), so removing or adding
#     other tasks during the day never breaks an already-sent checklist.
#   - "shown": for one-time tasks, whether it has already appeared in a
#     morning checklist. Used to purge it the following morning. Unused
#     for recurring tasks.
#   - "show_when": which checklist(s) the task appears on — "morning"
#     (default), "evening", or "both". Missing on older data, so callers
#     should read it with task.get("show_when", "morning").
DEFAULT_USER = {
    "timezone": "UTC",
    "tasks": [],  # list of {"id", "label", "emoji", "checked", "recurring", "shown", "show_when"}
    "streak": 0,
    "checklist_completed_today": False,
    "morning_time": "08:00",     # "HH:MM" in the user's local timezone, user-configurable
    "evening_time": "20:00",     # "HH:MM" in the user's local timezone, user-configurable
    "last_morning_sent": None,   # ISO date string, prevents duplicate sends
    "last_evening_sent": None,   # ISO date string, prevents duplicate sends
}


def load_data() -> dict:
    """Load the full data.json file into a dict. Returns {} if missing."""
    if not os.path.exists(DATA_FILE):
        return {}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # File exists but is empty or corrupted; fail safe with empty dict
            return {}


def save_data(data: dict) -> None:
    """
    Write the full data dict to data.json atomically.

    Writing to a temporary file first and then renaming it over the real
    file avoids ending up with a half-written / broken JSON file if the
    process is killed mid-write (important since this runs on a free
    cloud host that can restart at any time).
    """
    directory = os.path.dirname(os.path.abspath(DATA_FILE)) or "."

    # delete=False because we need to close the file before renaming it
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp"
    ) as tmp_file:
        json.dump(data, tmp_file, indent=2, ensure_ascii=False)
        temp_path = tmp_file.name

    os.replace(temp_path, DATA_FILE)


def get_user(data: dict, user_id: int) -> dict:
    """
    Get a user's record from the data dict, creating it with default
    values if it doesn't exist yet. Mutates `data` in place and returns
    the user's dict so callers can modify it directly.
    """
    key = str(user_id)  # JSON object keys must be strings
    if key not in data:
        # deepcopy is required here: DEFAULT_USER contains a mutable list
        # ("tasks"). A shallow dict(DEFAULT_USER) copy would make every new
        # user share the exact same list object, so adding a task for one
        # user would silently add it for all users.
        data[key] = copy.deepcopy(DEFAULT_USER)
    else:
        # Backfill any keys added to DEFAULT_USER after this user record
        # was first created (e.g. morning_time/evening_time), so older
        # entries in data.json don't crash on missing fields.
        for field, default_value in DEFAULT_USER.items():
            data[key].setdefault(field, copy.deepcopy(default_value))
    return data[key]


def user_exists(data: dict, user_id: int) -> bool:
    """Check whether a user already has a record, without creating one."""
    return str(user_id) in data
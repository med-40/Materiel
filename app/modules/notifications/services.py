from typing import Callable

SEVERITY_RANK = {"overdue": 2, "upcoming": 1}

_PROVIDERS: list[Callable] = []


def register_provider(fn: Callable) -> None:
    if fn not in _PROVIDERS:
        _PROVIDERS.append(fn)


def get_all_notifications(db) -> list[dict]:
    merged: dict[str, dict] = {}

    for provider in _PROVIDERS:
        for note in provider(db):
            key = note["key"]
            existing = merged.get(key)
            if not existing or SEVERITY_RANK.get(note["severity"], 0) > SEVERITY_RANK.get(existing["severity"], 0):
                merged[key] = note

    notes = list(merged.values())
    notes.sort(key=lambda n: SEVERITY_RANK.get(n["severity"], 0), reverse=True)
    return notes

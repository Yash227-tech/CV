"""
Teacher registry.

The tech-team admin console adds teachers here (id + name). The teacher app
then lets a teacher pick themselves from this list when checking in to a
lecture, instead of typing a free-text name.
"""
import json
import os

import config


def _load():
    if not os.path.exists(config.TEACHERS_PATH):
        return []
    try:
        with open(config.TEACHERS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return [t for t in data if isinstance(t, dict) and t.get("id")]
    except Exception:
        return []


def _save(rows):
    config.ensure_dirs()
    with open(config.TEACHERS_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def _sanitize(text):
    return "".join(c for c in str(text).strip() if c.isalnum() or c in (" ", "_", "-", ".")).strip()


def list_teachers():
    """Return [(id, name)] sorted by id."""
    return sorted(((t["id"], t.get("name", t["id"])) for t in _load()), key=lambda x: x[0])


def count():
    return len(_load())


def add_teacher(teacher_id, name):
    """Add or update a teacher. Returns (status, (id, name))."""
    tid = _sanitize(teacher_id)
    nm = _sanitize(name)
    if not tid or not nm:
        return "Both an ID and a name are required.", None
    rows = _load()
    for t in rows:
        if t["id"] == tid:
            t["name"] = nm
            _save(rows)
            return f"Updated teacher {nm} (id={tid}).", (tid, nm)
    rows.append({"id": tid, "name": nm})
    _save(rows)
    return f"Added teacher {nm} (id={tid}).", (tid, nm)


def delete_teacher(teacher_id):
    tid = _sanitize(teacher_id)
    rows = _load()
    kept = [t for t in rows if t["id"] != tid]
    if len(kept) == len(rows):
        return f"No teacher with id '{tid}'."
    _save(kept)
    return f"Deleted teacher id={tid}."


def display_names():
    """Human-friendly strings for a dropdown, e.g. 'Dr. Smith (T01)'."""
    return [f"{name} ({tid})" for tid, name in list_teachers()]

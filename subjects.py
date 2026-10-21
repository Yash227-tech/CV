"""
Subject registry.

Remembers subject names so the GUI can offer them in a dropdown without
retyping. The list is the union of (a) names saved here and (b) any subject
folders that already have attendance files.
"""
import json
import os

import config


def sanitize(subject: str) -> str:
    s = "".join(c for c in subject.strip() if c.isalnum() or c in (" ", "_", "-")).replace(" ", "_")
    return s


def _load_saved():
    if not os.path.exists(config.SUBJECTS_PATH):
        return []
    try:
        with open(config.SUBJECTS_PATH, encoding="utf-8") as f:
            return list(json.load(f))
    except Exception:
        return []


def _from_folders():
    if not os.path.isdir(config.ATTENDANCE_DIR):
        return []
    out = []
    for name in os.listdir(config.ATTENDANCE_DIR):
        d = os.path.join(config.ATTENDANCE_DIR, name)
        if os.path.isdir(d):
            out.append(name)
    return out


def list_subjects():
    """All known subjects (saved + existing folders), sorted, de-duplicated."""
    return sorted(set(_load_saved()) | set(_from_folders()))


def add_subject(subject: str) -> str:
    """Remember a subject. Returns the sanitized name, or '' if invalid."""
    name = sanitize(subject)
    if not name:
        return ""
    saved = _load_saved()
    if name not in saved:
        saved.append(name)
        config.ensure_dirs()
        with open(config.SUBJECTS_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(set(saved)), f, indent=2)
    return name

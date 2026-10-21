"""
Attendance report: per-student totals, per subject.

Attendance is stored as attendance/<subject>/<subject>_<date>.csv (one file =
one session day). This report counts how many days each student was present for
a subject and shows attendance % against the enrolled roster.

Usage:
    python report.py                         # report for every subject
    python report.py --subject Maths         # one subject
    python report.py --subject Maths --date 2026-10-21   # one day
    python report.py --subject Maths --export            # write summary.csv
"""
import argparse
import csv
import glob
import os
from datetime import datetime

import config
import store


def list_subjects():
    """Subject folders that have at least one attendance file."""
    if not os.path.isdir(config.ATTENDANCE_DIR):
        return []
    subjects = []
    for name in sorted(os.listdir(config.ATTENDANCE_DIR)):
        d = os.path.join(config.ATTENDANCE_DIR, name)
        if os.path.isdir(d) and glob.glob(os.path.join(d, "*.csv")):
            subjects.append(name)
    return subjects


def session_files(subject):
    pattern = os.path.join(config.ATTENDANCE_DIR, subject, "*.csv")
    return sorted(f for f in glob.glob(pattern) if os.path.basename(f) != "summary.csv")


def read_day(path):
    """Return (date_str, {id: name}) for one daily CSV."""
    present = {}
    date_str = ""
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            present[row["id"]] = row["name"]
            date_str = row.get("date", date_str)
    if not date_str:
        base = os.path.basename(path).replace(".csv", "")
        date_str = base.split("_")[-1]
    return date_str, present


def build_summary(subject):
    """Return (dates, rows) of per-student stats for one subject."""
    files = session_files(subject)
    dates, present_by_day = [], []
    for path in files:
        date_str, present = read_day(path)
        dates.append(date_str)
        present_by_day.append(present)

    ids, names, _ = store.load_enrollments()
    roster = {sid: name for sid, name in zip(ids, names)}
    for present in present_by_day:
        for sid, name in present.items():
            roster.setdefault(sid, name)

    total_days = len(files)
    rows = []
    for sid, name in sorted(roster.items(), key=lambda kv: kv[0]):
        days_present = sum(1 for present in present_by_day if sid in present)
        pct = (days_present / total_days * 100) if total_days else 0.0
        rows.append({
            "id": sid, "name": name,
            "days_present": days_present, "total_days": total_days,
            "percent": round(pct, 1),
        })
    return dates, rows


def summary_text(subject):
    """Return the summary table for one subject as a printable string."""
    dates, rows = build_summary(subject)
    lines = []
    if not dates:
        return f"No attendance records for subject '{subject}'."
    lines.append(f"Subject: {subject}  |  {len(dates)} day(s): {dates[0]} .. {dates[-1]}")
    lines.append("-" * 56)
    lines.append(f"{'ID':<8}{'Name':<22}{'Present':>8}{'Total':>7}{'%':>8}")
    lines.append("-" * 56)
    for r in rows:
        lines.append(f"{r['id']:<8}{r['name']:<22}{r['days_present']:>8}{r['total_days']:>7}{r['percent']:>7.1f}%")
    lines.append("-" * 56)
    never = [r for r in rows if r["days_present"] == 0]
    if never:
        lines.append("Never present: " + ", ".join(f"{r['name']}({r['id']})" for r in never))
    return "\n".join(lines)


def day_text(subject, date_str):
    path = os.path.join(config.ATTENDANCE_DIR, subject, f"{subject}_{date_str}.csv")
    if not os.path.exists(path):
        return f"No attendance file for {subject} on {date_str}."
    _, present = read_day(path)
    lines = [f"{subject} - present on {date_str} ({len(present)}):"]
    for sid, name in sorted(present.items()):
        lines.append(f"  {sid:<8}{name}")
    ids, names, _ = store.load_enrollments()
    absent = [(sid, nm) for sid, nm in zip(ids, names) if sid not in present]
    if absent:
        lines.append(f"Absent ({len(absent)}):")
        for sid, nm in sorted(absent):
            lines.append(f"  {sid:<8}{nm}")
    return "\n".join(lines)


def export_summary(subject):
    _, rows = build_summary(subject)
    out = os.path.join(config.ATTENDANCE_DIR, subject, "summary.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "days_present", "total_days", "percent"])
        writer.writeheader()
        writer.writerows(rows)
    return out


def print_summary(subject=None):
    subjects = [subject] if subject else list_subjects()
    if not subjects:
        print("No attendance records yet in", config.ATTENDANCE_DIR)
        return
    for s in subjects:
        print()
        print(summary_text(s))


def main():
    config.ensure_dirs()
    parser = argparse.ArgumentParser(description="Attendance report.")
    parser.add_argument("--subject", help="Subject to report on (default: all)")
    parser.add_argument("--date", help="Show present/absent for one day (needs --subject)")
    parser.add_argument("--export", action="store_true", help="Write summary.csv for the subject")
    args = parser.parse_args()

    if args.date:
        if not args.subject:
            raise SystemExit("--date needs --subject")
        print(day_text(args.subject, args.date))
    else:
        print_summary(args.subject)
        if args.export and args.subject:
            print("\nWrote", export_summary(args.subject))


if __name__ == "__main__":
    main()

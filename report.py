"""
Attendance report: per-student totals, per subject.

Attendance is stored as attendance/<subject>/<subject>_<date>_<label>.csv, one
file per SESSION (lecture). A subject can have several sessions in a day. This
report counts how many sessions each student attended and shows attendance %
against the enrolled roster.

Usage:
    python report.py                         # report for every subject
    python report.py --subject Maths         # one subject
    python report.py --subject Maths --export            # write summary.csv
"""
import argparse
import csv
import glob
import os

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


def read_session(path, subject):
    """Return (session_token, {id: name}) for one session CSV."""
    present = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            present[row["id"]] = row["name"]
    prefix = f"{subject}_"
    token = os.path.basename(path)[len(prefix):-4]
    return token, present


def build_summary(subject):
    """Return (sessions, rows) of per-student stats for one subject."""
    files = session_files(subject)
    sessions, present_by_session = [], []
    for path in files:
        token, present = read_session(path, subject)
        sessions.append(token)
        present_by_session.append(present)

    ids, names, _ = store.load_enrollments()
    roster = {sid: name for sid, name in zip(ids, names)}
    for present in present_by_session:
        for sid, name in present.items():
            roster.setdefault(sid, name)

    total = len(files)
    rows = []
    for sid, name in sorted(roster.items(), key=lambda kv: kv[0]):
        attended = sum(1 for present in present_by_session if sid in present)
        pct = (attended / total * 100) if total else 0.0
        rows.append({
            "id": sid, "name": name,
            "sessions_attended": attended, "total_sessions": total,
            "percent": round(pct, 1),
        })
    return sessions, rows


def summary_text(subject):
    """Return the summary table for one subject as a printable string."""
    sessions, rows = build_summary(subject)
    if not sessions:
        return f"No attendance records for subject '{subject}'."
    lines = [f"Subject: {subject}  |  {len(sessions)} session(s)"]
    lines.append("-" * 58)
    lines.append(f"{'ID':<8}{'Name':<22}{'Attended':>9}{'Total':>7}{'%':>8}")
    lines.append("-" * 58)
    for r in rows:
        lines.append(f"{r['id']:<8}{r['name']:<22}{r['sessions_attended']:>9}"
                     f"{r['total_sessions']:>7}{r['percent']:>7.1f}%")
    lines.append("-" * 58)
    never = [r for r in rows if r["sessions_attended"] == 0]
    if never:
        lines.append("Never present: " + ", ".join(f"{r['name']}({r['id']})" for r in never))
    return "\n".join(lines)


def export_summary(subject):
    _, rows = build_summary(subject)
    out = os.path.join(config.ATTENDANCE_DIR, subject, "summary.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "name", "sessions_attended", "total_sessions", "percent"])
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
    parser.add_argument("--export", action="store_true", help="Write summary.csv for the subject")
    args = parser.parse_args()

    print_summary(args.subject)
    if args.export and args.subject:
        print("\nWrote", export_summary(args.subject))


if __name__ == "__main__":
    main()

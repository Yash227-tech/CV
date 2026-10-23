"""
Take attendance (per subject) using single-photo enrollments.

Faces are detected (YuNet), embedded (SFace), and matched against enrolled
students by cosine similarity. Each recognised student is marked present once
per subject per day, in:

    attendance/<subject>/<subject>_<date>.csv

Usage:
    python attendance.py --subject Maths
    python attendance.py                 # will prompt for the subject

Controls while the camera is open:
    q  - quit and show the summary
"""
import argparse
import csv
import glob
import os
from datetime import datetime

import cv2
import numpy as np

import config
import store
from face_engine import FaceEngine


def sanitize_subject(subject: str) -> str:
    s = "".join(c for c in subject.strip() if c.isalnum() or c in (" ", "_", "-")).replace(" ", "_")
    return s or "General"


def subject_dir(subject: str) -> str:
    d = os.path.join(config.ATTENDANCE_DIR, sanitize_subject(subject))
    os.makedirs(d, exist_ok=True)
    return d


def sanitize_label(label: str) -> str:
    s = "".join(c for c in label.strip() if c.isalnum() or c in (" ", "_", "-")).replace(" ", "_")
    return s


def make_session(label: str = None) -> str:
    """Build a session token '<date>_<label>'.

    A session is one lecture. Give a label (e.g. 'L1', 'Lecture2') to make a
    named, resumable session; leave it blank and the current time is used, so
    each run of the same subject on the same day is a distinct session - which
    is exactly how two lectures of one subject in a day are kept separate.
    """
    now = datetime.now()
    lab = sanitize_label(label) if (label and label.strip()) else f"{now:%H%M}"
    return f"{now:%Y-%m-%d}_{lab}"


def csv_path_for(subject: str, session: str = None) -> str:
    """Path to a session's CSV. `session` is a token from make_session();
    if omitted, a new time-based session for today is created."""
    session = session or make_session()
    subj = sanitize_subject(subject)
    return os.path.join(subject_dir(subject), f"{subj}_{session}.csv")


def list_sessions(subject: str):
    """All session tokens recorded for a subject, sorted (oldest first)."""
    subj = sanitize_subject(subject)
    prefix = f"{subj}_"
    out = []
    for f in glob.glob(os.path.join(subject_dir(subject), f"{subj}_*.csv")):
        base = os.path.basename(f)
        if base == "summary.csv":
            continue
        out.append(base[len(prefix):-4])
    return sorted(out)


def today_sessions(subject: str):
    """Session tokens for a subject recorded today."""
    today = f"{datetime.now():%Y-%m-%d}"
    return [s for s in list_sessions(subject) if s.startswith(today + "_")]


def load_already_marked(path):
    marked = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                marked.add(row["id"])
    return marked


def mark_present(path, student_id, name, method="face"):
    """Append a present record. Returns False if the student is already marked."""
    if student_id in load_already_marked(path):
        return False
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["id", "name", "date", "time", "method"])
        now = datetime.now()
        writer.writerow([student_id, name, f"{now:%Y-%m-%d}", f"{now:%H:%M:%S}", method])
    return True


def mark_manually(subject, student_id, name=None, session=None):
    """Mark a student present by id, without the camera, for a given session.

    If name is None it is looked up from the enrollments. If session is None a
    new time-based session is created. Returns a status string.
    """
    ids, names, _ = store.load_enrollments()
    roster = dict(zip(ids, names))
    student_id = str(student_id).strip()
    if name is None:
        if student_id not in roster:
            return f"Unknown id '{student_id}' (not enrolled). Pass a name or enroll first."
        name = roster[student_id]
    session = session or make_session()
    path = csv_path_for(subject, session)
    if mark_present(path, student_id, name, method="manual"):
        return f"Marked present (manual): {name} (id={student_id}) for {sanitize_subject(subject)} [{session}]"
    return f"{name} (id={student_id}) was already marked in session {session}."


def unmark(subject, student_id, session):
    """Remove a student's attendance record from a specific session.

    Lets a teacher correct a wrong mark. Returns a status string.
    """
    student_id = str(student_id).strip()
    path = csv_path_for(subject, session)
    if not os.path.exists(path):
        return f"No attendance file for {sanitize_subject(subject)} session {session}."

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or ["id", "name", "date", "time", "method"]
        rows = list(reader)

    kept = [r for r in rows if r.get("id") != student_id]
    removed_name = next((r.get("name", student_id) for r in rows if r.get("id") == student_id), None)
    if removed_name is None:
        return f"id '{student_id}' was not marked present for {sanitize_subject(subject)}."

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(kept)
    return f"Removed attendance: {removed_name} (id={student_id}) from {sanitize_subject(subject)}."


def best_match(embedding, enrolled):
    """enrolled is (N, 128) L2-normalised. Return (index, cosine_score) of best match."""
    if len(enrolled) == 0:
        return -1, -1.0
    scores = enrolled @ embedding
    i = int(np.argmax(scores))
    return i, float(scores[i])


def run(subject, session=None):
    config.ensure_dirs()
    subject = sanitize_subject(subject)
    session = session or make_session()
    ids, names, enrolled = store.load_enrollments()
    if len(ids) == 0:
        raise SystemExit("No students enrolled yet. Run enroll.py first.")

    engine = FaceEngine()

    # Anti-spoofing: passive CNN + active (move/turn) challenge.
    live = active = None
    if config.ANTISPOOF_ENABLED:
        from liveness import LivenessDetector, ActiveLiveness, yaw_proxy
        live = LivenessDetector()
        active = ActiveLiveness()
        if not live.available():
            print("WARNING: anti-spoof model not found at", config.ANTISPOOF_PATH)
            print("         Running WITHOUT spoof protection (see README to add it).")

    cam = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cam.isOpened():
        raise SystemExit("Could not open the webcam. Check CAMERA_INDEX in config.py.")

    csv_path = csv_path_for(subject, session)
    marked = load_already_marked(csv_path)

    print(f"\nAttendance running for subject: {subject}, session: {session}. {len(ids)} student(s) enrolled.")
    print(f"Writing to: {csv_path}")
    if config.ANTISPOOF_ENABLED and live.available():
        print("Anti-spoofing ON" + (" + move/turn challenge." if config.ACTIVE_LIVENESS_ENABLED else "."))
    print("Press 'q' to stop.\n")

    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                continue

            RED, GREEN, YELLOW = (0, 0, 255), (0, 255, 0), (0, 255, 255)

            for face in engine.detect(frame):
                x, y, w, h = face[:4].astype(int)
                emb = engine.embed(frame, face)
                idx, score = best_match(emb, enrolled)
                recognized = score >= config.COSINE_THRESHOLD

                if not recognized:
                    text, color = f"Unknown ({score:.2f})", RED
                else:
                    student_id, name = ids[idx], names[idx]
                    if student_id in marked:
                        text, color = f"{name} (present)", GREEN
                    elif active is not None:
                        # Passive score (smoothed over frames) + movement check.
                        p = live.real_score(frame, (x, y, w, h)) if live is not None else None
                        active.update(student_id, p, yaw_proxy(face))
                        if active.is_spoof(student_id):
                            s = active.smoothed_real(student_id)
                            text, color = f"SPOOF? {s:.2f}", RED
                        elif active.passed(student_id):
                            mark_present(csv_path, student_id, name, method="face")
                            marked.add(student_id)
                            print(f"  Marked present: {name} (id={student_id}) at {datetime.now():%H:%M:%S}")
                            text, color = f"{name} (present)", GREEN
                        elif not active.real_enough(student_id):
                            text, color = f"{name}: hold still, verifying", YELLOW
                        else:
                            text, color = f"{name}: turn head slowly", YELLOW
                    else:
                        mark_present(csv_path, student_id, name, method="face")
                        marked.add(student_id)
                        print(f"  Marked present: {name} (id={student_id}) at {datetime.now():%H:%M:%S}")
                        text, color = f"{name} (present)", GREEN

                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, text, (x, max(20, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            cv2.putText(frame, f"{subject} [{session}] | Present: {len(marked)}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
            cv2.imshow("Attendance - press q to quit", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()

    print(f"\nSession {session} ended. {len(marked)} student(s) marked present for {subject}.")
    if marked:
        print(f"See: {csv_path}")
    return len(marked)


def main():
    parser = argparse.ArgumentParser(description="Take attendance for a subject.")
    parser.add_argument("--subject", help="Subject name, e.g. Maths")
    parser.add_argument("--session", help="Lecture label, e.g. L1 (blank = start time)")
    args = parser.parse_args()
    subject = args.subject or input("Subject name: ")
    run(subject, make_session(args.session))


if __name__ == "__main__":
    main()

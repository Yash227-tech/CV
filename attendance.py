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


def csv_path_for(subject: str, date: str = None) -> str:
    date = date or f"{datetime.now():%Y-%m-%d}"
    subj = sanitize_subject(subject)
    return os.path.join(subject_dir(subject), f"{subj}_{date}.csv")


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


def mark_manually(subject, student_id, name=None):
    """Mark a student present by id, without the camera.

    If name is None it is looked up from the enrollments. Returns a status string.
    """
    ids, names, _ = store.load_enrollments()
    roster = dict(zip(ids, names))
    student_id = str(student_id).strip()
    if name is None:
        if student_id not in roster:
            return f"Unknown id '{student_id}' (not enrolled). Pass a name or enroll first."
        name = roster[student_id]
    path = csv_path_for(subject)
    if mark_present(path, student_id, name, method="manual"):
        return f"Marked present (manual): {name} (id={student_id}) for {sanitize_subject(subject)}"
    return f"{name} (id={student_id}) was already marked for {sanitize_subject(subject)} today."


def best_match(embedding, enrolled):
    """enrolled is (N, 128) L2-normalised. Return (index, cosine_score) of best match."""
    if len(enrolled) == 0:
        return -1, -1.0
    scores = enrolled @ embedding
    i = int(np.argmax(scores))
    return i, float(scores[i])


def run(subject):
    config.ensure_dirs()
    subject = sanitize_subject(subject)
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

    csv_path = csv_path_for(subject)
    marked = load_already_marked(csv_path)

    print(f"\nAttendance running for subject: {subject}. {len(ids)} student(s) enrolled.")
    print(f"Writing to: {csv_path}")
    if config.ANTISPOOF_ENABLED and live.available():
        print("Anti-spoofing ON" + (" + move/turn challenge." if config.ACTIVE_LIVENESS_ENABLED else "."))
    print("Press 'q' to stop.\n")

    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                continue

            for face in engine.detect(frame):
                x, y, w, h = face[:4].astype(int)
                emb = engine.embed(frame, face)
                idx, score = best_match(emb, enrolled)
                recognized = score >= config.COSINE_THRESHOLD

                # ---- Passive liveness (photo / screen rejection) -------------
                passive_ok, p = (True, None)
                if live is not None:
                    passive_ok, p = live.is_real(frame, (x, y, w, h))

                RED, GREEN, YELLOW, ORANGE = (0, 0, 255), (0, 255, 0), (0, 255, 255), (0, 165, 255)

                if live is not None and not passive_ok:
                    # Looks like a photo or a screen - never mark.
                    text, color = f"SPOOF? {p:.2f}", RED
                elif not recognized:
                    text, color = f"Unknown ({score:.2f})", RED
                else:
                    student_id, name = ids[idx], names[idx]
                    if student_id in marked:
                        text, color = f"{name} (present)", GREEN
                    elif active is not None:
                        # Active challenge: require real streak + head movement.
                        active.update(student_id, passive_ok, yaw_proxy(face))
                        if active.passed(student_id):
                            mark_present(csv_path, student_id, name, method="face")
                            marked.add(student_id)
                            print(f"  Marked present: {name} (id={student_id}) at {datetime.now():%H:%M:%S}")
                            text, color = f"{name} (present)", GREEN
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

            cv2.putText(frame, f"{subject} | Present: {len(marked)}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
            cv2.imshow("Attendance - press q to quit", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()

    print(f"\nSession ended. {len(marked)} student(s) marked present for {subject} today.")
    if marked:
        print(f"See: {csv_path}")
    return len(marked)


def main():
    parser = argparse.ArgumentParser(description="Take attendance for a subject.")
    parser.add_argument("--subject", help="Subject name, e.g. Maths")
    args = parser.parse_args()
    subject = args.subject or input("Subject name: ")
    run(subject)


if __name__ == "__main__":
    main()

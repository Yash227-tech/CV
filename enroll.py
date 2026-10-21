"""
Enroll students from a SINGLE photo each (no training step needed).

Three ways to enroll:

1. From one image file:
       python enroll.py --image photos/alice.jpg --id 101 --name "Alice"

2. From a folder of photos, one image per student, named "<id>_<name>.jpg":
       python enroll.py --dir photos
   e.g. photos/101_Alice.jpg, photos/102_Bob.jpg

3. From a webcam snapshot (press SPACE to capture, q to cancel):
       python enroll.py --webcam --id 101 --name "Alice"
"""
import argparse
import os

import cv2

import config
import store
from face_engine import FaceEngine


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp")


def _store_refs(student_id, name, embs, append):
    """append=True adds to a student's existing references; False replaces them."""
    if append:
        refs, total = store.add_references(student_id, name, embs)
        verb = "added photo to"
    else:
        refs, total = store.set_references(student_id, name, embs)
        verb = "enrolled"
    print(f"  {verb}: {name} (id={student_id})  [references: {refs}, students: {total}]")


def enroll_image(engine, image_path, student_id, name, append=False):
    img = cv2.imread(image_path)
    if img is None:
        print(f"  ! Could not read image: {image_path}")
        return False
    embs = engine.embed_references(img)
    if not embs:
        print(f"  ! No face detected in: {image_path}")
        return False
    _store_refs(student_id, name, embs, append)
    return True


def enroll_dir(engine, folder):
    if not os.path.isdir(folder):
        raise SystemExit(f"Not a folder: {folder}")
    files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith(IMAGE_EXTS)]
    if not files:
        raise SystemExit(f"No images found in {folder}")

    print(f"Enrolling from {folder} ({len(files)} image(s))...")
    ok = 0
    for f in files:
        stem = os.path.splitext(f)[0]
        student_id, _, name = stem.partition("_")
        if not name:
            name = student_id
        if enroll_image(engine, os.path.join(folder, f), student_id, name):
            ok += 1
    print(f"\nEnrolled {ok}/{len(files)} student(s).")


def enroll_webcam(engine, student_id, name, append=False):
    cam = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cam.isOpened():
        raise SystemExit("Could not open the webcam. Check CAMERA_INDEX in config.py.")

    print("\nLook at the camera. Press SPACE to capture, q to cancel.")
    captured = None
    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                continue
            faces = engine.detect(frame)
            face = engine.largest_face(faces)
            if face is not None:
                x, y, w, h = face[:4].astype(int)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, "SPACE = capture   q = cancel", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.imshow("Enroll", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" ") and face is not None:
                captured = frame.copy()
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()

    if captured is None:
        print("Cancelled - nothing captured.")
        return
    embs = engine.embed_references(captured)
    if not embs:
        print("No face found in the captured frame.")
        return
    _store_refs(student_id, name, embs, append)


def list_students():
    rows = store.roster()
    if not rows:
        print("No students enrolled yet.")
        return
    print(f"Enrolled students ({len(rows)}):")
    for sid, name, refs in rows:
        print(f"  {sid:<8}{name:<20} ({refs} reference photo{'s' if refs != 1 else ''})")


def main():
    parser = argparse.ArgumentParser(description="Enroll students from a single photo each.")
    parser.add_argument("--image", help="Path to one student's photo")
    parser.add_argument("--dir", help="Folder of photos named <id>_<name>.jpg")
    parser.add_argument("--webcam", action="store_true", help="Capture one snapshot from the webcam")
    parser.add_argument("--id", help="Student ID (for --image / --webcam)")
    parser.add_argument("--name", help="Student name (for --image / --webcam)")
    parser.add_argument("--list", action="store_true", help="List enrolled students")
    parser.add_argument("--delete", metavar="ID", help="Delete an enrolled student by ID")
    parser.add_argument("--append", action="store_true",
                        help="Add this photo as an EXTRA reference (e.g. without glasses) "
                             "instead of replacing the student's existing photos")
    args = parser.parse_args()

    config.ensure_dirs()

    if args.list:
        list_students()
        return
    if args.delete:
        removed, remaining = store.delete(args.delete)
        if removed is None:
            print(f"No enrolled student with id '{args.delete}'.")
        else:
            print(f"Deleted {removed} (id={args.delete}). [{remaining} still enrolled]")
        return

    # When appending, the name can be looked up from the existing enrollment.
    def resolve_name():
        if args.name:
            return args.name
        if args.append:
            for sid, name, _ in store.roster():
                if sid == str(args.id).strip():
                    return name
        return None

    engine = FaceEngine()
    if args.dir:
        enroll_dir(engine, args.dir)
    elif args.image:
        name = resolve_name()
        if not args.id or not name:
            raise SystemExit("--image also needs --id and --name")
        enroll_image(engine, args.image, args.id, name, append=args.append)
    elif args.webcam:
        name = resolve_name()
        if not args.id or not name:
            raise SystemExit("--webcam also needs --id and --name")
        enroll_webcam(engine, args.id, name, append=args.append)
    else:
        parser.print_help()
        return

    print("\nNext step: run  python attendance.py")


if __name__ == "__main__":
    main()

"""
Face Recognition Attendance - command-line menu.
(For the graphical version, run:  python gui.py)

    python main.py
"""
import config
import store
import attendance
import report
from face_engine import FaceEngine
import enroll


def menu():
    config.ensure_dirs()
    while True:
        print("\n=== Face Recognition Attendance (single-photo) ===")
        print(f"Enrolled students: {store.student_count()}   |   Subjects: {len(report.list_subjects())}")
        print("1. Enroll a student from an image file")
        print("2. Enroll a student from a webcam snapshot")
        print("3. Enroll everyone from a folder of photos")
        print("4. Add another photo to a student (e.g. without glasses)")
        print("5. Take attendance (face) for a subject")
        print("6. Manual attendance for a subject")
        print("7. Show attendance report")
        print("8. List / delete enrolled students")
        print("9. Launch graphical interface (GUI)")
        print("0. Exit")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            path = input("Image path: ").strip().strip('"')
            sid = input("Student ID: ")
            name = input("Student name: ")
            enroll.enroll_image(FaceEngine(), path, sid, name)
        elif choice == "2":
            sid = input("Student ID: ")
            name = input("Student name: ")
            enroll.enroll_webcam(FaceEngine(), sid, name)
        elif choice == "3":
            folder = input("Folder path (files named <id>_<name>.jpg): ").strip().strip('"')
            enroll.enroll_dir(FaceEngine(), folder)
        elif choice == "4":
            enroll.list_students()
            sid = input("Student ID to add a photo to: ").strip()
            name = next((n for i, n, _ in store.roster() if i == sid), None)
            if name is None:
                print(f"No enrolled student with id '{sid}'.")
            else:
                src = input("Source - [i]mage file or [w]ebcam? ").strip().lower()
                if src.startswith("w"):
                    enroll.enroll_webcam(FaceEngine(), sid, name, append=True)
                else:
                    path = input("Image path: ").strip().strip('"')
                    enroll.enroll_image(FaceEngine(), path, sid, name, append=True)
        elif choice == "5":
            subject = input("Subject name: ")
            attendance.run(subject)
        elif choice == "6":
            subject = input("Subject name: ")
            sid = input("Student ID to mark present: ")
            print(attendance.mark_manually(subject, sid))
        elif choice == "7":
            subject = input("Subject (blank = all): ").strip()
            report.print_summary(subject or None)
        elif choice == "8":
            enroll.list_students()
            sid = input("Enter an ID to delete (blank to skip): ").strip()
            if sid:
                removed, remaining = store.delete(sid)
                if removed is None:
                    print(f"No enrolled student with id '{sid}'.")
                else:
                    print(f"Deleted {removed} (id={sid}). [{remaining} still enrolled]")
        elif choice == "9":
            import gui
            gui.main()
        elif choice == "0":
            print("Bye.")
            break
        else:
            print("Invalid choice, try again.")


if __name__ == "__main__":
    menu()

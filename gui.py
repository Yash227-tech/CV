"""
Teacher app - the day-to-day interface for teachers.

Teachers open their lecture (check-in), take attendance (face or manual) and
view reports. It does NOT contain any enrollment screens - students and
teachers are set up by the tech team in the admin console (admin.py).

Run:
    python gui.py
"""
import csv
import os
import tkinter as tk
from tkinter import ttk, messagebox

import store
import subjects
import teachers
import attendance
import report
from ui_common import BaseApp, C, FONT

# The face engine loads ~37 MB of models, so create it lazily and reuse it.
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from face_engine import FaceEngine
        _engine = FaceEngine()
    return _engine


class TeacherApp(BaseApp):
    def __init__(self, root):
        self.subject_var = tk.StringVar()
        self.session_var = tk.StringVar()
        self.teacher_var = tk.StringVar()
        self.report_subject_var = tk.StringVar()
        super().__init__(root, "Face Attendance", "teacher · attendance",
                         nav=[("dashboard", "Dashboard"), ("attendance", "Attendance"),
                              ("reports", "Reports")])

    def refresh_status(self):
        self.status.configure(
            text=f"{store.student_count()} students   ·   {teachers.count()} teachers   ·   "
                 f"{len(subjects.list_subjects())} subjects")

    def _build_pages(self):
        for name in ("dashboard", "attendance", "reports"):
            self.pages[name] = tk.Frame(self.content, bg=C["bg"])
        self._build_dashboard(self.pages["dashboard"])
        self._build_attendance(self.pages["attendance"])
        self._build_reports(self.pages["reports"])

    # ---- Dashboard ----------------------------------------------------------
    def _build_dashboard(self, page):
        row = tk.Frame(page, bg=C["bg"]); row.pack(fill="x")
        self.stat_vals = {}
        for key, label in (("students", "Students enrolled"), ("teachers", "Teachers"),
                           ("subjects", "Subjects")):
            wrap, card = self._card(row)
            wrap.pack(side="left", expand=True, fill="x", padx=(0, 14))
            val = tk.Label(card, text="0", bg=C["card"], fg=C["accent"], font=(FONT, 30, "bold"))
            val.pack(anchor="w", padx=18, pady=(16, 0))
            tk.Label(card, text=label, bg=C["card"], fg=C["muted"], font=(FONT, 10)).pack(anchor="w", padx=18, pady=(0, 16))
            self.stat_vals[key] = val

        wrap, card = self._card(page)
        wrap.pack(fill="both", expand=True, pady=(18, 0))
        self._card_title(card, "How to take attendance")
        steps = ("1.  Go to Attendance and choose your Subject.\n"
                 "2.  Check in: click 'Open lecture' and verify your face at the camera.\n"
                 "3.  Click 'Start Face Attendance' (or mark students manually).\n"
                 "        Students look at the camera and turn their head slightly (anti-spoofing).\n"
                 "4.  When the class ends, click 'Close lecture' (verify your face again).\n"
                 "5.  See attendance % per subject in Reports.\n\n"
                 "Students and teachers (with their face photos) are added by the tech team\n"
                 "in the admin console.")
        tk.Label(card, text=steps, bg=C["card"], fg=C["text"], font=(FONT, 11),
                 justify="left").pack(anchor="w", padx=18, pady=(8, 18))

    def refresh_dashboard(self):
        ids, _, _ = store.load_enrollments()
        self.stat_vals["students"].configure(text=str(store.student_count()))
        self.stat_vals["teachers"].configure(text=str(teachers.count()))
        self.stat_vals["subjects"].configure(text=str(len(subjects.list_subjects())))

    # ---- Attendance ---------------------------------------------------------
    def _build_attendance(self, page):
        wrap, card = self._card(page)
        wrap.pack(fill="x")
        inner = tk.Frame(card, bg=C["card"]); inner.pack(fill="x", padx=16, pady=16)

        tk.Label(inner, text="Subject", bg=C["card"], fg=C["muted"], font=(FONT, 9)).grid(row=0, column=0, sticky="w")
        self.subject_combo = ttk.Combobox(inner, textvariable=self.subject_var, width=24)
        self.subject_combo.grid(row=1, column=0, sticky="w", pady=(0, 10))
        self.subject_combo.bind("<<ComboboxSelected>>", lambda e: self._on_subject_change())
        self.subject_combo.bind("<Return>", lambda e: self.add_subject())
        ttk.Button(inner, text="Add / set", style="Ghost.TButton",
                   command=self.add_subject).grid(row=1, column=1, padx=8, pady=(0, 10))

        tk.Label(inner, text="Session (existing)", bg=C["card"], fg=C["muted"], font=(FONT, 9)).grid(row=2, column=0, sticky="w")
        tk.Label(inner, text="or New lecture label", bg=C["card"], fg=C["muted"], font=(FONT, 9)).grid(row=2, column=1, sticky="w", padx=(8, 0))
        self.session_combo = ttk.Combobox(inner, textvariable=self.session_var, width=24, state="readonly")
        self.session_combo.grid(row=3, column=0, sticky="w")
        self.session_combo.bind("<<ComboboxSelected>>", lambda e: self._on_session_change())
        self.new_session_entry = ttk.Entry(inner, width=14)
        self.new_session_entry.grid(row=3, column=1, sticky="w", padx=(8, 0))
        ttk.Button(inner, text="▶  Start Face Attendance", style="Big.TButton",
                   command=self.start_attendance).grid(row=3, column=2, padx=(18, 0))

        trow = tk.Frame(card, bg=C["card"]); trow.pack(fill="x", padx=16, pady=(4, 6))
        ttk.Button(trow, text="Open lecture (face check-in)", style="Accent.TButton",
                   command=self.open_lecture).pack(side="left")
        ttk.Button(trow, text="Close lecture (end)", style="Danger.TButton",
                   command=self.close_lecture).pack(side="left", padx=(8, 0))
        self.session_status = tk.Label(trow, text="", bg=C["card"], font=(FONT, 10, "bold"))
        self.session_status.pack(side="left", padx=14)

        tk.Label(card, text="Open the lecture first - you verify your face at the camera (registered "
                            "teachers only); only then is student attendance allowed. Closing a lecture "
                            "also needs your face. Each lecture is a session - a subject can have many per day.",
                 bg=C["card"], fg=C["muted"], font=(FONT, 9), justify="left", wraplength=820).pack(anchor="w", padx=16, pady=(0, 12))

        panes = tk.Frame(page, bg=C["bg"]); panes.pack(fill="both", expand=True, pady=(16, 0))
        wrap, card = self._card(panes)
        wrap.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._card_title(card, "Manual attendance")
        tframe, self.manual_tree = self._styled_tree(card, ("id", "name"), ("ID", "Name"),
                                                     (70, 190), ("center", "w"), height=9)
        tframe.pack(fill="both", expand=True, padx=16, pady=(8, 8))
        ttk.Button(card, text="Mark present (manual)", style="Accent.TButton",
                   command=self.manual_mark).pack(padx=16, pady=(0, 14), anchor="w")

        wrap, card = self._card(panes)
        wrap.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._card_title(card, "Present in selected session")
        tframe, self.today_tree = self._styled_tree(
            card, ("id", "name", "time", "method"), ("ID", "Name", "Time", "By"),
            (60, 140, 80, 70), ("center", "w", "center", "center"), height=9)
        tframe.pack(fill="both", expand=True, padx=16, pady=(8, 8))
        tbar = tk.Frame(card, bg=C["card"]); tbar.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(tbar, text="Remove selected", style="Danger.TButton", command=self.remove_attendance).pack(side="left")
        ttk.Button(tbar, text="Refresh", style="Ghost.TButton", command=self.refresh_present).pack(side="right")

    def refresh_attendance(self):
        self.subject_combo["values"] = subjects.list_subjects()
        self._fill_tree(self.manual_tree, [(s, n) for s, n, _ in store.roster()])
        self._refresh_sessions()
        self.refresh_present()

    def _refresh_sessions(self, select=None):
        subject = subjects.sanitize(self.subject_var.get())
        sess = attendance.today_sessions(subject) if subject else []
        self.session_combo["values"] = sess
        if select:
            self.session_var.set(select)
        elif self.session_var.get() not in sess:
            self.session_var.set(sess[-1] if sess else "")
        self._update_session_status()

    def _update_session_status(self):
        subject = subjects.sanitize(self.subject_var.get())
        session = self.session_var.get().strip()
        status = attendance.session_status(subject, session) if (subject and session) else "none"
        if status == "open":
            t = attendance.session_teacher(subject, session) or "Teacher"
            self.session_status.configure(text=f"● Open (teacher: {t})", fg=C["success"])
        elif status == "closed":
            t = attendance.session_teacher(subject, session) or "Teacher"
            self.session_status.configure(text=f"● Closed (teacher: {t})", fg=C["muted"])
        else:
            self.session_status.configure(text="● Not open – teacher check-in required", fg=C["danger"])

    def _on_session_change(self):
        self.refresh_present()
        self._update_session_status()

    def _on_subject_change(self):
        self._refresh_sessions()
        self.refresh_present()
        self.refresh_status()

    def add_subject(self):
        name = subjects.add_subject(self.subject_var.get())
        if not name:
            messagebox.showwarning("Subject", "Enter a subject name first.")
            return
        self.subject_var.set(name)
        self.subject_combo["values"] = subjects.list_subjects()
        self._on_subject_change()

    def _current_subject(self):
        name = subjects.sanitize(self.subject_var.get())
        if not name:
            messagebox.showwarning("Subject", "Select or type a subject first.")
        return name

    def _target_session(self):
        label = self.new_session_entry.get().strip()
        if label:
            return attendance.make_session(label)
        if self.session_var.get().strip():
            return self.session_var.get().strip()
        return attendance.make_session()

    def _verify_teacher(self, purpose):
        """Scan + verify a registered teacher's face. Returns the teacher name,
        or None (a message is shown explaining why)."""
        if teachers.faces_count() == 0:
            messagebox.showwarning(
                "No teacher faces",
                "No teacher has a face enrolled yet. Ask the tech team to enrol teacher "
                "photos in the admin console before lectures can be opened or closed.")
            return None
        messagebox.showinfo("Teacher check-in",
                            f"A camera window opens to verify your face before you {purpose} the lecture.\n\n"
                            "Look at the camera and turn your head slightly (anti-spoofing). Press q to cancel.")
        res = attendance.verify_teacher(purpose)
        if res["ok"]:
            return res["name"]
        reason = {
            "no_faces": "No teacher faces are enrolled. Ask the tech team to enrol teacher photos.",
            "no_camera": "Could not open the webcam. Check CAMERA_INDEX in config.py.",
            "cancelled": "Face not verified (cancelled or no registered teacher recognised). "
                         f"The lecture was not {purpose}ed.",
        }.get(res["reason"], "Teacher not verified.")
        messagebox.showwarning("Not verified", reason)
        return None

    def open_lecture(self):
        subject = self._current_subject()
        if not subject:
            return
        teacher = self._verify_teacher("open")
        if not teacher:
            return
        subjects.add_subject(subject)
        self.subject_combo["values"] = subjects.list_subjects()
        session = self._target_session()
        msg = attendance.open_session(subject, session, teacher)
        self.new_session_entry.delete(0, "end")
        self._refresh_sessions(select=session)
        self.refresh_present()
        messagebox.showinfo("Lecture", msg)

    def close_lecture(self):
        subject = self._current_subject()
        if not subject:
            return
        session = self.session_var.get().strip()
        if not session:
            messagebox.showwarning("Session", "Select the lecture (session) you want to close first.")
            return
        if attendance.session_status(subject, session) != "open":
            messagebox.showinfo("Lecture", f"Lecture {session} is not open, so there is nothing to close.")
            return
        if not messagebox.askyesno("Close lecture",
                                   f"End (close) {subject} lecture {session}?\n\n"
                                   "No further attendance can be marked for it until it is re-opened."):
            return
        teacher = self._verify_teacher("close")
        if not teacher:
            return
        msg = attendance.close_session(subject, session, teacher)
        self._update_session_status()
        self.refresh_present()
        messagebox.showinfo("Lecture", msg)

    def start_attendance(self):
        if store.student_count() == 0:
            messagebox.showwarning("No students", "No students enrolled. Ask the tech team to enroll students.")
            return
        subject = self._current_subject()
        if not subject:
            return
        session = self._target_session()
        if not attendance.session_opened(subject, session):
            messagebox.showwarning("Lecture not open",
                                   "Open this lecture first: select your name as Teacher and click "
                                   "'Open lecture (check-in)'.")
            return
        messagebox.showinfo("Attendance", f"Camera opens for '{subject}', session {session}.\nPress q to stop.")
        try:
            n = attendance.run(subject, session)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        messagebox.showinfo("Done", f"{n} student(s) marked present for {subject} [{session}].")
        self._refresh_sessions(select=session)
        self.refresh_present(); self.refresh_status()

    def manual_mark(self):
        subject = self._current_subject()
        if not subject:
            return
        sel = self.manual_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Pick a student from the list first.")
            return
        sid, name = self.manual_tree.item(sel[0], "values")
        session = self._target_session()
        messagebox.showinfo("Manual attendance", attendance.mark_manually(subject, sid, name, session))
        self._refresh_sessions(select=session)
        self.refresh_present()

    def remove_attendance(self):
        subject = self._current_subject()
        if not subject:
            return
        session = self.session_var.get().strip()
        if not session:
            messagebox.showwarning("Session", "Select a session first.")
            return
        sel = self.today_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Pick a record from the session list to remove.")
            return
        sid, name = self.today_tree.item(sel[0], "values")[:2]
        if not messagebox.askyesno("Remove attendance",
                                   f"Remove {name} (id={sid}) from {subject} session {session}?"):
            return
        messagebox.showinfo("Attendance", attendance.unmark(subject, sid, session))
        self.refresh_present()

    def refresh_present(self):
        subject = subjects.sanitize(self.subject_var.get())
        session = self.session_var.get().strip()
        rows = []
        if subject and session:
            path = attendance.csv_path_for(subject, session)
            if os.path.exists(path):
                with open(path, newline="", encoding="utf-8") as f:
                    for r in csv.DictReader(f):
                        rows.append((r.get("id", ""), r.get("name", ""), r.get("time", ""), r.get("method", "")))
        self._fill_tree(self.today_tree, rows)

    # ---- Reports ------------------------------------------------------------
    def _build_reports(self, page):
        wrap, card = self._card(page)
        wrap.pack(fill="x")
        bar = tk.Frame(card, bg=C["card"]); bar.pack(fill="x", padx=16, pady=16)
        tk.Label(bar, text="Subject", bg=C["card"], fg=C["muted"], font=(FONT, 9)).pack(side="left", padx=(0, 8))
        self.report_combo = ttk.Combobox(bar, textvariable=self.report_subject_var, width=24, state="readonly")
        self.report_combo.pack(side="left")
        ttk.Button(bar, text="Show report", style="Accent.TButton", command=self.show_report).pack(side="left", padx=10)
        ttk.Button(bar, text="Export CSV", style="Ghost.TButton", command=self.export_report).pack(side="left")
        self.report_info = tk.Label(bar, text="", bg=C["card"], fg=C["muted"], font=(FONT, 10))
        self.report_info.pack(side="right")

        wrap, card = self._card(page)
        wrap.pack(fill="both", expand=True, pady=(16, 0))
        tframe, self.report_tree = self._styled_tree(
            card, ("id", "name", "present", "total", "percent"),
            ("ID", "Name", "Sessions attended", "Total sessions", "Attendance %"),
            (80, 240, 140, 120, 120), ("center", "w", "center", "center", "center"), height=11)
        tframe.pack(fill="both", expand=True, padx=16, pady=16)

    def refresh_reports(self):
        subs = report.list_subjects()
        self.report_combo["values"] = subs
        if subs and not self.report_subject_var.get():
            self.report_subject_var.set(subs[0])
        if self.report_subject_var.get():
            self.show_report()
        else:
            self._fill_tree(self.report_tree, [])
            self.report_info.configure(text="No attendance records yet")

    def show_report(self):
        subject = self.report_subject_var.get()
        if not subject:
            return
        sessions, rows = report.build_summary(subject)
        self.report_info.configure(text=(f"{len(sessions)} session(s)" if sessions else "no records"))
        self._fill_tree(self.report_tree, [
            (r["id"], r["name"], r["sessions_attended"], r["total_sessions"], f"{r['percent']:.1f}%")
            for r in rows])

    def export_report(self):
        subject = self.report_subject_var.get()
        if not subject:
            messagebox.showinfo("Report", "Pick a subject first.")
            return
        messagebox.showinfo("Exported", f"Wrote:\n{report.export_summary(subject)}")


def main():
    root = tk.Tk()
    TeacherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""
Face Recognition Attendance - graphical application.

A tabbed desktop UI (Tkinter/ttk):
  - Students : enroll / add photo / delete, shown in a table
  - Attendance : pick a subject ONCE (dropdown), then face or manual attendance
  - Reports : per-student attendance %, per subject, with CSV export

Run:
    python gui.py
"""
import csv
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import config
import store
import subjects
import attendance
import report

# The face engine loads ~37 MB of models, so create it lazily and reuse it.
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from face_engine import FaceEngine
        _engine = FaceEngine()
    return _engine


PAD = {"padx": 8, "pady": 6}


class App:
    def __init__(self, root):
        self.root = root
        root.title("Face Recognition Attendance")
        root.geometry("820x600")
        root.minsize(720, 540)
        config.ensure_dirs()

        self._init_style()
        self.subject_var = tk.StringVar()

        # Header
        header = ttk.Frame(root, padding=(14, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Face Recognition Attendance",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="single-photo · multi-subject",
                  style="Sub.TLabel").pack(side="left", padx=12)

        # Tabs
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.tab_students = ttk.Frame(self.nb, padding=12)
        self.tab_attend = ttk.Frame(self.nb, padding=12)
        self.tab_reports = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_students, text="  Students  ")
        self.nb.add(self.tab_attend, text="  Attendance  ")
        self.nb.add(self.tab_reports, text="  Reports  ")

        self._build_students_tab()
        self._build_attendance_tab()
        self._build_reports_tab()

        # Status bar
        self.status = ttk.Label(root, anchor="w", relief="sunken", style="Status.TLabel")
        self.status.pack(fill="x", side="bottom")

        self.refresh_subjects()
        self.refresh_students()
        self.refresh_status()

    # ---- styling ------------------------------------------------------------
    def _init_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 10), foreground="#666")
        style.configure("Status.TLabel", font=("Segoe UI", 9), padding=4, foreground="#333")
        style.configure("H.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Treeview", rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def refresh_status(self):
        self.status.config(
            text=f"  Enrolled students: {store.student_count()}    |    "
                 f"Subjects: {len(subjects.list_subjects())}    |    "
                 f"Current subject: {self.subject_var.get() or '(none selected)'}")

    # ---- Students tab -------------------------------------------------------
    def _build_students_tab(self):
        t = self.tab_students

        form = ttk.LabelFrame(t, text="Enroll a new student", padding=10)
        form.pack(fill="x")
        ttk.Label(form, text="ID:").grid(row=0, column=0, sticky="e", **PAD)
        self.id_entry = ttk.Entry(form, width=14)
        self.id_entry.grid(row=0, column=1, sticky="w", **PAD)
        ttk.Label(form, text="Name:").grid(row=0, column=2, sticky="e", **PAD)
        self.name_entry = ttk.Entry(form, width=22)
        self.name_entry.grid(row=0, column=3, sticky="w", **PAD)
        ttk.Button(form, text="Enroll from image…", command=self.enroll_image).grid(row=0, column=4, **PAD)
        ttk.Button(form, text="Enroll from webcam", command=self.enroll_webcam).grid(row=0, column=5, **PAD)

        # Table of enrolled students
        table = ttk.LabelFrame(t, text="Enrolled students", padding=10)
        table.pack(fill="both", expand=True, pady=(10, 0))
        cols = ("id", "name", "photos")
        self.stu_tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="browse")
        for c, txt, w, anc in (("id", "ID", 90, "center"), ("name", "Name", 300, "w"),
                               ("photos", "Reference photos", 140, "center")):
            self.stu_tree.heading(c, text=txt)
            self.stu_tree.column(c, width=w, anchor=anc)
        self.stu_tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(table, orient="vertical", command=self.stu_tree.yview)
        sb.pack(side="right", fill="y")
        self.stu_tree.configure(yscrollcommand=sb.set)

        btns = ttk.Frame(t, padding=(0, 10))
        btns.pack(fill="x")
        ttk.Button(btns, text="Add another photo (e.g. no glasses)…",
                   command=self.add_photo).pack(side="left", padx=4)
        ttk.Button(btns, text="Enroll everyone from a folder…",
                   command=self.enroll_folder).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete selected", command=self.delete_student).pack(side="left", padx=4)
        ttk.Button(btns, text="Refresh", command=self.refresh_students).pack(side="left", padx=4)

    def refresh_students(self):
        self.stu_tree.delete(*self.stu_tree.get_children())
        for sid, name, refs in store.roster():
            self.stu_tree.insert("", "end", values=(sid, name, refs))
        self.refresh_status()

    def _selected_student(self):
        sel = self.stu_tree.selection()
        if not sel:
            messagebox.showwarning("Select a student", "Pick a student from the table first.")
            return None
        return self.stu_tree.item(sel[0], "values")  # (id, name, photos)

    def _form_id_name(self):
        sid = self.id_entry.get().strip()
        name = self.name_entry.get().strip()
        if not sid or not name:
            messagebox.showwarning("Missing info", "Enter both an ID and a Name above first.")
            return None, None
        return sid, name

    def enroll_image(self):
        sid, name = self._form_id_name()
        if not sid:
            return
        path = filedialog.askopenfilename(
            title="Choose the student's photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")])
        if not path:
            return
        self._do_enroll_image(path, sid, name, append=False)

    def enroll_webcam(self):
        sid, name = self._form_id_name()
        if not sid:
            return
        messagebox.showinfo("Webcam", "A camera window opens.\nPress SPACE to capture, q to cancel.")
        import enroll as enr
        try:
            enr.enroll_webcam(get_engine(), sid, name, append=False)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        self._clear_form(); self.refresh_students()

    def enroll_folder(self):
        folder = filedialog.askdirectory(title="Folder of photos named <id>_<name>.jpg")
        if not folder:
            return
        import enroll as enr
        try:
            enr.enroll_dir(get_engine(), folder)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        messagebox.showinfo("Done", "Folder enrollment finished (see console for per-file details).")
        self.refresh_students()

    def _do_enroll_image(self, path, sid, name, append):
        import enroll as enr
        try:
            ok = enr.enroll_image(get_engine(), path, sid, name, append=append)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        if ok:
            msg = "Added another photo." if append else f"Enrolled {name} (id={sid})."
            messagebox.showinfo("Success", msg)
            self._clear_form(); self.refresh_students()
        else:
            messagebox.showwarning("No face", "Could not detect a face in that image.")

    def _clear_form(self):
        self.id_entry.delete(0, "end")
        self.name_entry.delete(0, "end")

    def add_photo(self):
        s = self._selected_student()
        if not s:
            return
        sid, name = s[0], s[1]
        if messagebox.askyesno("Source", f"Add a photo for {name}.\n\nYes = image file,  No = webcam"):
            path = filedialog.askopenfilename(
                title=f"Another photo of {name}",
                filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")])
            if not path:
                return
            self._do_enroll_image(path, sid, name, append=True)
        else:
            messagebox.showinfo("Webcam", "Camera opens. SPACE to capture, q to cancel.")
            import enroll as enr
            enr.enroll_webcam(get_engine(), sid, name, append=True)
            self.refresh_students()

    def delete_student(self):
        s = self._selected_student()
        if not s:
            return
        sid, name = s[0], s[1]
        if messagebox.askyesno("Confirm delete",
                               f"Delete {name} (id={sid}) and all their reference photos?"):
            store.delete(sid)
            self.refresh_students()

    # ---- Attendance tab -----------------------------------------------------
    def _build_attendance_tab(self):
        t = self.tab_attend

        bar = ttk.LabelFrame(t, text="Subject", padding=10)
        bar.pack(fill="x")
        ttk.Label(bar, text="Select or type a subject:").pack(side="left", **PAD)
        self.subject_combo = ttk.Combobox(bar, textvariable=self.subject_var, width=24)
        self.subject_combo.pack(side="left", **PAD)
        self.subject_combo.bind("<<ComboboxSelected>>", lambda e: self._on_subject_change())
        self.subject_combo.bind("<Return>", lambda e: self.add_subject())
        ttk.Button(bar, text="Add / set subject", command=self.add_subject).pack(side="left", **PAD)

        act = ttk.Frame(t, padding=(0, 14))
        act.pack(fill="x")
        ttk.Button(act, text="▶  Start Face Attendance", style="Big.TButton",
                   command=self.start_attendance).pack(side="left", padx=4)
        ttk.Label(act, text="Marks everyone the camera recognises, once each.",
                  style="Sub.TLabel").pack(side="left", padx=8)

        # Manual + today's list, side by side
        panes = ttk.Frame(t)
        panes.pack(fill="both", expand=True)

        manual = ttk.LabelFrame(panes, text="Manual attendance", padding=10)
        manual.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ttk.Label(manual, text="Pick a student and mark them present\nfor the selected subject:",
                  style="Sub.TLabel").pack(anchor="w")
        self.manual_tree = ttk.Treeview(manual, columns=("id", "name"), show="headings",
                                        selectmode="browse", height=10)
        self.manual_tree.heading("id", text="ID"); self.manual_tree.heading("name", text="Name")
        self.manual_tree.column("id", width=70, anchor="center"); self.manual_tree.column("name", width=180)
        self.manual_tree.pack(fill="both", expand=True, pady=6)
        ttk.Button(manual, text="Mark present (manual)", command=self.manual_mark).pack()

        todays = ttk.LabelFrame(panes, text="Present today (selected subject)", padding=10)
        todays.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.today_tree = ttk.Treeview(todays, columns=("id", "name", "time", "method"),
                                       show="headings", height=10)
        for c, txt, w in (("id", "ID", 60), ("name", "Name", 130), ("time", "Time", 80), ("method", "By", 70)):
            self.today_tree.heading(c, text=txt); self.today_tree.column(c, width=w, anchor="center")
        self.today_tree.pack(fill="both", expand=True, pady=6)
        ttk.Button(todays, text="Refresh", command=self.refresh_today).pack()

    def _on_subject_change(self):
        self.refresh_today()
        self.refresh_status()

    def add_subject(self):
        raw = self.subject_var.get()
        name = subjects.add_subject(raw)
        if not name:
            messagebox.showwarning("Subject", "Enter a subject name first.")
            return
        self.subject_var.set(name)
        self.refresh_subjects()
        self._on_subject_change()

    def refresh_subjects(self):
        subs = subjects.list_subjects()
        self.subject_combo["values"] = subs
        if self.subject_var.get() not in subs and subs:
            pass  # keep whatever the user typed
        self.refresh_report_subjects()

    def _current_subject(self):
        name = subjects.sanitize(self.subject_var.get())
        if not name:
            messagebox.showwarning("Subject", "Select or type a subject first (Attendance tab).")
        return name

    def refresh_manual_list(self):
        self.manual_tree.delete(*self.manual_tree.get_children())
        for sid, name, _refs in store.roster():
            self.manual_tree.insert("", "end", values=(sid, name))

    def start_attendance(self):
        if store.student_count() == 0:
            messagebox.showwarning("No students", "Enroll at least one student first.")
            return
        subject = self._current_subject()
        if not subject:
            return
        subjects.add_subject(subject)
        messagebox.showinfo("Attendance", f"Camera opens for '{subject}'.\nPress q to stop.")
        try:
            n = attendance.run(subject)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        messagebox.showinfo("Done", f"{n} student(s) marked present for {subject}.")
        self.refresh_subjects(); self.refresh_today(); self.refresh_status()

    def manual_mark(self):
        subject = self._current_subject()
        if not subject:
            return
        sel = self.manual_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Pick a student from the list first.")
            return
        sid, name = self.manual_tree.item(sel[0], "values")
        subjects.add_subject(subject)
        msg = attendance.mark_manually(subject, sid, name)
        messagebox.showinfo("Manual attendance", msg)
        self.refresh_subjects(); self.refresh_today(); self.refresh_status()

    def refresh_today(self):
        self.today_tree.delete(*self.today_tree.get_children())
        subject = subjects.sanitize(self.subject_var.get())
        if not subject:
            return
        path = attendance.csv_path_for(subject)
        if not os.path.exists(path):
            return
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self.today_tree.insert("", "end", values=(
                    row.get("id", ""), row.get("name", ""),
                    row.get("time", ""), row.get("method", "")))

    # ---- Reports tab --------------------------------------------------------
    def _build_reports_tab(self):
        t = self.tab_reports
        bar = ttk.Frame(t)
        bar.pack(fill="x")
        ttk.Label(bar, text="Subject:").pack(side="left", **PAD)
        self.report_subject_var = tk.StringVar()
        self.report_combo = ttk.Combobox(bar, textvariable=self.report_subject_var, width=24, state="readonly")
        self.report_combo.pack(side="left", **PAD)
        ttk.Button(bar, text="Show report", command=self.show_report).pack(side="left", **PAD)
        ttk.Button(bar, text="Export summary.csv", command=self.export_report).pack(side="left", **PAD)

        self.report_info = ttk.Label(t, text="", style="Sub.TLabel")
        self.report_info.pack(anchor="w", pady=(6, 0))

        frame = ttk.Frame(t)
        frame.pack(fill="both", expand=True, pady=6)
        cols = ("id", "name", "present", "total", "percent")
        self.report_tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, txt, w, anc in (("id", "ID", 80, "center"), ("name", "Name", 240, "w"),
                               ("present", "Days present", 110, "center"),
                               ("total", "Total days", 100, "center"),
                               ("percent", "Attendance %", 110, "center")):
            self.report_tree.heading(c, text=txt); self.report_tree.column(c, width=w, anchor=anc)
        self.report_tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.report_tree.yview)
        sb.pack(side="right", fill="y")
        self.report_tree.configure(yscrollcommand=sb.set)

    def refresh_report_subjects(self):
        if not hasattr(self, "report_combo"):
            return
        subs = report.list_subjects()
        self.report_combo["values"] = subs
        if subs and not self.report_subject_var.get():
            self.report_subject_var.set(subs[0])

    def show_report(self):
        subject = self.report_subject_var.get()
        if not subject:
            messagebox.showinfo("Report", "No subject with attendance records yet.")
            return
        self.report_tree.delete(*self.report_tree.get_children())
        dates, rows = report.build_summary(subject)
        self.report_info.config(
            text=f"{subject}: {len(dates)} day(s)" + (f"  ({dates[0]} .. {dates[-1]})" if dates else ""))
        for r in rows:
            self.report_tree.insert("", "end", values=(
                r["id"], r["name"], r["days_present"], r["total_days"], f"{r['percent']:.1f}%"))

    def export_report(self):
        subject = self.report_subject_var.get()
        if not subject:
            messagebox.showinfo("Report", "Pick a subject first.")
            return
        out = report.export_summary(subject)
        messagebox.showinfo("Exported", f"Wrote:\n{out}")

    # ---- tab switch hook: keep lists fresh ----------------------------------
    def on_tab_changed(self, _event=None):
        self.refresh_students()
        self.refresh_manual_list()
        self.refresh_report_subjects()
        self.refresh_today()


def main():
    root = tk.Tk()
    app = App(root)
    app.refresh_manual_list()
    root.bind("<<NotebookTabChanged>>", app.on_tab_changed)
    root.mainloop()


if __name__ == "__main__":
    main()

"""
Face Recognition Attendance - desktop application (restyled).

A single-window app with a sidebar, card-style panels and a custom theme.
Pages: Dashboard, Students, Attendance (per subject), Reports.

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

# ---- Colour palette ---------------------------------------------------------
C = {
    "sidebar":   "#1e2430",
    "sidebar_fg": "#aeb6c6",
    "sidebar_hi": "#2a3140",
    "accent":    "#3b82f6",
    "accent_dk": "#2563eb",
    "bg":        "#eef1f6",
    "card":      "#ffffff",
    "border":    "#e2e6ee",
    "text":      "#1f2733",
    "muted":     "#7a8699",
    "head":      "#eef2f8",
    "row_alt":   "#f7f9fc",
    "success":   "#16a34a",
    "danger":    "#dc2626",
    "chip":      "#eaf1fe",
}

FONT = "Segoe UI"

# The face engine loads ~37 MB of models, so create it lazily and reuse it.
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from face_engine import FaceEngine
        _engine = FaceEngine()
    return _engine


class App:
    def __init__(self, root):
        self.root = root
        root.title("Face Recognition Attendance")
        root.geometry("980x660")
        root.minsize(900, 600)
        root.configure(bg=C["bg"])
        config.ensure_dirs()

        self.subject_var = tk.StringVar()
        self.report_subject_var = tk.StringVar()
        self._init_style()
        self._build_layout()

        self.pages = {}
        self.nav_buttons = {}
        self._build_sidebar()
        self._build_pages()
        self.show_page("dashboard")

    # ---- theme --------------------------------------------------------------
    def _init_style(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass

        s.configure(".", font=(FONT, 10), background=C["bg"], foreground=C["text"])

        # Buttons
        s.configure("Accent.TButton", font=(FONT, 10, "bold"), foreground="white",
                    background=C["accent"], borderwidth=0, focusthickness=0, padding=(14, 9))
        s.map("Accent.TButton", background=[("active", C["accent_dk"]), ("pressed", C["accent_dk"])])

        s.configure("Big.TButton", font=(FONT, 12, "bold"), foreground="white",
                    background=C["accent"], borderwidth=0, padding=(18, 14))
        s.map("Big.TButton", background=[("active", C["accent_dk"])])

        s.configure("Ghost.TButton", font=(FONT, 10), foreground=C["text"],
                    background="#e7ebf2", borderwidth=0, padding=(12, 8))
        s.map("Ghost.TButton", background=[("active", "#d7dde8")])

        s.configure("Danger.TButton", font=(FONT, 10), foreground="white",
                    background=C["danger"], borderwidth=0, padding=(12, 8))
        s.map("Danger.TButton", background=[("active", "#b91c1c")])

        # Sidebar nav buttons
        s.configure("Nav.TButton", font=(FONT, 11), foreground=C["sidebar_fg"],
                    background=C["sidebar"], borderwidth=0, anchor="w", padding=(22, 12))
        s.map("Nav.TButton", background=[("active", C["sidebar_hi"])])
        s.configure("NavActive.TButton", font=(FONT, 11, "bold"), foreground="white",
                    background=C["accent"], borderwidth=0, anchor="w", padding=(22, 12))
        s.map("NavActive.TButton", background=[("active", C["accent"])])

        # Inputs
        s.configure("TEntry", padding=6, fieldbackground="white", bordercolor=C["border"])
        s.configure("TCombobox", padding=6, fieldbackground="white")

        # Treeview
        s.configure("Treeview", background="white", fieldbackground="white",
                    foreground=C["text"], rowheight=30, borderwidth=0)
        s.configure("Treeview.Heading", font=(FONT, 9, "bold"), foreground="#51607a",
                    background=C["head"], relief="flat", padding=8)
        s.map("Treeview.Heading", background=[("active", C["head"])])
        s.map("Treeview", background=[("selected", C["accent"])],
              foreground=[("selected", "white")])

    # ---- layout scaffolding -------------------------------------------------
    def _build_layout(self):
        self.sidebar = tk.Frame(self.root, bg=C["sidebar"], width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        right = tk.Frame(self.root, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        # Header bar
        self.header = tk.Frame(right, bg=C["bg"])
        self.header.pack(fill="x", padx=24, pady=(20, 6))
        self.page_title = tk.Label(self.header, text="", bg=C["bg"], fg=C["text"],
                                   font=(FONT, 20, "bold"))
        self.page_title.pack(side="left")
        self.status = tk.Label(self.header, text="", bg=C["bg"], fg=C["muted"],
                               font=(FONT, 10))
        self.status.pack(side="right", pady=10)

        # Content container
        self.content = tk.Frame(right, bg=C["bg"])
        self.content.pack(fill="both", expand=True, padx=24, pady=(6, 20))

    def _build_sidebar(self):
        tk.Label(self.sidebar, text="  Face\n  Attendance", bg=C["sidebar"], fg="white",
                 font=(FONT, 15, "bold"), justify="left").pack(anchor="w", pady=(26, 6), padx=6)
        tk.Label(self.sidebar, text="  single-photo · anti-spoof", bg=C["sidebar"],
                 fg=C["sidebar_fg"], font=(FONT, 8)).pack(anchor="w", padx=6, pady=(0, 22))

        for key, label in (("dashboard", "Dashboard"), ("students", "Students"),
                           ("attendance", "Attendance"), ("reports", "Reports")):
            b = ttk.Button(self.sidebar, text=label, style="Nav.TButton",
                           command=lambda k=key: self.show_page(k), takefocus=False)
            b.pack(fill="x")
            self.nav_buttons[key] = b

        tk.Frame(self.sidebar, bg=C["sidebar"]).pack(fill="both", expand=True)
        tk.Button(self.sidebar, text="Exit", command=self.root.destroy,
                  bg=C["sidebar"], fg=C["sidebar_fg"], activebackground=C["sidebar_hi"],
                  activeforeground="white", relief="flat", bd=0, font=(FONT, 10),
                  anchor="w", padx=22, pady=12).pack(fill="x", side="bottom")

    def _card(self, parent, pad=16):
        wrap = tk.Frame(parent, bg=C["border"])
        inner = tk.Frame(wrap, bg=C["card"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        inner._pad = pad
        return wrap, inner

    def _card_title(self, parent, text):
        tk.Label(parent, text=text, bg=C["card"], fg=C["text"],
                 font=(FONT, 12, "bold")).pack(anchor="w", padx=16, pady=(14, 0))

    def _styled_tree(self, parent, columns, headings, widths, anchors, height=10):
        frame = tk.Frame(parent, bg=C["card"])
        tree = ttk.Treeview(frame, columns=columns, show="headings",
                            selectmode="browse", height=height)
        for c, t, w, a in zip(columns, headings, widths, anchors):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor=a)
        tree.tag_configure("odd", background=C["row_alt"])
        tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        sb.pack(side="right", fill="y")
        tree.configure(yscrollcommand=sb.set)
        return frame, tree

    @staticmethod
    def _fill_tree(tree, rows):
        tree.delete(*tree.get_children())
        for i, values in enumerate(rows):
            tree.insert("", "end", values=values, tags=("odd",) if i % 2 else ())

    # ---- page switching -----------------------------------------------------
    def show_page(self, name):
        for f in self.pages.values():
            f.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        for k, b in self.nav_buttons.items():
            b.configure(style="NavActive.TButton" if k == name else "Nav.TButton")
        self.page_title.configure(text={
            "dashboard": "Dashboard", "students": "Students",
            "attendance": "Attendance", "reports": "Reports"}[name])
        {"dashboard": self.refresh_dashboard, "students": self.refresh_students,
         "attendance": self.refresh_attendance, "reports": self.refresh_reports}[name]()
        self.refresh_status()

    def refresh_status(self):
        self.status.configure(
            text=f"{store.student_count()} students   ·   {len(subjects.list_subjects())} subjects")

    def _build_pages(self):
        for name in ("dashboard", "students", "attendance", "reports"):
            self.pages[name] = tk.Frame(self.content, bg=C["bg"])
        self._build_dashboard(self.pages["dashboard"])
        self._build_students(self.pages["students"])
        self._build_attendance(self.pages["attendance"])
        self._build_reports(self.pages["reports"])

    # ---- Dashboard ----------------------------------------------------------
    def _build_dashboard(self, page):
        row = tk.Frame(page, bg=C["bg"])
        row.pack(fill="x")
        self.stat_vals = {}
        for key, label in (("students", "Enrolled students"), ("photos", "Reference photos"),
                           ("subjects", "Subjects")):
            wrap, card = self._card(row)
            wrap.pack(side="left", expand=True, fill="x", padx=(0, 14))
            val = tk.Label(card, text="0", bg=C["card"], fg=C["accent"], font=(FONT, 30, "bold"))
            val.pack(anchor="w", padx=18, pady=(16, 0))
            tk.Label(card, text=label, bg=C["card"], fg=C["muted"],
                     font=(FONT, 10)).pack(anchor="w", padx=18, pady=(0, 16))
            self.stat_vals[key] = val

        wrap, card = self._card(page)
        wrap.pack(fill="both", expand=True, pady=(18, 0))
        self._card_title(card, "Getting started")
        steps = ("1.  Students  →  enter an ID & name, then Enroll from image or webcam.\n"
                 "2.  Attendance  →  pick a subject, then Start Face Attendance.\n"
                 "        Look at the camera and turn your head slightly (anti-spoofing).\n"
                 "3.  Reports  →  see attendance % per subject and export a CSV.\n\n"
                 "Tip: add a second photo of a student (e.g. without glasses) from the\n"
                 "Students page to boost recognition accuracy.")
        tk.Label(card, text=steps, bg=C["card"], fg=C["text"], font=(FONT, 11),
                 justify="left").pack(anchor="w", padx=18, pady=(8, 18))

    def refresh_dashboard(self):
        ids, _, _ = store.load_enrollments()
        self.stat_vals["students"].configure(text=str(store.student_count()))
        self.stat_vals["photos"].configure(text=str(len(ids)))
        self.stat_vals["subjects"].configure(text=str(len(subjects.list_subjects())))

    # ---- Students -----------------------------------------------------------
    def _build_students(self, page):
        wrap, card = self._card(page)
        wrap.pack(fill="x")
        self._card_title(card, "Enroll a new student")
        form = tk.Frame(card, bg=C["card"])
        form.pack(fill="x", padx=16, pady=14)
        tk.Label(form, text="ID", bg=C["card"], fg=C["muted"], font=(FONT, 9)).grid(row=0, column=0, sticky="w")
        tk.Label(form, text="Name", bg=C["card"], fg=C["muted"], font=(FONT, 9)).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.id_entry = ttk.Entry(form, width=14)
        self.id_entry.grid(row=1, column=0, sticky="w")
        self.name_entry = ttk.Entry(form, width=26)
        self.name_entry.grid(row=1, column=1, sticky="w", padx=(10, 16))
        ttk.Button(form, text="Enroll from image", style="Accent.TButton",
                   command=self.enroll_image).grid(row=1, column=2, padx=4)
        ttk.Button(form, text="Enroll from webcam", style="Ghost.TButton",
                   command=self.enroll_webcam).grid(row=1, column=3, padx=4)

        wrap, card = self._card(page)
        wrap.pack(fill="both", expand=True, pady=(16, 0))
        self._card_title(card, "Enrolled students")
        tframe, self.stu_tree = self._styled_tree(
            card, ("id", "name", "photos"), ("ID", "Name", "Reference photos"),
            (110, 320, 150), ("center", "w", "center"), height=9)
        tframe.pack(fill="both", expand=True, padx=16, pady=(8, 8))

        bar = tk.Frame(card, bg=C["card"])
        bar.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(bar, text="Add another photo", style="Ghost.TButton",
                   command=self.add_photo).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Enroll from folder", style="Ghost.TButton",
                   command=self.enroll_folder).pack(side="left", padx=6)
        ttk.Button(bar, text="Delete selected", style="Danger.TButton",
                   command=self.delete_student).pack(side="left", padx=6)
        ttk.Button(bar, text="Refresh", style="Ghost.TButton",
                   command=self.refresh_students).pack(side="right")

    def refresh_students(self):
        self._fill_tree(self.stu_tree, store.roster())

    # ---- Attendance ---------------------------------------------------------
    def _build_attendance(self, page):
        wrap, card = self._card(page)
        wrap.pack(fill="x")
        inner = tk.Frame(card, bg=C["card"])
        inner.pack(fill="x", padx=16, pady=16)
        tk.Label(inner, text="Subject", bg=C["card"], fg=C["muted"],
                 font=(FONT, 9)).grid(row=0, column=0, sticky="w")
        self.subject_combo = ttk.Combobox(inner, textvariable=self.subject_var, width=26)
        self.subject_combo.grid(row=1, column=0, sticky="w")
        self.subject_combo.bind("<<ComboboxSelected>>", lambda e: self._on_subject_change())
        self.subject_combo.bind("<Return>", lambda e: self.add_subject())
        ttk.Button(inner, text="Add / set subject", style="Ghost.TButton",
                   command=self.add_subject).grid(row=1, column=1, padx=10)
        ttk.Button(inner, text="▶  Start Face Attendance", style="Big.TButton",
                   command=self.start_attendance).grid(row=1, column=2, padx=(20, 0))

        panes = tk.Frame(page, bg=C["bg"])
        panes.pack(fill="both", expand=True, pady=(16, 0))

        wrap, card = self._card(panes)
        wrap.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._card_title(card, "Manual attendance")
        tframe, self.manual_tree = self._styled_tree(
            card, ("id", "name"), ("ID", "Name"), (70, 190), ("center", "w"), height=9)
        tframe.pack(fill="both", expand=True, padx=16, pady=(8, 8))
        ttk.Button(card, text="Mark present (manual)", style="Accent.TButton",
                   command=self.manual_mark).pack(padx=16, pady=(0, 14), anchor="w")

        wrap, card = self._card(panes)
        wrap.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._card_title(card, "Present today (this subject)")
        tframe, self.today_tree = self._styled_tree(
            card, ("id", "name", "time", "method"), ("ID", "Name", "Time", "By"),
            (60, 140, 80, 70), ("center", "w", "center", "center"), height=9)
        tframe.pack(fill="both", expand=True, padx=16, pady=(8, 8))
        tbar = tk.Frame(card, bg=C["card"])
        tbar.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(tbar, text="Remove selected", style="Danger.TButton",
                   command=self.remove_attendance).pack(side="left")
        ttk.Button(tbar, text="Refresh", style="Ghost.TButton",
                   command=self.refresh_today).pack(side="right")

    def refresh_attendance(self):
        subs = subjects.list_subjects()
        self.subject_combo["values"] = subs
        self._fill_tree(self.manual_tree, [(s, n) for s, n, _ in store.roster()])
        self.refresh_today()

    def _on_subject_change(self):
        self.refresh_today()
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

    def start_attendance(self):
        if store.student_count() == 0:
            messagebox.showwarning("No students", "Enroll at least one student first.")
            return
        subject = self._current_subject()
        if not subject:
            return
        subjects.add_subject(subject)
        self.subject_combo["values"] = subjects.list_subjects()
        messagebox.showinfo("Attendance", f"Camera opens for '{subject}'.\nPress q to stop.")
        try:
            n = attendance.run(subject)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        messagebox.showinfo("Done", f"{n} student(s) marked present for {subject}.")
        self.refresh_today(); self.refresh_status()

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
        messagebox.showinfo("Manual attendance", attendance.mark_manually(subject, sid, name))
        self.refresh_today(); self.refresh_status()

    def remove_attendance(self):
        subject = self._current_subject()
        if not subject:
            return
        sel = self.today_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Pick a record from 'Present today' to remove.")
            return
        sid, name = self.today_tree.item(sel[0], "values")[:2]
        if not messagebox.askyesno("Remove attendance",
                                   f"Remove {name} (id={sid}) from today's {subject} attendance?"):
            return
        messagebox.showinfo("Attendance", attendance.unmark(subject, sid))
        self.refresh_today()

    def refresh_today(self):
        subject = subjects.sanitize(self.subject_var.get())
        rows = []
        if subject:
            path = attendance.csv_path_for(subject)
            if os.path.exists(path):
                with open(path, newline="", encoding="utf-8") as f:
                    for r in csv.DictReader(f):
                        rows.append((r.get("id", ""), r.get("name", ""),
                                     r.get("time", ""), r.get("method", "")))
        self._fill_tree(self.today_tree, rows)

    # ---- Reports ------------------------------------------------------------
    def _build_reports(self, page):
        wrap, card = self._card(page)
        wrap.pack(fill="x")
        bar = tk.Frame(card, bg=C["card"])
        bar.pack(fill="x", padx=16, pady=16)
        tk.Label(bar, text="Subject", bg=C["card"], fg=C["muted"],
                 font=(FONT, 9)).pack(side="left", padx=(0, 8))
        self.report_combo = ttk.Combobox(bar, textvariable=self.report_subject_var,
                                         width=26, state="readonly")
        self.report_combo.pack(side="left")
        ttk.Button(bar, text="Show report", style="Accent.TButton",
                   command=self.show_report).pack(side="left", padx=10)
        ttk.Button(bar, text="Export CSV", style="Ghost.TButton",
                   command=self.export_report).pack(side="left")
        self.report_info = tk.Label(bar, text="", bg=C["card"], fg=C["muted"], font=(FONT, 10))
        self.report_info.pack(side="right")

        wrap, card = self._card(page)
        wrap.pack(fill="both", expand=True, pady=(16, 0))
        tframe, self.report_tree = self._styled_tree(
            card, ("id", "name", "present", "total", "percent"),
            ("ID", "Name", "Days present", "Total days", "Attendance %"),
            (80, 240, 110, 100, 120), ("center", "w", "center", "center", "center"), height=11)
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
        dates, rows = report.build_summary(subject)
        self.report_info.configure(
            text=(f"{len(dates)} day(s)  ({dates[0]} .. {dates[-1]})" if dates else "no records"))
        self._fill_tree(self.report_tree, [
            (r["id"], r["name"], r["days_present"], r["total_days"], f"{r['percent']:.1f}%")
            for r in rows])

    def export_report(self):
        subject = self.report_subject_var.get()
        if not subject:
            messagebox.showinfo("Report", "Pick a subject first.")
            return
        messagebox.showinfo("Exported", f"Wrote:\n{report.export_summary(subject)}")

    # ---- shared enrollment handlers -----------------------------------------
    def _form_id_name(self):
        sid = self.id_entry.get().strip()
        name = self.name_entry.get().strip()
        if not sid or not name:
            messagebox.showwarning("Missing info", "Enter both an ID and a Name first.")
            return None, None
        return sid, name

    def _clear_form(self):
        self.id_entry.delete(0, "end")
        self.name_entry.delete(0, "end")

    def enroll_image(self):
        sid, name = self._form_id_name()
        if not sid:
            return
        path = filedialog.askopenfilename(title="Choose the student's photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")])
        if path:
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
        self._clear_form(); self.refresh_students(); self.refresh_status()

    def enroll_folder(self):
        folder = filedialog.askdirectory(title="Folder of photos named <id>_<name>.jpg")
        if not folder:
            return
        import enroll as enr
        try:
            enr.enroll_dir(get_engine(), folder)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        messagebox.showinfo("Done", "Folder enrollment finished (see console for details).")
        self.refresh_students(); self.refresh_status()

    def _do_enroll_image(self, path, sid, name, append):
        import enroll as enr
        try:
            ok = enr.enroll_image(get_engine(), path, sid, name, append=append)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        if ok:
            messagebox.showinfo("Success",
                                "Added another photo." if append else f"Enrolled {name} (id={sid}).")
            self._clear_form(); self.refresh_students(); self.refresh_status()
        else:
            messagebox.showwarning("No face", "Could not detect a face in that image.")

    def add_photo(self):
        sel = self.stu_tree.selection()
        if not sel:
            messagebox.showwarning("Select a student", "Pick a student from the table first.")
            return
        sid, name = self.stu_tree.item(sel[0], "values")[:2]
        if messagebox.askyesno("Source", f"Add a photo for {name}.\n\nYes = image file,  No = webcam"):
            path = filedialog.askopenfilename(title=f"Another photo of {name}",
                filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")])
            if path:
                self._do_enroll_image(path, sid, name, append=True)
        else:
            messagebox.showinfo("Webcam", "Camera opens. SPACE to capture, q to cancel.")
            import enroll as enr
            enr.enroll_webcam(get_engine(), sid, name, append=True)
            self.refresh_students()

    def delete_student(self):
        sel = self.stu_tree.selection()
        if not sel:
            messagebox.showwarning("Select a student", "Pick a student from the table first.")
            return
        sid, name = self.stu_tree.item(sel[0], "values")[:2]
        if messagebox.askyesno("Confirm delete",
                               f"Delete {name} (id={sid}) and all their reference photos?"):
            store.delete(sid)
            self.refresh_students(); self.refresh_status()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

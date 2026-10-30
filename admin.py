"""
Tech-team admin console.

For the people who SET UP the system - not for teachers or students. Here the
tech team enrolls and manages:
  - Students (with their face reference photos)
  - Teachers (id + name) used for lecture check-in in the teacher app

Run:
    python admin.py
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import config
import store
import teachers
from ui_common import BaseApp, C, FONT

IMAGE_TYPES = [("Images", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]

# The face engine loads ~37 MB of models, so create it lazily and reuse it.
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from face_engine import FaceEngine
        _engine = FaceEngine()
    return _engine


class AdminApp(BaseApp):
    def __init__(self, root):
        super().__init__(root, "Admin Console", "tech team · setup",
                         nav=[("students", "Students"), ("teachers", "Teachers")])

    def refresh_status(self):
        self.status.configure(
            text=f"{store.student_count()} students   ·   {teachers.count()} teachers")

    def _build_pages(self):
        self.pages["students"] = tk.Frame(self.content, bg=C["bg"])
        self.pages["teachers"] = tk.Frame(self.content, bg=C["bg"])
        self._build_students(self.pages["students"])
        self._build_teachers(self.pages["teachers"])

    # ---- Students -----------------------------------------------------------
    def _build_students(self, page):
        wrap, card = self._card(page)
        wrap.pack(fill="x")
        self._card_title(card, "Enroll a new student")
        form = tk.Frame(card, bg=C["card"])
        form.pack(fill="x", padx=16, pady=14)
        tk.Label(form, text="ID", bg=C["card"], fg=C["muted"], font=(FONT, 9)).grid(row=0, column=0, sticky="w")
        tk.Label(form, text="Name", bg=C["card"], fg=C["muted"], font=(FONT, 9)).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.s_id = ttk.Entry(form, width=14); self.s_id.grid(row=1, column=0, sticky="w")
        self.s_name = ttk.Entry(form, width=26); self.s_name.grid(row=1, column=1, sticky="w", padx=(10, 16))
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
        bar = tk.Frame(card, bg=C["card"]); bar.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(bar, text="Add another photo", style="Ghost.TButton", command=self.add_photo).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Enroll from folder", style="Ghost.TButton", command=self.enroll_folder).pack(side="left", padx=6)
        ttk.Button(bar, text="Delete selected", style="Danger.TButton", command=self.delete_student).pack(side="left", padx=6)
        ttk.Button(bar, text="Refresh", style="Ghost.TButton", command=self.refresh_students).pack(side="right")

    def refresh_students(self):
        self._fill_tree(self.stu_tree, store.roster())

    def _student_form(self):
        sid, name = self.s_id.get().strip(), self.s_name.get().strip()
        if not sid or not name:
            messagebox.showwarning("Missing info", "Enter both an ID and a Name first.")
            return None, None
        return sid, name

    def _clear_student_form(self):
        self.s_id.delete(0, "end"); self.s_name.delete(0, "end")

    def _do_enroll_image(self, path, sid, name, append):
        import enroll as enr
        try:
            ok = enr.enroll_image(get_engine(), path, sid, name, append=append)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        if ok:
            messagebox.showinfo("Success", "Added another photo." if append else f"Enrolled {name} (id={sid}).")
            self._clear_student_form(); self.refresh_students(); self.refresh_status()
        else:
            messagebox.showwarning("No face", "Could not detect a face in that image.")

    def enroll_image(self):
        sid, name = self._student_form()
        if not sid:
            return
        path = filedialog.askopenfilename(title="Choose the student's photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")])
        if path:
            self._do_enroll_image(path, sid, name, append=False)

    def enroll_webcam(self):
        sid, name = self._student_form()
        if not sid:
            return
        messagebox.showinfo("Webcam", "A camera window opens.\nPress SPACE to capture, q to cancel.")
        import enroll as enr
        try:
            enr.enroll_webcam(get_engine(), sid, name, append=False)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        self._clear_student_form(); self.refresh_students(); self.refresh_status()

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
        if messagebox.askyesno("Confirm delete", f"Delete {name} (id={sid}) and all their reference photos?"):
            store.delete(sid)
            self.refresh_students(); self.refresh_status()

    # ---- Teachers -----------------------------------------------------------
    def _build_teachers(self, page):
        wrap, card = self._card(page)
        wrap.pack(fill="x")
        self._card_title(card, "Add a teacher")
        form = tk.Frame(card, bg=C["card"])
        form.pack(fill="x", padx=16, pady=14)
        tk.Label(form, text="ID", bg=C["card"], fg=C["muted"], font=(FONT, 9)).grid(row=0, column=0, sticky="w")
        tk.Label(form, text="Name", bg=C["card"], fg=C["muted"], font=(FONT, 9)).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.t_id = ttk.Entry(form, width=14); self.t_id.grid(row=1, column=0, sticky="w")
        self.t_name = ttk.Entry(form, width=26); self.t_name.grid(row=1, column=1, sticky="w", padx=(10, 16))
        ttk.Button(form, text="Add teacher", style="Accent.TButton", command=self.add_teacher).grid(row=1, column=2, padx=4)
        ttk.Button(form, text="Enroll face (image)", style="Ghost.TButton",
                   command=lambda: self.enroll_teacher_face("image")).grid(row=1, column=3, padx=4)
        ttk.Button(form, text="Enroll face (webcam)", style="Ghost.TButton",
                   command=lambda: self.enroll_teacher_face("webcam")).grid(row=1, column=4, padx=4)
        tk.Label(card, text="A teacher needs a face enrolled to open or close lectures in the teacher app. "
                            "Enter ID + Name, then enroll their face.",
                 bg=C["card"], fg=C["muted"], font=(FONT, 9), justify="left", wraplength=820).pack(anchor="w", padx=16, pady=(0, 10))

        wrap, card = self._card(page)
        wrap.pack(fill="both", expand=True, pady=(16, 0))
        self._card_title(card, "Registered teachers")
        tframe, self.tea_tree = self._styled_tree(
            card, ("id", "name", "face"), ("ID", "Name", "Face enrolled"),
            (110, 320, 150), ("center", "w", "center"), height=10)
        tframe.pack(fill="both", expand=True, padx=16, pady=(8, 8))
        bar = tk.Frame(card, bg=C["card"]); bar.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(bar, text="Add face to selected", style="Ghost.TButton",
                   command=self.add_teacher_face).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Remove face", style="Ghost.TButton",
                   command=self.remove_teacher_face).pack(side="left", padx=6)
        ttk.Button(bar, text="Delete selected", style="Danger.TButton", command=self.delete_teacher).pack(side="left", padx=6)
        ttk.Button(bar, text="Refresh", style="Ghost.TButton", command=self.refresh_teachers).pack(side="right")

    def refresh_teachers(self):
        rows = []
        for tid, name in teachers.list_teachers():
            refs = teachers.face_refs(tid)
            rows.append((tid, name, f"{refs} photo{'s' if refs != 1 else ''}" if refs else "— no face"))
        self._fill_tree(self.tea_tree, rows)

    def add_teacher(self):
        tid, name = self.t_id.get().strip(), self.t_name.get().strip()
        msg, ok = teachers.add_teacher(tid, name)
        if ok:
            self.t_id.delete(0, "end"); self.t_name.delete(0, "end")
            self.refresh_teachers(); self.refresh_status()
        messagebox.showinfo("Teachers", msg)

    def _do_teacher_face(self, tid, name, source, append):
        """Enroll a teacher's face into the teacher store. Ensures the teacher
        exists in the registry first."""
        teachers.add_teacher(tid, name)  # idempotent: create/refresh registry entry
        import enroll as enr
        tpath = config.TEACHER_ENROLL_PATH
        try:
            if source == "image":
                img = filedialog.askopenfilename(title=f"Photo of {name}", filetypes=IMAGE_TYPES)
                if not img:
                    return
                ok = enr.enroll_image(get_engine(), img, tid, name, append=append, path=tpath)
                if not ok:
                    messagebox.showwarning("No face", "Could not detect a face in that image.")
                    return
            else:
                messagebox.showinfo("Webcam", "A camera window opens.\nPress SPACE to capture, q to cancel.")
                enr.enroll_webcam(get_engine(), tid, name, append=append, path=tpath)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        messagebox.showinfo("Teacher face",
                            f"{'Added another photo for' if append else 'Enrolled face for'} {name} (id={tid}).")
        self.refresh_teachers(); self.refresh_status()

    def enroll_teacher_face(self, source):
        tid, name = self.t_id.get().strip(), self.t_name.get().strip()
        if not tid or not name:
            messagebox.showwarning("Missing info", "Enter both an ID and a Name first.")
            return
        self._do_teacher_face(tid, name, source, append=False)
        self.t_id.delete(0, "end"); self.t_name.delete(0, "end")

    def add_teacher_face(self):
        sel = self.tea_tree.selection()
        if not sel:
            messagebox.showwarning("Select a teacher", "Pick a teacher from the table first.")
            return
        tid, name = self.tea_tree.item(sel[0], "values")[:2]
        source = "image" if messagebox.askyesno(
            "Source", f"Add a face photo for {name}.\n\nYes = image file,  No = webcam") else "webcam"
        self._do_teacher_face(tid, name, source, append=True)

    def remove_teacher_face(self):
        sel = self.tea_tree.selection()
        if not sel:
            messagebox.showwarning("Select a teacher", "Pick a teacher from the table first.")
            return
        tid, name = self.tea_tree.item(sel[0], "values")[:2]
        if not teachers.has_face(tid):
            messagebox.showinfo("Teacher face", f"{name} has no face enrolled.")
            return
        if messagebox.askyesno("Remove face", f"Remove {name}'s enrolled face?\n\n"
                                              "They will not be able to open/close lectures until re-enrolled."):
            teachers.remove_face(tid)
            self.refresh_teachers(); self.refresh_status()

    def delete_teacher(self):
        sel = self.tea_tree.selection()
        if not sel:
            messagebox.showwarning("Select a teacher", "Pick a teacher from the table first.")
            return
        tid, name = self.tea_tree.item(sel[0], "values")[:2]
        if messagebox.askyesno("Confirm delete", f"Delete teacher {name} (id={tid}) and their enrolled face?"):
            messagebox.showinfo("Teachers", teachers.delete_teacher(tid))
            self.refresh_teachers(); self.refresh_status()


def main():
    root = tk.Tk()
    AdminApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

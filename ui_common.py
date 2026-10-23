"""
Shared UI theme and a base window shell for the desktop apps.

Both the tech-team admin console (admin.py) and the teacher app (gui.py) use
these so they look identical, with no duplicated styling code.
"""
import tkinter as tk
from tkinter import ttk

# ---- Colour palette ---------------------------------------------------------
C = {
    "sidebar":    "#1e2430",
    "sidebar_fg": "#aeb6c6",
    "sidebar_hi": "#2a3140",
    "accent":     "#3b82f6",
    "accent_dk":  "#2563eb",
    "bg":         "#eef1f6",
    "card":       "#ffffff",
    "border":     "#e2e6ee",
    "text":       "#1f2733",
    "muted":      "#7a8699",
    "head":       "#eef2f8",
    "row_alt":    "#f7f9fc",
    "success":    "#16a34a",
    "danger":     "#dc2626",
}

FONT = "Segoe UI"


def init_style():
    s = ttk.Style()
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass
    s.configure(".", font=(FONT, 10), background=C["bg"], foreground=C["text"])

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

    s.configure("Nav.TButton", font=(FONT, 11), foreground=C["sidebar_fg"],
                background=C["sidebar"], borderwidth=0, anchor="w", padding=(22, 12))
    s.map("Nav.TButton", background=[("active", C["sidebar_hi"])])
    s.configure("NavActive.TButton", font=(FONT, 11, "bold"), foreground="white",
                background=C["accent"], borderwidth=0, anchor="w", padding=(22, 12))
    s.map("NavActive.TButton", background=[("active", C["accent"])])

    s.configure("TEntry", padding=6, fieldbackground="white", bordercolor=C["border"])
    s.configure("TCombobox", padding=6, fieldbackground="white")

    s.configure("Treeview", background="white", fieldbackground="white",
                foreground=C["text"], rowheight=30, borderwidth=0)
    s.configure("Treeview.Heading", font=(FONT, 9, "bold"), foreground="#51607a",
                background=C["head"], relief="flat", padding=8)
    s.map("Treeview.Heading", background=[("active", C["head"])])
    s.map("Treeview", background=[("selected", C["accent"])], foreground=[("selected", "white")])


# ---- widget helpers ---------------------------------------------------------
def card(parent):
    wrap = tk.Frame(parent, bg=C["border"])
    inner = tk.Frame(wrap, bg=C["card"])
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    return wrap, inner


def card_title(parent, text):
    tk.Label(parent, text=text, bg=C["card"], fg=C["text"],
             font=(FONT, 12, "bold")).pack(anchor="w", padx=16, pady=(14, 0))


def styled_tree(parent, columns, headings, widths, anchors, height=10):
    frame = tk.Frame(parent, bg=C["card"])
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", height=height)
    for c, t, w, a in zip(columns, headings, widths, anchors):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor=a)
    tree.tag_configure("odd", background=C["row_alt"])
    tree.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    sb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=sb.set)
    return frame, tree


def fill_tree(tree, rows):
    tree.delete(*tree.get_children())
    for i, values in enumerate(rows):
        tree.insert("", "end", values=values, tags=("odd",) if i % 2 else ())


class BaseApp:
    """Sidebar + header + swappable content pages, shared by both apps.

    Subclasses provide `nav` (list of (key, label)), implement `_build_pages()`
    to create self.pages[key] frames, optional `refresh_<key>()` methods, and
    may override `refresh_status()`.
    """

    def __init__(self, root, title, subtitle, nav, geometry="1040x680", minsize=(940, 620)):
        self.root = root
        self.nav = nav
        root.title(title)
        root.geometry(geometry)
        root.minsize(*minsize)
        root.configure(bg=C["bg"])
        init_style()
        self.nav_buttons = {}
        self.pages = {}
        self._build_shell(title, subtitle)
        self._build_pages()
        self.show_page(nav[0][0])

    def _build_shell(self, title, subtitle):
        self.sidebar = tk.Frame(self.root, bg=C["sidebar"], width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        right = tk.Frame(self.root, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)
        self.header = tk.Frame(right, bg=C["bg"])
        self.header.pack(fill="x", padx=24, pady=(20, 6))
        self.page_title = tk.Label(self.header, text="", bg=C["bg"], fg=C["text"], font=(FONT, 20, "bold"))
        self.page_title.pack(side="left")
        self.status = tk.Label(self.header, text="", bg=C["bg"], fg=C["muted"], font=(FONT, 10))
        self.status.pack(side="right", pady=10)
        self.content = tk.Frame(right, bg=C["bg"])
        self.content.pack(fill="both", expand=True, padx=24, pady=(6, 20))

        tk.Label(self.sidebar, text="  " + title, bg=C["sidebar"], fg="white",
                 font=(FONT, 14, "bold"), justify="left", wraplength=186).pack(anchor="w", pady=(26, 2), padx=6)
        tk.Label(self.sidebar, text="  " + subtitle, bg=C["sidebar"], fg=C["sidebar_fg"],
                 font=(FONT, 8)).pack(anchor="w", padx=6, pady=(0, 22))
        for key, label in self.nav:
            b = ttk.Button(self.sidebar, text=label, style="Nav.TButton",
                           command=lambda k=key: self.show_page(k), takefocus=False)
            b.pack(fill="x")
            self.nav_buttons[key] = b
        tk.Frame(self.sidebar, bg=C["sidebar"]).pack(fill="both", expand=True)
        tk.Button(self.sidebar, text="Exit", command=self.root.destroy, bg=C["sidebar"],
                  fg=C["sidebar_fg"], activebackground=C["sidebar_hi"], activeforeground="white",
                  relief="flat", bd=0, font=(FONT, 10), anchor="w", padx=22, pady=12).pack(fill="x", side="bottom")

    def show_page(self, name):
        for f in self.pages.values():
            f.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        for k, b in self.nav_buttons.items():
            b.configure(style="NavActive.TButton" if k == name else "Nav.TButton")
        self.page_title.configure(text=dict(self.nav)[name])
        getattr(self, f"refresh_{name}", lambda: None)()
        self.refresh_status()

    def refresh_status(self):
        pass

    # thin wrappers so subclasses can call self._card(...) etc.
    def _card(self, parent):
        return card(parent)

    def _card_title(self, parent, text):
        card_title(parent, text)

    def _styled_tree(self, *a, **k):
        return styled_tree(*a, **k)

    def _fill_tree(self, tree, rows):
        fill_tree(tree, rows)

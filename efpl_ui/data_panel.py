import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import shutil

from efpl_ui.theme import Theme

DATA_DIR = Path("workspace") / "data"
ALLOWED_EXTS = {".csv", ".xlsx", ".xls", ".json", ".tsv"}


class DataPanel(tk.Frame):
    """Sidebar panel for managing uploaded data files."""

    def __init__(self, parent, on_insert=None, **kwargs):
        super().__init__(parent, bg=Theme.BG, **kwargs)
        self.on_insert = on_insert   # callback(text) → inserts into editor

        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # ── Header ────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=Theme.TOOLBAR_BG, pady=4, padx=8)
        header.pack(fill=tk.X)
        tk.Label(
            header, text="DATA FILES", font=("Consolas", 9, "bold"),
            bg=Theme.TOOLBAR_BG, fg=Theme.FG_DIM
        ).pack(side=tk.LEFT)
        tk.Button(
            header, text="📤", command=self.upload_file,
            bg=Theme.TOOLBAR_BG, fg=Theme.ACCENT, relief=tk.FLAT,
            font=("Consolas", 12), cursor="hand2",
            activebackground=Theme.HOVER, activeforeground=Theme.ACCENT
        ).pack(side=tk.RIGHT)

        # ── Treeview style ─────────────────────────────────────────────────
        style = ttk.Style(self)
        style.configure(
            "Data.Treeview",
            background=Theme.BG, foreground=Theme.FG,
            fieldbackground=Theme.BG, borderwidth=0, font=("Consolas", 10),
            rowheight=26
        )
        style.map("Data.Treeview",
                  background=[("selected", Theme.SELECTION)],
                  foreground=[("selected", Theme.FG)])

        # ── Tree ──────────────────────────────────────────────────────────
        self.tree = ttk.Treeview(self, show="tree", style="Data.Treeview")
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._show_context_menu)

        # ── Context menu ─────────────────────────────────────────────────
        self.ctx_menu = tk.Menu(
            self, tearoff=0,
            bg=Theme.TOOLBAR_BG, fg=Theme.FG,
            activebackground=Theme.HOVER, activeforeground=Theme.FG
        )
        self.ctx_menu.add_command(label="📋 Insert load statement", command=self._insert_load)
        self.ctx_menu.add_command(label="🗑 Delete file",            command=self._delete_file)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="🔄 Refresh",               command=self.refresh)

        # ── Info bar ──────────────────────────────────────────────────────
        info = tk.Frame(self, bg=Theme.TOOLBAR_BG, pady=3, padx=8)
        info.pack(fill=tk.X, side=tk.BOTTOM)
        self.info_var = tk.StringVar(value="Double-click to load into editor")
        tk.Label(
            info, textvariable=self.info_var,
            bg=Theme.TOOLBAR_BG, fg=Theme.FG_DIM, font=("Consolas", 8),
            anchor="w"
        ).pack(fill=tk.X)

        self.refresh()

    # ------------------------------------------------------------------ #
    #  File management                                                     #
    # ------------------------------------------------------------------ #
    def upload_file(self):
        paths = filedialog.askopenfilenames(
            title="Upload Data Files",
            filetypes=[
                ("Data Files", "*.csv *.xlsx *.xls *.json *.tsv"),
                ("CSV",         "*.csv"),
                ("Excel",       "*.xlsx *.xls"),
                ("JSON",        "*.json"),
                ("TSV",         "*.tsv"),
                ("All Files",   "*.*"),
            ]
        )
        if not paths:
            return
        copied = []
        for src in paths:
            src_path = Path(src)
            dst = DATA_DIR / src_path.name
            if dst.exists():
                if not messagebox.askyesno(
                    "Overwrite?",
                    f'"{src_path.name}" already exists in Data. Overwrite?'
                ):
                    continue
            shutil.copy2(src_path, dst)
            copied.append(src_path.name)
        self.refresh()
        if copied:
            self.info_var.set(f"Uploaded: {', '.join(copied)}")

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        if not DATA_DIR.exists():
            return
        files = sorted(
            [f for f in DATA_DIR.iterdir() if f.is_file() and f.suffix.lower() in ALLOWED_EXTS],
            key=lambda f: f.name.lower()
        )
        icons = {".csv": "📊", ".xlsx": "📗", ".xls": "📗",
                 ".json": "📋", ".tsv": "📊"}
        for f in files:
            icon = icons.get(f.suffix.lower(), "📄")
            size_kb = f.stat().st_size / 1024
            label = f"{icon} {f.name}  ({size_kb:.1f} KB)"
            self.tree.insert("", "end", iid=str(f), text=label, values=(f.name,))

        count = len(files)
        self.info_var.set(f"{count} file{'s' if count != 1 else ''} in workspace/data/")

    def _selected_file(self):
        sel = self.tree.focus()
        if sel:
            return Path(sel)
        return None

    def _on_double_click(self, event):
        f = self._selected_file()
        if f and self.on_insert:
            stem = f.stem.replace(" ", "_").replace("-", "_")
            snippet = f'load "{f.name}" as {stem}\n'
            self.on_insert(snippet)

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.focus(item)
            self.tree.selection_set(item)
        self.ctx_menu.post(event.x_root, event.y_root)

    def _insert_load(self):
        f = self._selected_file()
        if f and self.on_insert:
            stem = f.stem.replace(" ", "_").replace("-", "_")
            snippet = f'load "{f.name}" as {stem}\n'
            self.on_insert(snippet)

    def _delete_file(self):
        f = self._selected_file()
        if not f:
            return
        if messagebox.askyesno("Delete", f'Delete "{f.name}" from workspace/data/?'):
            f.unlink(missing_ok=True)
            self.refresh()

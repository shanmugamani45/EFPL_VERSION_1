import tkinter as tk
from tkinter import ttk
from pathlib import Path
from efpl_ui.theme import Theme

class FileExplorer(tk.Frame):
    def __init__(self, parent, on_file_select=None, **kwargs):
        super().__init__(parent, bg=Theme.BG, **kwargs)
        self.on_file_select = on_file_select
        
        # Header
        header = tk.Frame(self, bg=Theme.TOOLBAR_BG, pady=4, padx=8)
        header.pack(fill=tk.X)
        tk.Label(
            header, text="WORKSPACE", font=("Consolas", 9, "bold"),
            bg=Theme.TOOLBAR_BG, fg=Theme.FG_DIM
        ).pack(side=tk.LEFT)
        
        # Style for Treeview
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "FileExplorer.Treeview",
            background=Theme.BG,
            foreground=Theme.FG,
            fieldbackground=Theme.BG,
            borderwidth=0,
            font=("Consolas", 10),
            rowheight=26
        )
        style.map(
            "FileExplorer.Treeview",
            background=[("selected", Theme.SELECTION)],
            foreground=[("selected", Theme.FG)]
        )
        
        self.tree = ttk.Treeview(self, show="tree", style="FileExplorer.Treeview")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self._on_double_click)
        
        self.workspace_path = Path("workspace").resolve()
        self.refresh()
        
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        if self.workspace_path.exists():
            self._populate_tree("", self.workspace_path)
            
    def _populate_tree(self, parent, path):
        # Insert directories first, then files
        dirs = []
        files = []
        for p in sorted(path.iterdir(), key=lambda x: x.name.lower()):
            if p.is_dir() and p.name not in ("__pycache__", ".git"):
                dirs.append(p)
            elif p.is_file() and p.suffix in (".efpl", ".txt"):
                files.append(p)
                
        for d in dirs:
            node = self.tree.insert(parent, "end", text=f"📂 {d.name}", open=True, values=(str(d), "dir"))
            self._populate_tree(node, d)
            
        for f in files:
            icon = "📄 " if f.suffix == ".txt" else "⚡ "
            self.tree.insert(parent, "end", text=f"{icon}{f.name}", values=(str(f), "file"))
            
    def _on_double_click(self, event):
        item_id = self.tree.focus()
        if not item_id:
            return
            
        values = self.tree.item(item_id, "values")
        if values and values[1] == "file":
            path = values[0]
            if self.on_file_select:
                self.on_file_select(path)

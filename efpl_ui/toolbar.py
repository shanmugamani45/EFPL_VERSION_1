import tkinter as tk
from efpl_ui.theme import Theme

class Toolbar(tk.Frame):
    def __init__(self, parent, commands, **kwargs):
        super().__init__(parent, bg=Theme.TOOLBAR_BG, pady=6, padx=10, **kwargs)
        
        self.commands = commands
        
        # Left side buttons
        self._add_btn("☰", self.commands.get("toggle_sidebar"), Theme.FG)
        tk.Frame(self, bg=Theme.DIVIDER, width=2).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)
        
        self._add_btn("📄", self.commands.get("new"), Theme.FG)
        self._add_btn("📂", self.commands.get("open"), Theme.FG)
        self._add_btn("💾", self.commands.get("save"), Theme.FG)
        
        # Separator
        tk.Frame(self, bg=Theme.DIVIDER, width=2).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)
        
        # Right/Center buttons
        self._add_btn("▶", self.commands.get("run"), Theme.GREEN, bold=True)
        self._add_btn("🗑", self.commands.get("clear"), Theme.RED)
        
        # Separator
        tk.Frame(self, bg=Theme.DIVIDER, width=2).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)
        self._add_btn("📤 Upload Data", self.commands.get("upload_data"), Theme.ACCENT)
        
    def _add_btn(self, text, command, color, bold=False):
        if not command:
            return
        font = ("Consolas", 10, "bold") if bold else ("Consolas", 10)
        btn = tk.Button(
            self, text=text, command=command,
            bg=Theme.BG, fg=color, relief=tk.FLAT,
            font=font, padx=10, pady=2, cursor="hand2",
            activebackground=Theme.HOVER, activeforeground=color
        )
        btn.pack(side=tk.LEFT, padx=4)
        btn.bind("<Enter>", lambda e, b=btn: b.config(bg=Theme.HOVER))
        btn.bind("<Leave>", lambda e, b=btn: b.config(bg=Theme.BG))

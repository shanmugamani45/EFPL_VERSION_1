import tkinter as tk
from efpl_ui.theme import Theme


class FindReplaceBar(tk.Frame):
    """A floating Find / Replace bar that docks at the bottom of the editor."""

    def __init__(self, parent, text_widget, **kwargs):
        super().__init__(parent, bg=Theme.TOOLBAR_BG, pady=6, padx=10, **kwargs)
        self.text = text_widget
        self._matches = []
        self._match_idx = 0

        # Configure tag for matches
        self.text.tag_config("found",         background="#f9e2af", foreground="#1e1e2e")
        self.text.tag_config("found_current", background="#cba6f7", foreground="#1e1e2e")

        # ── Row 1: Find ───────────────────────────────────────────────────
        row1 = tk.Frame(self, bg=Theme.TOOLBAR_BG)
        row1.pack(fill=tk.X)

        tk.Label(row1, text="Find:", bg=Theme.TOOLBAR_BG, fg=Theme.FG_DIM,
                 font=("Consolas", 10), width=8, anchor="w").pack(side=tk.LEFT)

        self._find_var = tk.StringVar()
        self._find_var.trace_add("write", lambda *_: self._do_find())
        self._find_entry = tk.Entry(
            row1, textvariable=self._find_var,
            bg=Theme.DIVIDER, fg=Theme.FG, insertbackground=Theme.ACCENT,
            font=("Consolas", 11), relief=tk.FLAT, bd=0, width=35
        )
        self._find_entry.pack(side=tk.LEFT, ipady=4, padx=(0, 10))

        self._case_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            row1, text="Aa", variable=self._case_var,
            bg=Theme.TOOLBAR_BG, fg=Theme.FG_DIM,
            selectcolor=Theme.DIVIDER, activebackground=Theme.TOOLBAR_BG,
            font=("Consolas", 9), command=self._do_find
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(row1, text="◀", command=self._prev, bg=Theme.TOOLBAR_BG,
                  fg=Theme.FG, relief=tk.FLAT, font=("Consolas", 10),
                  cursor="hand2", activebackground=Theme.HOVER).pack(side=tk.LEFT, padx=1)
        tk.Button(row1, text="▶", command=self._next, bg=Theme.TOOLBAR_BG,
                  fg=Theme.FG, relief=tk.FLAT, font=("Consolas", 10),
                  cursor="hand2", activebackground=Theme.HOVER).pack(side=tk.LEFT, padx=1)

        self._count_label = tk.Label(row1, text="", bg=Theme.TOOLBAR_BG,
                                     fg=Theme.FG_DIM, font=("Consolas", 9))
        self._count_label.pack(side=tk.LEFT, padx=6)

        tk.Button(row1, text="✕", command=self.close, bg=Theme.TOOLBAR_BG,
                  fg=Theme.FG_DIM, relief=tk.FLAT, font=("Consolas", 10),
                  cursor="hand2", activebackground=Theme.HOVER).pack(side=tk.RIGHT)

        # ── Row 2: Replace (hidden by default) ───────────────────────────
        self._replace_row = tk.Frame(self, bg=Theme.TOOLBAR_BG)

        tk.Label(self._replace_row, text="Replace:", bg=Theme.TOOLBAR_BG,
                 fg=Theme.FG_DIM, font=("Consolas", 10), width=8, anchor="w").pack(side=tk.LEFT)

        self._replace_var = tk.StringVar()
        self._replace_entry = tk.Entry(
            self._replace_row, textvariable=self._replace_var,
            bg=Theme.DIVIDER, fg=Theme.FG, insertbackground=Theme.ACCENT,
            font=("Consolas", 11), relief=tk.FLAT, bd=0, width=35
        )
        self._replace_entry.pack(side=tk.LEFT, ipady=4, padx=(0, 10))

        tk.Button(self._replace_row, text="Replace", command=self._replace_one,
                  bg=Theme.DIVIDER, fg=Theme.FG, relief=tk.FLAT,
                  font=("Consolas", 9), cursor="hand2",
                  activebackground=Theme.HOVER, padx=6).pack(side=tk.LEFT, padx=2)
        tk.Button(self._replace_row, text="Replace All", command=self._replace_all,
                  bg=Theme.DIVIDER, fg=Theme.FG, relief=tk.FLAT,
                  font=("Consolas", 9), cursor="hand2",
                  activebackground=Theme.HOVER, padx=6).pack(side=tk.LEFT, padx=2)

        # Bindings
        self._find_entry.bind("<Return>", lambda e: self._next())
        self._find_entry.bind("<Shift-Return>", lambda e: self._prev())

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #
    def show_find(self):
        if self._replace_row.winfo_ismapped():
            self._replace_row.pack_forget()
        self.pack(fill=tk.X, side=tk.BOTTOM, before=self.master.winfo_children()[0])
        self._find_entry.focus_set()
        self._find_entry.select_range(0, tk.END)

    def show_replace(self):
        self.pack(fill=tk.X, side=tk.BOTTOM, before=self.master.winfo_children()[0])
        self._replace_row.pack(fill=tk.X)
        self._find_entry.focus_set()
        self._find_entry.select_range(0, tk.END)

    def close(self):
        self._clear_highlights()
        self.pack_forget()

    # ------------------------------------------------------------------ #
    #  Find logic                                                          #
    # ------------------------------------------------------------------ #
    def _do_find(self, *_):
        self._clear_highlights()
        query = self._find_var.get()
        if not query:
            self._count_label.config(text="")
            return

        nocase = not self._case_var.get()
        start = "1.0"
        self._matches = []

        while True:
            pos = self.text.search(query, start, stopindex=tk.END,
                                   nocase=nocase, regexp=False)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self._matches.append((pos, end))
            self.text.tag_add("found", pos, end)
            start = end

        total = len(self._matches)
        if total:
            self._match_idx = 0
            self._highlight_current()
            self._count_label.config(text=f"1 / {total}")
        else:
            self._count_label.config(text="No matches")

    def _highlight_current(self):
        self.text.tag_remove("found_current", "1.0", tk.END)
        if not self._matches:
            return
        pos, end = self._matches[self._match_idx]
        self.text.tag_add("found_current", pos, end)
        self.text.see(pos)
        total = len(self._matches)
        self._count_label.config(text=f"{self._match_idx + 1} / {total}")

    def _next(self):
        if not self._matches:
            self._do_find()
            return
        self._match_idx = (self._match_idx + 1) % len(self._matches)
        self._highlight_current()

    def _prev(self):
        if not self._matches:
            return
        self._match_idx = (self._match_idx - 1) % len(self._matches)
        self._highlight_current()

    def _clear_highlights(self):
        self.text.tag_remove("found",         "1.0", tk.END)
        self.text.tag_remove("found_current", "1.0", tk.END)
        self._matches = []

    # ------------------------------------------------------------------ #
    #  Replace logic                                                       #
    # ------------------------------------------------------------------ #
    def _replace_one(self):
        if not self._matches:
            return
        pos, end = self._matches[self._match_idx]
        self.text.delete(pos, end)
        replacement = self._replace_var.get()
        self.text.insert(pos, replacement)
        self._do_find()

    def _replace_all(self):
        replacement = self._replace_var.get()
        query = self._find_var.get()
        if not query:
            return
        self._do_find()
        # Replace in reverse to preserve positions
        for pos, end in reversed(self._matches):
            self.text.delete(pos, end)
            self.text.insert(pos, replacement)
        self._do_find()

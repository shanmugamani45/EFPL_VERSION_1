import tkinter as tk
from tkinter import font as tkfont
import re
from efpl_ui.theme import Theme
from efpl_ui.find_replace import FindReplaceBar


class Editor(tk.Frame):
    """
    A self-contained Tkinter code editor widget with:
    - Line numbers
    - Syntax highlighting for EFPL keywords
    - Monospaced font
    """
    KEYWORDS = [
        "set", "to", "show", "if", "else", "end", "while", "for", "from", "step",
        "do", "switch", "case", "default", "break", "continue", "add", "remove",
        "take", "input", "as", "and", "or", "not", "true", "false", "number",
        "text", "function", "return", "call", "length", "upper", "lower",
        "contains", "replace", "sort", "reverse", "join", "import", "use",
        "math", "random", "time", "array", "file", "read", "write", "append",
        "type", "visual", "figure", "line", "bar", "scatter", "pie", "hist", "title",
        "xlabel", "ylabel", "grid", "legend", "save", "render", "clear",
        "sqrt", "round", "abs", "min", "max", "now", "today", "to_number",
        "to_text", "to_boolean", "type_of", "is_number", "is_text",
        "is_array", "is_dictionary",
        # data module
        "load", "data", "null", "filter", "select", "rename", "export",
        "sum", "average", "unique", "flatten", "map", "reduce", "zip",
        "class", "extends", "new", "self", "database", "http", "json", "os",
    ]

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self._code_font = tkfont.Font(family="Consolas", size=12)
        self._line_font = tkfont.Font(family="Consolas", size=12)

        # --- Line number canvas ---
        self.line_numbers = tk.Canvas(
            self, width=45, bg=Theme.BG, highlightthickness=0
        )
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        # --- Scrollbar ---
        from tkinter import ttk
        scrollbar = ttk.Scrollbar(self, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Text widget ---
        self.text = tk.Text(
            self,
            font=self._code_font,
            bg=Theme.BG,
            fg=Theme.FG,
            insertbackground=Theme.ACCENT,
            selectbackground=Theme.SELECTION,
            selectforeground=Theme.FG,
            relief=tk.FLAT,
            bd=0,
            wrap=tk.NONE,
            yscrollcommand=self._on_scroll,
            padx=8,
            pady=4,
            tabs=("2c",),
            undo=True,
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text.yview)

        # --- Highlight tag configurations ---
        self.text.tag_config("keyword", foreground=Theme.ACCENT)
        self.text.tag_config("string",  foreground=Theme.GREEN)
        self.text.tag_config("number",  foreground=Theme.ORANGE)
        self.text.tag_config("comment", foreground=Theme.GRAY, font=self._code_font)
        self.text.tag_config("error_line", background=Theme.RED_DARK)
        self._update_line_numbers()
        self._find_bar = FindReplaceBar(self, self.text)

        # Bind events
        self.text.bind("<KeyRelease>", self._on_key)
        self.text.bind("<ButtonRelease>", self._update_line_numbers)
        self.text.bind("<MouseWheel>", self._on_mousewheel)
        self.text.bind("<Control-space>", self._show_autocomplete)
        self.text.bind("<Escape>", self._hide_autocomplete)
        self.text.bind("<Control-f>", lambda e: (self._find_bar.show_find(), "break")[1])
        self.text.bind("<Control-h>", lambda e: (self._find_bar.show_replace(), "break")[1])

        self._update_line_numbers()

    # ------------------------------------------------------------------ #
    #  Scroll sync                                                         #
    # ------------------------------------------------------------------ #
    def _on_scroll(self, *args):
        self.line_numbers.yview_moveto(args[0])

    def _on_mousewheel(self, event):
        self.text.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._update_line_numbers()
        return "break"

    # ------------------------------------------------------------------ #
    #  Line numbers                                                        #
    # ------------------------------------------------------------------ #
    def _update_line_numbers(self, event=None):
        self.line_numbers.delete("all")
        i = self.text.index("@0,0")
        while True:
            dline = self.text.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.line_numbers.create_text(
                38, y + 2,
                anchor="ne",
                text=linenum,
                fill=Theme.FG_DIM,
                font=self._line_font,
            )
            i = self.text.index(f"{i}+1line")

    # ------------------------------------------------------------------ #
    #  Syntax highlighting                                                 #
    # ------------------------------------------------------------------ #
    def _on_key(self, event=None):
        self._highlight()
        self._update_line_numbers()
        if self._autocomplete is not None:
            self._refresh_autocomplete()

    def _highlight(self):
        """Re-apply all highlight tags on the current content."""
        for tag in ("keyword", "string", "number", "comment"):
            self.text.tag_remove(tag, "1.0", tk.END)

        content = self.text.get("1.0", tk.END)
        lines = content.split("\n")

        for lineno, line in enumerate(lines, start=1):
            # --- Comments (lines starting with #) ---
            stripped = line.lstrip()
            if stripped.startswith("#"):
                start = f"{lineno}.0"
                end = f"{lineno}.{len(line)}"
                self.text.tag_add("comment", start, end)
                continue  # no further highlighting on comment lines

            # --- Strings ---
            for m in re.finditer(r'"[^"]*"', line):
                self.text.tag_add("string", f"{lineno}.{m.start()}", f"{lineno}.{m.end()}")

            # --- Numbers ---
            for m in re.finditer(r'\b\d+(\.\d+)?\b', line):
                self.text.tag_add("number", f"{lineno}.{m.start()}", f"{lineno}.{m.end()}")

            # --- Keywords ---
            for kw in self.KEYWORDS:
                for m in re.finditer(rf'\b{kw}\b', line, re.IGNORECASE):
                    self.text.tag_add("keyword", f"{lineno}.{m.start()}", f"{lineno}.{m.end()}")

    # ------------------------------------------------------------------ #
    #  Error highlighting and autocomplete                                #
    # ------------------------------------------------------------------ #
    def clear_error(self):
        self.text.tag_remove("error_line", "1.0", tk.END)

    def mark_error_line(self, line_no: int):
        self.clear_error()
        self.text.tag_add("error_line", f"{line_no}.0", f"{line_no}.end")
        self.text.see(f"{line_no}.0")

    def _current_prefix(self):
        index = self.text.index(tk.INSERT)
        line_start = self.text.index(f"{index} linestart")
        before = self.text.get(line_start, index)
        match = re.search(r"[A-Za-z_][A-Za-z0-9_\.]*$", before)
        return match.group(0) if match else ""

    def _suggestions(self, prefix):
        content = self.text.get("1.0", tk.END)
        names = set(self.KEYWORDS)
        names.update(re.findall(r"\bset\s+([A-Za-z_][A-Za-z0-9_]*)\s+to\b", content, re.IGNORECASE))
        names.update(re.findall(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", content, re.IGNORECASE))
        names.update([
            "math.sqrt", "math.round", "math.abs", "math.min", "math.max",
            "random.random", "time.now", "time.today", "text.upper",
            "text.lower", "array.sort", "array.reverse", "array.join",
            "type.to_number", "type.to_text", "type.to_boolean", "type.type_of",
            "visual.figure", "visual.line", "visual.bar", "visual.scatter",
            "visual.pie", "visual.hist", "visual.title", "visual.xlabel",
            "visual.ylabel", "visual.grid", "visual.legend", "visual.save",
            "visual.render", "visual.clear",
        ])
        prefix_low = prefix.lower()
        return sorted(name for name in names if name.lower().startswith(prefix_low))[:10]

    def _show_autocomplete(self, event=None):
        prefix = self._current_prefix()
        matches = self._suggestions(prefix)
        if not matches:
            self._hide_autocomplete()
            return "break"

        if self._autocomplete is None:
            self._autocomplete = tk.Listbox(
                self.text,
                height=6,
                bg=Theme.TOOLBAR_BG,
                fg=Theme.FG,
                selectbackground=Theme.HOVER,
                selectforeground=Theme.FG,
                relief=tk.FLAT,
                font=self._code_font,
            )
            self._autocomplete.bind("<Return>", self._apply_autocomplete)
            self._autocomplete.bind("<Tab>", self._apply_autocomplete)
            self._autocomplete.bind("<Double-Button-1>", self._apply_autocomplete)

        self._autocomplete.delete(0, tk.END)
        for item in matches:
            self._autocomplete.insert(tk.END, item)
        self._autocomplete.selection_set(0)

        bbox = self.text.bbox(tk.INSERT)
        if bbox:
            x, y, _, h = bbox
            self._autocomplete.place(x=x, y=y + h, width=220)
        return "break"

    def _refresh_autocomplete(self):
        self._show_autocomplete()

    def _apply_autocomplete(self, event=None):
        if self._autocomplete is None:
            return "break"
        selection = self._autocomplete.curselection()
        if not selection:
            return "break"
        value = self._autocomplete.get(selection[0])
        prefix = self._current_prefix()
        if prefix:
            self.text.delete(f"insert-{len(prefix)}c", tk.INSERT)
        self.text.insert(tk.INSERT, value)
        self._hide_autocomplete()
        self._highlight()
        return "break"

    def _hide_autocomplete(self, event=None):
        if self._autocomplete is not None:
            self._autocomplete.place_forget()
            self._autocomplete.destroy()
            self._autocomplete = None
        return "break"

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #
    def get_code(self) -> str:
        return self.text.get("1.0", tk.END)

    def set_code(self, code: str):
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", code)
        self.clear_error()
        self._highlight()
        self._update_line_numbers()

    def clear(self):
        self.text.delete("1.0", tk.END)
        self.clear_error()
        self._update_line_numbers()

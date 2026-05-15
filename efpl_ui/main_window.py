import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import re
from pathlib import Path

from efpl_ui.editor import Editor
from efpl_ui.console import Console
from efpl_ui.theme import Theme
from efpl_ui.file_explorer import FileExplorer
from efpl_ui.toolbar import Toolbar
from efpl_ui.data_panel import DataPanel
from tkinter import ttk
from efpl_runtime.executor import run_script
from efpl_runtime.file_manager import load_script, save_script


class EFPLApp:
    """Main EFPL IDE window."""

    APP_TITLE = "EFPL Desktop IDE"
    LIBRARIES = {
        "math": "Math",
        "random": "Random",
        "time": "Time",
        "text": "Text",
        "array": "Array",
        "file": "File",
        "type": "Type",
        "visual": "Visual",
        "dsa": "DSA",
        "http": "HTTP",
        "json": "JSON",
        "os": "OS",
    }
    # Colors are now managed by Theme

    # ------------------------------------------------------------------ #
    #  Bootstrap                                                           #
    # ------------------------------------------------------------------ #
    def __init__(self, root: tk.Tk):
        self.root = root
        self._current_file: str | None = None
        self._running = False
        self._sidebar_visible = True
        self._library_vars: dict[str, tk.BooleanVar] = {}
        self._library_buttons: dict[str, tk.Button] = {}

        self._configure_root()
        self._build_menubar()

        self._build_main_pane()
        self._build_status_bar()

        # Welcome message
        self.console.write("EFPL IDE ready. Write your code and press ▶ Run.", tag="dim")
        self.console.write('Try:  set x to 10\n      show x', tag="dim")

    # ------------------------------------------------------------------ #
    #  Root window setup                                                   #
    # ------------------------------------------------------------------ #
    def _configure_root(self):
        self.root.title(self.APP_TITLE)
        self.root.configure(bg=Theme.BG)
        self.root.minsize(900, 600)
        self.root.geometry("1100x700")

        self.root.update_idletasks()
        try:
            import ctypes
            import os
            if os.name == 'nt':
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(2)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

        try:
            self.root.tk.call("tk", "scaling", 1.25)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Menus                                                               #
    # ------------------------------------------------------------------ #
    def _build_menubar(self):
        menubar = tk.Menu(self.root, bg=Theme.TOOLBAR_BG, fg=Theme.FG,
                          activebackground=Theme.DIVIDER, activeforeground=Theme.FG,
                          relief=tk.FLAT)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0, bg=Theme.TOOLBAR_BG, fg=Theme.FG,
                            activebackground=Theme.DIVIDER, activeforeground=Theme.FG)
        file_menu.add_command(label="New           Ctrl+N", command=self.new_file)
        file_menu.add_command(label="Open…         Ctrl+O", command=self.open_file)
        file_menu.add_command(label="Save          Ctrl+S", command=self.save_file)
        file_menu.add_command(label="Save As…      Ctrl+Shift+S", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Run menu
        run_menu = tk.Menu(menubar, tearoff=0, bg=Theme.TOOLBAR_BG, fg=Theme.FG,
                           activebackground=Theme.DIVIDER, activeforeground=Theme.FG)
        run_menu.add_command(label="Run Script     F5",  command=self.run_code)
        run_menu.add_command(label="Clear Console  F6",  command=lambda: self.console.clear())
        menubar.add_cascade(label="Run", menu=run_menu)

        # Examples menu
        examples_menu = tk.Menu(menubar, tearoff=0, bg=Theme.TOOLBAR_BG, fg=Theme.FG,
                                activebackground=Theme.DIVIDER, activeforeground=Theme.FG)
        examples = {
            "Calculator": "calculator.efpl",
            "Feature Check": "feature_check.efpl",
            "Library Popup Check": "library_popup_check.efpl",
            "Visual Charts": "visual_charts.efpl",
            "Functions": "functions.efpl",
            "File Read Write": "file_read_write.efpl",
            "Arrays": "arrays.efpl",
            "Dictionaries": "dictionaries.efpl",
        }
        for label, filename in examples.items():
            examples_menu.add_command(label=label, command=lambda name=filename: self._load_example(name))
        menubar.add_cascade(label="Examples", menu=examples_menu)

        # Library button
        menubar.add_command(label="Library", command=self._show_library_popup)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0, bg=Theme.TOOLBAR_BG, fg=Theme.FG,
                            activebackground=Theme.DIVIDER, activeforeground=Theme.FG)
        help_menu.add_command(label="EFPL Language Reference", command=self._show_help)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

        # Keyboard shortcuts
        self.root.bind("<Control-n>", lambda e: self.new_file())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-S>", lambda e: self.save_file_as())
        self.root.bind("<F5>",        lambda e: self.run_code())
        self.root.bind("<F6>",        lambda e: self.console.clear())


    # ------------------------------------------------------------------ #
    #  Main split pane: editor (top) + console (bottom)                   #
    # ------------------------------------------------------------------ #
    def _build_main_pane(self):
        # Toolbar
        self.toolbar = Toolbar(self.root, commands={
            "new": self.new_file,
            "open": self.open_file,
            "save": self.save_file,
            "run": self.run_code,
            "clear": lambda: self.console.clear(),
            "toggle_sidebar": self.toggle_sidebar,
            "upload_data": self._upload_data,
        })
        self.toolbar.pack(fill=tk.X)

        # Outer split pane (Horizontal: Sidebar | Editor+Console)
        self.main_pane = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL,
            bg=Theme.DIVIDER, sashrelief=tk.FLAT, sashwidth=4,
            handlesize=0
        )
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # ── Left tabbed sidebar ──────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Sidebar.TNotebook",
            background=Theme.TOOLBAR_BG, borderwidth=0, tabmargins=0
        )
        style.configure(
            "Sidebar.TNotebook.Tab",
            background=Theme.TOOLBAR_BG, foreground=Theme.FG_DIM,
            font=("Consolas", 9, "bold"), padding=[16, 6]
        )
        style.map(
            "Sidebar.TNotebook.Tab",
            background=[("selected", Theme.BG)],
            foreground=[("selected", Theme.ACCENT)]
        )

        # Global Scrollbar style
        style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background=Theme.DIVIDER,
            darkcolor=Theme.BG,
            lightcolor=Theme.BG,
            troughcolor=Theme.BG,
            bordercolor=Theme.BG,
            arrowcolor=Theme.FG_DIM
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", Theme.HOVER), ("pressed", Theme.ACCENT)]
        )
        self.sidebar_notebook = ttk.Notebook(self.main_pane, style="Sidebar.TNotebook")

        self.file_explorer = FileExplorer(
            self.sidebar_notebook, on_file_select=self._open_from_explorer
        )
        self.data_panel = DataPanel(
            self.sidebar_notebook, on_insert=self._insert_snippet
        )
        self.sidebar_notebook.add(self.file_explorer, text="📁 Files")
        self.sidebar_notebook.add(self.data_panel,    text="📊 Data")

        self.main_pane.add(self.sidebar_notebook, minsize=180)

        # ── Right inner pane (Vertical: Editor / Console) ────────────────
        self.inner_pane = tk.PanedWindow(
            self.main_pane, orient=tk.VERTICAL,
            bg=Theme.DIVIDER, sashrelief=tk.FLAT, sashwidth=4,
            handlesize=0
        )
        self.main_pane.add(self.inner_pane, minsize=400)

        # Editor section
        editor_frame = tk.Frame(self.inner_pane, bg=Theme.BG)
        editor_label = tk.Frame(editor_frame, bg=Theme.TOOLBAR_BG, pady=4, padx=8)
        editor_label.pack(fill=tk.X)
        tk.Label(
            editor_label, text="EDITOR", font=("Consolas", 9, "bold"),
            bg=Theme.TOOLBAR_BG, fg=Theme.FG_DIM
        ).pack(side=tk.LEFT)
        self.file_label = tk.Label(
            editor_label, text="untitled.efpl",
            font=("Consolas", 9), bg=Theme.TOOLBAR_BG, fg=Theme.FG_DIM
        )
        self.file_label.pack(side=tk.LEFT, padx=12)

        self.editor = Editor(editor_frame)
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.inner_pane.add(editor_frame, minsize=200)

        # Console section
        self.console = Console(self.inner_pane)
        self.inner_pane.add(self.console, minsize=100)

        # Default sash positions
        self.root.update_idletasks()
        self.main_pane.sash_place(0, 200, 0)
        self.inner_pane.sash_place(0, 0, 460)

    def toggle_sidebar(self):
        if self._sidebar_visible:
            self.main_pane.forget(self.sidebar_notebook)
            self._sidebar_visible = False
        else:
            self.main_pane.add(self.sidebar_notebook, before=self.inner_pane, minsize=180)
            self._sidebar_visible = True

    def _insert_snippet(self, text):
        """Insert text at the current editor cursor position."""
        self.editor.text.insert(tk.INSERT, text)
        self.editor.text.focus_set()
        self.editor._highlight()

    def _upload_data(self):
        """Delegate to DataPanel upload and switch to Data tab."""
        self.sidebar_notebook.select(self.data_panel)
        self.data_panel.upload_file()

    # ------------------------------------------------------------------ #
    #  Status bar                                                          #
    # ------------------------------------------------------------------ #
    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=Theme.STATUS_BG, pady=3, padx=10)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            bar, textvariable=self.status_var,
            bg=Theme.STATUS_BG, fg=Theme.FG_DIM, font=("Consolas", 9)
        ).pack(side=tk.LEFT)
        tk.Label(
            bar, text="EFPL v1.3", bg=Theme.STATUS_BG, fg=Theme.FG_DIM, font=("Consolas", 9)
        ).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------ #
    #  File operations                                                     #
    # ------------------------------------------------------------------ #
    def new_file(self):
        self.editor.clear()
        self._current_file = None
        self.file_label.config(text="untitled.efpl")
        self.status_var.set("New file")

    def _open_from_explorer(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            self.editor.set_code(code)
            self._current_file = path
            self.file_label.config(text=Path(path).name)
            self.status_var.set(f"Opened: {path}")
        except Exception as e:
            messagebox.showerror("Open Error", str(e))

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open EFPL Script",
            filetypes=[("EFPL Files", "*.efpl"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            self.editor.set_code(code)
            self._current_file = path
            self.file_label.config(text=path.split("/")[-1].split("\\")[-1])
            self.status_var.set(f"Opened: {path}")
        except Exception as e:
            messagebox.showerror("Open Error", str(e))

    def save_file(self):
        if self._current_file:
            self._write_file(self._current_file)
        else:
            self.save_file_as()

    def save_file_as(self):
        path = filedialog.asksaveasfilename(
            title="Save EFPL Script",
            defaultextension=".efpl",
            filetypes=[("EFPL Files", "*.efpl"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not path:
            return
        self._write_file(path)
        self._current_file = path
        self.file_label.config(text=path.split("/")[-1].split("\\")[-1])

    def _write_file(self, path: str):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.get_code())
            self.status_var.set(f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _load_example(self, filename: str):
        path = Path("workspace") / "scripts" / filename
        try:
            code = path.read_text(encoding="utf-8")
            self.editor.set_code(code)
            self._current_file = str(path)
            self.file_label.config(text=filename)
            self.status_var.set(f"Loaded example: {filename}")
        except Exception as e:
            messagebox.showerror("Example Error", str(e))

    # ------------------------------------------------------------------ #
    #  Library popup                                                       #
    # ------------------------------------------------------------------ #
    def _show_library_popup(self):
        win = tk.Toplevel(self.root)
        win.title("EFPL Libraries")
        win.configure(bg=Theme.BG)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        self._library_buttons = {}

        self.root.update_idletasks()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        win.geometry(f"360x360+{px + 120}+{py + 90}")

        tk.Label(
            win,
            text="Library",
            bg=Theme.TOOLBAR_BG,
            fg=Theme.ACCENT,
            font=("Consolas", 12, "bold"),
            anchor="w",
            padx=14,
            pady=8,
        ).pack(fill=tk.X)

        body = tk.Frame(win, bg=Theme.BG, padx=14, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            body,
            text="Turn ON only the built-in libraries this program needs.",
            bg=Theme.BG,
            fg=Theme.FG,
            font=("Consolas", 10),
            anchor="w",
            wraplength=320,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 10))

        canvas = tk.Canvas(body, bg=Theme.BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(body, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=Theme.BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=310)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except tk.TclError:
                pass
            
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        for key, label in self.LIBRARIES.items():
            var = self._library_vars.get(key)
            if var is None:
                var = tk.BooleanVar(value=False)
                self._library_vars[key] = var

            row = tk.Frame(scrollable_frame, bg=Theme.BG)
            row.pack(fill=tk.X, pady=4)
            tk.Label(
                row,
                text=label,
                bg=Theme.BG,
                fg=Theme.FG,
                font=("Consolas", 11, "bold"),
                width=12,
                anchor="w",
            ).pack(side=tk.LEFT)
            button = tk.Button(
                row,
                text="ON" if var.get() else "OFF",
                command=lambda name=key: self._toggle_library(name),
                bg=Theme.GREEN if var.get() else "#313244",
                fg=Theme.ACTIVE_FG if var.get() else Theme.FG,
                activebackground=Theme.ACTIVE_BG if var.get() else "#45475a",
                activeforeground="#1e1e2e" if var.get() else Theme.FG,
                font=("Consolas", 10),
                relief=tk.FLAT,
                width=8,
                cursor="hand2",
            )
            button.pack(side=tk.RIGHT)
            self._library_buttons[key] = button

        def _on_close():
            try:
                canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass
            win.destroy()
            
        win.protocol("WM_DELETE_WINDOW", _on_close)

        footer = tk.Frame(win, bg=Theme.BG, padx=14, pady=10)
        footer.pack(fill=tk.X)
        tk.Button(
            footer,
            text="Close",
            command=_on_close,
            bg=Theme.DIVIDER,
            fg=Theme.FG,
            font=("Consolas", 10),
            relief=tk.FLAT,
            padx=14,
            cursor="hand2",
            activebackground=Theme.HOVER,
            activeforeground=Theme.FG,
        ).pack(side=tk.RIGHT)

        self._update_library_status()

    def _toggle_library(self, name: str):
        var = self._library_vars[name]
        var.set(not var.get())
        self._sync_library_buttons()
        self._update_library_status()

    def _sync_library_buttons(self):
        for key, button in self._library_buttons.items():
            enabled = self._library_vars[key].get()
            button.config(
                text="ON" if enabled else "OFF",
                bg=Theme.GREEN if enabled else Theme.DIVIDER,
                fg=Theme.ACTIVE_FG if enabled else Theme.FG,
                activebackground=Theme.ACTIVE_BG if enabled else Theme.HOVER,
                activeforeground=Theme.ACTIVE_FG if enabled else Theme.FG,
            )

    def _enabled_libraries(self) -> list[str]:
        return [
            key for key, var in self._library_vars.items()
            if var.get()
        ]

    def _update_library_status(self):
        enabled = self._enabled_libraries()
        if enabled:
            self.status_var.set("Libraries ON: " + ", ".join(enabled))
        else:
            self.status_var.set("Libraries OFF")

    # ------------------------------------------------------------------ #
    #  Input collection (called before run)                                #
    # ------------------------------------------------------------------ #
    def _collect_inputs(self, code: str) -> dict | None:
        """
        Scan code for `take [number|text] input ... as varname` lines.
        For each found, show a styled input dialog.
        Returns a dict {varname: value}, or None if user cancelled.
        """
        inputs = {}
        for line in code.splitlines():
            stripped = line.strip()
            low = stripped.lower()
            if not re.match(r"^take\s+(?:(?:number|text)\s+)?input\b", low):
                continue
            if " as " not in low:
                continue

            # Extract prompt text (between quotes if present)
            left, var_part = re.split(r"\s+as\s+", stripped, maxsplit=1, flags=re.IGNORECASE)
            var = re.split(r"\s+default\s+", var_part, maxsplit=1, flags=re.IGNORECASE)[0].strip()

            prompt_text = var  # fallback label
            m = re.search(r'"([^"]*)"', left)
            if m:
                prompt_text = m.group(1)

            value = self._input_dialog(prompt_text, var)
            if value is None:          # user pressed Cancel
                return None
            inputs[var] = value

        return inputs

    def _input_dialog(self, prompt: str, var_name: str) -> str | None:
        """Show a styled modal input dialog. Returns string or None on cancel."""
        result = [None]
        dialog = tk.Toplevel(self.root)
        dialog.title("Input Required")
        dialog.configure(bg=Theme.BG)
        dialog.resizable(False, False)
        dialog.grab_set()   # modal

        # Center on parent
        self.root.update_idletasks()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        dialog.geometry(f"400x180+{px + pw//2 - 200}+{py + ph//2 - 90}")

        # Header
        tk.Label(
            dialog, text=f'Input for  "{var_name}"',
            bg=Theme.TOOLBAR_BG, fg=Theme.ACCENT,
            font=("Consolas", 10, "bold"), anchor="w", padx=14, pady=8
        ).pack(fill=tk.X)

        # Prompt label
        tk.Label(
            dialog, text=prompt,
            bg=Theme.BG, fg=Theme.FG,
            font=("Consolas", 11), anchor="w", padx=20
        ).pack(fill=tk.X, pady=(16, 6))

        # Entry
        entry_var = tk.StringVar()
        entry = tk.Entry(
            dialog, textvariable=entry_var,
            bg=Theme.DIVIDER, fg=Theme.FG, insertbackground=Theme.ACCENT,
            font=("Consolas", 12), relief=tk.FLAT, bd=0
        )
        entry.pack(fill=tk.X, padx=20, ipady=8)
        entry.focus_set()

        # Buttons
        btn_frame = tk.Frame(dialog, bg=Theme.BG)
        btn_frame.pack(fill=tk.X, padx=16, pady=10)

        def on_ok(e=None):
            result[0] = entry_var.get()
            dialog.destroy()

        def on_cancel():
            result[0] = None
            dialog.destroy()

        entry.bind("<Return>", on_ok)
        dialog.bind("<Escape>", lambda e: on_cancel())

        tk.Button(
            btn_frame, text="OK", command=on_ok,
            bg=Theme.GREEN, fg=Theme.ACTIVE_FG, font=("Consolas", 10, "bold"),
            relief=tk.FLAT, padx=20, cursor="hand2",
            activebackground=Theme.ACTIVE_BG
        ).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(
            btn_frame, text="Cancel", command=on_cancel,
            bg=Theme.DIVIDER, fg=Theme.FG, font=("Consolas", 10),
            relief=tk.FLAT, padx=12, cursor="hand2",
            activebackground=Theme.HOVER
        ).pack(side=tk.RIGHT)

        dialog.wait_window()
        return result[0]

    # ------------------------------------------------------------------ #
    #  Run                                                                 #
    # ------------------------------------------------------------------ #
    def run_code(self):
        if self._running:
            return
        code = self.editor.get_code()
        self.editor.clear_error()

        # Collect all user inputs before starting thread
        inputs = self._collect_inputs(code)
        if inputs is None:   # user cancelled an input dialog
            self.console.write("Run cancelled by user.", tag="warn")
            return

        self.console.clear()
        self._set_running(True)
        self.console.write("> Running script...", tag="dim")

        def worker():
            try:
                logs = run_script(
                    code,
                    inputs,
                    script_path=self._current_file,
                    enabled_modules=self._enabled_libraries(),
                )
                self.root.after(0, self._on_run_complete, logs)
            except Exception as e:
                self.root.after(0, self._on_run_complete, [f"Runtime error: {e}"])

        threading.Thread(target=worker, daemon=True).start()

    def _on_run_complete(self, logs: list):
        self.console.write_logs(logs)
        self._mark_first_error(logs)
        self.console.write("■ Execution finished.", tag="dim")
        self._set_running(False)

    def _mark_first_error(self, logs: list):
        for line in logs:
            match = re.search(r"(?:Syntax|Runtime) Error at line (\d+)", str(line), re.IGNORECASE)
            if match:
                self.editor.mark_error_line(int(match.group(1)))
                return

    def _set_running(self, running: bool):
        self._running = running
        self.status_var.set("Running…" if running else "Ready")


    # ------------------------------------------------------------------ #
    #  Help dialog                                                         #
    # ------------------------------------------------------------------ #
    HELP_SECTIONS = [
        ("Variables & Output", "#89b4fa", """DESCRIPTION
  Variables store values. EFPL uses natural English syntax.
  Supported types: number, text, boolean, array, dictionary, set.

COMMENTS
  # Use 'set <name> to <value>' to declare any variable.
  # Use 'show' to print any value to the console.

USAGE
  set x to 10               # number
  set name to "Alice"       # text
  set flag to true          # boolean
  set items to [1, 2, 3]    # array
  set info to {"key": "v"}  # dictionary
  set s to {1, 2, 3}        # set

  show x
  show "Hello, " + name
  show items[0]             # index access"""),

        ("Input", "#89b4fa", """DESCRIPTION
  Collect values from the user at runtime.
  Input dialogs are shown automatically when the script runs in the IDE.

COMMENTS
  # Syntax: take [number|text] input "Prompt" as varname [default "val"]
  # 'number input' coerces to numeric type automatically.

USAGE
  take input "Enter your name:" as name
  take number input "Enter your age:" as age
  take text input "Enter city:" as city default "Chennai"
  show "Hello " + name + ", age " + age"""),

        ("Operators", "#fab387", """DESCRIPTION
  EFPL supports standard arithmetic, comparison, and logical operators.

COMMENTS
  # Arithmetic : + - * / % **  (** = power)
  # Comparison : == != > < >= <=
  # Logical    : and  or  not

USAGE
  set result to (10 + 5) * 2 - 3 / 1.5
  set power  to 2 ** 8          # 256

  if x > 5 and x < 20
    show "in range"
  end

  if not flag
    show "flag is false"
  end"""),

        ("Conditionals", "#cba6f7", """DESCRIPTION
  Branch code execution based on conditions.

COMMENTS
  # if / else if / else blocks must end with 'end'.
  # switch/case can replace long if-chains.

USAGE
  if score >= 90
    show "Grade A"
  else if score >= 60
    show "Grade B"
  else
    show "Grade F"
  end

  switch grade
    case "A"
      show "Excellent"
    case "B"
      show "Good"
    default
      show "Try harder"
  end"""),

        ("Loops", "#cba6f7", """DESCRIPTION
  Repeat blocks of code using for, while, or do-while loops.

COMMENTS
  # 'for' loops iterate over a numeric range.
  # 'while' checks condition before each iteration.
  # 'do...while' runs at least once.
  # Use 'break' to exit, 'continue' to skip.

USAGE
  for i from 1 to 5
    show i
  end

  for i from 0 to 10 step 2
    show i
  end

  set x to 5
  while x > 0
    show x
    set x to x - 1
  end

  do
    show x
    set x to x + 1
  while x < 3

  for i from 1 to 10
    if i == 5
      break
    end
  end"""),

        ("Functions", "#a6e3a1", """DESCRIPTION
  Reusable named blocks of code that accept parameters and return values.

COMMENTS
  # Define with 'function name(params)...end'.
  # Call with 'call name(args)' (side-effects) or assign result to a variable.
  # 'return' exits and produces a value.

USAGE
  function add(a, b)
    return a + b
  end

  set total to add(10, 20)
  show total               # 30

  function greet(name)
    show "Hello, " + name
  end

  call greet("Alice")"""),

        ("Arrays", "#a6e3a1", """DESCRIPTION
  Ordered, mutable lists of values. Supports add/remove and index access.

COMMENTS
  # Activate with: use array
  # Indexing is 0-based.

USAGE
  use array
  set nums to [10, 20, 30]

  add 40 to nums            # [10,20,30,40]
  remove 10 from nums       # [20,30,40]
  set nums[0] to 99

  show nums[1]              # 30
  show length(nums)         # 3
  show sort(nums)
  show reverse(nums)
  show join(nums, ", ")"""),

        ("Dictionaries & Sets", "#f9e2af", """DESCRIPTION
  Dictionaries store key-value pairs. Sets store unique unordered values.

COMMENTS
  # Dictionary keys must be strings.
  # Sets automatically remove duplicates.

USAGE
  # Dictionary
  set person to {"name": "Alice", "age": 20}
  show person["name"]
  set person["age"] to 21

  # Set
  set my_set to {1, 2, 3, 2, 1}
  show my_set              # {1, 2, 3}"""),

        ("Strings / Text", "#f38ba8", """DESCRIPTION
  Built-in string functions for manipulation and inspection.

COMMENTS
  # Activate with: use text
  # Strings are concatenated with '+'.

USAGE
  use text
  set s to "Hello World"

  show length(s)            # 11
  show upper(s)             # HELLO WORLD
  show lower(s)             # hello world
  show contains(s, "World") # true
  show replace(s, "World", "EFPL")
  show s + "!"              # Hello World!"""),

        ("Math / Random / Time", "#fab387", """DESCRIPTION
  Built-in mathematical, random, and time/date functions.

COMMENTS
  # Activate each module separately: use math / use random / use time

USAGE
  use math
  show sqrt(25)             # 5.0
  show round(3.14159, 2)    # 3.14
  show abs(-42)             # 42
  show min(1, 5, 3)         # 1
  show max(1, 5, 3)         # 5
  show pi()                 # 3.14159...
  show floor(3.9)           # 3
  show ceil(3.1)            # 4

  use random
  show random(1, 10)        # random int 1–10

  use time
  show now()                # current datetime
  show today()              # current date"""),

        ("Type Utilities", "#cba6f7", """DESCRIPTION
  Check and convert between EFPL data types at runtime.

COMMENTS
  # Activate with: use type

USAGE
  use type
  show to_number("123")     # 123
  show to_text(123)         # "123"
  show to_boolean("true")   # true
  show type_of(42)          # "number"
  show is_number(42)        # true
  show is_text("hi")        # true
  show is_array([1, 2])     # true
  show is_dictionary({})    # true"""),

        ("Classes & OOP", "#89b4fa", """DESCRIPTION
  EFPL supports object-oriented programming with classes, instantiation,
  method calls, and single inheritance via 'extends'.

COMMENTS
  # Use 'function init(...)' as the constructor.
  # 'self' refers to the current instance.
  # Child classes inherit all parent methods.
  # Override a method by redefining it in the child class.

USAGE
  class Animal
    function init(name)
      set self.name to name
    end
    function speak()
      show self.name + " makes a sound"
    end
  end

  class Dog extends Animal
    function speak()
      show self.name + " barks!"
    end
    function fetch()
      show self.name + " fetches the ball"
    end
  end

  set d to new Dog("Rex")
  call d.speak()            # Rex barks!
  call d.fetch()            # Rex fetches the ball"""),

        ("Files", "#a6e3a1", """DESCRIPTION
  Read and write plain text files within the workspace.

COMMENTS
  # Activate with: use file
  # Files are restricted to the workspace/files directory.
  # 'write' creates/overwrites. 'append' adds to the end.

USAGE
  use file
  write "Hello EFPL" to file "notes.txt"
  append " — more text" to file "notes.txt"

  read file "notes.txt" as content
  show content"""),

        ("Database", "#f9e2af", """DESCRIPTION
  Persistent local data storage using SQLite via the database module.

COMMENTS
  # Activate with: use database
  # 'execute' runs INSERT/UPDATE/DELETE and returns rowcount.
  # 'query' runs SELECT and returns a list of dictionaries.
  # Always close the connection when done.

USAGE
  use database
  set db to database.connect("app.db")

  call database.execute(db,
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")

  call database.execute(db,
    "INSERT INTO users (name) VALUES (?)", ["Alice"])

  set rows to database.query(db, "SELECT * FROM users")
  show rows

  call database.close(db)"""),

        ("HTTP & JSON", "#f38ba8", """DESCRIPTION
  Make HTTP requests and parse/stringify JSON data.

COMMENTS
  # HTTP: use http  |  JSON: use json
  # http.get(url)             → response text
  # http.post(url, dict)      → response text
  # json.parse(text)          → dictionary/array
  # json.stringify(dict/list) → JSON text

USAGE
  use http
  use json

  set resp to http.get("https://api.example.com/data")
  set data to json.parse(resp)
  show data["title"]

  set payload to {"user": "Alice", "score": 99}
  set result to http.post("https://api.example.com/score", payload)
  show json.stringify(payload)"""),

        ("OS & System", "#fab387", """DESCRIPTION
  Interact with the operating system: environment variables and shell commands.

COMMENTS
  # Activate with: use os
  # os.env(key)   → reads an environment variable (returns "" if missing)
  # os.run(cmd)   → runs a shell command and returns stdout

USAGE
  use os
  show os.env("PATH")
  show os.env("HOME")
  show os.run("echo Hello from Shell")
  show os.run("python --version")"""),

        ("Visual / Charts", "#cba6f7", """DESCRIPTION
  Generate charts and graphs using the visual module (requires matplotlib).

COMMENTS
  # Activate with: use visual
  # Charts are saved to workspace/outputs as PNG files.
  # Call visual.render() to display inline in the IDE console.

USAGE
  use visual
  set x to [1, 2, 3, 4, 5]
  set y to [1, 4, 9, 16, 25]

  call visual.clear()
  call visual.figure(8, 5)
  call visual.line(x, y)
  call visual.title("Squares")
  call visual.xlabel("n")
  call visual.ylabel("n²")
  call visual.grid(true)
  show visual.render("squares.png")

  # Other chart types:
  call visual.bar(["A","B","C"], [10, 25, 15])
  call visual.scatter(x, y)
  call visual.pie([40, 60], ["Done", "Left"])
  call visual.hist([1, 2, 2, 3, 3, 3])"""),

        ("Comments & Imports", "#6c7086", """DESCRIPTION
  Annotate code with comments or split code across multiple files.

COMMENTS
  # Single-line comments start with #
  # Block comments use /* ... */
  # Import other .efpl scripts using 'import'

USAGE
  # This is a single-line comment

  /*
    This is a
    multi-line block comment
  */

  import "helpers.efpl"    # loads and runs helpers.efpl
  call my_helper_function()"""),
    ]

    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title("EFPL Language Reference")
        win.configure(bg=Theme.BG)
        win.geometry("860x580")
        win.minsize(700, 480)

        # ── Outer layout ─────────────────────────────────────────────────
        outer = tk.Frame(win, bg=Theme.BG)
        outer.pack(fill=tk.BOTH, expand=True)

        # ── Left sidebar: section list ────────────────────────────────────
        sidebar = tk.Frame(outer, bg=Theme.TOOLBAR_BG, width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar, text="EFPL REFERENCE", font=("Consolas", 9, "bold"),
            bg=Theme.TOOLBAR_BG, fg=Theme.FG_DIM, pady=10, padx=10, anchor="w"
        ).pack(fill=tk.X)

        tk.Frame(sidebar, bg=Theme.DIVIDER, height=1).pack(fill=tk.X)

        # Scrollable nav list
        nav_canvas = tk.Canvas(sidebar, bg=Theme.TOOLBAR_BG, highlightthickness=0)
        nav_canvas.pack(fill=tk.BOTH, expand=True)
        nav_frame = tk.Frame(nav_canvas, bg=Theme.TOOLBAR_BG)
        nav_canvas.create_window((0, 0), window=nav_frame, anchor="nw")
        nav_frame.bind("<Configure>", lambda e: nav_canvas.configure(
            scrollregion=nav_canvas.bbox("all")))
        nav_canvas.bind("<MouseWheel>", lambda e: nav_canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))

        # ── Right content pane ────────────────────────────────────────────
        content_frame = tk.Frame(outer, bg=Theme.BG)
        content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Section title bar
        title_bar = tk.Frame(content_frame, bg=Theme.TOOLBAR_BG, pady=8, padx=16)
        title_bar.pack(fill=tk.X)
        title_label = tk.Label(
            title_bar, text="", font=("Consolas", 13, "bold"),
            bg=Theme.TOOLBAR_BG, fg=Theme.ACCENT, anchor="w"
        )
        title_label.pack(side=tk.LEFT)

        tk.Frame(content_frame, bg=Theme.DIVIDER, height=1).pack(fill=tk.X)

        # Scrollable content text widget
        text_scroll = tk.Scrollbar(content_frame)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        content_text = tk.Text(
            content_frame,
            font=("Consolas", 11),
            bg=Theme.BG, fg=Theme.FG,
            relief=tk.FLAT, bd=0,
            padx=20, pady=14,
            wrap=tk.WORD,
            state=tk.DISABLED,
            yscrollcommand=text_scroll.set,
        )
        content_text.pack(fill=tk.BOTH, expand=True)
        text_scroll.config(command=content_text.yview)

        # Text tags for structured display
        content_text.tag_config("heading",  foreground=Theme.ACCENT,    font=("Consolas", 10, "bold"))
        content_text.tag_config("desc",     foreground=Theme.FG,        font=("Consolas", 11))
        content_text.tag_config("comment",  foreground=Theme.GRAY,      font=("Consolas", 10, "italic"))
        content_text.tag_config("code",     foreground=Theme.GREEN,     font=("Consolas", 11))
        content_text.tag_config("divider",  foreground=Theme.DIVIDER)

        def show_section(title, color, raw_text):
            title_label.config(text=title, fg=color)
            content_text.config(state=tk.NORMAL)
            content_text.delete("1.0", tk.END)

            for line in raw_text.strip().splitlines():
                stripped = line.strip()
                if stripped in ("DESCRIPTION", "COMMENTS", "USAGE"):
                    content_text.insert(tk.END, f"\n── {stripped} ──\n", "heading")
                elif stripped.startswith("#"):
                    content_text.insert(tk.END, f"  {line}\n", "comment")
                elif stripped == "":
                    content_text.insert(tk.END, "\n")
                else:
                    content_text.insert(tk.END, f"  {line}\n", "code")

            content_text.config(state=tk.DISABLED)

        # ── Build nav buttons ─────────────────────────────────────────────
        btn_refs = []

        def make_nav_click(t, c, txt, btn):
            def handler():
                for b in btn_refs:
                    b.config(bg=Theme.TOOLBAR_BG, fg=Theme.FG)
                btn.config(bg=Theme.SELECTION, fg=Theme.ACCENT)
                show_section(t, c, txt)
            return handler

        for title, color, raw in self.HELP_SECTIONS:
            b = tk.Button(
                nav_frame, text=f"  {title}", anchor="w",
                bg=Theme.TOOLBAR_BG, fg=Theme.FG,
                font=("Consolas", 10), relief=tk.FLAT,
                padx=6, pady=5, cursor="hand2",
                activebackground=Theme.HOVER, activeforeground=Theme.FG,
                width=22,
            )
            b.pack(fill=tk.X)
            btn_refs.append(b)
            b.config(command=make_nav_click(title, color, raw, b))

        # Load first section by default
        if self.HELP_SECTIONS:
            t, c, raw = self.HELP_SECTIONS[0]
            btn_refs[0].config(bg=Theme.SELECTION, fg=Theme.ACCENT)
            show_section(t, c, raw)


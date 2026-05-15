import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog
from pathlib import Path
import shutil
from efpl_ui.theme import Theme


class Console(tk.Frame):
    """
    A read-only Tkinter console widget with:
    - Colour-coded log levels (INFO, ERROR, WARN)
    - Auto-scroll to bottom
    - Clear functionality
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=Theme.STATUS_BG, **kwargs)

        self._font = tkfont.Font(family="Consolas", size=11)
        self._images = []

        # --- Header bar ---
        header = tk.Frame(self, bg=Theme.TOOLBAR_BG, pady=4, padx=8)
        header.pack(fill=tk.X)
        tk.Label(
            header, text="OUTPUT CONSOLE", font=("Consolas", 9, "bold"),
            bg=Theme.TOOLBAR_BG, fg=Theme.FG_DIM
        ).pack(side=tk.LEFT)
        tk.Button(
            header, text="Clear", command=self.clear,
            bg=Theme.DIVIDER, fg=Theme.FG, relief=tk.FLAT,
            font=("Consolas", 9), padx=6, cursor="hand2",
            activebackground=Theme.HOVER, activeforeground=Theme.FG
        ).pack(side=tk.RIGHT)

        # --- Scrollbar ---
        from tkinter import ttk
        scrollbar = ttk.Scrollbar(self, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Text widget ---
        self.text = tk.Text(
            self,
            font=self._font,
            bg=Theme.STATUS_BG,
            fg=Theme.FG,
            state=tk.DISABLED,
            relief=tk.FLAT,
            bd=0,
            wrap=tk.WORD,
            padx=10,
            pady=6,
            yscrollcommand=scrollbar.set,
        )
        self.text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text.yview)

        # --- Tag styles ---
        self.text.tag_config("info",  foreground=Theme.FG)
        self.text.tag_config("error", foreground=Theme.RED)
        self.text.tag_config("warn",  foreground=Theme.YELLOW)
        self.text.tag_config("ok",    foreground=Theme.GREEN)
        self.text.tag_config("dim",   foreground=Theme.FG_DIM)

    # ------------------------------------------------------------------ #
    #  Public write API                                                    #
    # ------------------------------------------------------------------ #
    def write(self, text: str, tag: str = "info"):
        """Append text to the console with the given colour tag."""
        self.text.config(state=tk.NORMAL)
        self.text.insert(tk.END, str(text) + "\n", tag)
        self.text.config(state=tk.DISABLED)
        self.text.see(tk.END)

    def write_logs(self, logs: list):
        """Write a list of log strings, auto-detecting error lines."""
        for line in logs:
            line_str = str(line)
            if line_str.startswith("VISUAL_RENDER:"):
                self.write_visual(line_str.split(":", 1)[1])
            elif line_str.lower().startswith(("error", "runtime error", "invalid", "unknown")):
                self.write(line_str, tag="error")
            elif line_str.lower().startswith("warn"):
                self.write(line_str, tag="warn")
            else:
                self.write(line_str, tag="ok")

    def write_visual(self, path: str):
        """Render a generated visual image inside the console."""
        image_path = Path(path)
        if not image_path.exists():
            self.write(f"Visual preview missing: {image_path}", tag="error")
            return

        try:
            image = tk.PhotoImage(file=str(image_path))
        except Exception as exc:
            self.write(f"Visual preview error: {exc}", tag="error")
            return

        max_width = 760
        max_height = 360
        scale = max(
            1,
            int((image.width() + max_width - 1) / max_width),
            int((image.height() + max_height - 1) / max_height),
        )
        if scale > 1:
            image = image.subsample(scale, scale)

        self._images.append(image)
        self.text.config(state=tk.NORMAL)
        self.text.insert(tk.END, "\n")
        self.text.image_create(tk.END, image=image)
        self.text.insert(tk.END, "\n")
        self.text.config(state=tk.DISABLED)

        row = tk.Frame(self.text, bg=Theme.STATUS_BG, pady=4)
        tk.Label(
            row,
            text=str(image_path),
            bg=Theme.STATUS_BG,
            fg=Theme.GREEN,
            font=("Consolas", 9),
        ).pack(side=tk.LEFT)
        tk.Button(
            row,
            text="Save As",
            command=lambda p=image_path: self._save_visual_as(p),
            bg=Theme.DIVIDER,
            fg=Theme.FG,
            relief=tk.FLAT,
            font=("Consolas", 9),
            padx=8,
            cursor="hand2",
            activebackground=Theme.HOVER,
            activeforeground=Theme.FG,
        ).pack(side=tk.RIGHT, padx=8)

        self.text.config(state=tk.NORMAL)
        self.text.window_create(tk.END, window=row)
        self.text.insert(tk.END, "\n")
        self.text.config(state=tk.DISABLED)
        self.text.see(tk.END)

    def _save_visual_as(self, source: Path):
        target = filedialog.asksaveasfilename(
            title="Save Visual",
            defaultextension=source.suffix or ".png",
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
            initialfile=source.name,
        )
        if not target:
            return
        try:
            shutil.copyfile(source, target)
            self.write(f"Visual saved: {target}", tag="ok")
        except Exception as exc:
            self.write(f"Visual save error: {exc}", tag="error")

    def clear(self):
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.config(state=tk.DISABLED)
        self._images.clear()

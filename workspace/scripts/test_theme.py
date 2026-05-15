import tkinter as tk

root = tk.Tk()
root.geometry("200x200")

def toggle():
    global dark
    dark = not dark
    if dark:
        root.tk_setPalette(background="#1e1e2e", foreground="#cdd6f4", activeBackground="#313244", activeForeground="#cdd6f4")
    else:
        root.tk_setPalette(background="#eff1f5", foreground="#4c4f69", activeBackground="#ccd0da", activeForeground="#4c4f69")

dark = True
tk.Button(root, text="Toggle", command=toggle).pack()
tk.Label(root, text="Hello").pack()
tk.Text(root, width=10, height=2).pack()

# root.mainloop()

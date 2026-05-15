from pathlib import Path

WORKSPACE = Path("workspace")

def load_script(name):
    p = WORKSPACE / "scripts" / name
    return p.read_text(encoding="utf-8")

def save_script(name, code):
    p = WORKSPACE / "scripts" / name
    p.write_text(code, encoding="utf-8")

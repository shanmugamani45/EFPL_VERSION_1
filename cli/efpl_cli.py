"""
efpl_cli.py — Command-line runner for EFPL scripts.

Usage:
    python -m cli.efpl_cli run <script.efpl>
    python -m cli.efpl_cli run <script.efpl> --input name=Alice age=20
    python -m cli.efpl_cli repl
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on the path when run via `python -m`
_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from efpl_runtime.executor import run_script


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _parse_inputs(raw: list[str]) -> dict:
    """Convert key=value pairs from --input into a dict."""
    result = {}
    for item in raw:
        if "=" not in item:
            print(f"[WARN] Invalid input format (expected key=value): {item!r}")
            continue
        key, _, value = item.partition("=")
        result[key.strip()] = value.strip()
    return result


def _print_logs(logs: list):
    for line in logs:
        text = str(line)
        if text.lower().startswith(("error", "runtime error", "invalid", "unknown")):
            print(f"\033[91m{text}\033[0m")          # red
        elif text.lower().startswith("warn"):
            print(f"\033[93m{text}\033[0m")          # yellow
        else:
            print(f"\033[92m{text}\033[0m")          # green


# ------------------------------------------------------------------ #
#  Commands                                                            #
# ------------------------------------------------------------------ #

def cmd_run(args):
    """Run an EFPL script file."""
    path = Path(args.script)
    if not path.exists():
        print(f"\033[91mError: File not found: {path}\033[0m", file=sys.stderr)
        sys.exit(1)

    code = path.read_text(encoding="utf-8")
    inputs = _parse_inputs(args.input or [])

    print(f"\033[90m> Running: {path}\033[0m")
    try:
        def cli_input_callback(prompt_text):
            try:
                return input(f"{prompt_text}")
            except EOFError:
                return ""
                
        logs = run_script(code, inputs, script_path=path, input_callback=cli_input_callback)
        _print_logs(logs)
        print(f"\033[90m* Done.\033[0m")
    except Exception as e:
        print(f"\033[91mRuntime error: {e}\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_repl(_args):
    """Interactive EFPL REPL — read-eval-print loop."""
    from efpl_core.interpreter import EFPLRuntime
    from efpl_runtime.executor import run_script

    print("\033[96mEFPL Interactive REPL (type 'exit' or Ctrl-C to quit)\033[0m")
    print("\033[90mEnter EFPL statements. Blank line to execute a multi-line block.\033[0m\n")

    runtime = EFPLRuntime()
    buffer = []

    try:
        while True:
            prompt = "... " if buffer else "efpl> "
            try:
                line = input(prompt)
            except EOFError:
                break

            if line.strip().lower() == "exit":
                break

            if line.strip() == "" and buffer:
                # Execute buffered block
                code = "\n".join(buffer)
                buffer.clear()
                try:
                    logs = run_script(code, input_callback=lambda p: input(p))
                    _print_logs(logs)
                except Exception as e:
                    print(f"\033[91mRuntime error: {e}\033[0m")
            elif line.strip() == "":
                pass
            else:
                buffer.append(line)
                # Auto-execute single-line commands that don't open a block
                low = line.strip().lower()
                is_block_start = any(
                    low.startswith(kw)
                    for kw in ("if ", "while ", "for ", "do", "switch ", "else")
                )
                if not is_block_start and not buffer[:-1]:
                    code = buffer.pop()
                    try:
                        logs = run_script(code, input_callback=lambda p: input(p))
                        _print_logs(logs)
                    except Exception as e:
                        print(f"\033[91mRuntime error: {e}\033[0m")
    except KeyboardInterrupt:
        pass

    print("\n\033[90mBye!\033[0m")


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(
        prog="efpl",
        description="EFPL — Easy Friendly Programming Language CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- run command ---
    run_p = sub.add_parser("run", help="Run an EFPL script file")
    run_p.add_argument("script", help="Path to the .efpl file")
    run_p.add_argument(
        "--input", "-i",
        nargs="*",
        metavar="key=value",
        help="Input variables (e.g. --input name=Alice age=30)"
    )
    run_p.set_defaults(func=cmd_run)

    # --- repl command ---
    repl_p = sub.add_parser("repl", help="Start the interactive REPL")
    repl_p.set_defaults(func=cmd_repl)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

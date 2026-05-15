import re
from pathlib import Path

from efpl_core.interpreter import EFPLRuntime, EFPLRuntimeError, EFPLSyntaxError

MAX_LOOP = 10000
MAX_RECURSION = 200
IMPORT_LIMIT = 50


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


def _strip_block_comments(code):
    result = []
    in_comment = False

    for line_no, raw in enumerate(code.splitlines(), start=1):
        line = raw.rstrip()
        out = ""
        i = 0

        while i < len(line):
            if in_comment:
                end = line.find("*/", i)
                if end == -1:
                    i = len(line)
                else:
                    in_comment = False
                    i = end + 2
            else:
                start = line.find("/*", i)
                if start == -1:
                    out += line[i:]
                    i = len(line)
                else:
                    out += line[i:start]
                    in_comment = True
                    i = start + 2

        result.append((line_no, out.rstrip()))

    if in_comment:
        raise EFPLSyntaxError("Unclosed block comment")

    return result


def _resolve_import(name, current_dir):
    raw = Path(name)
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        if current_dir is not None:
            candidates.append(current_dir / raw)
        candidates.append(Path("workspace") / "scripts" / raw)
        candidates.append(raw)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    raise EFPLRuntimeError(f"Import file not found: {name}")


def _expand_imports(code, current_dir=None, seen=None, depth=0):
    if seen is None:
        seen = set()
    if depth > IMPORT_LIMIT:
        raise EFPLRuntimeError("Import limit exceeded")

    expanded = []
    for raw in code.splitlines():
        line = raw.strip()
        match = re.match(r'^import\s+"([^"]+)"\s*$', line, re.IGNORECASE)
        if not match:
            expanded.append(raw)
            continue

        path = _resolve_import(match.group(1), current_dir)
        if path in seen:
            continue
        seen.add(path)
        imported = path.read_text(encoding="utf-8")
        expanded.append(f"# imported from {path.name}")
        expanded.append(_expand_imports(imported, path.parent, seen, depth + 1))

    return "\n".join(expanded)


def _is_block_start(low):
    return (
        low.startswith("if ")
        or low.startswith("for ")
        or low.startswith("while ")
        or low == "do"
        or low.startswith("switch ")
        or low.startswith("function ")
        or low.startswith("class ")
        or low == "try"
    )


def _find_end(lines, start, limit):
    depth = 0
    i = start

    while i < limit:
        line_no, line = lines[i]
        low = line.strip().lower()

        if not low or low.startswith("#"):
            i += 1
            continue

        if low == "do":
            i = _find_do_while(lines, i, limit)
        elif _is_block_start(low):
            depth += 1
        elif low == "end":
            depth -= 1
            if depth == 0:
                return i
            if depth < 0:
                raise EFPLSyntaxError("Unexpected end", line_no)

        i += 1

    start_no, start_line = lines[start]
    raise EFPLSyntaxError(f"Missing end for '{start_line.strip()}'", start_no)


def _find_do_while(lines, start, limit):
    i = start + 1

    while i < limit:
        line_no, line = lines[i]
        low = line.strip().lower()

        if not low or low.startswith("#"):
            i += 1
            continue

        if low == "do":
            i = _find_do_while(lines, i, limit)
        elif low.startswith("while "):
            return i
        elif _is_block_start(low):
            end = _find_end(lines, i, limit)
            i = end

        i += 1

    start_no, _ = lines[start]
    raise EFPLSyntaxError("Missing while for do block", start_no)


def _split_if_branches(lines, start, end):
    branches = []
    branch_cond = lines[start][1].strip()[3:].strip()
    branch_start = start + 1
    depth = 0
    i = start + 1

    while i < end:
        line_no, line = lines[i]
        low = line.strip().lower()

        if not low or low.startswith("#"):
            i += 1
            continue

        if low == "do":
            i = _find_do_while(lines, i, end)
        elif _is_block_start(low):
            depth += 1
        elif low == "end":
            depth -= 1
        elif depth == 0 and low.startswith("else if "):
            branches.append((branch_cond, branch_start, i))
            branch_cond = line.strip()[8:].strip()
            branch_start = i + 1
        elif depth == 0 and low == "else":
            branches.append((branch_cond, branch_start, i))
            branch_cond = None
            branch_start = i + 1

        i += 1

    branches.append((branch_cond, branch_start, end))
    return branches


def _parse_function_header(line, line_no):
    match = re.match(r"^function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*$", line, re.IGNORECASE)
    if not match:
        raise EFPLSyntaxError("Expected: function name(param1, param2)", line_no)
    name = match.group(1)
    params_text = match.group(2).strip()
    params = []
    if params_text:
        params = [p.strip() for p in params_text.split(",")]
        for param in params:
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", param):
                raise EFPLSyntaxError(f"Invalid parameter name '{param}'", line_no)
    return name, params


def _parse_class_header(line, line_no):
    match = re.match(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+([A-Za-z_][A-Za-z0-9_]*))?\s*$", line, re.IGNORECASE)
    if not match:
        raise EFPLSyntaxError("Expected: class ClassName [extends ParentName]", line_no)
    return match.group(1), match.group(2)

def _parse_class(lines, start, end):
    methods = {}
    i = start + 1
    while i < end:
        line_no, line = lines[i]
        low = line.strip().lower()
        if not low or low.startswith("#"):
            i += 1
            continue
        if low.startswith("function "):
            func_end = _find_end(lines, i, end)
            name, params = _parse_function_header(line.strip(), line_no)
            methods[name] = {
                "params": params,
                "body_start": i + 1,
                "body_end": func_end,
                "line_no": line_no,
            }
            i = func_end + 1
        else:
            raise EFPLSyntaxError(f"Unexpected statement in class body: {line.strip()}", line_no)
    return methods


def _parse_for(line, line_no, rt):
    match = re.match(
        r"^for\s+([A-Za-z_][A-Za-z0-9_]*)\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+step\s+(.+))?$",
        line,
        re.IGNORECASE,
    )
    if not match:
        raise EFPLSyntaxError("Expected: for i from start to end [step value]", line_no)
    var, start_expr, end_expr, step_expr = match.groups()
    start = rt.eval_expr(start_expr, line_no)
    stop = rt.eval_expr(end_expr, line_no)
    step = rt.eval_expr(step_expr, line_no) if step_expr else (1 if start <= stop else -1)
    if step == 0:
        raise EFPLRuntimeError("For loop step cannot be 0", line_no)
    return var, start, stop, step


def _split_cases(lines, start, end):
    parts = []
    current_value = None
    current_start = None
    depth = 0

    for i in range(start + 1, end):
        line_no, line = lines[i]
        low = line.strip().lower()

        if not low or low.startswith("#"):
            continue

        if low == "do":
            i = _find_do_while(lines, i, end)
        elif _is_block_start(low):
            depth += 1
        elif low == "end":
            depth -= 1
        elif depth == 0 and (low.startswith("case ") or low == "default"):
            if current_start is not None:
                parts.append((current_value, current_start, i))
            current_value = None if low == "default" else line.strip()[5:].strip()
            current_start = i + 1

    if current_start is not None:
        parts.append((current_value, current_start, end))
    return parts


def _split_try_catch(lines, start, end):
    catch_var = None
    try_start = start + 1
    catch_start = None
    try_end = None
    depth = 0

    for i in range(start + 1, end):
        line_no, line = lines[i]
        low = line.strip().lower()

        if not low or low.startswith("#"):
            continue

        if low == "do":
            i = _find_do_while(lines, i, end)
        elif _is_block_start(low):
            depth += 1
        elif low == "end":
            depth -= 1
        elif depth == 0 and low.startswith("catch "):
            try_end = i
            catch_var = line.strip()[6:].strip()
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", catch_var):
                raise EFPLSyntaxError(f"Invalid variable name '{catch_var}' in catch", line_no)
            catch_start = i + 1

    if try_end is None:
        try_end = end

    catch_end = end if catch_start else None
    return try_start, try_end, catch_var, catch_start, catch_end


def _register_functions(lines, rt):
    i = 0
    while i < len(lines):
        line_no, line = lines[i]
        low = line.strip().lower()
        if low.startswith("function "):
            end = _find_end(lines, i, len(lines))
            name, params = _parse_function_header(line.strip(), line_no)
            rt.functions[name] = {
                "params": params,
                "body_start": i + 1,
                "body_end": end,
                "line_no": line_no,
            }
            i = end + 1
        elif low.startswith("class "):
            end = _find_end(lines, i, len(lines))
            name, parent = _parse_class_header(line.strip(), line_no)
            methods = _parse_class(lines, i, end)
            rt.classes[name] = {"methods": methods, "parent": parent}
            i = end + 1
        else:
            i += 1


def run_script(code, inputs=None, script_path=None, enabled_modules=None, input_callback=None):
    rt = EFPLRuntime()
    rt.input_callback = input_callback
    inputs = inputs or {}
    for module_name in enabled_modules or []:
        rt.use_module(module_name)
    current_dir = Path(script_path).resolve().parent if script_path else None
    try:
        code = _expand_imports(code, current_dir)
        lines = _strip_block_comments(code)
        _register_functions(lines, rt)
    except (EFPLRuntimeError, EFPLSyntaxError) as exc:
        rt.log(str(exc))
        return rt.logs
    call_depth = {"value": 0}

    def run_function(name, args, line_no=None):
        info = rt.functions[name]
        params = info["params"]
        if len(args) != len(params):
            raise EFPLRuntimeError(
                f"Function '{name}' expects {len(params)} argument(s), got {len(args)}",
                line_no,
            )
        if call_depth["value"] >= MAX_RECURSION:
            raise EFPLRuntimeError("Maximum recursion depth reached", line_no)

        call_depth["value"] += 1
        rt.push_scope(dict(zip(params, args)))
        try:
            try:
                execute_range(info["body_start"], info["body_end"])
            except _ReturnSignal as signal:
                return signal.value
            return None
        finally:
            rt.pop_scope()
            call_depth["value"] -= 1

    def run_method(instance, name, args, line_no=None):
        curr = instance.efpl_class
        info = None
        while curr:
            if name in curr.methods:
                info = curr.methods[name]
                break
            curr = getattr(curr, 'parent', None)
            
        if not info:
            raise EFPLRuntimeError(f"Method '{name}' not found", line_no)
            
        params = info["params"]
        if call_depth["value"] >= MAX_RECURSION:
            raise EFPLRuntimeError("Maximum recursion depth reached", line_no)

        call_depth["value"] += 1
        scope = dict(zip(params, args))
        scope["self"] = instance
        rt.push_scope(scope)
        try:
            try:
                execute_range(info["body_start"], info["body_end"])
            except _ReturnSignal as signal:
                return signal.value
            return None
        finally:
            rt.pop_scope()
            call_depth["value"] -= 1

    rt.method_runner = run_method

    def execute_range(start, end):
        i = start
        while i < end:
            line_no, raw = lines[i]
            line = raw.strip()
            low = line.lower()

            if not line or line.startswith("#"):
                i += 1
                continue

            if low.startswith("function ") or low.startswith("class "):
                i = _find_end(lines, i, end) + 1
                continue

            if low.startswith("import "):
                i += 1
                continue

            if low.startswith("use "):
                module_name = line[4:].strip()
                if not module_name:
                    raise EFPLSyntaxError("Expected module name after use", line_no)
                rt.use_module(module_name, line_no)
                i += 1
                continue

            if low.startswith("if "):
                block_end = _find_end(lines, i, end)
                for cond, branch_start, branch_end in _split_if_branches(lines, i, block_end):
                    if cond is None or bool(rt.eval_expr(cond, line_no)):
                        execute_range(branch_start, branch_end)
                        break
                i = block_end + 1
                continue

            if low.startswith("while "):
                block_end = _find_end(lines, i, end)
                cond = line[6:].strip()
                loop_count = 0
                while bool(rt.eval_expr(cond, line_no)):
                    loop_count += 1
                    if loop_count > MAX_LOOP:
                        raise EFPLRuntimeError("Loop limit exceeded", line_no)
                    try:
                        execute_range(i + 1, block_end)
                    except _ContinueSignal:
                        continue
                    except _BreakSignal:
                        break
                i = block_end + 1
                continue

            if low.startswith("for "):
                block_end = _find_end(lines, i, end)
                if " in " in low:
                    match = re.match(r"^for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+)$", line, re.IGNORECASE)
                    if not match:
                        raise EFPLSyntaxError("Expected: for item in array", line_no)
                    var, arr_expr = match.groups()
                    arr = rt.eval_expr(arr_expr, line_no)
                    if not isinstance(arr, list):
                        raise EFPLRuntimeError(f"'{arr_expr}' is not an array", line_no)
                    
                    loop_count = 0
                    for item in arr:
                        loop_count += 1
                        if loop_count > MAX_LOOP:
                            raise EFPLRuntimeError("Loop limit exceeded", line_no)
                        rt.set_var(var, item)
                        try:
                            execute_range(i + 1, block_end)
                        except _ContinueSignal:
                            pass
                        except _BreakSignal:
                            break
                else:
                    var, current, stop, step = _parse_for(line, line_no, rt)
                    loop_count = 0
                    while (step > 0 and current <= stop) or (step < 0 and current >= stop):
                        loop_count += 1
                        if loop_count > MAX_LOOP:
                            raise EFPLRuntimeError("Loop limit exceeded", line_no)
                        rt.set_var(var, current)
                        try:
                            execute_range(i + 1, block_end)
                        except _ContinueSignal:
                            pass
                        except _BreakSignal:
                            break
                        current += step
                i = block_end + 1
                continue

            if low == "do":
                while_index = _find_do_while(lines, i, end)
                cond_line_no, cond_line = lines[while_index]
                cond = cond_line.strip()[6:].strip()
                loop_count = 0
                while True:
                    loop_count += 1
                    if loop_count > MAX_LOOP:
                        raise EFPLRuntimeError("Loop limit exceeded", line_no)
                    try:
                        execute_range(i + 1, while_index)
                    except _ContinueSignal:
                        pass
                    except _BreakSignal:
                        break
                    if not bool(rt.eval_expr(cond, cond_line_no)):
                        break
                i = while_index + 1
                continue

            if low.startswith("switch "):
                block_end = _find_end(lines, i, end)
                value = rt.eval_expr(line[7:].strip(), line_no)
                selected = None
                default = None
                for case_expr, case_start, case_end in _split_cases(lines, i, block_end):
                    if case_expr is None:
                        default = (case_start, case_end)
                    elif rt.eval_expr(case_expr, line_no) == value:
                        selected = (case_start, case_end)
                        break
                if selected is None:
                    selected = default
                if selected is not None:
                    try:
                        execute_range(selected[0], selected[1])
                    except _BreakSignal:
                        pass
                i = block_end + 1
                continue

            if low == "try":
                block_end = _find_end(lines, i, end)
                try_start, try_end, catch_var, catch_start, catch_end = _split_try_catch(lines, i, block_end)
                try:
                    execute_range(try_start, try_end)
                except Exception as e:
                    if catch_start is not None:
                        if catch_var:
                            error_msg = getattr(e, 'message', str(e))
                            rt.set_var(catch_var, error_msg)
                        execute_range(catch_start, catch_end)
                    else:
                        raise e
                i = block_end + 1
                continue

            if low in ("else", "end") or low.startswith("else if ") or low.startswith("case ") or low == "default" or low.startswith("catch "):
                raise EFPLSyntaxError(f"Unexpected '{line}'", line_no)

            if low == "break":
                raise _BreakSignal()

            if low == "continue":
                raise _ContinueSignal()

            if low.startswith("return"):
                expr = line[6:].strip()
                value = rt.eval_expr(expr, line_no) if expr else None
                raise _ReturnSignal(value)

            if low.startswith("call "):
                expr = line[5:].strip()
                rt.eval_expr(expr, line_no)
                i += 1
                continue

            # ── data module multi-word statements ────────────────────────
            if low.startswith("load ") and " as " in low:
                m = re.match(r'^load\s+"([^"]+)"\s+as\s+([A-Za-z_][A-Za-z0-9_]*)$', line, re.IGNORECASE)
                if m:
                    rt._require_module("data", line_no)
                    fname, var = m.group(1), m.group(2)
                    result = rt._data_builtin("load", [fname], line_no)
                    rt.set_var(var, result)
                    i += 1
                    continue

            if low.startswith("sort ") and " by " in low:
                m = re.match(r'^sort\s+([A-Za-z_][A-Za-z0-9_]*)\s+by\s+"([^"]+)"(\s+desc)?$', line, re.IGNORECASE)
                if m:
                    rt._require_module("data", line_no)
                    var, col, desc = m.group(1), m.group(2), m.group(3)
                    df = rt.get_var(var, line_no)
                    asc = desc is None
                    rt.set_var(var, rt._data_builtin("sort", [df, col, asc], line_no))
                    i += 1
                    continue

            if low.startswith("remove null from "):
                m = re.match(r'^remove\s+null\s+from\s+([A-Za-z_][A-Za-z0-9_]*)$', line, re.IGNORECASE)
                if m:
                    rt._require_module("data", line_no)
                    var = m.group(1)
                    df = rt.get_var(var, line_no)
                    rt.set_var(var, rt._data_builtin("remove_null", [df], line_no))
                    i += 1
                    continue

            if low.startswith("fill null in ") and " with " in low:
                m = re.match(r'^fill\s+null\s+in\s+([A-Za-z_][A-Za-z0-9_]*)\s+with\s+(.+)$', line, re.IGNORECASE)
                if m:
                    rt._require_module("data", line_no)
                    var, val_expr = m.group(1), m.group(2)
                    df = rt.get_var(var, line_no)
                    val = rt.eval_expr(val_expr, line_no)
                    rt.set_var(var, rt._data_builtin("fill_null", [df, val], line_no))
                    i += 1
                    continue

            if low.startswith("filter ") and " where " in low and " as " in low:
                m = re.match(r'^filter\s+([A-Za-z_][A-Za-z0-9_]*)\s+where\s+"([^"]+)"\s*(==|!=|>=|<=|>|<)\s*(.+?)\s+as\s+([A-Za-z_][A-Za-z0-9_]*)$', line, re.IGNORECASE)
                if m:
                    rt._require_module("data", line_no)
                    src, col, op, val_expr, out = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
                    df = rt.get_var(src, line_no)
                    val = rt.eval_expr(val_expr, line_no)
                    rt.set_var(out, rt._data_builtin("filter", [df, col, op, val], line_no))
                    i += 1
                    continue

            if low.startswith("select ") and " from " in low and " as " in low:
                m = re.match(r'^select\s+(.+?)\s+from\s+([A-Za-z_][A-Za-z0-9_]*)\s+as\s+([A-Za-z_][A-Za-z0-9_]*)$', line, re.IGNORECASE)
                if m:
                    rt._require_module("data", line_no)
                    cols_str, src, out = m.group(1), m.group(2), m.group(3)
                    cols = [c.strip().strip('"') for c in re.split(r'\s+and\s+', cols_str, flags=re.IGNORECASE)]
                    df = rt.get_var(src, line_no)
                    rt.set_var(out, rt._data_builtin("select", [df] + cols, line_no))
                    i += 1
                    continue

            if low.startswith("rename ") and " to " in low and " in " in low:
                m = re.match(r'^rename\s+"([^"]+)"\s+to\s+"([^"]+)"\s+in\s+([A-Za-z_][A-Za-z0-9_]*)$', line, re.IGNORECASE)
                if m:
                    rt._require_module("data", line_no)
                    old, new, var = m.group(1), m.group(2), m.group(3)
                    df = rt.get_var(var, line_no)
                    rt.set_var(var, rt._data_builtin("rename", [df, old, new], line_no))
                    i += 1
                    continue

            if low.startswith("export ") and " as " in low:
                m = re.match(r'^export\s+([A-Za-z_][A-Za-z0-9_]*)\s+as\s+"([^"]+)"$', line, re.IGNORECASE)
                if m:
                    rt._require_module("data", line_no)
                    var, fname = m.group(1), m.group(2)
                    df = rt.get_var(var, line_no)
                    result = rt._data_builtin("export", [df, fname], line_no)
                    rt.log(result)
                    i += 1
                    continue

            if low.startswith("render ") and " from " in low:
                # render "col1" [and "col2"] as <type> from <df>
                m = re.match(
                    r'^render\s+"([^"]+)"(?:\s+and\s+"([^"]+)")?\s+as\s+(\w+)\s+from\s+([A-Za-z_][A-Za-z0-9_]*)$',
                    line, re.IGNORECASE
                )
                if not m:
                    # render "col1" from <df>  (default: table)
                    m = re.match(
                        r'^render\s+"([^"]+)"\s+from\s+([A-Za-z_][A-Za-z0-9_]*)$',
                        line, re.IGNORECASE
                    )
                    if m:
                        rt._require_module("data", line_no)
                        col1, df_var = m.group(1), m.group(2)
                        df = rt.get_var(df_var, line_no)
                        result = rt._data_builtin("render", [df, col1, "table"], line_no)
                        rt.log(result)
                        i += 1
                        continue
                else:
                    rt._require_module("data", line_no)
                    col1, col2, chart, df_var = m.group(1), m.group(2), m.group(3), m.group(4)
                    df = rt.get_var(df_var, line_no)
                    args = [df, col1, col2, chart] if col2 else [df, col1, chart]
                    result = rt._data_builtin("render", args, line_no)
                    rt.log(result)
                    i += 1
                    continue

            # show columns/shape/head/tail/describe of <var>
            if low.startswith("show ") and " of " in low:
                m = re.match(r'^show\s+(columns|shape|head|tail|describe)\s+of\s+([A-Za-z_][A-Za-z0-9_]*)$', line, re.IGNORECASE)
                if m:
                    rt._require_module("data", line_no)
                    op, var = m.group(1).lower(), m.group(2)
                    df = rt.get_var(var, line_no)
                    result = rt._data_builtin(op, [df], line_no)
                    rt.log(result)
                    i += 1
                    continue

            rt.exec_line(line, inputs, line_no)
            i += 1

    rt.function_runner = run_function

    try:
        execute_range(0, len(lines))
    except (EFPLRuntimeError, EFPLSyntaxError) as exc:
        rt.log(str(exc))
    except _BreakSignal:
        rt.log("Runtime Error: break used outside a loop or switch")
    except _ContinueSignal:
        rt.log("Runtime Error: continue used outside a loop")
    except _ReturnSignal:
        rt.log("Runtime Error: return used outside a function")
    except Exception as exc:
        rt.log(f"Runtime Error: {exc}")

    return rt.logs

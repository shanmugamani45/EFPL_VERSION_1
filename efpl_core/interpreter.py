import ast
import datetime
import json
import math
import operator
import os
from pathlib import Path
import random
import re
import subprocess
import urllib.request
import urllib.parse


class EFPLRuntimeError(Exception):
    def __init__(self, message, line_no=None):
        self.message = message
        self.line_no = line_no
        super().__init__(message)

    def __str__(self):
        if self.line_no is None:
            return f"Runtime Error: {self.message}"
        return f"Runtime Error at line {self.line_no}: {self.message}"


class EFPLSyntaxError(Exception):
    def __init__(self, message, line_no=None):
        self.message = message
        self.line_no = line_no
        super().__init__(message)

    def __str__(self):
        if self.line_no is None:
            return f"Syntax Error: {self.message}"
        return f"Syntax Error at line {self.line_no}: {self.message}"


class EFPLStack:
    def __init__(self):
        self.items = []
    def __str__(self):
        return f"Stack({self.items})"


class EFPLQueue:
    def __init__(self):
        self.items = []
    def __str__(self):
        return f"Queue({self.items})"


class EFPLNode:
    def __init__(self, value):
        self.value = value
        self.next = None
    def __str__(self):
        return str(self.value)


class EFPLLinkedList:
    def __init__(self):
        self.head = None
    def __str__(self):
        items = []
        curr = self.head
        while curr:
            items.append(str(curr.value))
            curr = curr.next
        return f"LinkedList([{', '.join(items)}])"


class EFPLClass:
    def __init__(self, name, methods, parent=None):
        self.name = name
        self.methods = methods
        self.parent = parent
    def __str__(self):
        return f"<Class {self.name}>"

class EFPLInstance:
    def __init__(self, efpl_class):
        self.efpl_class = efpl_class
        self.attributes = {}
    def __str__(self):
        return f"<Instance of {self.efpl_class.name}>"

class EFPLRuntime:
    def __init__(self):
        self.global_vars = {}
        self.scopes = [self.global_vars]
        self.modules = {
            "math": False,
            "text": False,
            "array": False,
            "file": False,
            "time": False,
            "random": False,
            "type": False,
            "visual": False,
            "dsa": False,
            "http": False,
            "json": False,
            "os": False,
            "database": False,
            "data": False,
        }
        self.data_root = Path("workspace") / "data"
        self.files = {}
        self.tables = {}
        self.logs = []
        self.classes = {}
        self.functions = {}
        self.function_runner = None
        self.file_root = Path("workspace") / "files"
        self.visual_root = Path("workspace") / "visuals"
        self._visual_ready = False
        self.input_callback = None

    @property
    def vars(self):
        return self.scopes[-1]

    @vars.setter
    def vars(self, value):
        self.scopes[-1] = value

    def push_scope(self, values=None):
        self.scopes.append(dict(values or {}))

    def pop_scope(self):
        if len(self.scopes) == 1:
            raise EFPLRuntimeError("Cannot remove global scope")
        self.scopes.pop()

    def log(self, msg):
        self.logs.append(str(msg))

    def use_module(self, name, line_no=None):
        lname = name.lower().strip()
        if lname not in self.modules:
            raise EFPLRuntimeError(f"Unknown module '{name}'", line_no)
        self.modules[lname] = True

    def get_var(self, name, line_no=None):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise EFPLRuntimeError(f"Undefined variable '{name}'", line_no)

    def set_var(self, name, value):
        self.scopes[-1][name] = value

    def get_value(self, text, line_no=None):
        text = text.strip()

        if not text:
            return ""

        try:
            return self.get_var(text, line_no)
        except EFPLRuntimeError:
            pass

        if text.startswith('f"') and text.endswith('"'):
            content = text[2:-1]
            def replacer(match):
                expr = match.group(1)
                return str(self.eval_expr(expr, line_no))
            try:
                return re.sub(r"\{([^}]+)\}", replacer, content)
            except Exception as e:
                raise EFPLRuntimeError(f"String interpolation failed: {e}", line_no)

        if text.startswith('"') and text.endswith('"'):
            return text[1:-1]

        if text.lower() == "true":
            return True
        if text.lower() == "false":
            return False

        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            return text

    def _builtin(self, name, args, line_no):
        lname = name.lower()

        if lname == "length":
            self._expect_count(name, args, 1, line_no)
            self._require_module("array" if isinstance(args[0], list) else "text", line_no)
            return len(args[0])
        if lname == "upper":
            self._expect_count(name, args, 1, line_no)
            self._require_module("text", line_no)
            return str(args[0]).upper()
        if lname == "lower":
            self._expect_count(name, args, 1, line_no)
            self._require_module("text", line_no)
            return str(args[0]).lower()
        if lname == "contains":
            self._expect_count(name, args, 2, line_no)
            if isinstance(args[0], list):
                self._require_module("array", line_no)
                return args[1] in args[0]
            self._require_module("text", line_no)
            return str(args[1]) in str(args[0])
        if lname == "replace":
            self._expect_count(name, args, 3, line_no)
            self._require_module("text", line_no)
            return str(args[0]).replace(str(args[1]), str(args[2]))
        if lname == "split":
            self._expect_count(name, args, 2, line_no)
            self._require_module("text", line_no)
            return str(args[0]).split(str(args[1]))
        if lname == "trim":
            self._expect_count(name, args, 1, line_no)
            self._require_module("text", line_no)
            return str(args[0]).strip()
        if lname == "starts_with":
            self._expect_count(name, args, 2, line_no)
            self._require_module("text", line_no)
            return str(args[0]).startswith(str(args[1]))
        if lname == "ends_with":
            self._expect_count(name, args, 2, line_no)
            self._require_module("text", line_no)
            return str(args[0]).endswith(str(args[1]))
        if lname == "sort":
            self._expect_count(name, args, 1, line_no)
            self._require_module("array", line_no)
            if not isinstance(args[0], list):
                raise EFPLRuntimeError("sort expects an array", line_no)
            return sorted(args[0])
        if lname == "reverse":
            self._expect_count(name, args, 1, line_no)
            if isinstance(args[0], list):
                self._require_module("array", line_no)
                return list(reversed(args[0]))
            self._require_module("text", line_no)
            return str(args[0])[::-1]
        if lname == "join":
            self._expect_count(name, args, 2, line_no)
            self._require_module("array", line_no)
            if not isinstance(args[0], list):
                raise EFPLRuntimeError("join expects an array as first value", line_no)
            return str(args[1]).join(str(item) for item in args[0])
        if lname == "index":
            self._expect_count(name, args, 2, line_no)
            self._require_module("array", line_no)
            if not isinstance(args[0], list):
                raise EFPLRuntimeError("index expects an array as first value", line_no)
            try:
                return args[0].index(args[1])
            except ValueError:
                return -1
        if lname == "slice":
            self._expect_count(name, args, 3, line_no)
            self._require_module("array", line_no)
            if not isinstance(args[0], list):
                raise EFPLRuntimeError("slice expects an array as first value", line_no)
            start = int(args[1])
            end = int(args[2])
            return args[0][start:end]
        if lname == "sqrt":
            self._expect_count(name, args, 1, line_no)
            self._require_module("math", line_no)
            return math.sqrt(args[0])
        if lname == "round":
            if len(args) not in (1, 2):
                raise EFPLRuntimeError("round expects 1 or 2 argument(s)", line_no)
            self._require_module("math", line_no)
            return round(args[0], int(args[1]) if len(args) == 2 else 0)
        if lname == "pi":
            self._expect_count(name, args, 0, line_no)
            self._require_module("math", line_no)
            return math.pi
        if lname == "sin":
            self._expect_count(name, args, 1, line_no)
            self._require_module("math", line_no)
            return math.sin(args[0])
        if lname == "cos":
            self._expect_count(name, args, 1, line_no)
            self._require_module("math", line_no)
            return math.cos(args[0])
        if lname == "tan":
            self._expect_count(name, args, 1, line_no)
            self._require_module("math", line_no)
            return math.tan(args[0])
        if lname == "floor":
            self._expect_count(name, args, 1, line_no)
            self._require_module("math", line_no)
            return math.floor(args[0])
        if lname == "ceil":
            self._expect_count(name, args, 1, line_no)
            self._require_module("math", line_no)
            return math.ceil(args[0])
        if lname == "pow":
            self._expect_count(name, args, 2, line_no)
            self._require_module("math", line_no)
            return math.pow(args[0], args[1])
        if lname == "random":
            self._expect_count(name, args, 2, line_no)
            self._require_module("random", line_no)
            return random.randint(int(args[0]), int(args[1]))
        if lname == "abs":
            self._expect_count(name, args, 1, line_no)
            self._require_module("math", line_no)
            return abs(args[0])
        if lname == "min":
            if not args:
                raise EFPLRuntimeError("min expects at least 1 argument", line_no)
            self._require_module("math", line_no)
            return min(args)
        if lname == "max":
            if not args:
                raise EFPLRuntimeError("max expects at least 1 argument", line_no)
            self._require_module("math", line_no)
            return max(args)
        if lname == "now":
            self._expect_count(name, args, 0, line_no)
            self._require_module("time", line_no)
            return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if lname == "today":
            self._expect_count(name, args, 0, line_no)
            self._require_module("time", line_no)
            return datetime.date.today().isoformat()
        if lname == "to_number":
            self._expect_count(name, args, 1, line_no)
            self._require_module("type", line_no)
            return self._convert_to_number(args[0], line_no)
        if lname == "to_text":
            self._expect_count(name, args, 1, line_no)
            self._require_module("type", line_no)
            return str(args[0])
        if lname == "to_boolean":
            self._expect_count(name, args, 1, line_no)
            self._require_module("type", line_no)
            return self._convert_to_boolean(args[0])
        if lname == "type_of":
            self._expect_count(name, args, 1, line_no)
            self._require_module("type", line_no)
            return self._type_name(args[0])
        if lname == "is_number":
            self._expect_count(name, args, 1, line_no)
            self._require_module("type", line_no)
            return isinstance(args[0], (int, float)) and not isinstance(args[0], bool)
        if lname == "is_text":
            self._expect_count(name, args, 1, line_no)
            self._require_module("type", line_no)
            return isinstance(args[0], str)
        if lname == "is_array":
            self._expect_count(name, args, 1, line_no)
            self._require_module("type", line_no)
            return isinstance(args[0], list)
        if lname == "is_dictionary":
            self._expect_count(name, args, 1, line_no)
            self._require_module("type", line_no)
            return isinstance(args[0], dict)

        return None

    def _expect_count(self, name, args, count, line_no):
        if len(args) != count:
            raise EFPLRuntimeError(f"{name} expects {count} argument(s)", line_no)

    def _require_module(self, name, line_no=None):
        if not self.modules.get(name, False):
            raise EFPLRuntimeError(f"Library '{name}' is OFF. Turn it ON or write: use {name}", line_no)

    def _resolve_class(self, name, line_no=None):
        if name not in self.classes:
            raise EFPLRuntimeError(f"Unknown class '{name}'", line_no)
        cls_def = self.classes[name]
        if isinstance(cls_def, dict) and "methods" in cls_def:
            methods = cls_def["methods"]
            parent_name = cls_def.get("parent")
        else:
            methods = cls_def
            parent_name = None
        
        parent_class = self._resolve_class(parent_name, line_no) if parent_name else None
        return EFPLClass(name, methods, parent_class)

    def _has_method(self, efpl_class, method_name):
        curr = efpl_class
        while curr:
            if method_name in curr.methods:
                return True
            curr = curr.parent
        return False

    def _get_method(self, efpl_class, method_name):
        curr = efpl_class
        while curr:
            if method_name in curr.methods:
                return curr.methods[method_name]
            curr = curr.parent
        return None

    def instantiate_class(self, class_name, args, line_no=None):
        efpl_class = self._resolve_class(class_name, line_no)
        instance = EFPLInstance(efpl_class)
        
        if self._has_method(efpl_class, "init"):
            self.call_instance_method(instance, "init", args, line_no)
        elif args:
            raise EFPLRuntimeError(f"Class '{class_name}' takes no arguments without an init function", line_no)
            
        return instance

    def call_instance_method(self, instance, method_name, args, line_no=None):
        method_info = self._get_method(instance.efpl_class, method_name)
        if not method_info:
            raise EFPLRuntimeError(f"Class '{instance.efpl_class.name}' has no method '{method_name}'", line_no)
            
        if self.function_runner is None:
            raise EFPLRuntimeError("Function runner is not configured", line_no)
            
        return self._run_method(instance, method_name, args, line_no)

    def _run_method(self, instance, method_name, args, line_no=None):
        method_info = self._get_method(instance.efpl_class, method_name)
        params = method_info["params"]
        if len(args) != len(params):
            raise EFPLRuntimeError(
                f"Method '{method_name}' expects {len(params)} argument(s), got {len(args)}",
                line_no,
            )
            
        # Instead of calling function_runner, we execute it directly, similar to run_function in executor.py
        # BUT executor.py handles the execution stack!
        # This means we MUST pass method calls back to executor.py
        if not hasattr(self, 'method_runner') or self.method_runner is None:
            raise EFPLRuntimeError("Method runner is not configured", line_no)
        return self.method_runner(instance, method_name, args, line_no)

    def call_function(self, name, args, line_no=None):
        builtin = self._builtin(name, args, line_no)
        if builtin is not None:
            return builtin

        if name not in self.functions:
            raise EFPLRuntimeError(f"Unknown function '{name}'", line_no)
        if self.function_runner is None:
            raise EFPLRuntimeError("Function runner is not configured", line_no)
        return self.function_runner(name, args, line_no)

    def call_module_function(self, module, name, args, line_no=None):
        module = module.lower()
        if module not in self.modules:
            raise EFPLRuntimeError(f"Unknown module '{module}'", line_no)
        if not self.modules[module]:
            raise EFPLRuntimeError(f"Use module before calling it: use {module}", line_no)

        mapping = {
            "math": {"sqrt", "round", "abs", "min", "max", "pi", "sin", "cos", "tan", "floor", "ceil", "pow"},
            "random": {"random"},
            "time": {"now", "today"},
            "text": {"length", "upper", "lower", "contains", "replace", "split", "trim", "starts_with", "ends_with"},
            "array": {"length", "sort", "reverse", "join", "contains", "index", "slice"},
            "file": set(),
            "type": {"to_number", "to_text", "to_boolean", "type_of", "is_number", "is_text", "is_array", "is_dictionary"},
            "visual": {
                "figure", "line", "bar", "scatter", "pie", "hist", "title",
                "xlabel", "ylabel", "grid", "legend", "save", "render", "show", "clear"
            },
            "dsa": {
                "stack", "push", "pop", "peek",
                "queue", "enqueue", "dequeue", "front", "is_empty",
                "linkedlist", "append", "prepend", "delete", "to_array"
            },
            "http": {"get", "post"},
            "json": {"parse", "stringify"},
            "os": {"env", "run"},
            "database": {"connect", "execute", "query", "close"},
            "data": {"load", "columns", "shape", "head", "tail", "describe",
                     "sort", "remove_null", "fill_null", "filter", "select",
                     "rename", "export", "render"},
        }
        allowed = mapping.get(module, set())
        if name.lower() not in allowed:
            raise EFPLRuntimeError(f"Module '{module}' has no function '{name}'", line_no)
        if module == "visual":
            return self._visual_builtin(name, args, line_no)
        if module == "dsa":
            return self._dsa_builtin(name, args, line_no)
        if module == "http":
            return self._http_builtin(name, args, line_no)
        if module == "json":
            return self._json_builtin(name, args, line_no)
        if module == "os":
            return self._os_builtin(name, args, line_no)
        if module == "database":
            return self._database_builtin(name, args, line_no)
        if module == "data":
            return self._data_builtin(name, args, line_no)
        return self._builtin(name, args, line_no)

    def _visual_builtin(self, name, args, line_no=None):
        plt = self._visual_pyplot(line_no)
        lname = name.lower()

        if lname == "figure":
            if len(args) > 2:
                raise EFPLRuntimeError("visual.figure expects width and height or no arguments", line_no)
            if args:
                width = args[0]
                height = args[1] if len(args) == 2 else args[0]
                plt.figure(figsize=(width, height))
            else:
                plt.figure()
            return "Visual figure created"

        if lname == "line":
            self._expect_count("visual.line", args, 2, line_no)
            plt.plot(args[0], args[1])
            return "Line plot added"

        if lname == "bar":
            self._expect_count("visual.bar", args, 2, line_no)
            plt.bar(args[0], args[1])
            return "Bar chart added"

        if lname == "scatter":
            self._expect_count("visual.scatter", args, 2, line_no)
            plt.scatter(args[0], args[1])
            return "Scatter plot added"

        if lname == "pie":
            if len(args) not in (1, 2):
                raise EFPLRuntimeError("visual.pie expects values and optional labels", line_no)
            if len(args) == 2:
                plt.pie(args[0], labels=args[1], autopct="%1.1f%%")
            else:
                plt.pie(args[0], autopct="%1.1f%%")
            return "Pie chart added"

        if lname == "hist":
            self._expect_count("visual.hist", args, 1, line_no)
            plt.hist(args[0])
            return "Histogram added"

        if lname == "title":
            self._expect_count("visual.title", args, 1, line_no)
            plt.title(str(args[0]))
            return "Title set"

        if lname == "xlabel":
            self._expect_count("visual.xlabel", args, 1, line_no)
            plt.xlabel(str(args[0]))
            return "X label set"

        if lname == "ylabel":
            self._expect_count("visual.ylabel", args, 1, line_no)
            plt.ylabel(str(args[0]))
            return "Y label set"

        if lname == "grid":
            if len(args) > 1:
                raise EFPLRuntimeError("visual.grid expects true/false or no arguments", line_no)
            plt.grid(bool(args[0]) if args else True)
            return "Grid updated"

        if lname == "legend":
            if len(args) > 1:
                raise EFPLRuntimeError("visual.legend expects labels array or no arguments", line_no)
            if args:
                plt.legend(args[0])
            else:
                plt.legend()
            return "Legend updated"

        if lname == "save":
            self._expect_count("visual.save", args, 1, line_no)
            path = self._safe_visual_path(args[0], line_no)
            plt.tight_layout()
            plt.savefig(path)
            return f"Visual saved: {path}"

        if lname == "render":
            if len(args) > 1:
                raise EFPLRuntimeError("visual.render expects an optional name", line_no)
            file_name = args[0] if args else "_preview.png"
            path = self._safe_visual_path(file_name, line_no)
            plt.tight_layout()
            plt.savefig(path)
            return f"VISUAL_RENDER:{path}"

        if lname == "show":
            if args:
                raise EFPLRuntimeError("visual.show expects no arguments", line_no)
            path = self._safe_visual_path("_preview.png", line_no)
            plt.tight_layout()
            plt.savefig(path)
            return f"VISUAL_RENDER:{path}"

        if lname == "clear":
            if args:
                raise EFPLRuntimeError("visual.clear expects no arguments", line_no)
            plt.close("all")
            self._visual_ready = False
            return "Visual cleared"

        raise EFPLRuntimeError(f"Unknown visual function '{name}'", line_no)

    def _visual_pyplot(self, line_no=None):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as exc:
            raise EFPLRuntimeError(
                f"Visual library needs matplotlib installed: {exc}",
                line_no,
            )
        if not self._visual_ready:
            plt.figure()
            self._visual_ready = True
        return plt

    def _safe_visual_path(self, file_name, line_no):
        root = self.visual_root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        path = (root / str(file_name)).resolve()
        if root != path and root not in path.parents:
            raise EFPLRuntimeError("Visual path must stay inside workspace/visuals", line_no)
        if not path.suffix:
            path = path.with_suffix(".png")
        return path

    def _dsa_builtin(self, name, args, line_no=None):
        lname = name.lower()

        # Stack
        if lname == "stack":
            self._expect_count("dsa.stack", args, 0, line_no)
            return EFPLStack()
        if lname == "push":
            self._expect_count("dsa.push", args, 2, line_no)
            if not isinstance(args[0], EFPLStack):
                raise EFPLRuntimeError("dsa.push expects a Stack", line_no)
            args[0].items.append(args[1])
            return args[1]
        if lname == "pop":
            self._expect_count("dsa.pop", args, 1, line_no)
            if not isinstance(args[0], EFPLStack):
                raise EFPLRuntimeError("dsa.pop expects a Stack", line_no)
            if not args[0].items:
                raise EFPLRuntimeError("Cannot pop from an empty Stack", line_no)
            return args[0].items.pop()
        if lname == "peek":
            self._expect_count("dsa.peek", args, 1, line_no)
            if not isinstance(args[0], EFPLStack):
                raise EFPLRuntimeError("dsa.peek expects a Stack", line_no)
            if not args[0].items:
                raise EFPLRuntimeError("Cannot peek an empty Stack", line_no)
            return args[0].items[-1]

        # Queue
        if lname == "queue":
            self._expect_count("dsa.queue", args, 0, line_no)
            return EFPLQueue()
        if lname == "enqueue":
            self._expect_count("dsa.enqueue", args, 2, line_no)
            if not isinstance(args[0], EFPLQueue):
                raise EFPLRuntimeError("dsa.enqueue expects a Queue", line_no)
            args[0].items.append(args[1])
            return args[1]
        if lname == "dequeue":
            self._expect_count("dsa.dequeue", args, 1, line_no)
            if not isinstance(args[0], EFPLQueue):
                raise EFPLRuntimeError("dsa.dequeue expects a Queue", line_no)
            if not args[0].items:
                raise EFPLRuntimeError("Cannot dequeue from an empty Queue", line_no)
            return args[0].items.pop(0)
        if lname == "front":
            self._expect_count("dsa.front", args, 1, line_no)
            if not isinstance(args[0], EFPLQueue):
                raise EFPLRuntimeError("dsa.front expects a Queue", line_no)
            if not args[0].items:
                raise EFPLRuntimeError("Queue is empty", line_no)
            return args[0].items[0]

        # LinkedList
        if lname == "linkedlist":
            self._expect_count("dsa.linkedlist", args, 0, line_no)
            return EFPLLinkedList()
        if lname == "append":
            self._expect_count("dsa.append", args, 2, line_no)
            if not isinstance(args[0], EFPLLinkedList):
                raise EFPLRuntimeError("dsa.append expects a LinkedList", line_no)
            new_node = EFPLNode(args[1])
            if not args[0].head:
                args[0].head = new_node
            else:
                curr = args[0].head
                while curr.next:
                    curr = curr.next
                curr.next = new_node
            return args[1]
        if lname == "prepend":
            self._expect_count("dsa.prepend", args, 2, line_no)
            if not isinstance(args[0], EFPLLinkedList):
                raise EFPLRuntimeError("dsa.prepend expects a LinkedList", line_no)
            new_node = EFPLNode(args[1])
            new_node.next = args[0].head
            args[0].head = new_node
            return args[1]
        if lname == "delete":
            self._expect_count("dsa.delete", args, 2, line_no)
            if not isinstance(args[0], EFPLLinkedList):
                raise EFPLRuntimeError("dsa.delete expects a LinkedList", line_no)
            curr = args[0].head
            prev = None
            while curr:
                if curr.value == args[1]:
                    if prev:
                        prev.next = curr.next
                    else:
                        args[0].head = curr.next
                    return True
                prev = curr
                curr = curr.next
            return False
        if lname == "to_array":
            self._expect_count("dsa.to_array", args, 1, line_no)
            if not isinstance(args[0], EFPLLinkedList):
                raise EFPLRuntimeError("dsa.to_array expects a LinkedList", line_no)
            arr = []
            curr = args[0].head
            while curr:
                arr.append(curr.value)
                curr = curr.next
            return arr

        # Shared
        if lname == "is_empty":
            self._expect_count("dsa.is_empty", args, 1, line_no)
            if isinstance(args[0], (EFPLStack, EFPLQueue)):
                return len(args[0].items) == 0
            if isinstance(args[0], EFPLLinkedList):
                return args[0].head is None
            raise EFPLRuntimeError("dsa.is_empty expects a Stack, Queue, or LinkedList", line_no)

        raise EFPLRuntimeError(f"Unknown dsa function '{name}'", line_no)

    def _http_builtin(self, name, args, line_no=None):
        lname = name.lower()
        if lname == "get":
            self._expect_count("http.get", args, 1, line_no)
            try:
                req = urllib.request.Request(str(args[0]), headers={'User-Agent': 'EFPL/1.0'})
                with urllib.request.urlopen(req) as response:
                    return response.read().decode('utf-8')
            except Exception as e:
                raise EFPLRuntimeError(f"HTTP GET failed: {e}", line_no)
        if lname == "post":
            self._expect_count("http.post", args, 2, line_no)
            if not isinstance(args[1], dict):
                raise EFPLRuntimeError("http.post expects a dictionary for data", line_no)
            try:
                data = json.dumps(args[1]).encode('utf-8')
                req = urllib.request.Request(str(args[0]), data=data, headers={'Content-Type': 'application/json', 'User-Agent': 'EFPL/1.0'}, method='POST')
                with urllib.request.urlopen(req) as response:
                    return response.read().decode('utf-8')
            except Exception as e:
                raise EFPLRuntimeError(f"HTTP POST failed: {e}", line_no)
        raise EFPLRuntimeError(f"Unknown http function '{name}'", line_no)

    def _json_builtin(self, name, args, line_no=None):
        lname = name.lower()
        if lname == "parse":
            self._expect_count("json.parse", args, 1, line_no)
            try:
                return json.loads(str(args[0]))
            except Exception as e:
                raise EFPLRuntimeError(f"JSON parsing failed: {e}", line_no)
        if lname == "stringify":
            self._expect_count("json.stringify", args, 1, line_no)
            if not isinstance(args[0], (dict, list)):
                raise EFPLRuntimeError("json.stringify expects a dictionary or array", line_no)
            try:
                return json.dumps(args[0])
            except Exception as e:
                raise EFPLRuntimeError(f"JSON stringify failed: {e}", line_no)
        raise EFPLRuntimeError(f"Unknown json function '{name}'", line_no)

    def _os_builtin(self, name, args, line_no=None):
        lname = name.lower()
        if lname == "env":
            self._expect_count("os.env", args, 1, line_no)
            return os.environ.get(str(args[0]), "")
        if lname == "run":
            self._expect_count("os.run", args, 1, line_no)
            try:
                result = subprocess.run(str(args[0]), shell=True, capture_output=True, text=True)
                return result.stdout if result.returncode == 0 else result.stderr
            except Exception as e:
                raise EFPLRuntimeError(f"OS command failed: {e}", line_no)
        raise EFPLRuntimeError(f"Unknown os function '{name}'", line_no)

    def _data_builtin(self, name, args, line_no=None):
        """Data module: pandas-powered operations on uploaded files."""
        try:
            import pandas as pd
            import matplotlib
            matplotlib.use("TkAgg")
            import matplotlib.pyplot as plt
        except ImportError as e:
            raise EFPLRuntimeError(f"Data module requires pandas and matplotlib: {e}", line_no)

        lname = name.lower()

        # ── load ──────────────────────────────────────────────────────
        if lname == "load":
            # args: [filename]  →  returns DataFrame
            self._expect_count("data.load", args, 1, line_no)
            fname = str(args[0])
            path = (self.data_root / fname).resolve()
            if not path.exists():
                raise EFPLRuntimeError(
                    f"Data file '{fname}' not found in workspace/data/. "
                    f"Use the Data panel to upload it first.", line_no
                )
            ext = path.suffix.lower()
            try:
                if ext == ".csv":
                    return pd.read_csv(path)
                elif ext in (".xlsx", ".xls"):
                    return pd.read_excel(path)
                elif ext == ".json":
                    return pd.read_json(path)
                elif ext == ".tsv":
                    return pd.read_csv(path, sep="\t")
                else:
                    raise EFPLRuntimeError(f"Unsupported file type: {ext}", line_no)
            except Exception as e:
                raise EFPLRuntimeError(f"Could not load '{fname}': {e}", line_no)

        # ── columns ───────────────────────────────────────────────────
        if lname == "columns":
            self._expect_count("data.columns", args, 1, line_no)
            df = args[0]
            if not hasattr(df, 'columns'):
                raise EFPLRuntimeError("data.columns expects a loaded dataframe", line_no)
            return list(df.columns)

        # ── shape ─────────────────────────────────────────────────────
        if lname == "shape":
            self._expect_count("data.shape", args, 1, line_no)
            df = args[0]
            if not hasattr(df, 'shape'):
                raise EFPLRuntimeError("data.shape expects a loaded dataframe", line_no)
            r, c = df.shape
            return f"{r} rows × {c} columns"

        # ── head / tail ───────────────────────────────────────────────
        if lname in ("head", "tail"):
            n = 5
            if len(args) == 2:
                n = int(args[1])
            elif len(args) != 1:
                raise EFPLRuntimeError(f"data.{lname} expects 1 or 2 argument(s)", line_no)
            df = args[0]
            result = df.head(n) if lname == "head" else df.tail(n)
            return result.to_string(index=False)

        # ── describe ─────────────────────────────────────────────────
        if lname == "describe":
            self._expect_count("data.describe", args, 1, line_no)
            df = args[0]
            return df.describe().to_string()

        # ── sort ──────────────────────────────────────────────────────
        if lname == "sort":
            # args: [df, col_name, ascending=True]
            if len(args) not in (2, 3):
                raise EFPLRuntimeError("data.sort expects df, column [, ascending]", line_no)
            df, col = args[0], str(args[1])
            asc = bool(args[2]) if len(args) == 3 else True
            if col not in df.columns:
                raise EFPLRuntimeError(f"Column '{col}' not found", line_no)
            return df.sort_values(by=col, ascending=asc).reset_index(drop=True)

        # ── remove_null ───────────────────────────────────────────────
        if lname == "remove_null":
            self._expect_count("data.remove_null", args, 1, line_no)
            return args[0].dropna().reset_index(drop=True)

        # ── fill_null ─────────────────────────────────────────────────
        if lname == "fill_null":
            self._expect_count("data.fill_null", args, 2, line_no)
            return args[0].fillna(args[1])

        # ── filter ───────────────────────────────────────────────────
        if lname == "filter":
            # args: [df, col, op, value]
            self._expect_count("data.filter", args, 4, line_no)
            df, col, op, val = args[0], str(args[1]), str(args[2]), args[3]
            if col not in df.columns:
                raise EFPLRuntimeError(f"Column '{col}' not found", line_no)
            ops = {">":">","<":"<",">=":">=","<=":"<=","==":"==","!=":"!="}
            if op not in ops:
                raise EFPLRuntimeError(f"Unknown filter operator '{op}'", line_no)
            return df.query(f"`{col}` {op} @val", local_dict={"val": val}).reset_index(drop=True)

        # ── select ────────────────────────────────────────────────────
        if lname == "select":
            # args: [df, col1, col2, ...]
            if len(args) < 2:
                raise EFPLRuntimeError("data.select expects df and at least one column", line_no)
            df = args[0]
            cols = [str(c) for c in args[1:]]
            missing = [c for c in cols if c not in df.columns]
            if missing:
                raise EFPLRuntimeError(f"Columns not found: {missing}", line_no)
            return df[cols].copy()

        # ── rename ────────────────────────────────────────────────────
        if lname == "rename":
            self._expect_count("data.rename", args, 3, line_no)
            df, old_name, new_name = args[0], str(args[1]), str(args[2])
            if old_name not in df.columns:
                raise EFPLRuntimeError(f"Column '{old_name}' not found", line_no)
            return df.rename(columns={old_name: new_name})

        # ── export ────────────────────────────────────────────────────
        if lname == "export":
            self._expect_count("data.export", args, 2, line_no)
            df, fname = args[0], str(args[1])
            out_path = (self.data_root / fname).resolve()
            ext = Path(fname).suffix.lower()
            try:
                if ext == ".csv":
                    df.to_csv(out_path, index=False)
                elif ext in (".xlsx", ".xls"):
                    df.to_excel(out_path, index=False)
                elif ext == ".json":
                    df.to_json(out_path, orient="records")
                else:
                    df.to_csv(out_path, index=False)
                return f"Exported to workspace/data/{fname}"
            except Exception as e:
                raise EFPLRuntimeError(f"Export failed: {e}", line_no)

        # ── render ────────────────────────────────────────────────────
        if lname == "render":
            # args: [df, col1, col2_or_none, chart_type]
            # chart_type: "table", "bar", "line", "scatter", "hist", "pie"
            if len(args) < 3:
                raise EFPLRuntimeError(
                    "data.render expects df, col1, chart_type [, col2]", line_no
                )
            df = args[0]
            col1 = str(args[1])
            # last arg is always chart type
            chart_type = str(args[-1]).lower()
            col2 = str(args[2]) if len(args) == 4 else None

            # Validate columns
            for c in ([col1] + ([col2] if col2 else [])):
                if c not in df.columns:
                    raise EFPLRuntimeError(f"Column '{c}' not found in dataframe", line_no)

            try:
                fig, ax = plt.subplots(figsize=(9, 5))
                fig.patch.set_facecolor("#1e1e2e")
                ax.set_facecolor("#181825")
                ax.tick_params(colors="#cdd6f4")
                ax.xaxis.label.set_color("#cdd6f4")
                ax.yaxis.label.set_color("#cdd6f4")
                ax.title.set_color("#cba6f7")
                for spine in ax.spines.values():
                    spine.set_edgecolor("#313244")

                if chart_type in ("table", "preview"):
                    ax.axis("off")
                    cols_to_show = [col1, col2] if col2 else [col1]
                    subset = df[cols_to_show].head(20)
                    tbl = ax.table(
                        cellText=subset.values,
                        colLabels=subset.columns,
                        cellLoc="center", loc="center"
                    )
                    tbl.auto_set_font_size(False)
                    tbl.set_fontsize(10)
                    ax.set_title(f"Preview: {' & '.join(cols_to_show)}", color="#cba6f7", pad=12)

                elif chart_type == "bar":
                    x_col = col1
                    y_col = col2 if col2 else df.select_dtypes(include="number").columns[0]
                    ax.bar(df[x_col].astype(str), df[y_col], color="#cba6f7", edgecolor="#313244")
                    ax.set_xlabel(x_col); ax.set_ylabel(y_col)
                    ax.set_title(f"{y_col} by {x_col}", color="#cba6f7")
                    plt.xticks(rotation=45, ha="right", color="#cdd6f4")

                elif chart_type == "line":
                    x_col = col1
                    y_col = col2 if col2 else df.select_dtypes(include="number").columns[0]
                    ax.plot(df[x_col], df[y_col], color="#89b4fa", linewidth=2)
                    ax.set_xlabel(x_col); ax.set_ylabel(y_col)
                    ax.set_title(f"{y_col} over {x_col}", color="#cba6f7")

                elif chart_type == "scatter":
                    if not col2:
                        raise EFPLRuntimeError("scatter requires two columns", line_no)
                    ax.scatter(df[col1], df[col2], color="#a6e3a1", alpha=0.7, edgecolors="#313244")
                    ax.set_xlabel(col1); ax.set_ylabel(col2)
                    ax.set_title(f"{col1} vs {col2}", color="#cba6f7")

                elif chart_type == "hist":
                    ax.hist(df[col1], bins=20, color="#fab387", edgecolor="#313244")
                    ax.set_xlabel(col1); ax.set_ylabel("Frequency")
                    ax.set_title(f"Distribution of {col1}", color="#cba6f7")

                elif chart_type == "pie":
                    values = df[col1].value_counts()
                    ax.pie(
                        values.values,
                        labels=values.index.astype(str),
                        autopct="%1.1f%%",
                        colors=["#cba6f7","#89b4fa","#a6e3a1","#fab387","#f38ba8","#f9e2af"]
                    )
                    ax.set_title(f"{col1} Distribution", color="#cba6f7")

                else:
                    raise EFPLRuntimeError(f"Unknown chart type '{chart_type}'", line_no)

                plt.tight_layout()
                plt.show(block=False)
                return f"Chart rendered: {chart_type} of {col1}" + (f" & {col2}" if col2 else "")

            except EFPLRuntimeError:
                raise
            except Exception as e:
                raise EFPLRuntimeError(f"Render failed: {e}", line_no)

        raise EFPLRuntimeError(f"Unknown data function '{name}'", line_no)

    def _database_builtin(self, name, args, line_no=None):
        lname = name.lower()
        if lname == "connect":
            self._expect_count("database.connect", args, 1, line_no)
            try:
                import sqlite3
                db_path = self._safe_file_path(str(args[0]), line_no)
                conn = sqlite3.connect(db_path)
                return {"_db_conn": conn}
            except Exception as e:
                raise EFPLRuntimeError(f"Database connect failed: {e}", line_no)
        if lname == "execute":
            if len(args) not in (2, 3):
                raise EFPLRuntimeError("database.execute expects conn, query, [params]", line_no)
            conn_dict = args[0]
            if not isinstance(conn_dict, dict) or "_db_conn" not in conn_dict:
                raise EFPLRuntimeError("First argument to database.execute must be a database connection", line_no)
            try:
                conn = conn_dict["_db_conn"]
                query = str(args[1])
                params = args[2] if len(args) == 3 else []
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount
            except Exception as e:
                raise EFPLRuntimeError(f"Database execute failed: {e}", line_no)
        if lname == "query":
            if len(args) not in (2, 3):
                raise EFPLRuntimeError("database.query expects conn, query, [params]", line_no)
            conn_dict = args[0]
            if not isinstance(conn_dict, dict) or "_db_conn" not in conn_dict:
                raise EFPLRuntimeError("First argument to database.query must be a database connection", line_no)
            try:
                conn = conn_dict["_db_conn"]
                query = str(args[1])
                params = args[2] if len(args) == 3 else []
                cursor = conn.cursor()
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                results = []
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                return results
            except Exception as e:
                raise EFPLRuntimeError(f"Database query failed: {e}", line_no)
        if lname == "close":
            self._expect_count("database.close", args, 1, line_no)
            conn_dict = args[0]
            if not isinstance(conn_dict, dict) or "_db_conn" not in conn_dict:
                raise EFPLRuntimeError("First argument to database.close must be a database connection", line_no)
            try:
                conn_dict["_db_conn"].close()
                del conn_dict["_db_conn"]
                return True
            except Exception as e:
                raise EFPLRuntimeError(f"Database close failed: {e}", line_no)
        raise EFPLRuntimeError(f"Unknown database function '{name}'", line_no)

    def _convert_to_number(self, value, line_no=None):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        text = str(value).strip()
        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            raise EFPLRuntimeError(f"Cannot convert {value!r} to number", line_no)

    def _convert_to_boolean(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value).strip().lower() in ("true", "yes", "1", "on")

    def _type_name(self, value):
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, str):
            return "text"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "dictionary"
        if isinstance(value, EFPLStack):
            return "stack"
        if isinstance(value, EFPLQueue):
            return "queue"
        if isinstance(value, EFPLLinkedList):
            return "linkedlist"
        if isinstance(value, set):
            return "set"
        if value is None:
            return "nothing"
        return type(value).__name__

    # ---------------- SAFE EXPR EVAL ----------------
    def _safe_eval(self, expr, line_no=None):
        arith_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.FloorDiv: operator.floordiv,
        }
        cmp_ops = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
        }

        def _eval(node):
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Name):
                name = node.id
                if name.lower() == "true":
                    return True
                if name.lower() == "false":
                    return False
                return self.get_var(name, line_no)
            if isinstance(node, ast.Attribute):
                obj = _eval(node.value)
                if isinstance(obj, EFPLInstance):
                    return obj.attributes.get(node.attr)
                raise EFPLRuntimeError(f"Cannot read property '{node.attr}'", line_no)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                return -_eval(node.operand)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                return not _eval(node.operand)
            if isinstance(node, ast.BinOp):
                op_fn = arith_ops.get(type(node.op))
                if op_fn is None:
                    raise EFPLRuntimeError(f"Unsupported operator: {type(node.op).__name__}", line_no)
                try:
                    return op_fn(_eval(node.left), _eval(node.right))
                except ZeroDivisionError:
                    raise EFPLRuntimeError("Cannot divide by zero", line_no)
                except TypeError as exc:
                    raise EFPLRuntimeError(str(exc), line_no)
            if isinstance(node, ast.Compare):
                left = _eval(node.left)
                for op, comp in zip(node.ops, node.comparators):
                    right = _eval(comp)
                    fn = cmp_ops.get(type(op))
                    if fn is None:
                        raise EFPLRuntimeError(f"Unsupported comparison: {type(op).__name__}", line_no)
                    if not fn(left, right):
                        return False
                    left = right
                return True
            if isinstance(node, ast.BoolOp):
                if isinstance(node.op, ast.And):
                    for value in node.values:
                        if not _eval(value):
                            return False
                    return True
                if isinstance(node.op, ast.Or):
                    for value in node.values:
                        if _eval(value):
                            return True
                    return False
            if isinstance(node, ast.Lambda):
                params = [arg.arg for arg in node.args.args]
                expr_str = ast.unparse(node.body)
                def _lambda_func(args_list, call_line_no=line_no):
                    if len(args_list) != len(params):
                        raise EFPLRuntimeError(f"Lambda expects {len(params)} arguments", call_line_no)
                    self.push_scope(dict(zip(params, args_list)))
                    try:
                        return self._safe_eval(expr_str, call_line_no)
                    finally:
                        self.pop_scope()
                return _lambda_func
            if isinstance(node, ast.List):
                return [_eval(item) for item in node.elts]
            if isinstance(node, ast.Dict):
                return {_eval(k): _eval(v) for k, v in zip(node.keys, node.values)}
            if isinstance(node, ast.Set):
                return {_eval(item) for item in node.elts}
            if isinstance(node, ast.Subscript):
                target = _eval(node.value)
                key = _eval(node.slice)
                try:
                    return target[key]
                except IndexError:
                    raise EFPLRuntimeError(f"Array index {key} is out of range", line_no)
                except KeyError:
                    raise EFPLRuntimeError(f"Dictionary key {key!r} was not found", line_no)
                except TypeError:
                    raise EFPLRuntimeError("Invalid index access", line_no)
            if isinstance(node, ast.Call):
                args = [_eval(arg) for arg in node.args]
                if isinstance(node.func, ast.Name):
                    if node.func.id.startswith("__new__"):
                        class_name = node.func.id[7:]
                        return self.instantiate_class(class_name, args, line_no)
                    
                    try:
                        val = self.get_var(node.func.id, line_no)
                        if callable(val):
                            return val(args, line_no)
                    except EFPLRuntimeError:
                        pass
                        
                    return self.call_function(node.func.id, args, line_no)
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id in self.modules:
                        return self.call_module_function(node.func.value.id, node.func.attr, args, line_no)
                    # For imported namespaces (Phase 1 part 3)
                    if isinstance(node.func.value, ast.Name) and hasattr(self, 'namespaces') and node.func.value.id in self.namespaces:
                        return self.call_namespace_function(node.func.value.id, node.func.attr, args, line_no)
                    obj = _eval(node.func.value)
                    if isinstance(obj, EFPLInstance):
                        return self.call_instance_method(obj, node.func.attr, args, line_no)
                raise EFPLRuntimeError("Unsupported function call", line_no)
            if isinstance(node, ast.JoinedStr):
                return "".join(str(_eval(v)) for v in node.values)
            if isinstance(node, ast.FormattedValue):
                return _eval(node.value)
            raise EFPLRuntimeError(f"Unsupported expression: {type(node).__name__}", line_no)

        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            raise EFPLSyntaxError(f"Invalid expression '{expr}'", line_no)
        return _eval(tree.body)

    # ---------------- EXPRESSION ----------------
    def eval_expr(self, expr, line_no=None):
        expr = expr.strip()

        if expr.startswith("#"):
            return None

        # Fix new ClassName(...) syntax
        expr = re.sub(r'\bnew\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(', r'__new__\1(', expr)
        
        # Support EFPL lambdas: (x) => x * 2  -->  lambda x: x * 2
        # This regex looks for (args) => expr and converts to Python lambda syntax
        expr = re.sub(r'\(([^)]*)\)\s*=>\s*(.+)', r'lambda \1: \2', expr)

        try:
            return self._safe_eval(expr, line_no)
        except (EFPLRuntimeError, EFPLSyntaxError):
            raise

    # ---------------- EXEC ----------------
    def exec_line(self, line, inputs, line_no=None):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return

        low = stripped.lower()

        if low.startswith("set "):
            self._exec_set(stripped, line_no)
            return

        if low.startswith("show "):
            expr = stripped[5:].strip()
            self.log(self.eval_expr(expr, line_no))
            return

        if low.startswith("add "):
            self._exec_add(stripped, line_no)
            return

        if low.startswith("remove "):
            self._exec_remove(stripped, line_no)
            return

        if low.startswith("take ") and " input" in low:
            self._exec_input(stripped, inputs, line_no)
            return

        if low.startswith("write "):
            self._exec_write(stripped, line_no)
            return

        if low.startswith("append "):
            self._exec_append(stripped, line_no)
            return

        if low.startswith("read file "):
            self._exec_read(stripped, line_no)
            return

        raise EFPLSyntaxError(f"Unknown command '{line}'", line_no)

    def _split_to(self, text, line_no):
        match = re.search(r"\s+to\s+", text, re.IGNORECASE)
        if not match:
            raise EFPLSyntaxError("Expected 'to'", line_no)
        return text[:match.start()], text[match.end():]

    def _exec_set(self, line, line_no):
        left, expr = self._split_to(line[4:].strip(), line_no)
        target = left.strip()
        value = self.eval_expr(expr.strip(), line_no)

        if "[" in target and target.endswith("]"):
            name, key_expr = target[:-1].split("[", 1)
            container = self.get_var(name.strip(), line_no)
            key = self.eval_expr(key_expr.strip(), line_no)
            try:
                container[key] = value
            except IndexError:
                raise EFPLRuntimeError(f"Array index {key} is out of range", line_no)
            except TypeError:
                raise EFPLRuntimeError("Invalid indexed assignment", line_no)
            return

        if "." in target:
            obj_name, attr = target.rsplit(".", 1)
            obj = self.eval_expr(obj_name, line_no)
            if isinstance(obj, EFPLInstance):
                obj.attributes[attr] = value
                return
            raise EFPLRuntimeError(f"Cannot set property on non-object '{obj_name}'", line_no)

        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", target):
            raise EFPLSyntaxError(f"Invalid variable name '{target}'", line_no)
        self.set_var(target, value)

    def _exec_add(self, line, line_no):
        match = re.search(r"\s+to\s+", line[4:], re.IGNORECASE)
        if not match:
            raise EFPLSyntaxError("Expected 'add value to array'", line_no)
        rest = line[4:]
        value_expr = rest[:match.start()].strip()
        name = rest[match.end():].strip()
        arr = self.get_var(name, line_no)
        if not isinstance(arr, list):
            raise EFPLRuntimeError(f"'{name}' is not an array", line_no)
        arr.append(self.eval_expr(value_expr, line_no))

    def _exec_remove(self, line, line_no):
        match = re.search(r"\s+from\s+", line[7:], re.IGNORECASE)
        if not match:
            raise EFPLSyntaxError("Expected 'remove value from container'", line_no)
        rest = line[7:]
        value_expr = rest[:match.start()].strip()
        name = rest[match.end():].strip()
        container = self.get_var(name, line_no)
        value = self.eval_expr(value_expr, line_no)
        
        if isinstance(container, list):
            try:
                container.remove(value)
            except ValueError:
                raise EFPLRuntimeError(f"Value {value!r} not found in '{name}'", line_no)
        elif isinstance(container, dict):
            if value in container:
                del container[value]
            else:
                raise EFPLRuntimeError(f"Key {value!r} not found in '{name}'", line_no)
        else:
            raise EFPLRuntimeError(f"'{name}' is not an array or dictionary", line_no)

    def _exec_input(self, line, inputs, line_no):
        pattern = (
            r'^take\s+(?:(number|text)\s+)?input'
            r'(?:\s+"([^"]*)")?\s+as\s+([A-Za-z_][A-Za-z0-9_]*)'
            r'(?:\s+default\s+(.+))?$'
        )
        match = re.match(pattern, line, re.IGNORECASE)
        if not match:
            raise EFPLSyntaxError(
                'Expected: take [number|text] input "prompt" as name [default value]',
                line_no,
            )

        input_type, prompt, var, default_expr = match.groups()
        if prompt and not self.input_callback:
            self.log(prompt)

        raw = inputs.get(var)
        if raw is None and self.input_callback:
            raw = self.input_callback(prompt if prompt else f"Enter value for {var}: ")

        if (raw is None or raw == "") and default_expr is not None:
            self.set_var(var, self.eval_expr(default_expr, line_no))
            return

        if input_type and input_type.lower() == "text":
            self.set_var(var, "" if raw is None else str(raw))
            return

        if input_type and input_type.lower() == "number":
            self.set_var(var, self._to_number(raw, line_no, var))
            return

        self.set_var(var, self._auto_convert(raw))

    def _safe_file_path(self, file_name, line_no):
        root = self.file_root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        path = (root / str(file_name)).resolve()
        if root != path and root not in path.parents:
            raise EFPLRuntimeError("File path must stay inside workspace/files", line_no)
        return path

    def _exec_write(self, line, line_no):
        self._require_module("file", line_no)
        match = re.match(r"^write\s+(.+?)\s+to\s+file\s+(.+)$", line, re.IGNORECASE)
        if not match:
            raise EFPLSyntaxError('Expected: write "text" to file "name.txt"', line_no)
        value = self.eval_expr(match.group(1).strip(), line_no)
        path = self._safe_file_path(self.eval_expr(match.group(2).strip(), line_no), line_no)
        path.write_text(str(value), encoding="utf-8")

    def _exec_append(self, line, line_no):
        self._require_module("file", line_no)
        match = re.match(r"^append\s+(.+?)\s+to\s+file\s+(.+)$", line, re.IGNORECASE)
        if not match:
            raise EFPLSyntaxError('Expected: append "text" to file "name.txt"', line_no)
        value = self.eval_expr(match.group(1).strip(), line_no)
        path = self._safe_file_path(self.eval_expr(match.group(2).strip(), line_no), line_no)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(str(value))

    def _exec_read(self, line, line_no):
        self._require_module("file", line_no)
        match = re.match(r"^read\s+file\s+(.+?)\s+as\s+([A-Za-z_][A-Za-z0-9_]*)$", line, re.IGNORECASE)
        if not match:
            raise EFPLSyntaxError('Expected: read file "name.txt" as variable', line_no)
        path = self._safe_file_path(self.eval_expr(match.group(1).strip(), line_no), line_no)
        if not path.exists():
            raise EFPLRuntimeError(f"File not found: {path.name}", line_no)
        self.set_var(match.group(2), path.read_text(encoding="utf-8"))

    def _to_number(self, raw, line_no, var):
        try:
            text = "" if raw is None else str(raw)
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            try:
                result = self.eval_expr(text, line_no)
                if isinstance(result, (int, float)):
                    return result
                raise EFPLRuntimeError(f"Input for '{var}' must evaluate to a number", line_no)
            except Exception as e:
                raise EFPLRuntimeError(f"Input for '{var}' must be a number: {e}", line_no)

    def _auto_convert(self, raw):
        if raw is None:
            return ""
        try:
            text = str(raw)
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            try:
                return self.eval_expr(text)
            except Exception:
                return raw

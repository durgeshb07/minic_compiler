"""
semantic.py  —  Semantic Analyser for Mini-C
Responsibilities:
  • Maintain a scoped Symbol Table
  • Check that variables are declared before use
  • Detect redeclarations within the same scope
  • Type-check assignments and binary operations (int vs float)
  • Report all semantic errors without stopping at the first one
"""

from errors import SemanticError


# ── Symbol Table ─────────────────────────────────────────────────────────────

class Symbol:
    def __init__(self, name, dtype, size, scope_level):
        self.name        = name
        self.dtype       = dtype          # "int" | "float" | "int[]" | "float[]"
        self.size        = size           # array length, or None
        self.scope_level = scope_level

    def __repr__(self):
        s = f"  {self.name:<16} {self.dtype:<10} "
        s += f"size={self.size:<6}" if self.size else " " * 12
        s += f"scope={self.scope_level}"
        return s


class SymbolTable:
    def __init__(self):
        self._scopes: list[dict] = [{}]   # index 0 = global
        self._all: list[Symbol]  = []

    @property
    def level(self):
        return len(self._scopes) - 1

    def push_scope(self):
        self._scopes.append({})

    def pop_scope(self):
        self._scopes.pop()

    def declare(self, name, dtype, size, line) -> bool:
        """Return True on success, False if already declared in this scope."""
        scope = self._scopes[-1]
        if name in scope:
            return False
        sym = Symbol(name, dtype, size, self.level)
        scope[name] = sym
        self._all.append(sym)
        return True

    def lookup(self, name) -> Symbol | None:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    def display(self):
        print("\n" + "═" * 60)
        print("  SYMBOL TABLE")
        print("═" * 60)
        print(f"  {'Name':<16} {'Type':<10} {'Size':<10} {'Scope'}")
        print("─" * 60)
        for s in self._all:
            size_str = str(s.size) if s.size is not None else "—"
            scope_str = "global" if s.scope_level == 0 else f"local (level {s.scope_level})"
            print(f"  {s.name:<16} {s.dtype:<10} {size_str:<10} {scope_str}")
        print("═" * 60 + "\n")


# ── Semantic Analyser ────────────────────────────────────────────────────────

class SemanticAnalyser:
    def __init__(self, symbol_table: SymbolTable):
        self.st = symbol_table
        self.errors: list[str] = []

    def error(self, msg, line=None):
        loc = f" [line {line}]" if line else ""
        self.errors.append(f"  SemanticError: {msg}{loc}")

    def _base_type(self, dtype):
        """Return 'int' or 'float' stripping array marker."""
        return dtype.replace("[]", "")

    def analyse(self, node):
        """Entry point — walk the full AST."""
        self._visit(node)

    def _visit(self, node):
        if node is None:
            return "void"
        t = node["type"]
        return getattr(self, f"_visit_{t}", self._visit_default)(node)

    def _visit_default(self, node):
        return "void"

    def _visit_Program(self, node):
        for s in node["body"]:
            self._visit(s)

    def _visit_Block(self, node):
        self.st.push_scope()
        for s in node["body"]:
            self._visit(s)
        self.st.pop_scope()

    def _visit_VarDecl(self, node):
        ok = self.st.declare(node["name"], node["dtype"], None, node.get("line"))
        if not ok:
            self.error(f"'{node['name']}' redeclared in the same scope", node.get("line"))
        if node["init"]:
            rtype = self._visit(node["init"])
            ltype = node["dtype"]
            if ltype == "int" and rtype == "float":
                self.error(
                    f"type mismatch — cannot assign float expression to int '{node['name']}'",
                    node.get("line"),
                )

    def _visit_ArrayDecl(self, node):
        dtype_arr = node["dtype"] + "[]"
        ok = self.st.declare(node["name"], dtype_arr, node["size"], node.get("line"))
        if not ok:
            self.error(f"'{node['name']}' redeclared in the same scope", node.get("line"))

    def _visit_ExprStmt(self, node):
        self._visit(node["expr"])

    def _visit_Assign(self, node):
        ltype = self._visit(node["left"])
        rtype = self._visit(node["right"])
        if ltype and rtype and ltype != rtype:
            # Allow int = int arithmetic result, allow float = int (widening)
            if ltype == "int" and rtype == "float":
                self.error(
                    f"type mismatch — cannot assign float to int lvalue",
                    node.get("line"),
                )
        return ltype

    def _visit_BinOp(self, node):
        lt = self._visit(node["left"])
        rt = self._visit(node["right"])
        if lt and rt:
            if lt != rt:
                # Mixed int/float arithmetic — result is float, that's OK
                return "float"
        return lt or "int"

    def _visit_UnOp(self, node):
        return self._visit(node["expr"])

    def _visit_PostfixOp(self, node):
        return self._visit(node["expr"])

    def _visit_Identifier(self, node):
        sym = self.st.lookup(node["name"])
        if sym is None:
            self.error(f"undeclared identifier '{node['name']}'", node.get("line"))
            return "int"
        return self._base_type(sym.dtype)

    def _visit_ArrayAccess(self, node):
        sym = self.st.lookup(node["name"])
        if sym is None:
            self.error(f"undeclared array '{node['name']}'", node.get("line"))
            return "int"
        if "[]" not in sym.dtype:
            self.error(f"'{node['name']}' is not an array", node.get("line"))
        self._visit(node["index"])
        return self._base_type(sym.dtype)

    def _visit_Literal(self, node):
        return node["dtype"]

    def _visit_If(self, node):
        self._visit(node["cond"])
        self.st.push_scope()
        self._visit(node["then"])
        self.st.pop_scope()
        if node["els"]:
            self.st.push_scope()
            self._visit(node["els"])
            self.st.pop_scope()

    def _visit_While(self, node):
        self._visit(node["cond"])
        self.st.push_scope()
        self._visit(node["body"])
        self.st.pop_scope()

    def _visit_For(self, node):
        self.st.push_scope()
        if node["init"]:
            self._visit(node["init"])
        if node["cond"]:
            self._visit(node["cond"])
        if node["update"]:
            self._visit(node["update"])
        self.st.push_scope()
        self._visit(node["body"])
        self.st.pop_scope()
        self.st.pop_scope()

    def _visit_Print(self, node):
        self._visit(node["arg"])

    def _visit_Return(self, node):
        if node["val"]:
            self._visit(node["val"])
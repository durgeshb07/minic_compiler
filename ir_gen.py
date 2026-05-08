"""
ir_gen.py  —  Intermediate Representation Generator for Mini-C
Produces Three-Address Code (TAC) as a list of Quadruples:
    (result, arg1, arg2, op)

Examples:
    t0 = x + y        →  ('t0', 'x', 'y', '+')
    x  = t0           →  ('x', 't0', '', '=')
    ifFalse t1 goto L2→  ('ifFalse', 't1', 'goto', 'L2')
    print x           →  ('print', 'x', '', '')
    L0:               →  ('L0:', '', '', '')
"""


class Quad:
    """One TAC instruction represented as a 4-tuple."""
    __slots__ = ("result", "arg1", "arg2", "op")

    def __init__(self, result="", arg1="", arg2="", op=""):
        self.result = result
        self.arg1   = arg1
        self.arg2   = arg2
        self.op     = op

    def __repr__(self):
        return f"({self.result!r:14}, {self.arg1!r:10}, {self.arg2!r:10}, {self.op!r})"

    def pretty(self):
        r, a1, a2, op = self.result, self.arg1, self.arg2, self.op
        # Label
        if r.endswith(":"):
            return r
        # Copy / assignment
        if op == "=":
            return f"    {r} = {a1}"
        # Binary op
        if op in ("+", "-", "*", "/", "%", "<", ">", "<=", ">=", "==", "!=", "&&", "||"):
            return f"    {r} = {a1} {op} {a2}"
        # Unary
        if op in ("UNARY-", "UNARY!"):
            sym = op[5:]
            return f"    {r} = {sym} {a1}"
        # Array store: arr[idx] = val
        if op == "ARRSTORE":
            return f"    {r}[{a1}] = {a2}"
        # Array load: val = arr[idx]
        if op == "ARRLOAD":
            return f"    {r} = {a1}[{a2}]"
        # Array alloc
        if op == "ALLOC":
            return f"    alloc {r}[{a1}]"
        # Conditional jump
        if r == "ifFalse":
            return f"    ifFalse {a1} goto {a2}"
        # Unconditional jump
        if r == "goto":
            return f"    goto {a1}"
        # Print
        if r == "print":
            return f"    print {a1}"
        # Return
        if r == "return":
            return f"    return {a1}" if a1 else "    return"
        return f"    {r} {a1} {a2} {op}"


class IRGenerator:
    def __init__(self):
        self._tmp_count   = 0
        self._label_count = 0
        self.quads: list[Quad] = []

    # ── Helpers ──────────────────────────────────────────────────────────────

    def new_tmp(self) -> str:
        t = f"t{self._tmp_count}"
        self._tmp_count += 1
        return t

    def new_label(self) -> str:
        lbl = f"L{self._label_count}"
        self._label_count += 1
        return lbl

    def emit(self, result="", arg1="", arg2="", op=""):
        self.quads.append(Quad(result, arg1, arg2, op))

    # ── Public entry ─────────────────────────────────────────────────────────

    def generate(self, node):
        self._gen_stmt(node)

    def display(self):
        print("═" * 60)
        print("  INTERMEDIATE REPRESENTATION  (Three-Address Code)")
        print("═" * 60)
        for i, q in enumerate(self.quads):
            idx_str = f"{i:>3}."
            print(f"  {idx_str}  {q.pretty().strip()}")
        print("═" * 60 + "\n")

    def display_quads(self):
        print("\n" + "═" * 70)
        print("  QUADRUPLES  (result, arg1, arg2, op)")
        print("═" * 70)
        print(f"  {'#':<5} {'result':<14} {'arg1':<12} {'arg2':<12} {'op'}")
        print("─" * 70)
        for i, q in enumerate(self.quads):
            print(f"  {i:<5} {q.result:<14} {q.arg1:<12} {q.arg2:<12} {q.op}")
        print("═" * 70 + "\n")

    # ── Statement generation ─────────────────────────────────────────────────

    def _gen_stmt(self, node):
        if node is None:
            return
        t = node["type"]
        return getattr(self, f"_stmt_{t}", lambda n: None)(node)

    def _stmt_Program(self, node):
        for s in node["body"]:
            self._gen_stmt(s)

    def _stmt_Block(self, node):
        for s in node["body"]:
            self._gen_stmt(s)

    def _stmt_VarDecl(self, node):
        if node["init"]:
            place = self._gen_expr(node["init"])
            self.emit(node["name"], place, "", "=")

    def _stmt_ArrayDecl(self, node):
        self.emit(node["name"], str(node["size"]), "", "ALLOC")

    def _stmt_ExprStmt(self, node):
        self._gen_expr(node["expr"])

    def _stmt_Print(self, node):
        place = self._gen_expr(node["arg"])
        self.emit("print", place, "", "")

    def _stmt_Return(self, node):
        if node["val"]:
            place = self._gen_expr(node["val"])
            self.emit("return", place, "", "")
        else:
            self.emit("return", "", "", "")

    def _stmt_If(self, node):
        cond = self._gen_expr(node["cond"])
        l_else = self.new_label()
        l_end  = self.new_label()
        self.emit("ifFalse", cond, l_else, "")
        self._gen_stmt(node["then"])
        if node["els"]:
            self.emit("goto", l_end, "", "")
            self.emit(l_else + ":", "", "", "")
            self._gen_stmt(node["els"])
            self.emit(l_end + ":", "", "", "")
        else:
            self.emit(l_else + ":", "", "", "")

    def _stmt_While(self, node):
        l_top = self.new_label()
        l_end = self.new_label()
        self.emit(l_top + ":", "", "", "")
        cond = self._gen_expr(node["cond"])
        self.emit("ifFalse", cond, l_end, "")
        self._gen_stmt(node["body"])
        self.emit("goto", l_top, "", "")
        self.emit(l_end + ":", "", "", "")

    def _stmt_For(self, node):
        if node["init"]:
            self._gen_stmt(node["init"])
        l_top = self.new_label()
        l_end = self.new_label()
        self.emit(l_top + ":", "", "", "")
        if node["cond"]:
            cond = self._gen_expr(node["cond"])
            self.emit("ifFalse", cond, l_end, "")
        self._gen_stmt(node["body"])
        if node["update"]:
            self._gen_expr(node["update"])
        self.emit("goto", l_top, "", "")
        self.emit(l_end + ":", "", "", "")

    # ── Expression generation  (returns the 'place' holding the result) ──────

    def _gen_expr(self, node) -> str:
        t = node["type"]
        return getattr(self, f"_expr_{t}", lambda n: "?")(node)

    def _expr_Literal(self, node) -> str:
        return str(node["value"])

    def _expr_Identifier(self, node) -> str:
        return node["name"]

    def _expr_ArrayAccess(self, node) -> str:
        idx = self._gen_expr(node["index"])
        t   = self.new_tmp()
        self.emit(t, node["name"], idx, "ARRLOAD")
        return t

    def _expr_Assign(self, node) -> str:
        rhs = self._gen_expr(node["right"])
        lhs = node["left"]
        if lhs["type"] == "ArrayAccess":
            idx = self._gen_expr(lhs["index"])
            self.emit(lhs["name"], idx, rhs, "ARRSTORE")
            return rhs
        # Simple variable
        self.emit(lhs["name"], rhs, "", "=")
        return lhs["name"]

    def _expr_BinOp(self, node) -> str:
        l = self._gen_expr(node["left"])
        r = self._gen_expr(node["right"])
        t = self.new_tmp()
        self.emit(t, l, r, node["op"])
        return t

    def _expr_UnOp(self, node) -> str:
        e = self._gen_expr(node["expr"])
        t = self.new_tmp()
        self.emit(t, e, "", "UNARY" + node["op"])
        return t

    def _expr_PostfixOp(self, node) -> str:
        e    = self._gen_expr(node["expr"])
        t    = self.new_tmp()
        op   = "+" if node["op"] == "++" else "-"
        self.emit(t, e, "1", op)
        if node["expr"]["type"] == "Identifier":
            self.emit(node["expr"]["name"], t, "", "=")
        return e    # postfix returns original value
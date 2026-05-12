"""
ir_gen.py  —  Mini-C IR Generator  (Stage 4)

Produces Three-Address Code (TAC) as a list of Quad 4-tuples:
    (result, arg1, arg2, op)

The generator uses ErrorReporter for any unexpected AST structures
(IRError) rather than crashing silently.
"""

from __future__ import annotations
from errors import IRError, ErrorReporter


# ══════════════════════════════════════════════════════════════════════════════
#  Quadruple
# ══════════════════════════════════════════════════════════════════════════════

class Quad:
    """
    A single Three-Address Code instruction.

    Fields
    ------
    result  : destination  (variable name, temp, label, or keyword)
    arg1    : first operand
    arg2    : second operand (empty string if unused)
    op      : operator / instruction mnemonic

    Instruction forms
    -----------------
    Copy          result='x',   arg1='y',    arg2='',    op='='
    BinOp         result='t0',  arg1='a',    arg2='b',   op='+'
    UnaryOp       result='t0',  arg1='x',    arg2='',    op='UNARY-'
    ArrayLoad     result='t0',  arg1='arr',  arg2='idx', op='ARRLOAD'
    ArrayStore    result='arr', arg1='idx',  arg2='val', op='ARRSTORE'
    ArrayAlloc    result='arr', arg1='size', arg2='',    op='ALLOC'
    CondJump      result='ifFalse', arg1='t0', arg2='L1', op=''
    GotoJump      result='goto',    arg1='L0', arg2='',   op=''
    Label         result='L0:',     arg1='',   arg2='',   op=''
    Print         result='print',   arg1='x',  arg2='',   op=''
    Return(val)   result='return',  arg1='x',  arg2='',   op=''
    Return(void)  result='return',  arg1='',   arg2='',   op=''
    """

    __slots__ = ("result", "arg1", "arg2", "op")

    def __init__(
        self,
        result: str = "",
        arg1:   str = "",
        arg2:   str = "",
        op:     str = "",
    ):
        self.result = result
        self.arg1   = arg1
        self.arg2   = arg2
        self.op     = op

    def __repr__(self) -> str:
        return (
            f"({self.result!r:16}, {self.arg1!r:12}, "
            f"{self.arg2!r:12}, {self.op!r})"
        )

    # ── Human-readable TAC string ────────────────────────────────────────────

    def pretty(self) -> str:
        r, a1, a2, op = self.result, self.arg1, self.arg2, self.op

        if r.endswith(":"):                              # label
            return r

        ARITH = {"+", "-", "*", "/", "%",
                 "<", ">", "<=", ">=", "==", "!=", "&&", "||"}

        if op == "=":                                    # copy
            return f"    {r} = {a1}"
        if op in ARITH:                                  # binary op
            return f"    {r} = {a1} {op} {a2}"
        if op.startswith("UNARY"):                       # unary op
            sym = op[5:]
            return f"    {r} = {sym}{a1}"
        if op == "ARRLOAD":                              # arr[idx] → tmp
            return f"    {r} = {a1}[{a2}]"
        if op == "ARRSTORE":                             # arr[idx] = val
            return f"    {r}[{a1}] = {a2}"
        if op == "ALLOC":                                # alloc arr[N]
            return f"    alloc {r}[{a1}]"
        if r == "ifFalse":                               # conditional jump
            return f"    ifFalse {a1} goto {a2}"
        if r == "goto":                                  # unconditional jump
            return f"    goto {a1}"
        if r == "print":                                 # print
            return f"    print {a1}"
        if r == "return":                                # return
            return f"    return {a1}" if a1 else "    return"

        # Fallback
        parts = [r, a1, a2, op]
        return "    " + " ".join(p for p in parts if p)


# ══════════════════════════════════════════════════════════════════════════════
#  IR Generator
# ══════════════════════════════════════════════════════════════════════════════

class IRGenerator:

    def __init__(self, reporter: ErrorReporter):
        self._reporter    = reporter
        self._tmp_count   = 0
        self._label_count = 0
        self.quads: list[Quad] = []

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _new_tmp(self) -> str:
        t = f"t{self._tmp_count}"
        self._tmp_count += 1
        return t

    def _new_label(self) -> str:
        lbl = f"L{self._label_count}"
        self._label_count += 1
        return lbl

    def _emit(
        self,
        result: str = "",
        arg1:   str = "",
        arg2:   str = "",
        op:     str = "",
    ) -> Quad:
        q = Quad(result, arg1, arg2, op)
        self.quads.append(q)
        return q

    # ── Public entry ─────────────────────────────────────────────────────────

    def generate(self, node: dict) -> None:
        self._gen_stmt(node)

    # ── Display helpers ───────────────────────────────────────────────────────

    def display_tac(self) -> None:
        """Print a numbered, human-readable TAC listing."""
        bar = "═" * 64
        print()
        print(bar)
        print("  INTERMEDIATE REPRESENTATION  —  Three-Address Code (TAC)")
        print(bar)
        label_count = sum(1 for q in self.quads if q.result.endswith(":"))
        instr_count = len(self.quads) - label_count
        idx = 0
        for q in self.quads:
            if q.result.endswith(":"):           # labels get no index
                print(f"  {q.pretty()}")
            else:
                print(f"  {idx:>3}.  {q.pretty().strip()}")
                idx += 1
        print(bar)
        print(f"  {instr_count} instruction(s),  {label_count} label(s)")
        print(bar)
        print()

    def display_quads(self) -> None:
        """Print the raw quadruple table."""
        bar  = "═" * 72
        thin = "─" * 72
        print(bar)
        print("  QUADRUPLES  (result, arg1, arg2, op)")
        print(bar)
        print(
            f"  {'#':<5} {'result':<16} {'arg1':<14} {'arg2':<14} {'op'}"
        )
        print(thin)
        for i, q in enumerate(self.quads):
            print(
                f"  {i:<5} {q.result:<16} {q.arg1:<14} {q.arg2:<14} {q.op}"
            )
        print(bar)
        print()

    def write_tac_file(self, path: str) -> None:
        """Write the TAC listing to *path*."""
        with open(path, "w") as f:
            f.write("Three-Address Code\n")
            f.write("=" * 50 + "\n")
            for q in self.quads:
                f.write(q.pretty().strip() + "\n")
        print(f"  TAC written to '{path}'.\n")

    # ══════════════════════════════════════════════════════════════════════════
    #  Statement code generation
    # ══════════════════════════════════════════════════════════════════════════

    def _gen_stmt(self, node: dict | None) -> None:
        if node is None:
            return
        t = node["type"]
        handler = getattr(self, f"_stmt_{t}", None)
        if handler is None:
            self._reporter.report_exception(
                IRError.unknown_node(t, node.get("line", 0))
            )
            return
        handler(node)

    def _stmt_Program(self, node: dict) -> None:
        for stmt in node["body"]:
            self._gen_stmt(stmt)

    def _stmt_Block(self, node: dict) -> None:
        for stmt in node["body"]:
            self._gen_stmt(stmt)

    def _stmt_VarDecl(self, node: dict) -> None:
        if node["init"] is not None:
            place = self._gen_expr(node["init"])
            self._emit(node["name"], place, "", "=")

    def _stmt_ArrayDecl(self, node: dict) -> None:
        self._emit(node["name"], str(node["size"]), "", "ALLOC")

    def _stmt_ExprStmt(self, node: dict) -> None:
        self._gen_expr(node["expr"])

    def _stmt_Print(self, node: dict) -> None:
        place = self._gen_expr(node["arg"])
        self._emit("print", place, "", "")

    def _stmt_Return(self, node: dict) -> None:
        if node["val"] is not None:
            place = self._gen_expr(node["val"])
            self._emit("return", place, "", "")
        else:
            self._emit("return", "", "", "")

    def _stmt_If(self, node: dict) -> None:
        cond   = self._gen_expr(node["cond"])
        l_else = self._new_label()
        l_end  = self._new_label()

        self._emit("ifFalse", cond, l_else, "")
        self._gen_stmt(node["then"])

        if node["els"] is not None:
            self._emit("goto", l_end, "", "")
            self._emit(l_else + ":", "", "", "")
            self._gen_stmt(node["els"])
            self._emit(l_end + ":", "", "", "")
        else:
            self._emit(l_else + ":", "", "", "")

    def _stmt_While(self, node: dict) -> None:
        l_top = self._new_label()
        l_end = self._new_label()

        self._emit(l_top + ":", "", "", "")
        cond = self._gen_expr(node["cond"])
        self._emit("ifFalse", cond, l_end, "")
        self._gen_stmt(node["body"])
        self._emit("goto", l_top, "", "")
        self._emit(l_end + ":", "", "", "")

    def _stmt_For(self, node: dict) -> None:
        # Init
        if node["init"] is not None:
            self._gen_stmt(node["init"])

        l_top = self._new_label()
        l_end = self._new_label()

        self._emit(l_top + ":", "", "", "")

        # Condition
        if node["cond"] is not None:
            cond = self._gen_expr(node["cond"])
            self._emit("ifFalse", cond, l_end, "")

        # Body
        self._gen_stmt(node["body"])

        # Update
        if node["update"] is not None:
            self._gen_expr(node["update"])

        self._emit("goto", l_top, "", "")
        self._emit(l_end + ":", "", "", "")

    # ══════════════════════════════════════════════════════════════════════════
    #  Expression code generation  (returns the 'place' holding the result)
    # ══════════════════════════════════════════════════════════════════════════

    def _gen_expr(self, node: dict) -> str:
        t = node["type"]
        handler = getattr(self, f"_expr_{t}", None)
        if handler is None:
            self._reporter.report_exception(
                IRError.unknown_node(t, node.get("line", 0))
            )
            return "?"
        return handler(node)

    def _expr_Literal(self, node: dict) -> str:
        return str(node["value"])

    def _expr_Identifier(self, node: dict) -> str:
        return node["name"]

    def _expr_ArrayAccess(self, node: dict) -> str:
        idx = self._gen_expr(node["index"])
        t   = self._new_tmp()
        self._emit(t, node["name"], idx, "ARRLOAD")
        return t

    def _expr_Assign(self, node: dict) -> str:
        rhs = self._gen_expr(node["right"])
        lhs = node["left"]

        if lhs["type"] == "ArrayAccess":
            idx = self._gen_expr(lhs["index"])
            self._emit(lhs["name"], idx, rhs, "ARRSTORE")
            return rhs

        # Simple variable assignment
        self._emit(lhs["name"], rhs, "", "=")
        return lhs["name"]

    def _expr_BinOp(self, node: dict) -> str:
        l = self._gen_expr(node["left"])
        r = self._gen_expr(node["right"])
        t = self._new_tmp()
        self._emit(t, l, r, node["op"])
        return t

    def _expr_UnOp(self, node: dict) -> str:
        e = self._gen_expr(node["expr"])
        t = self._new_tmp()
        self._emit(t, e, "", "UNARY" + node["op"])
        return t

    def _expr_PostfixOp(self, node: dict) -> str:
        """
        Postfix ++ / --
        Saves the original value in a temp (returned as the expression's value),
        then emits the increment/decrement and stores back to the variable.
        """
        original = self._gen_expr(node["expr"])
        saved    = self._new_tmp()
        result   = self._new_tmp()

        # Save original value
        self._emit(saved, original, "", "=")

        op = "+" if node["op"] == "++" else "-"
        self._emit(result, original, "1", op)

        if node["expr"]["type"] == "Identifier":
            self._emit(node["expr"]["name"], result, "", "=")

        return saved    # postfix: expression value is the *original*
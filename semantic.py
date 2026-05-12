"""
semantic.py  —  Mini-C Semantic Analyser  (Stage 3)

Responsibilities:
  • Build and maintain a scoped Symbol Table
  • Detect undeclared identifiers        → UndeclaredError
  • Detect same-scope redeclarations     → RedeclarationError
  • Type-check assignments               → TypeError_  (or narrowing Warning)
  • Type-check binary expressions        → TypeError_
  • Validate array access                → ScopeError / TypeError_
  • Detect zero/negative array sizes     → ScopeError
  • Warn on uninitialised use            → Warnings.uninitialised_use
  • Warn on unused variables             → Warnings.unused_variable
  • Warn on division by zero             → Warnings.division_by_zero
  • Warn on constant out-of-bounds index → Warnings.array_index_oob
  • Warn on dead code after return       → Warnings.dead_code_after_return
"""

from __future__ import annotations
from dataclasses import dataclass, field
from errors import (
    ErrorReporter, ErrorLocation,
    TypeError_, UndeclaredError, RedeclarationError, ScopeError,
    Warnings,
)


# ══════════════════════════════════════════════════════════════════════════════
#  Symbol
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Symbol:
    name:         str
    dtype:        str               # "int" | "float" | "int[]" | "float[]"
    size:         int | None        # array length, or None for scalars
    scope_level:  int               # 0 = global
    decl_line:    int = 0
    initialised:  bool = False      # has the variable been assigned a value?
    used:         bool = False      # has the variable been read?

    @property
    def is_array(self) -> bool:
        return "[]" in self.dtype

    @property
    def base_type(self) -> str:
        return self.dtype.replace("[]", "")


# ══════════════════════════════════════════════════════════════════════════════
#  Symbol Table
# ══════════════════════════════════════════════════════════════════════════════

class SymbolTable:
    def __init__(self):
        self._scopes: list[dict[str, Symbol]] = [{}]   # index 0 = global
        self._all:    list[Symbol]             = []     # insertion order

    # ── Scope management ────────────────────────────────────────────────────

    @property
    def level(self) -> int:
        return len(self._scopes) - 1

    def push_scope(self) -> None:
        self._scopes.append({})

    def pop_scope(self) -> list[Symbol]:
        """Remove the innermost scope and return its symbols (for unused-var check)."""
        return list(self._scopes.pop().values())

    # ── Symbol operations ────────────────────────────────────────────────────

    def declare(
        self,
        name:        str,
        dtype:       str,
        size:        int | None,
        decl_line:   int,
        initialised: bool = False,
    ) -> tuple[bool, Symbol | None]:
        """
        Declare *name* in the current scope.
        Returns (True, symbol) on success, (False, existing_symbol) on redeclaration.
        """
        scope = self._scopes[-1]
        if name in scope:
            return False, scope[name]
        sym = Symbol(
            name        = name,
            dtype       = dtype,
            size        = size,
            scope_level = self.level,
            decl_line   = decl_line,
            initialised = initialised,
        )
        scope[name] = sym
        self._all.append(sym)
        return True, sym

    def lookup(self, name: str) -> Symbol | None:
        """Search all scopes from innermost to outermost."""
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    def mark_initialised(self, name: str) -> None:
        sym = self.lookup(name)
        if sym:
            sym.initialised = True

    def mark_used(self, name: str) -> None:
        sym = self.lookup(name)
        if sym:
            sym.used = True

    # ── Display ──────────────────────────────────────────────────────────────

    def display(self) -> None:
        bar  = "═" * 72
        thin = "─" * 72
        print()
        print(bar)
        print("  SYMBOL TABLE")
        print(bar)
        print(f"  {'Name':<18} {'Type':<12} {'Size':<8} {'Scope':<18} {'Init':<6} {'Used'}")
        print(thin)
        for s in self._all:
            size_str  = str(s.size) if s.size is not None else "—"
            scope_str = "global" if s.scope_level == 0 else f"local (lvl {s.scope_level})"
            init_str  = "yes" if s.initialised else "no"
            used_str  = "yes" if s.used        else "no"
            print(
                f"  {s.name:<18} {s.dtype:<12} {size_str:<8} "
                f"{scope_str:<18} {init_str:<6} {used_str}"
            )
        print(bar)
        print()


# ══════════════════════════════════════════════════════════════════════════════
#  Semantic Analyser
# ══════════════════════════════════════════════════════════════════════════════

class SemanticAnalyser:
    def __init__(self, symbol_table: SymbolTable, reporter: ErrorReporter):
        self.st       = symbol_table
        self.reporter = reporter
        self._in_function_return_type: str | None = None
        self._seen_return = False    # for dead-code-after-return detection

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _loc(self, node: dict) -> ErrorLocation:
        return ErrorLocation(line=node.get("line", 0))

    def _warn_unused_in_scope(self, symbols: list[Symbol]) -> None:
        """Emit unused-variable warnings for symbols leaving scope."""
        for sym in symbols:
            if not sym.used and not sym.is_array:
                loc = ErrorLocation(line=sym.decl_line)
                self.reporter.warn(Warnings.unused_variable(sym.name, loc))

    # ── Public entry ─────────────────────────────────────────────────────────

    def analyse(self, node: dict) -> None:
        self._visit(node)
        # Warn about unused globals
        self._warn_unused_in_scope(list(self.st._scopes[0].values()))

    # ── Dispatcher ───────────────────────────────────────────────────────────

    def _visit(self, node: dict | None) -> str:
        """
        Visit an AST node.
        Returns the resolved type string ("int", "float", "string", "void").
        """
        if node is None:
            return "void"
        handler = getattr(self, f"_visit_{node['type']}", None)
        if handler is None:
            return "void"
        return handler(node) or "void"

    # ── Statement visitors ────────────────────────────────────────────────────

    def _visit_Program(self, node: dict) -> str:
        for stmt in node["body"]:
            self._visit(stmt)
        return "void"

    def _visit_Block(self, node: dict) -> str:
        prev_seen_return = self._seen_return
        self._seen_return = False
        self.st.push_scope()
        for stmt in node["body"]:
            if self._seen_return:
                self.reporter.warn(
                    Warnings.dead_code_after_return(self._loc(stmt))
                )
                break
            self._visit(stmt)
        exiting = self.st.pop_scope()
        self._warn_unused_in_scope(exiting)
        self._seen_return = prev_seen_return
        return "void"

    def _visit_VarDecl(self, node: dict) -> str:
        dtype = node["dtype"]
        name  = node["name"]
        line  = node.get("line", 0)
        has_init = node["init"] is not None

        ok, existing = self.st.declare(
            name, dtype, None, line, initialised=has_init
        )
        if not ok and existing:
            self.reporter.report_exception(
                RedeclarationError.variable(name, existing.decl_line, line)
            )

        if has_init:
            rtype = self._visit(node["init"])
            self._check_assign_types(dtype, rtype, name, node)

        return "void"

    def _visit_ArrayDecl(self, node: dict) -> str:
        dtype = node["dtype"]
        name  = node["name"]
        size  = node["size"]
        line  = node.get("line", 0)

        # Size validation
        if size == 0:
            self.reporter.report_exception(
                ScopeError.zero_size_array(name, line)
            )
        elif size < 0:
            self.reporter.report_exception(
                ScopeError.negative_array_size(name, size, line)
            )

        dtype_arr = dtype + "[]"
        ok, existing = self.st.declare(name, dtype_arr, size, line, initialised=True)
        if not ok and existing:
            self.reporter.report_exception(
                RedeclarationError.variable(name, existing.decl_line, line)
            )
        return "void"

    def _visit_ExprStmt(self, node: dict) -> str:
        self._visit(node["expr"])
        return "void"

    def _visit_Assign(self, node: dict) -> str:
        rtype = self._visit(node["right"])
        ltype = self._visit_lvalue(node["left"])
        if ltype != "void":
            self._check_assign_types(ltype, rtype, _lvalue_name(node["left"]), node)
        # Mark as initialised
        if node["left"]["type"] == "Identifier":
            self.st.mark_initialised(node["left"]["name"])
        return ltype

    def _visit_If(self, node: dict) -> str:
        self._visit(node["cond"])
        self.st.push_scope()
        self._visit(node["then"])
        exiting = self.st.pop_scope()
        self._warn_unused_in_scope(exiting)
        if node["els"]:
            self.st.push_scope()
            self._visit(node["els"])
            exiting = self.st.pop_scope()
            self._warn_unused_in_scope(exiting)
        return "void"

    def _visit_While(self, node: dict) -> str:
        self._visit(node["cond"])
        self.st.push_scope()
        self._visit(node["body"])
        exiting = self.st.pop_scope()
        self._warn_unused_in_scope(exiting)
        return "void"

    def _visit_For(self, node: dict) -> str:
        self.st.push_scope()
        if node["init"]:
            self._visit(node["init"])
        if node["cond"]:
            self._visit(node["cond"])
        if node["update"]:
            self._visit(node["update"])
        self.st.push_scope()
        self._visit(node["body"])
        exiting = self.st.pop_scope()
        self._warn_unused_in_scope(exiting)
        exiting = self.st.pop_scope()
        self._warn_unused_in_scope(exiting)
        return "void"

    def _visit_Print(self, node: dict) -> str:
        arg_type = self._visit(node["arg"])
        if arg_type == "void":
            self.reporter.report_exception(
                TypeError_.print_void(node.get("line", 0))
            )
        return "void"

    def _visit_Return(self, node: dict) -> str:
        self._seen_return = True
        if node["val"]:
            ret_type = self._visit(node["val"])
            if self._in_function_return_type and \
               ret_type != self._in_function_return_type:
                self.reporter.report_exception(
                    TypeError_.return_mismatch(
                        self._in_function_return_type, ret_type,
                        node.get("line", 0)
                    )
                )
        return "void"

    # ── Expression visitors ───────────────────────────────────────────────────

    def _visit_Literal(self, node: dict) -> str:
        return node["dtype"]

    def _visit_Identifier(self, node: dict) -> str:
        name = node["name"]
        sym  = self.st.lookup(name)
        if sym is None:
            self.reporter.report_exception(
                UndeclaredError.variable(name, node.get("line", 0))
            )
            return "int"   # assume int so analysis can continue
        # Uninitialised-use warning
        if not sym.initialised and not sym.is_array:
            loc = self._loc(node)
            self.reporter.warn(Warnings.uninitialised_use(name, loc))
        self.st.mark_used(name)
        return sym.base_type

    def _visit_ArrayAccess(self, node: dict) -> str:
        name = node["name"]
        sym  = self.st.lookup(name)
        if sym is None:
            self.reporter.report_exception(
                UndeclaredError.array(name, node.get("line", 0))
            )
            return "int"
        if not sym.is_array:
            self.reporter.report_exception(
                ScopeError.subscript_non_array(name, sym.dtype, node.get("line", 0))
            )
        self.st.mark_used(name)

        # Index type must be int
        idx_type = self._visit(node["index"])
        if idx_type == "float":
            self.reporter.report_exception(
                TypeError_.array_float_index(name, node.get("line", 0))
            )

        # Constant out-of-bounds warning
        idx_node = node["index"]
        if idx_node["type"] == "Literal" and idx_node["dtype"] == "int":
            idx_val = idx_node["value"]
            if sym.size is not None:
                if idx_val < 0:
                    loc = self._loc(node)
                    self.reporter.warn(
                        Warnings.array_index_oob(name, idx_val, sym.size, loc)
                    )
                elif idx_val >= sym.size:
                    loc = self._loc(node)
                    self.reporter.warn(
                        Warnings.array_index_oob(name, idx_val, sym.size, loc)
                    )

        return sym.base_type

    def _visit_BinOp(self, node: dict) -> str:
        ltype = self._visit(node["left"])
        rtype = self._visit(node["right"])

        # Division-by-zero warning
        op = node["op"]
        if op == "/" and node["right"]["type"] == "Literal":
            val = node["right"]["value"]
            if val == 0 or val == 0.0:
                self.reporter.warn(Warnings.division_by_zero(self._loc(node)))

        # Incompatible types for non-arithmetic ops
        if ltype != rtype:
            # int/float mixed — result promotes to float (allowed)
            if {ltype, rtype} <= {"int", "float"}:
                return "float"
            # any other mismatch
            self.reporter.report_exception(
                TypeError_.op_mismatch(op, ltype, rtype, node.get("line", 0))
            )
            return "int"

        return ltype

    def _visit_UnOp(self, node: dict) -> str:
        return self._visit(node["expr"])

    def _visit_PostfixOp(self, node: dict) -> str:
        return self._visit(node["expr"])

    # ── lvalue helper ─────────────────────────────────────────────────────────

    def _visit_lvalue(self, node: dict) -> str:
        """Resolve the type of an assignment target."""
        if node["type"] == "Identifier":
            sym = self.st.lookup(node["name"])
            if sym is None:
                self.reporter.report_exception(
                    UndeclaredError.variable(node["name"], node.get("line", 0))
                )
                return "void"
            return sym.base_type
        if node["type"] == "ArrayAccess":
            return self._visit_ArrayAccess(node)
        return "void"

    # ── Type-checking helper ──────────────────────────────────────────────────

    def _check_assign_types(
        self,
        ltype:   str,
        rtype:   str,
        varname: str,
        node:    dict,
    ) -> None:
        line = node.get("line", 0)
        if ltype == rtype:
            return
        if {ltype, rtype} <= {"int", "float"}:
            if ltype == "int" and rtype == "float":
                # Narrowing — error in Mini-C (no implicit float→int)
                self.reporter.report_exception(
                    TypeError_.assign_mismatch(ltype, rtype, varname, line)
                )
            # float = int is a widening conversion — emit a warning only
            elif ltype == "float" and rtype == "int":
                loc = ErrorLocation(line=line)
                self.reporter.warn(
                    Warnings.narrowing_conversion(rtype, ltype, varname, loc)
                )
            return
        # Completely incompatible types
        self.reporter.report_exception(
            TypeError_.assign_mismatch(ltype, rtype, varname, line)
        )


# ── Utility ──────────────────────────────────────────────────────────────────

def _lvalue_name(node: dict) -> str:
    if node["type"] == "Identifier":
        return node["name"]
    if node["type"] == "ArrayAccess":
        return node["name"] + "[...]"
    return "<expr>"
"""
parser.py  —  Mini-C Recursive-Descent Parser  (Stage 2)
Builds an Abstract Syntax Tree (AST) from the token list.
All errors are raised as ParseError instances from errors.py.
"""

from __future__ import annotations
from errors import ParseError, ErrorLocation
from lexer  import Token


# ══════════════════════════════════════════════════════════════════════════════
#  AST node
# ══════════════════════════════════════════════════════════════════════════════

class Node(dict):
    """
    An AST node is a plain dict with a mandatory 'type' key.
    Extra fields depend on the node type (see grammar below).
    """
    def __repr__(self):
        t = self.get("type", "?")
        keys = [k for k in self if k != "type"]
        brief = ", ".join(f"{k}={self[k]!r}" for k in keys[:3])
        return f"Node<{t}>({brief})"


# ══════════════════════════════════════════════════════════════════════════════
#  Parser
# ══════════════════════════════════════════════════════════════════════════════

class Parser:
    """
    Recursive-descent parser for Mini-C.

    Grammar (in precedence order, lowest first):
        program    → stmt*  EOF
        stmt       → decl | if_stmt | while_stmt | for_stmt
                   | print_stmt | return_stmt | block | expr_stmt
        decl       → type ID ('[' INT_LIT ']')? ('=' expr)? ';'
        if_stmt    → 'if' '(' expr ')' stmt ('else' stmt)?
        while_stmt → 'while' '(' expr ')' stmt
        for_stmt   → 'for' '(' (decl | expr_stmt | ';')
                               expr? ';' expr? ')' stmt
        print_stmt → 'print' '(' expr ')' ';'
        return_stmt→ 'return' expr? ';'
        block      → '{' stmt* '}'
        expr_stmt  → expr ';'

        expr       → assign
        assign     → or_expr ('=' assign)?
        or_expr    → and_expr ('||' and_expr)*
        and_expr   → rel_expr ('&&' rel_expr)*
        rel_expr   → add_expr (('<'|'>'|'<='|'>='|'=='|'!=') add_expr)*
        add_expr   → mul_expr (('+'|'-') mul_expr)*
        mul_expr   → unary   (('*'|'/'|'%') unary)*
        unary      → ('!'|'-') unary | postfix
        postfix    → primary ('++'|'--')?
        primary    → INT_LIT | FLOAT_LIT | STRING_LIT
                   | ID ('[' expr ']')?
                   | '(' expr ')'
    """

    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos    = 0

    # ── Low-level helpers ────────────────────────────────────────────────────

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _consume(self, expected_type: str | None = None) -> Token:
        tok = self._peek()
        if expected_type and tok.type != expected_type:
            raise ParseError.unexpected(
                got      = tok.value if tok.value != "" else tok.type,
                expected = expected_type,
                line     = tok.line,
                col      = tok.column,
            )
        self._pos += 1
        return tok

    def _match(self, *types: str) -> Token | None:
        if self._peek().type in types:
            return self._consume()
        return None

    def _check(self, *types: str) -> bool:
        return self._peek().type in types

    def _require_semi(self) -> Token:
        """Consume ';' or raise a targeted missing-semicolon error."""
        tok = self._peek()
        if tok.type != "SEMI":
            raise ParseError.missing_semi(tok.line, tok.column)
        return self._consume()

    def _require(self, tok_type: str, opener_line: int | None = None) -> Token:
        """
        Consume *tok_type* or raise an appropriate error.
        *opener_line* is used for unmatched-bracket messages.
        """
        tok = self._peek()
        if tok.type == tok_type:
            return self._consume()
        # Bracket-specific messages
        if tok_type == "RPAREN":
            raise ParseError.unmatched("(", opener_line or tok.line, tok.column)
        if tok_type == "RBRACE":
            raise ParseError.unmatched("{", opener_line or tok.line, tok.column)
        if tok_type == "RBRACKET":
            raise ParseError.unmatched("[", opener_line or tok.line, tok.column)
        raise ParseError.unexpected(
            got      = tok.value if tok.value != "" else tok.type,
            expected = tok_type,
            line     = tok.line,
            col      = tok.column,
        )

    # ── Public entry point ───────────────────────────────────────────────────

    def parse_program(self) -> Node:
        stmts: list[Node] = []
        while not self._check("EOF"):
            stmts.append(self._parse_stmt())
        self._consume("EOF")
        return Node(type="Program", body=stmts)

    # ── Statements ───────────────────────────────────────────────────────────

    def _parse_stmt(self) -> Node:
        t = self._peek().type
        if t in ("INT", "FLOAT"):   return self._parse_decl()
        if t == "IF":               return self._parse_if()
        if t == "WHILE":            return self._parse_while()
        if t == "FOR":              return self._parse_for()
        if t == "PRINT":            return self._parse_print()
        if t == "RETURN":           return self._parse_return()
        if t == "LBRACE":           return self._parse_block()
        if t == "ELSE":
            tok = self._peek()
            raise ParseError.dangling_else(tok.line, tok.column)
        return self._parse_expr_stmt()

    def _parse_decl(self) -> Node:
        kw    = self._consume()          # INT or FLOAT
        dtype = kw.value                 # "int" or "float"
        line  = kw.line

        id_tok = self._peek()
        if id_tok.type != "ID":
            raise ParseError.unexpected(
                got      = id_tok.value or id_tok.type,
                expected = "identifier",
                line     = id_tok.line,
                col      = id_tok.column,
            )
        name = self._consume().value

        # Array declaration: int name[SIZE];
        if self._match("LBRACKET"):
            size_tok = self._peek()
            # Size must be a positive integer literal
            if size_tok.type != "INT_LIT":
                raise ParseError.bad_array_size(
                    size_tok.value or size_tok.type,
                    size_tok.line,
                    size_tok.column,
                )
            size = self._consume().value
            if size <= 0:
                raise ParseError.bad_array_size(size, size_tok.line, size_tok.column)
            self._require("RBRACKET", line)
            self._require_semi()
            return Node(type="ArrayDecl", dtype=dtype, name=name,
                        size=size, line=line)

        # Scalar declaration: int name [= expr];
        init = None
        if self._match("ASSIGN"):
            tok = self._peek()
            if self._check("SEMI"):
                raise ParseError.empty_expression(tok.line, tok.column)
            init = self._parse_expr()
        self._require_semi()
        return Node(type="VarDecl", dtype=dtype, name=name, init=init, line=line)

    def _parse_if(self) -> Node:
        kw   = self._consume("IF")
        line = kw.line
        lp   = self._peek()
        if not self._match("LPAREN"):
            raise ParseError.missing_condition("if", line, lp.column)
        cond = self._parse_expr()
        self._require("RPAREN", line)
        then = self._parse_stmt()
        els  = None
        if self._match("ELSE"):
            els = self._parse_stmt()
        return Node(type="If", cond=cond, then=then, els=els, line=line)

    def _parse_while(self) -> Node:
        kw   = self._consume("WHILE")
        line = kw.line
        lp   = self._peek()
        if not self._match("LPAREN"):
            raise ParseError.missing_condition("while", line, lp.column)
        cond = self._parse_expr()
        self._require("RPAREN", line)
        body = self._parse_stmt()
        return Node(type="While", cond=cond, body=body, line=line)

    def _parse_for(self) -> Node:
        kw   = self._consume("FOR")
        line = kw.line
        self._require("LPAREN", line)

        # Init clause
        init: Node | None = None
        if not self._check("SEMI"):
            if self._check("INT", "FLOAT"):
                init = self._parse_decl()          # includes the semicolon
            else:
                init = self._parse_expr_stmt()     # includes the semicolon
        else:
            self._consume("SEMI")

        # Condition clause
        cond: Node | None = None
        if not self._check("SEMI"):
            cond = self._parse_expr()
        self._require_semi()

        # Update clause
        update: Node | None = None
        if not self._check("RPAREN"):
            update = self._parse_expr()
            # Validate lvalue for update expressions like i++
        self._require("RPAREN", line)

        body = self._parse_stmt()
        return Node(type="For", init=init, cond=cond, update=update,
                    body=body, line=line)

    def _parse_print(self) -> Node:
        kw   = self._consume("PRINT")
        line = kw.line
        lp   = self._peek()
        self._require("LPAREN", line)
        tok = self._peek()
        if self._check("RPAREN"):
            raise ParseError.empty_expression(tok.line, tok.column)
        arg = self._parse_expr()
        self._require("RPAREN", line)
        self._require_semi()
        return Node(type="Print", arg=arg, line=line)

    def _parse_return(self) -> Node:
        kw   = self._consume("RETURN")
        line = kw.line
        val: Node | None = None
        if not self._check("SEMI"):
            val = self._parse_expr()
        self._require_semi()
        return Node(type="Return", val=val, line=line)

    def _parse_block(self) -> Node:
        lb   = self._consume("LBRACE")
        line = lb.line
        stmts: list[Node] = []
        while not self._check("RBRACE"):
            if self._check("EOF"):
                raise ParseError.unmatched("{", line)
            stmts.append(self._parse_stmt())
        self._consume("RBRACE")
        return Node(type="Block", body=stmts)

    def _parse_expr_stmt(self) -> Node:
        tok = self._peek()
        if self._check("SEMI"):
            raise ParseError.empty_expression(tok.line, tok.column)
        expr = self._parse_expr()
        self._require_semi()
        return Node(type="ExprStmt", expr=expr)

    # ── Expressions (precedence chain) ───────────────────────────────────────

    def _parse_expr(self) -> Node:
        return self._parse_assign()

    def _parse_assign(self) -> Node:
        left = self._parse_or()
        if self._match("ASSIGN"):
            # Validate lvalue
            if left["type"] not in ("Identifier", "ArrayAccess"):
                raise ParseError.invalid_lvalue(
                    repr(left),
                    left.get("line", 0),
                )
            right = self._parse_assign()
            return Node(type="Assign", left=left, right=right,
                        line=left.get("line", 0))
        return left

    def _parse_or(self) -> Node:
        left = self._parse_and()
        while self._match("OR"):
            right = self._parse_and()
            left  = Node(type="BinOp", op="||", left=left, right=right,
                         line=left.get("line", 0))
        return left

    def _parse_and(self) -> Node:
        left = self._parse_rel()
        while self._match("AND"):
            right = self._parse_rel()
            left  = Node(type="BinOp", op="&&", left=left, right=right,
                         line=left.get("line", 0))
        return left

    def _parse_rel(self) -> Node:
        left = self._parse_add()
        while self._check("LT", "GT", "LE", "GE", "EQ", "NEQ"):
            op    = self._consume().type
            right = self._parse_add()
            left  = Node(type="BinOp", op=op, left=left, right=right,
                         line=left.get("line", 0))
        return left

    def _parse_add(self) -> Node:
        left = self._parse_mul()
        while self._check("PLUS", "MINUS"):
            op    = self._consume().value
            right = self._parse_mul()
            left  = Node(type="BinOp", op=op, left=left, right=right,
                         line=left.get("line", 0))
        return left

    def _parse_mul(self) -> Node:
        left = self._parse_unary()
        while self._check("TIMES", "DIVIDE", "MOD"):
            op    = self._consume().value
            right = self._parse_unary()
            left  = Node(type="BinOp", op=op, left=left, right=right,
                         line=left.get("line", 0))
        return left

    def _parse_unary(self) -> Node:
        if self._check("NOT"):
            op   = self._consume()
            expr = self._parse_unary()
            return Node(type="UnOp", op="!", expr=expr, line=op.line)
        if self._check("MINUS"):
            op   = self._consume()
            expr = self._parse_unary()
            return Node(type="UnOp", op="-", expr=expr, line=op.line)
        return self._parse_postfix()

    def _parse_postfix(self) -> Node:
        expr = self._parse_primary()
        if self._match("PLUSPLUS"):
            return Node(type="PostfixOp", op="++", expr=expr,
                        line=expr.get("line", 0))
        if self._match("MINUSMINUS"):
            return Node(type="PostfixOp", op="--", expr=expr,
                        line=expr.get("line", 0))
        return expr

    def _parse_primary(self) -> Node:
        tok = self._peek()

        if tok.type == "INT_LIT":
            self._consume()
            return Node(type="Literal", dtype="int", value=tok.value, line=tok.line)

        if tok.type == "FLOAT_LIT":
            self._consume()
            return Node(type="Literal", dtype="float", value=tok.value, line=tok.line)

        if tok.type == "STRING_LIT":
            self._consume()
            return Node(type="Literal", dtype="string", value=tok.value, line=tok.line)

        if tok.type == "ID":
            self._consume()
            # Array access: id[expr]
            if self._match("LBRACKET"):
                idx = self._parse_expr()
                self._require("RBRACKET", tok.line)
                return Node(type="ArrayAccess", name=tok.value,
                            index=idx, line=tok.line)
            return Node(type="Identifier", name=tok.value, line=tok.line)

        if tok.type == "LPAREN":
            lp = self._consume()
            if self._check("RPAREN"):
                raise ParseError.empty_expression(tok.line, tok.column)
            expr = self._parse_expr()
            self._require("RPAREN", lp.line)
            return expr

        # Nothing matched
        raise ParseError.unexpected(
            got      = tok.value if tok.value != "" else tok.type,
            expected = "expression",
            line     = tok.line,
            col      = tok.column,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  AST printer
# ══════════════════════════════════════════════════════════════════════════════

_USE_COLOUR_AST = __import__("sys").stdout.isatty()
_C = {
    "node":  "\033[1;34m",    # bold blue  — node type
    "key":   "\033[2m",       # dim        — field name
    "val":   "\033[33m",      # yellow     — literal / name
    "op":    "\033[35m",      # magenta    — operator
    "reset": "\033[0m",
}


def _c(kind: str, text: str) -> str:
    if not _USE_COLOUR_AST:
        return text
    return _C[kind] + text + _C["reset"]


def print_ast(node, depth: int = 0, prefix: str = "") -> None:
    """
    Print an indented tree representation of the AST.

    Example:
        Program
        ├── VarDecl  name='x'  dtype='int'
        │   └── Literal  dtype='int'  value=5
        └── Print
            └── Identifier  name='x'
    """
    if not isinstance(node, dict):
        return

    node_type = node.get("type", "?")
    extras: list[str] = []
    for key in ("name", "dtype", "op", "value", "size"):
        if key in node:
            v = node[key]
            if key == "op":
                extras.append(_c("key", f"{key}=") + _c("op", repr(v)))
            else:
                extras.append(_c("key", f"{key}=") + _c("val", repr(v)))

    label = _c("node", node_type)
    if extras:
        label += "  " + "  ".join(extras)

    print(prefix + label)

    # Collect child fields in a deterministic order
    child_fields = []
    for key in ("body", "init", "cond", "update", "then", "els",
                "left", "right", "expr", "arg", "val", "index"):
        child = node.get(key)
        if child is None:
            continue
        if isinstance(child, list):
            for item in child:
                child_fields.append((key, item))
        else:
            child_fields.append((key, child))

    for i, (key, child) in enumerate(child_fields):
        last = (i == len(child_fields) - 1)
        connector = "└── " if last else "├── "
        extender  = "    " if last else "│   "
        print(prefix + connector + _c("key", f"[{key}]"))
        print_ast(child, depth + 1, prefix + extender)
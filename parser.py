"""
parser.py  —  Mini-C Recursive-Descent Parser
Produces an Abstract Syntax Tree (AST) from the token list.

Grammar (simplified):
  program    → stmt*
  stmt       → decl | if_stmt | while_stmt | for_stmt
             | print_stmt | return_stmt | block | expr_stmt
  decl       → type ID ('[' INT_LIT ']')? ('=' expr)? ';'
  if_stmt    → 'if' '(' expr ')' stmt ('else' stmt)?
  while_stmt → 'while' '(' expr ')' stmt
  for_stmt   → 'for' '(' (decl | expr_stmt)? expr? ';' expr? ')' stmt
  print_stmt → 'print' '(' expr ')' ';'
  block      → '{' stmt* '}'
  expr       → assign | or_expr
  ...        (standard precedence chain down to primary)
"""

from errors import ParseError

# ── AST node helper ─────────────────────────────────────────────────────────
class Node(dict):
    """An AST node is just a plain dict with a 'type' key."""
    def __repr__(self):
        return f"Node({dict.__repr__(self)})"


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ── Low-level helpers ───────────────────────────────────────────────────

    def peek(self):
        return self.tokens[self.pos]

    def consume(self, expected_type=None):
        tok = self.peek()
        if expected_type and tok.type != expected_type:
            raise ParseError(
                f"Expected '{expected_type}' but got '{tok.value or tok.type}'",
                tok.line,
            )
        self.pos += 1
        return tok

    def match(self, *types):
        if self.peek().type in types:
            return self.consume()
        return None

    def is_type(self, *types):
        return self.peek().type in types

    # ── Grammar rules ───────────────────────────────────────────────────────

    def parse_program(self):
        stmts = []
        while not self.is_type("EOF"):
            stmts.append(self.parse_stmt())
        return Node(type="Program", body=stmts)

    def parse_stmt(self):
        t = self.peek().type
        if t in ("INT", "FLOAT"):
            return self.parse_decl()
        if t == "IF":
            return self.parse_if()
        if t == "WHILE":
            return self.parse_while()
        if t == "FOR":
            return self.parse_for()
        if t == "PRINT":
            return self.parse_print()
        if t == "RETURN":
            return self.parse_return()
        if t == "LBRACE":
            return self.parse_block()
        return self.parse_expr_stmt()

    def parse_decl(self):
        kw  = self.consume()           # INT or FLOAT
        dtype = kw.value
        line  = kw.line
        name  = self.consume("ID").value
        # array declaration?
        if self.match("LBRACKET"):
            size = self.consume("INT_LIT").value
            self.consume("RBRACKET")
            self.consume("SEMI")
            return Node(type="ArrayDecl", dtype=dtype, name=name, size=size, line=line)
        init = None
        if self.match("ASSIGN"):
            init = self.parse_expr()
        self.consume("SEMI")
        return Node(type="VarDecl", dtype=dtype, name=name, init=init, line=line)

    def parse_if(self):
        line = self.consume("IF").line
        self.consume("LPAREN")
        cond = self.parse_expr()
        self.consume("RPAREN")
        then = self.parse_stmt()
        els  = None
        if self.match("ELSE"):
            els = self.parse_stmt()
        return Node(type="If", cond=cond, then=then, els=els, line=line)

    def parse_while(self):
        line = self.consume("WHILE").line
        self.consume("LPAREN")
        cond = self.parse_expr()
        self.consume("RPAREN")
        body = self.parse_stmt()
        return Node(type="While", cond=cond, body=body, line=line)

    def parse_for(self):
        line = self.consume("FOR").line
        self.consume("LPAREN")
        # init
        init = None
        if not self.is_type("SEMI"):
            if self.peek().type in ("INT", "FLOAT"):
                init = self.parse_decl()
            else:
                init = self.parse_expr_stmt()
        else:
            self.consume("SEMI")
        # condition
        cond = None
        if not self.is_type("SEMI"):
            cond = self.parse_expr()
        self.consume("SEMI")
        # update
        update = None
        if not self.is_type("RPAREN"):
            update = self.parse_expr()
        self.consume("RPAREN")
        body = self.parse_stmt()
        return Node(type="For", init=init, cond=cond, update=update, body=body, line=line)

    def parse_print(self):
        line = self.consume("PRINT").line
        self.consume("LPAREN")
        arg = self.parse_expr()
        self.consume("RPAREN")
        self.consume("SEMI")
        return Node(type="Print", arg=arg, line=line)

    def parse_return(self):
        line = self.consume("RETURN").line
        val  = None
        if not self.is_type("SEMI"):
            val = self.parse_expr()
        self.consume("SEMI")
        return Node(type="Return", val=val, line=line)

    def parse_block(self):
        self.consume("LBRACE")
        stmts = []
        while not self.is_type("RBRACE"):
            stmts.append(self.parse_stmt())
        self.consume("RBRACE")
        return Node(type="Block", body=stmts)

    def parse_expr_stmt(self):
        expr = self.parse_expr()
        self.consume("SEMI")
        return Node(type="ExprStmt", expr=expr)

    # ── Expression precedence chain ─────────────────────────────────────────
    # assign > or > and > rel > add > mul > unary > postfix > primary

    def parse_expr(self):
        return self.parse_assign()

    def parse_assign(self):
        left = self.parse_or()
        if self.match("ASSIGN"):
            right = self.parse_assign()
            return Node(type="Assign", left=left, right=right)
        return left

    def parse_or(self):
        left = self.parse_and()
        while self.match("OR"):
            left = Node(type="BinOp", op="||", left=left, right=self.parse_and())
        return left

    def parse_and(self):
        left = self.parse_rel()
        while self.match("AND"):
            left = Node(type="BinOp", op="&&", left=left, right=self.parse_rel())
        return left

    def parse_rel(self):
        left = self.parse_add()
        while self.is_type("LT", "GT", "LE", "GE", "EQ", "NEQ"):
            op = self.consume().type
            left = Node(type="BinOp", op=op, left=left, right=self.parse_add())
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.is_type("PLUS", "MINUS"):
            op = self.consume().value
            left = Node(type="BinOp", op=op, left=left, right=self.parse_mul())
        return left

    def parse_mul(self):
        left = self.parse_unary()
        while self.is_type("TIMES", "DIVIDE", "MOD"):
            op = self.consume().value
            left = Node(type="BinOp", op=op, left=left, right=self.parse_unary())
        return left

    def parse_unary(self):
        if self.match("NOT"):
            return Node(type="UnOp", op="!", expr=self.parse_unary())
        if self.match("MINUS"):
            return Node(type="UnOp", op="-", expr=self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self):
        expr = self.parse_primary()
        if self.match("PLUSPLUS"):
            return Node(type="PostfixOp", op="++", expr=expr)
        if self.match("MINUSMINUS"):
            return Node(type="PostfixOp", op="--", expr=expr)
        return expr

    def parse_primary(self):
        tok = self.peek()
        if tok.type == "INT_LIT":
            self.consume()
            return Node(type="Literal", dtype="int", value=tok.value, line=tok.line)
        if tok.type == "FLOAT_LIT":
            self.consume()
            return Node(type="Literal", dtype="float", value=tok.value, line=tok.line)
        if tok.type == "STRING_LIT":
            self.consume()
            return Node(type="Literal", dtype="string", value=tok.value, line=tok.line)
        if tok.type == "ID":
            self.consume()
            if self.match("LBRACKET"):
                idx = self.parse_expr()
                self.consume("RBRACKET")
                return Node(type="ArrayAccess", name=tok.value, index=idx, line=tok.line)
            return Node(type="Identifier", name=tok.value, line=tok.line)
        if tok.type == "LPAREN":
            self.consume()
            expr = self.parse_expr()
            self.consume("RPAREN")
            return expr
        raise ParseError(
            f"Unexpected token '{tok.value or tok.type}'", tok.line
        )
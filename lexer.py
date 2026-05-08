"""
lexer.py  —  Mini-C Lexer
Tokenises source text into a flat list of Token objects.
Supported tokens: keywords, identifiers, int/float literals,
string literals, operators, punctuation.
"""

import re
from errors import LexError

# ── Token definition ────────────────────────────────────────────────────────
class Token:
    __slots__ = ("type", "value", "line")
    def __init__(self, type_, value, line):
        self.type  = type_
        self.value = value
        self.line  = line

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line})"


KEYWORDS = {
    "int", "float", "if", "else", "while", "for", "print", "return",
}

# Each rule: (token_type, compiled_regex)
# Order matters — longer/more specific patterns first.
TOKEN_SPEC = [
    ("FLOAT_LIT",   re.compile(r"\d+\.\d*(?:[eE][+-]?\d+)?|\d*\.\d+(?:[eE][+-]?\d+)?")),
    ("INT_LIT",     re.compile(r"\d+")),
    ("STRING_LIT",  re.compile(r'"(?:[^"\\]|\\.)*"')),
    ("ID",          re.compile(r"[A-Za-z_]\w*")),
    # 2-char operators (must precede 1-char)
    ("LE",          re.compile(r"<=")),
    ("GE",          re.compile(r">=")),
    ("EQ",          re.compile(r"==")),
    ("NEQ",         re.compile(r"!=")),
    ("AND",         re.compile(r"&&")),
    ("OR",          re.compile(r"\|\|")),
    ("PLUSPLUS",    re.compile(r"\+\+")),
    ("MINUSMINUS",  re.compile(r"--")),
    # 1-char operators
    ("PLUS",        re.compile(r"\+")),
    ("MINUS",       re.compile(r"-")),
    ("TIMES",       re.compile(r"\*")),
    ("DIVIDE",      re.compile(r"/")),
    ("MOD",         re.compile(r"%")),
    ("LT",          re.compile(r"<")),
    ("GT",          re.compile(r">")),
    ("NOT",         re.compile(r"!")),
    ("ASSIGN",      re.compile(r"=")),
    ("SEMI",        re.compile(r";")),
    ("COMMA",       re.compile(r",")),
    ("LPAREN",      re.compile(r"\(")),
    ("RPAREN",      re.compile(r"\)")),
    ("LBRACE",      re.compile(r"\{")),
    ("RBRACE",      re.compile(r"\}")),
    ("LBRACKET",    re.compile(r"\[")),
    ("RBRACKET",    re.compile(r"\]")),
]

_SKIP = re.compile(r"[ \t\r]+")
_NEWLINE = re.compile(r"\n")
_LINE_COMMENT  = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def tokenize(source: str) -> list[Token]:
    """Return a list of Token objects for the given source string."""
    tokens: list[Token] = []
    pos = 0
    line = 1
    n = len(source)

    while pos < n:
        # Skip whitespace
        m = _SKIP.match(source, pos)
        if m:
            pos = m.end()
            continue

        # Newline
        m = _NEWLINE.match(source, pos)
        if m:
            line += 1
            pos = m.end()
            continue

        # Block comment
        m = _BLOCK_COMMENT.match(source, pos)
        if m:
            line += m.group(0).count("\n")
            pos = m.end()
            continue

        # Line comment
        m = _LINE_COMMENT.match(source, pos)
        if m:
            pos = m.end()
            continue

        matched = False
        for tok_type, pattern in TOKEN_SPEC:
            m = pattern.match(source, pos)
            if m:
                raw = m.group(0)
                if tok_type == "ID" and raw in KEYWORDS:
                    tok_type = raw.upper()   # e.g. "int" → "INT"
                elif tok_type == "INT_LIT":
                    raw = int(raw)
                elif tok_type == "FLOAT_LIT":
                    raw = float(raw)
                elif tok_type == "STRING_LIT":
                    raw = raw[1:-1]          # strip quotes
                tokens.append(Token(tok_type, raw, line))
                pos = m.end()
                matched = True
                break

        if not matched:
            raise LexError(f"Illegal character '{source[pos]}'", line)

    tokens.append(Token("EOF", "", line))
    return tokens
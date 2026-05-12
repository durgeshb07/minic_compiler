"""
lexer.py  —  Mini-C Lexer  (Stage 1)
Produces a list of Token objects and prints a formatted token table.
Integrates fully with the new errors.py diagnostic system.
"""

from __future__ import annotations
import re
import sys
from errors import LexError, ErrorLocation, ErrorReporter, Warnings

# ══════════════════════════════════════════════════════════════════════════════
#  Token
# ══════════════════════════════════════════════════════════════════════════════

class Token:
    __slots__ = ("type", "value", "line", "column", "length")

    def __init__(self, type_: str, value, line: int, column: int, length: int = 1):
        self.type   = type_
        self.value  = value
        self.line   = line
        self.column = column
        self.length = length

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line}, col={self.column})"


# ══════════════════════════════════════════════════════════════════════════════
#  Keyword set
# ══════════════════════════════════════════════════════════════════════════════

KEYWORDS: set[str] = {
    "int", "float", "if", "else", "while", "for", "print", "return",
}

# ══════════════════════════════════════════════════════════════════════════════
#  Token patterns  (order is significant — longer / more specific first)
# ══════════════════════════════════════════════════════════════════════════════

_TOKEN_SPEC: list[tuple[str, re.Pattern]] = [
    # Literals
    ("FLOAT_LIT",    re.compile(r"\d+\.\d+(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+")),
    ("BAD_FLOAT",    re.compile(r"\d+\.\d+\.\d*")),          # e.g. 3.4.5
    ("INT_LIT",      re.compile(r"\d+")),
    ("STRING_LIT",   re.compile(r'"(?:[^"\\]|\\.)*"')),
    ("UNTERM_STR",   re.compile(r'"(?:[^"\\]|\\.)*$', re.MULTILINE)),
    # Identifiers / keywords
    ("ID",           re.compile(r"[A-Za-z_]\w*")),
    # 2-char operators (must precede single-char)
    ("LE",           re.compile(r"<=")),
    ("GE",           re.compile(r">=")),
    ("EQ",           re.compile(r"==")),
    ("NEQ",          re.compile(r"!=")),
    ("AND",          re.compile(r"&&")),
    ("OR",           re.compile(r"\|\|")),
    ("PLUSPLUS",     re.compile(r"\+\+")),
    ("MINUSMINUS",   re.compile(r"--")),
    # 1-char operators
    ("PLUS",         re.compile(r"\+")),
    ("MINUS",        re.compile(r"-")),
    ("TIMES",        re.compile(r"\*")),
    ("DIVIDE",       re.compile(r"/")),
    ("MOD",          re.compile(r"%")),
    ("LT",           re.compile(r"<")),
    ("GT",           re.compile(r">")),
    ("NOT",          re.compile(r"!")),
    ("ASSIGN",       re.compile(r"=")),
    # Punctuation
    ("SEMI",         re.compile(r";")),
    ("COMMA",        re.compile(r",")),
    ("LPAREN",       re.compile(r"\(")),
    ("RPAREN",       re.compile(r"\)")),
    ("LBRACE",       re.compile(r"\{")),
    ("RBRACE",       re.compile(r"\}")),
    ("LBRACKET",     re.compile(r"\[")),
    ("RBRACKET",     re.compile(r"\]")),
]

_SKIP          = re.compile(r"[ \t\r]+")
_NEWLINE       = re.compile(r"\n")
_LINE_COMMENT  = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_UNTERM_BLOCK  = re.compile(r"/\*")
_LEADING_ZERO  = re.compile(r"0\d+")

# ══════════════════════════════════════════════════════════════════════════════
#  Tokenizer
# ══════════════════════════════════════════════════════════════════════════════

INT_MAX =  2_147_483_647
INT_MIN = -2_147_483_648
FLOAT_MAX = 1.7976931348623157e+308

# Valid escape sequences inside string literals
_VALID_ESCAPES = set("ntr\\\"'0")


def _check_string_escapes(
    raw: str,
    line: int,
    col_start: int,
    reporter: ErrorReporter,
):
    """Walk the raw string body and report any unknown escape sequences."""
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw):
            seq = raw[i + 1]
            if seq not in _VALID_ESCAPES:
                reporter.report_exception(
                    LexError.invalid_escape(seq, line, col_start + i + 1)
                )
            i += 2
        else:
            i += 1


def tokenize(
    source: str,
    reporter: ErrorReporter,
    filename: str = "<source>",
) -> list[Token]:
    """
    Tokenise *source* and return a list of Token objects.
    Lexical errors are reported through *reporter* (non-fatal where possible)
    so that we collect as many errors as we can in one pass.
    A final EOF token is always appended.
    """
    tokens: list[Token] = []
    pos   = 0
    line  = 1
    line_start = 0        # byte offset of the current line's first char
    n     = len(source)

    def col_of(p: int) -> int:
        return p - line_start + 1

    while pos < n:

        # ── Whitespace ───────────────────────────────────────────────────────
        m = _SKIP.match(source, pos)
        if m:
            pos = m.end()
            continue

        # ── Newline ──────────────────────────────────────────────────────────
        m = _NEWLINE.match(source, pos)
        if m:
            line += 1
            pos = m.end()
            line_start = pos
            continue

        # ── Block comment ────────────────────────────────────────────────────
        m = _BLOCK_COMMENT.match(source, pos)
        if m:
            line += m.group(0).count("\n")
            pos = m.end()
            continue

        # Unterminated block comment
        m = _UNTERM_BLOCK.match(source, pos)
        if m:
            reporter.report_exception(
                LexError.unterminated_comment(line, col_of(pos))
            )
            pos = n   # consume rest of file — can't recover
            continue

        # ── Line comment ─────────────────────────────────────────────────────
        m = _LINE_COMMENT.match(source, pos)
        if m:
            pos = m.end()
            continue

        # ── Unterminated string (must check BEFORE normal string) ────────────
        m = _UNTERM_STR.match(source, pos) if False else None   # sentinel
        # We handle this inside the STRING_LIT branch below

        matched = False
        for tok_type, pattern in _TOKEN_SPEC:
            m = pattern.match(source, pos)
            if not m:
                continue

            raw    = m.group(0)
            t_col  = col_of(pos)
            t_line = line
            t_len  = len(raw)

            # ── Malformed float ──────────────────────────────────────────────
            if tok_type == "BAD_FLOAT":
                reporter.report_exception(
                    LexError.invalid_number(raw, t_line, t_col)
                )
                pos = m.end()
                matched = True
                break

            # ── Unterminated string ──────────────────────────────────────────
            if tok_type == "UNTERM_STR":
                reporter.report_exception(
                    LexError.unterminated_string(t_line, t_col)
                )
                pos = m.end()
                matched = True
                break

            # ── String literal — check escapes ───────────────────────────────
            if tok_type == "STRING_LIT":
                body = raw[1:-1]
                _check_string_escapes(body, t_line, t_col + 1, reporter)
                value = body
                tokens.append(Token("STRING_LIT", value, t_line, t_col, t_len))
                pos = m.end()
                matched = True
                break

            # ── Integer literal ──────────────────────────────────────────────
            if tok_type == "INT_LIT":
                # Leading-zero warning (looks octal)
                if _LEADING_ZERO.fullmatch(raw):
                    loc = ErrorLocation(line=t_line, column=t_col, length=t_len)
                    reporter.warn(Warnings.leading_zero(raw, loc))
                int_val = int(raw)
                if int_val > INT_MAX:
                    reporter.report_exception(
                        LexError.number_overflow(raw, t_line, t_col)
                    )
                    pos = m.end()
                    matched = True
                    break
                tokens.append(Token("INT_LIT", int_val, t_line, t_col, t_len))
                pos = m.end()
                matched = True
                break

            # ── Float literal ────────────────────────────────────────────────
            if tok_type == "FLOAT_LIT":
                float_val = float(raw)
                import math
                if math.isinf(float_val):
                    reporter.report_exception(
                        LexError.float_overflow(raw, t_line, t_col)
                    )
                    pos = m.end()
                    matched = True
                    break
                tokens.append(Token("FLOAT_LIT", float_val, t_line, t_col, t_len))
                pos = m.end()
                matched = True
                break

            # ── Identifier / keyword ─────────────────────────────────────────
            if tok_type == "ID":
                if raw in KEYWORDS:
                    tok_type = raw.upper()   # "int" → "INT", "while" → "WHILE" …
                tokens.append(Token(tok_type, raw, t_line, t_col, t_len))
                pos = m.end()
                matched = True
                break

            # ── Everything else (operators, punctuation) ─────────────────────
            tokens.append(Token(tok_type, raw, t_line, t_col, t_len))
            pos = m.end()
            matched = True
            break

        if not matched:
            reporter.report_exception(
                LexError.illegal_char(source[pos], line, col_of(pos))
            )
            pos += 1   # skip the bad character and keep going

    tokens.append(Token("EOF", "", line, col_of(pos), 0))
    return tokens


# ══════════════════════════════════════════════════════════════════════════════
#  Token table printer
# ══════════════════════════════════════════════════════════════════════════════

# Column widths
_W = {"#": 5, "type": 16, "value": 22, "line": 6, "col": 6, "length": 8}

_CATEGORY_COLOUR = {
    # Keywords  — cyan
    "INT": "\033[36m", "FLOAT": "\033[36m", "IF": "\033[36m",
    "ELSE": "\033[36m", "WHILE": "\033[36m", "FOR": "\033[36m",
    "PRINT": "\033[36m", "RETURN": "\033[36m",
    # Literals  — yellow
    "INT_LIT": "\033[33m", "FLOAT_LIT": "\033[33m", "STRING_LIT": "\033[33m",
    # Identifiers  — green
    "ID": "\033[32m",
    # Operators  — magenta
    "PLUS": "\033[35m", "MINUS": "\033[35m", "TIMES": "\033[35m",
    "DIVIDE": "\033[35m", "MOD": "\033[35m",
    "LT": "\033[35m", "GT": "\033[35m", "LE": "\033[35m",
    "GE": "\033[35m", "EQ": "\033[35m", "NEQ": "\033[35m",
    "AND": "\033[35m", "OR": "\033[35m", "NOT": "\033[35m",
    "ASSIGN": "\033[35m", "PLUSPLUS": "\033[35m", "MINUSMINUS": "\033[35m",
    # Punctuation  — white / default
}
_RESET = "\033[0m"
_BOLD  = "\033[1m"

_USE_COLOUR = sys.stdout.isatty()


def _cell(text: str, width: int, colour: str = "") -> str:
    s = str(text)
    if len(s) > width - 1:
        s = s[:width - 4] + "..."
    padded = s.ljust(width)
    if colour and _USE_COLOUR:
        return colour + padded + _RESET
    return padded


def print_token_table(tokens: list[Token]) -> None:
    """
    Print a formatted, coloured token table to stdout.

    Example output:
    ═══════════════════════════════════════════════════════════════════
      LEXICAL ANALYSIS — TOKEN TABLE
    ═══════════════════════════════════════════════════════════════════
      #     Type             Value                  Line  Col   Length
    ───────────────────────────────────────────────────────────────────
        0   INT              int                       1    1       3
        1   ID               x                         1    5       1
        2   ASSIGN           =                         1    7       1
        3   INT_LIT          5                         1    9       1
        4   SEMI             ;                         1   10       1
    ...
    ═══════════════════════════════════════════════════════════════════
      10 token(s) produced  (excluding EOF)
    ═══════════════════════════════════════════════════════════════════
    """
    total_w = 5 + 16 + 22 + 6 + 6 + 8 + 6   # columns + separators

    bar     = "═" * total_w
    thin    = "─" * total_w
    indent  = "  "

    print()
    print(indent + bar)
    if _USE_COLOUR:
        print(indent + _BOLD + "  LEXICAL ANALYSIS — TOKEN TABLE" + _RESET)
    else:
        print(indent + "  LEXICAL ANALYSIS — TOKEN TABLE")
    print(indent + bar)

    # Header
    hdr = (
        _cell("#",      _W["#"])
        + _cell("Type",   _W["type"])
        + _cell("Value",  _W["value"])
        + _cell("Line",   _W["line"])
        + _cell("Col",    _W["col"])
        + _cell("Length", _W["length"])
    )
    print(indent + "  " + hdr)
    print(indent + thin)

    # Rows  (skip the EOF sentinel for cleanliness)
    non_eof = [t for t in tokens if t.type != "EOF"]
    for i, tok in enumerate(non_eof):
        colour = _CATEGORY_COLOUR.get(tok.type, "")
        row = (
            _cell(str(i),        _W["#"])
            + _cell(tok.type,    _W["type"],  colour)
            + _cell(repr(tok.value) if isinstance(tok.value, str) else str(tok.value),
                    _W["value"], colour)
            + _cell(tok.line,    _W["line"])
            + _cell(tok.column,  _W["col"])
            + _cell(tok.length,  _W["length"])
        )
        print(indent + "  " + row)

    # Footer
    print(indent + bar)
    count = len(non_eof)
    print(indent + f"  {count} token(s) produced  (excluding EOF)")
    print(indent + bar)
    print()
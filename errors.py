"""
errors.py  —  Comprehensive Error Handling for the Mini-C Compiler

Error hierarchy:
    CompilerError (base)
    ├── LexError          Stage 1: illegal characters, malformed literals
    ├── ParseError        Stage 2: unexpected tokens, missing delimiters
    ├── SemanticError     Stage 3: type mismatches, undeclared vars, etc.
    │   ├── TypeError
    │   ├── UndeclaredError
    │   ├── RedeclarationError
    │   └── ScopeError
    └── IRError           Stage 4: IR generation failures

Supporting classes:
    ErrorLocation         — source position (file, line, column)
    ErrorSeverity         — ERROR / WARNING / NOTE
    DiagnosticMessage     — one formatted diagnostic with caret hint
    ErrorReporter         — collects all diagnostics, decides fatal threshold
"""

from __future__ import annotations

import sys
import textwrap
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  Severity
# ══════════════════════════════════════════════════════════════════════════════

class ErrorSeverity(Enum):
    NOTE    = auto()   # informational hint
    WARNING = auto()   # valid but suspicious
    ERROR   = auto()   # hard error, compilation cannot succeed


# ══════════════════════════════════════════════════════════════════════════════
#  Source location
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ErrorLocation:
    """Pinpoints exactly where in the source an error occurred."""
    line:    int            = 0
    column:  int            = 0
    length:  int            = 1     # token length for the caret span
    source_line: str        = ""    # the raw text of that source line
    filename:    str        = "<source>"

    def __str__(self):
        return f"{self.filename}:{self.line}:{self.column}"

    def caret_hint(self) -> str:
        """
        Produce the GCC/Clang-style source snippet + caret underline:

            int z = x + y;
                        ^~~ type mismatch
        """
        if not self.source_line:
            return ""
        # Clamp column to valid range
        col = max(0, self.column - 1)
        span = max(1, self.length)
        underline = " " * col + "^" + "~" * (span - 1)
        return f"    {self.source_line}\n    {underline}"


# ══════════════════════════════════════════════════════════════════════════════
#  Diagnostic message (one formatted error/warning/note)
# ══════════════════════════════════════════════════════════════════════════════

# ANSI colour codes (disabled automatically when not a TTY)
_USE_COLOUR = sys.stderr.isatty()

_COLOUR = {
    ErrorSeverity.ERROR:   "\033[1;31m",   # bold red
    ErrorSeverity.WARNING: "\033[1;35m",   # bold magenta
    ErrorSeverity.NOTE:    "\033[1;36m",   # bold cyan
}
_RESET   = "\033[0m"
_BOLD    = "\033[1m"


@dataclass
class DiagnosticMessage:
    """
    A single human-readable diagnostic.

    Attributes
    ----------
    severity  : ERROR / WARNING / NOTE
    code      : short machine-readable tag  e.g. "E001", "W003"
    message   : human-readable description
    location  : optional source position
    notes     : supplementary NOTE messages attached to this diagnostic
    hint      : a one-line suggestion to fix the problem
    """
    severity:  ErrorSeverity
    code:      str
    message:   str
    location:  Optional[ErrorLocation] = None
    notes:     list[str]               = field(default_factory=list)
    hint:      Optional[str]           = None

    # ── Formatting ──────────────────────────────────────────────────────────

    def format(self, *, colour: bool = True) -> str:
        use_col = colour and _USE_COLOUR
        lines: list[str] = []

        # Header line:  path:line:col: severity[code]: message
        sev_name = self.severity.name.lower()
        if use_col:
            sev_str = _COLOUR[self.severity] + sev_name + _RESET
            code_str = f"[{_BOLD}{self.code}{_RESET}]"
            msg_str  = _BOLD + self.message + _RESET
        else:
            sev_str  = sev_name
            code_str = f"[{self.code}]"
            msg_str  = self.message

        loc_str = str(self.location) if self.location else "<unknown>"
        lines.append(f"{loc_str}: {sev_str} {code_str}: {msg_str}")

        # Source snippet + caret
        if self.location:
            hint = self.location.caret_hint()
            if hint:
                lines.append(hint)

        # Fix hint
        if self.hint:
            prefix = "    hint: " if not use_col else f"    {_BOLD}hint{_RESET}: "
            lines.append(prefix + self.hint)

        # Attached notes
        for note in self.notes:
            prefix = "    note: " if not use_col else f"    {_BOLD}note{_RESET}: "
            lines.append(prefix + note)

        return "\n".join(lines)

    def __str__(self):
        return self.format()


# ══════════════════════════════════════════════════════════════════════════════
#  Error codes catalogue
# ══════════════════════════════════════════════════════════════════════════════

class ErrorCode:
    """
    All Mini-C diagnostic codes in one place.
    Naming convention:
        E   = hard error
        W   = warning
        L   = lexical stage
        P   = parse stage
        S   = semantic stage
        I   = IR stage
    """

    # ── Lexical ─────────────────────────────────────────────────────────────
    ILLEGAL_CHAR          = "EL001"   # character not in language alphabet
    UNTERMINATED_STRING   = "EL002"   # string literal never closed
    UNTERMINATED_COMMENT  = "EL003"   # block comment never closed
    INVALID_NUMBER        = "EL004"   # malformed numeric literal (e.g. 3.4.5)
    INVALID_ESCAPE        = "EL005"   # unknown escape sequence in string literal
    LEADING_ZERO          = "WL006"   # octal-style literal  (warning only)
    NUMBER_TOO_LARGE      = "EL007"   # integer overflow
    FLOAT_TOO_LARGE       = "EL008"   # float overflow / infinity

    # ── Parse ────────────────────────────────────────────────────────────────
    UNEXPECTED_TOKEN      = "EP001"   # got X, expected Y
    MISSING_SEMI          = "EP002"   # missing semicolon
    MISSING_RPAREN        = "EP003"   # unmatched (
    MISSING_RBRACE        = "EP004"   # unmatched {
    MISSING_RBRACKET      = "EP005"   # unmatched [
    EMPTY_EXPRESSION      = "EP006"   # expression expected but got ;
    INVALID_LVALUE        = "EP007"   # assignment to non-lvalue
    BAD_ARRAY_SIZE        = "EP008"   # array size is not a positive integer literal
    MISSING_CONDITION     = "EP009"   # if/while/for has no condition
    ELSE_WITHOUT_IF       = "EP010"   # dangling else

    # ── Semantic ─────────────────────────────────────────────────────────────
    UNDECLARED_VAR        = "ES001"   # variable used before declaration
    REDECLARED_VAR        = "ES002"   # variable declared twice in same scope
    TYPE_MISMATCH_ASSIGN  = "ES003"   # incompatible types in assignment
    TYPE_MISMATCH_OP      = "ES004"   # incompatible types in binary expression
    TYPE_MISMATCH_RETURN  = "ES005"   # return type doesn't match function type
    TYPE_MISMATCH_ARG     = "ES006"   # wrong argument type in function call
    NOT_AN_ARRAY          = "ES007"   # subscript applied to a non-array
    ARRAY_INDEX_FLOAT     = "ES008"   # array index is float, not int
    ARRAY_INDEX_NEGATIVE  = "WS009"   # array index is a negative constant (warning)
    ARRAY_INDEX_OOB       = "WS010"   # constant index >= declared size (warning)
    ZERO_SIZE_ARRAY       = "ES011"   # array declared with size 0
    NEGATIVE_ARRAY_SIZE   = "ES012"   # array declared with negative size
    NARROWING_CONVERSION  = "WS013"   # float assigned to int (data loss, warning)
    UNINITIALISED_USE     = "WS014"   # variable used before being initialised
    DEAD_CODE_AFTER_RET   = "WS015"   # statements after return
    UNUSED_VARIABLE       = "WS016"   # declared but never read
    DIVISION_BY_ZERO      = "WS017"   # constant division by zero (warning)
    PRINT_VOID            = "ES018"   # print() called with no-value expression

    # ── IR ───────────────────────────────────────────────────────────────────
    IR_INTERNAL_ERROR     = "EI001"   # unexpected AST node type during IR gen


# ══════════════════════════════════════════════════════════════════════════════
#  Base exception class
# ══════════════════════════════════════════════════════════════════════════════

class CompilerError(Exception):
    """
    Base class for all Mini-C compiler exceptions.

    Parameters
    ----------
    message  : human-readable description
    line     : source line number (1-based)
    column   : source column number (1-based)
    code     : error code from ErrorCode catalogue
    hint     : suggested fix shown to the user
    location : full ErrorLocation (overrides line/column if given)
    """

    def __init__(
        self,
        message:  str,
        line:     Optional[int]           = None,
        column:   Optional[int]           = None,
        code:     str                     = "E000",
        hint:     Optional[str]           = None,
        location: Optional[ErrorLocation] = None,
    ):
        self.code    = code
        self.hint    = hint

        # Build / normalise location
        if location is not None:
            self.location = location
        else:
            self.location = ErrorLocation(
                line   = line   or 0,
                column = column or 0,
            )

        # Friendly string used by str(exception)
        loc_str = f" [line {self.location.line}]" if self.location.line else ""
        super().__init__(f"{code}: {message}{loc_str}")

    # Convenience properties
    @property
    def line(self):
        return self.location.line

    @property
    def column(self):
        return self.location.column

    def to_diagnostic(self, severity=ErrorSeverity.ERROR) -> DiagnosticMessage:
        return DiagnosticMessage(
            severity = severity,
            code     = self.code,
            message  = self.args[0].split(": ", 1)[-1],   # strip "CODE: "
            location = self.location,
            hint     = self.hint,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Stage-specific exception subclasses
# ══════════════════════════════════════════════════════════════════════════════

class LexError(CompilerError):
    """
    Raised during Stage 1 (Lexical Analysis).

    Factory class-methods cover every distinct lexical failure:
        LexError.illegal_char(ch, line, col)
        LexError.unterminated_string(line, col)
        LexError.unterminated_comment(line, col)
        LexError.invalid_number(text, line, col)
        LexError.invalid_escape(seq, line, col)
        LexError.number_overflow(text, line, col)
        LexError.float_overflow(text, line, col)
    """

    @classmethod
    def illegal_char(cls, char: str, line: int, col: int) -> "LexError":
        printable = repr(char)
        return cls(
            message  = f"illegal character {printable}",
            line     = line,
            column   = col,
            code     = ErrorCode.ILLEGAL_CHAR,
            hint     = (
                f"Remove or replace {printable}. "
                "Mini-C only accepts ASCII letters, digits, and standard operators."
            ),
        )

    @classmethod
    def unterminated_string(cls, line: int, col: int) -> "LexError":
        return cls(
            message  = "unterminated string literal — missing closing '\"'",
            line     = line,
            column   = col,
            code     = ErrorCode.UNTERMINATED_STRING,
            hint     = 'Add a closing double-quote (\") at the end of the string.',
        )

    @classmethod
    def unterminated_comment(cls, line: int, col: int) -> "LexError":
        return cls(
            message  = "unterminated block comment — missing closing '*/'",
            line     = line,
            column   = col,
            code     = ErrorCode.UNTERMINATED_COMMENT,
            hint     = "Add */ to close the block comment.",
        )

    @classmethod
    def invalid_number(cls, text: str, line: int, col: int) -> "LexError":
        return cls(
            message  = f"malformed numeric literal '{text}'",
            line     = line,
            column   = col,
            code     = ErrorCode.INVALID_NUMBER,
            hint     = "A float must have at most one decimal point, e.g. 3.14.",
        )

    @classmethod
    def invalid_escape(cls, seq: str, line: int, col: int) -> "LexError":
        return cls(
            message  = f"unknown escape sequence '\\{seq}' in string literal",
            line     = line,
            column   = col,
            code     = ErrorCode.INVALID_ESCAPE,
            hint     = r"Valid escapes: \n  \t  \r  \\  \"",
        )

    @classmethod
    def number_overflow(cls, text: str, line: int, col: int) -> "LexError":
        return cls(
            message  = f"integer literal '{text}' overflows int (max 2^31-1 = 2147483647)",
            line     = line,
            column   = col,
            code     = ErrorCode.NUMBER_TOO_LARGE,
            hint     = "Use a smaller value, or declare the variable as float.",
        )

    @classmethod
    def float_overflow(cls, text: str, line: int, col: int) -> "LexError":
        return cls(
            message  = f"float literal '{text}' is too large (overflows IEEE 754 double)",
            line     = line,
            column   = col,
            code     = ErrorCode.FLOAT_TOO_LARGE,
            hint     = "Use a value within the range of IEEE 754 double precision.",
        )


# ── Parse errors ─────────────────────────────────────────────────────────────

class ParseError(CompilerError):
    """
    Raised during Stage 2 (Syntax Analysis).

    Factory methods:
        ParseError.unexpected(got, expected, line, col)
        ParseError.missing_semi(line, col)
        ParseError.unmatched(opener, line, col)
        ParseError.empty_expression(line, col)
        ParseError.invalid_lvalue(expr_str, line, col)
        ParseError.bad_array_size(value, line, col)
        ParseError.missing_condition(keyword, line, col)
        ParseError.dangling_else(line, col)
    """

    @classmethod
    def unexpected(
        cls,
        got:      str,
        expected: str | list[str],
        line:     int,
        col:      int = 0,
    ) -> "ParseError":
        if isinstance(expected, list):
            exp_str = ", ".join(f"'{e}'" for e in expected)
            exp_str = f"one of {exp_str}"
        else:
            exp_str = f"'{expected}'"
        return cls(
            message = f"unexpected token '{got}' — expected {exp_str}",
            line    = line,
            column  = col,
            code    = ErrorCode.UNEXPECTED_TOKEN,
            hint    = f"Insert or replace the token so that {exp_str} appears here.",
        )

    @classmethod
    def missing_semi(cls, line: int, col: int = 0) -> "ParseError":
        return cls(
            message = "missing ';' at end of statement",
            line    = line,
            column  = col,
            code    = ErrorCode.MISSING_SEMI,
            hint    = "Add a semicolon ';' to terminate the statement.",
        )

    @classmethod
    def unmatched(cls, opener: str, line: int, col: int = 0) -> "ParseError":
        pairs = {"(": ")", "{": "}", "[": "]"}
        closer = pairs.get(opener, "?")
        codes  = {"(": ErrorCode.MISSING_RPAREN,
                  "{": ErrorCode.MISSING_RBRACE,
                  "[": ErrorCode.MISSING_RBRACKET}
        return cls(
            message = f"unmatched '{opener}' — missing closing '{closer}'",
            line    = line,
            column  = col,
            code    = codes.get(opener, ErrorCode.UNEXPECTED_TOKEN),
            hint    = f"Add '{closer}' to close the '{opener}' opened on line {line}.",
        )

    @classmethod
    def empty_expression(cls, line: int, col: int = 0) -> "ParseError":
        return cls(
            message = "expression expected but got ';' or end of input",
            line    = line,
            column  = col,
            code    = ErrorCode.EMPTY_EXPRESSION,
            hint    = "Provide a valid expression here.",
        )

    @classmethod
    def invalid_lvalue(cls, expr_str: str, line: int, col: int = 0) -> "ParseError":
        return cls(
            message = f"invalid assignment target '{expr_str}' — not an lvalue",
            line    = line,
            column  = col,
            code    = ErrorCode.INVALID_LVALUE,
            hint    = "Only variables and array elements can be assigned to.",
        )

    @classmethod
    def bad_array_size(cls, value, line: int, col: int = 0) -> "ParseError":
        return cls(
            message = f"array size must be a positive integer literal, got '{value}'",
            line    = line,
            column  = col,
            code    = ErrorCode.BAD_ARRAY_SIZE,
            hint    = "Use a constant positive integer, e.g. int arr[10];",
        )

    @classmethod
    def missing_condition(cls, keyword: str, line: int, col: int = 0) -> "ParseError":
        return cls(
            message = f"'{keyword}' statement requires a condition in parentheses",
            line    = line,
            column  = col,
            code    = ErrorCode.MISSING_CONDITION,
            hint    = f"Add a condition: {keyword} (condition) {{ ... }}",
        )

    @classmethod
    def dangling_else(cls, line: int, col: int = 0) -> "ParseError":
        return cls(
            message = "'else' without a preceding 'if'",
            line    = line,
            column  = col,
            code    = ErrorCode.ELSE_WITHOUT_IF,
            hint    = "Make sure every 'else' is paired with an 'if'.",
        )


# ── Semantic errors ───────────────────────────────────────────────────────────

class SemanticError(CompilerError):
    """
    Base class for Stage 3 (Semantic Analysis) errors.
    Prefer the specialised subclasses below for richer messages.
    """


class TypeError_(SemanticError):
    """
    Type-related semantic errors.

    Factory methods:
        TypeError_.assign_mismatch(ltype, rtype, varname, line)
        TypeError_.op_mismatch(op, ltype, rtype, line)
        TypeError_.narrowing(from_type, to_type, varname, line)
        TypeError_.array_float_index(varname, line)
        TypeError_.print_void(line)
        TypeError_.return_mismatch(expected, got, line)
        TypeError_.arg_mismatch(func, param, expected, got, line)
    """

    @classmethod
    def assign_mismatch(
        cls,
        ltype:   str,
        rtype:   str,
        varname: str,
        line:    int,
        col:     int = 0,
    ) -> "TypeError_":
        return cls(
            message = (
                f"cannot assign '{rtype}' expression to '{ltype}' variable '{varname}'"
            ),
            line    = line,
            column  = col,
            code    = ErrorCode.TYPE_MISMATCH_ASSIGN,
            hint    = (
                f"Cast the right-hand side to '{ltype}', "
                f"or change '{varname}' to '{rtype}'."
            ),
        )

    @classmethod
    def op_mismatch(
        cls,
        op:    str,
        ltype: str,
        rtype: str,
        line:  int,
        col:   int = 0,
    ) -> "TypeError_":
        return cls(
            message = (
                f"operator '{op}' cannot be applied to '{ltype}' and '{rtype}'"
            ),
            line    = line,
            column  = col,
            code    = ErrorCode.TYPE_MISMATCH_OP,
            hint    = "Ensure both operands have compatible types.",
        )

    @classmethod
    def narrowing(
        cls,
        from_type: str,
        to_type:   str,
        varname:   str,
        line:      int,
        col:       int = 0,
    ) -> "TypeError_":
        return cls(
            message = (
                f"implicit narrowing conversion from '{from_type}' to '{to_type}' "
                f"in assignment to '{varname}' — possible data loss"
            ),
            line    = line,
            column  = col,
            code    = ErrorCode.NARROWING_CONVERSION,
            hint    = f"Declare '{varname}' as 'float', or explicitly truncate the value.",
        )

    @classmethod
    def array_float_index(cls, varname: str, line: int, col: int = 0) -> "TypeError_":
        return cls(
            message = f"array index for '{varname}' must be an integer, not float",
            line    = line,
            column  = col,
            code    = ErrorCode.ARRAY_INDEX_FLOAT,
            hint    = "Convert the index expression to int, e.g. use an int variable.",
        )

    @classmethod
    def print_void(cls, line: int, col: int = 0) -> "TypeError_":
        return cls(
            message = "print() argument has no value (void expression)",
            line    = line,
            column  = col,
            code    = ErrorCode.PRINT_VOID,
            hint    = "Pass a variable or arithmetic expression to print().",
        )

    @classmethod
    def return_mismatch(
        cls,
        expected: str,
        got:      str,
        line:     int,
        col:      int = 0,
    ) -> "TypeError_":
        return cls(
            message = (
                f"return type mismatch — function expects '{expected}', "
                f"got '{got}'"
            ),
            line    = line,
            column  = col,
            code    = ErrorCode.TYPE_MISMATCH_RETURN,
            hint    = f"Change the return expression to produce a '{expected}' value.",
        )

    @classmethod
    def arg_mismatch(
        cls,
        func:     str,
        param:    str,
        expected: str,
        got:      str,
        line:     int,
        col:      int = 0,
    ) -> "TypeError_":
        return cls(
            message = (
                f"argument '{param}' of '{func}()' expects '{expected}', got '{got}'"
            ),
            line    = line,
            column  = col,
            code    = ErrorCode.TYPE_MISMATCH_ARG,
            hint    = f"Pass a '{expected}' value for parameter '{param}'.",
        )


class UndeclaredError(SemanticError):
    """Used when a name is referenced before being declared."""

    @classmethod
    def variable(cls, name: str, line: int, col: int = 0) -> "UndeclaredError":
        return cls(
            message = f"use of undeclared variable '{name}'",
            line    = line,
            column  = col,
            code    = ErrorCode.UNDECLARED_VAR,
            hint    = f"Declare '{name}' before using it, e.g. 'int {name};'",
        )

    @classmethod
    def array(cls, name: str, line: int, col: int = 0) -> "UndeclaredError":
        return cls(
            message = f"use of undeclared array '{name}'",
            line    = line,
            column  = col,
            code    = ErrorCode.UNDECLARED_VAR,
            hint    = f"Declare '{name}' before using it, e.g. 'int {name}[N];'",
        )


class RedeclarationError(SemanticError):
    """Used when a name is declared more than once in the same scope."""

    @classmethod
    def variable(
        cls,
        name:       str,
        first_line: int,
        second_line: int,
        col:        int = 0,
    ) -> "RedeclarationError":
        e = cls(
            message = f"'{name}' already declared in this scope",
            line    = second_line,
            column  = col,
            code    = ErrorCode.REDECLARED_VAR,
            hint    = (
                f"Remove the second declaration of '{name}', "
                "or rename one of them."
            ),
        )
        e.to_diagnostic().notes.append(
            f"'{name}' was first declared on line {first_line}"
        )
        return e


class ScopeError(SemanticError):
    """Miscellaneous scope-related errors."""

    @classmethod
    def subscript_non_array(cls, name: str, dtype: str, line: int, col: int = 0) -> "ScopeError":
        return cls(
            message = f"'{name}' is of type '{dtype}', not an array — cannot subscript",
            line    = line,
            column  = col,
            code    = ErrorCode.NOT_AN_ARRAY,
            hint    = f"Remove the '[...]', or re-declare '{name}' as an array.",
        )

    @classmethod
    def zero_size_array(cls, name: str, line: int, col: int = 0) -> "ScopeError":
        return cls(
            message = f"array '{name}' declared with size 0",
            line    = line,
            column  = col,
            code    = ErrorCode.ZERO_SIZE_ARRAY,
            hint    = "Array size must be a positive integer greater than 0.",
        )

    @classmethod
    def negative_array_size(cls, name: str, size: int, line: int, col: int = 0) -> "ScopeError":
        return cls(
            message = f"array '{name}' declared with negative size {size}",
            line    = line,
            column  = col,
            code    = ErrorCode.NEGATIVE_ARRAY_SIZE,
            hint    = "Array size must be a positive integer.",
        )


# ── IR errors ─────────────────────────────────────────────────────────────────

class IRError(CompilerError):
    """Raised during Stage 4 (IR Generation) for unexpected AST structures."""

    @classmethod
    def unknown_node(cls, node_type: str, line: int = 0) -> "IRError":
        return cls(
            message = f"IR generator encountered unknown AST node type '{node_type}'",
            line    = line,
            code    = ErrorCode.IR_INTERNAL_ERROR,
            hint    = "This is a compiler-internal error. Check the parser output.",
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Compiler-wide warnings (non-fatal DiagnosticMessages, not exceptions)
# ══════════════════════════════════════════════════════════════════════════════

class Warnings:
    """
    Factory for WARNING-level DiagnosticMessages.
    These are collected by ErrorReporter rather than raised as exceptions.
    """

    @staticmethod
    def narrowing_conversion(
        from_type: str,
        to_type:   str,
        varname:   str,
        loc:       ErrorLocation,
    ) -> DiagnosticMessage:
        return DiagnosticMessage(
            severity = ErrorSeverity.WARNING,
            code     = ErrorCode.NARROWING_CONVERSION,
            message  = (
                f"implicit narrowing from '{from_type}' to '{to_type}' "
                f"in assignment to '{varname}'"
            ),
            location = loc,
            hint     = f"Declare '{varname}' as float, or cast explicitly.",
        )

    @staticmethod
    def uninitialised_use(name: str, loc: ErrorLocation) -> DiagnosticMessage:
        return DiagnosticMessage(
            severity = ErrorSeverity.WARNING,
            code     = ErrorCode.UNINITIALISED_USE,
            message  = f"variable '{name}' may be used before being initialised",
            location = loc,
            hint     = f"Assign a value to '{name}' before reading it.",
        )

    @staticmethod
    def unused_variable(name: str, loc: ErrorLocation) -> DiagnosticMessage:
        return DiagnosticMessage(
            severity = ErrorSeverity.WARNING,
            code     = ErrorCode.UNUSED_VARIABLE,
            message  = f"variable '{name}' is declared but never used",
            location = loc,
            hint     = f"Remove the declaration of '{name}' or use its value.",
        )

    @staticmethod
    def dead_code_after_return(loc: ErrorLocation) -> DiagnosticMessage:
        return DiagnosticMessage(
            severity = ErrorSeverity.WARNING,
            code     = ErrorCode.DEAD_CODE_AFTER_RET,
            message  = "unreachable code after 'return' statement",
            location = loc,
            hint     = "Remove or restructure the code that follows 'return'.",
        )

    @staticmethod
    def division_by_zero(loc: ErrorLocation) -> DiagnosticMessage:
        return DiagnosticMessage(
            severity = ErrorSeverity.WARNING,
            code     = ErrorCode.DIVISION_BY_ZERO,
            message  = "division by zero constant detected",
            location = loc,
            hint     = "Ensure the divisor is never zero.",
        )

    @staticmethod
    def array_index_oob(name: str, index: int, size: int, loc: ErrorLocation) -> DiagnosticMessage:
        return DiagnosticMessage(
            severity = ErrorSeverity.WARNING,
            code     = ErrorCode.ARRAY_INDEX_OOB,
            message  = (
                f"constant index {index} is out of bounds for "
                f"'{name}[{size}]' (valid range: 0..{size-1})"
            ),
            location = loc,
            hint     = f"Use an index between 0 and {size - 1}.",
        )

    @staticmethod
    def leading_zero(text: str, loc: ErrorLocation) -> DiagnosticMessage:
        return DiagnosticMessage(
            severity = ErrorSeverity.WARNING,
            code     = ErrorCode.LEADING_ZERO,
            message  = f"integer literal '{text}' has a leading zero (looks like octal — Mini-C treats it as decimal)",
            location = loc,
            hint     = f"Write '{int(text)}' to silence this warning.",
        )


# ══════════════════════════════════════════════════════════════════════════════
#  ErrorReporter — collects all diagnostics, prints a final summary
# ══════════════════════════════════════════════════════════════════════════════

class ErrorReporter:
    """
    Central diagnostics bus used by all compiler stages.

    Usage
    -----
    reporter = ErrorReporter(source_lines)

    # From any stage — report a caught exception:
    try:
        ...
    except CompilerError as e:
        reporter.report_exception(e)

    # Or report a pre-built diagnostic directly:
    reporter.report(Warnings.unused_variable("x", loc))

    # At the end of each stage:
    reporter.raise_if_errors()   # stops compilation if hard errors exist

    # Final summary:
    reporter.print_summary()
    """

    def __init__(
        self,
        source_lines: list[str] | None = None,
        filename:     str               = "<source>",
        fatal_threshold: int            = 1,     # stop after this many errors
    ):
        self._source    = source_lines or []
        self._filename  = filename
        self._threshold = fatal_threshold
        self._diags:    list[DiagnosticMessage] = []

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _enrich_location(self, loc: ErrorLocation) -> ErrorLocation:
        """Attach the source text for the caret hint if not already present."""
        if not loc.source_line and self._source and loc.line:
            idx = loc.line - 1
            if 0 <= idx < len(self._source):
                loc = ErrorLocation(
                    line        = loc.line,
                    column      = loc.column,
                    length      = loc.length,
                    source_line = self._source[idx].rstrip("\n"),
                    filename    = self._filename,
                )
        return loc

    # ── Public API ────────────────────────────────────────────────────────────

    def report(self, diag: DiagnosticMessage) -> None:
        """Add a pre-built diagnostic."""
        if diag.location:
            diag.location = self._enrich_location(diag.location)
        self._diags.append(diag)
        print(diag.format(), file=sys.stderr)
        print(file=sys.stderr)

    def report_exception(
        self,
        exc:      CompilerError,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
    ) -> None:
        """Convert a caught CompilerError into a diagnostic and record it."""
        loc = self._enrich_location(exc.location)
        diag = DiagnosticMessage(
            severity = severity,
            code     = exc.code,
            message  = str(exc).split(": ", 1)[-1],
            location = loc,
            hint     = exc.hint,
        )
        self._diags.append(diag)
        print(diag.format(), file=sys.stderr)
        print(file=sys.stderr)

    def warn(self, diag: DiagnosticMessage) -> None:
        """Convenience wrapper — same as report() but documents intent."""
        self.report(diag)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self._diags if d.severity == ErrorSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self._diags if d.severity == ErrorSeverity.WARNING)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    def raise_if_errors(self) -> None:
        """
        If any hard errors have been collected, raise a CompilerError
        summarising the count so the driver can stop the pipeline.
        """
        if self.error_count >= self._threshold:
            raise CompilerError(
                f"compilation aborted — "
                f"{self.error_count} error(s), {self.warning_count} warning(s)"
            )

    def print_summary(self) -> None:
        """Print the final error/warning tally."""
        ec = self.error_count
        wc = self.warning_count
        if ec == 0 and wc == 0:
            print("Compilation successful — no errors or warnings.", file=sys.stderr)
        else:
            parts = []
            if ec:
                parts.append(f"{ec} error{'s' if ec != 1 else ''}")
            if wc:
                parts.append(f"{wc} warning{'s' if wc != 1 else ''}")
            status = "failed" if ec else "succeeded with warnings"
            print(
                f"Compilation {status}: {', '.join(parts)}.",
                file=sys.stderr,
            )

    def all_diagnostics(self) -> list[DiagnosticMessage]:
        return list(self._diags)
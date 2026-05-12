"""
main.py  —  Mini-C Compiler Driver

Usage:
    python3 main.py <source.mc> [--ast] [--quads] [--no-tac]

Flags:
    --ast      Print the Abstract Syntax Tree after parsing
    --quads    Print the raw quadruple table as well as the TAC listing
    --no-tac   Skip the TAC display (still writes the .tac file)

Pipeline:
    1. Lexical Analysis   → token list  + token table printed
    2. Syntax Analysis    → AST
    3. Semantic Analysis  → symbol table  (errors collected via ErrorReporter)
    4. IR Generation      → TAC / quadruples
"""

from __future__ import annotations
import sys
import os

from errors   import ErrorReporter, CompilerError
from lexer    import tokenize, print_token_table
from parser   import Parser, print_ast
from semantic import SymbolTable, SemanticAnalyser
from ir_gen   import IRGenerator


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _banner(title: str, width: int = 64) -> None:
    bar = "═" * width
    print()
    print(bar)
    print(f"  {title}")
    print(bar)


def _stage_header(number: int, name: str) -> None:
    print(f"\n[ Stage {number} ]  {name} …")


def _stage_ok(detail: str = "") -> None:
    tick = "  ✓"
    print(f"{tick}  {detail}" if detail else tick)


# ══════════════════════════════════════════════════════════════════════════════
#  Compiler pipeline
# ══════════════════════════════════════════════════════════════════════════════

def compile_file(path: str, *, show_ast: bool, show_quads: bool, show_tac: bool) -> None:

    # ── Read source ──────────────────────────────────────────────────────────
    if not os.path.isfile(path):
        print(f"Error: file '{path}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        source = f.read()

    source_lines = source.splitlines()
    filename     = os.path.basename(path)

    _banner(f"Mini-C Compiler  —  {filename}")

    # Shared reporter (used by ALL stages)
    reporter = ErrorReporter(
        source_lines     = source_lines,
        filename         = filename,
        fatal_threshold  = 1,       # stop pipeline on first hard error
    )

    # ════════════════════════════════════════════════════════════════════════
    #  Stage 1 — Lexical Analysis
    # ════════════════════════════════════════════════════════════════════════
    _stage_header(1, "Lexical Analysis")

    tokens = tokenize(source, reporter, filename)

    # Always print the token table immediately after lexing
    print_token_table(tokens)

    # Stop if there were lex errors
    try:
        reporter.raise_if_errors()
    except CompilerError as e:
        print(f"\n  Lexical analysis failed: {e}", file=sys.stderr)
        reporter.print_summary()
        sys.exit(1)

    non_eof = [t for t in tokens if t.type != "EOF"]
    _stage_ok(f"{len(non_eof)} token(s) produced")

    # ════════════════════════════════════════════════════════════════════════
    #  Stage 2 — Syntax Analysis
    # ════════════════════════════════════════════════════════════════════════
    _stage_header(2, "Syntax Analysis (Parsing)")

    try:
        parser = Parser(tokens)
        ast    = parser.parse_program()
    except CompilerError as e:
        reporter.report_exception(e)
        reporter.print_summary()
        sys.exit(1)

    _stage_ok("AST constructed successfully")

    if show_ast:
        _banner("ABSTRACT SYNTAX TREE")
        print_ast(ast)

    # ════════════════════════════════════════════════════════════════════════
    #  Stage 3 — Semantic Analysis
    # ════════════════════════════════════════════════════════════════════════
    _stage_header(3, "Semantic Analysis")

    sym_table = SymbolTable()
    analyser  = SemanticAnalyser(sym_table, reporter)
    analyser.analyse(ast)

    # Always print the symbol table
    sym_table.display()

    try:
        reporter.raise_if_errors()
    except CompilerError as e:
        print(f"  Semantic analysis failed — see errors above.", file=sys.stderr)
        reporter.print_summary()
        sys.exit(1)

    _stage_ok("No semantic errors")

    # ════════════════════════════════════════════════════════════════════════
    #  Stage 4 — IR Generation
    # ════════════════════════════════════════════════════════════════════════
    _stage_header(4, "Intermediate Representation (TAC) Generation")

    ir = IRGenerator(reporter)
    ir.generate(ast)

    try:
        reporter.raise_if_errors()
    except CompilerError as e:
        print(f"  IR generation failed — see errors above.", file=sys.stderr)
        reporter.print_summary()
        sys.exit(1)

    if show_tac:
        ir.display_tac()

    if show_quads:
        ir.display_quads()

    # Write TAC to file
    tac_path = path.rsplit(".", 1)[0] + ".tac"
    ir.write_tac_file(tac_path)

    _stage_ok(f"{len(ir.quads)} quadruple(s) generated")

    # ════════════════════════════════════════════════════════════════════════
    #  Final summary
    # ════════════════════════════════════════════════════════════════════════
    reporter.print_summary()
    print()


# ══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    args = sys.argv[1:]

    if not args or args[0].startswith("--"):
        print("Usage: python3 main.py <source.mc> [--ast] [--quads] [--no-tac]")
        print()
        print("  --ast      Print the Abstract Syntax Tree")
        print("  --quads    Print raw quadruple table (alongside TAC)")
        print("  --no-tac   Suppress the TAC listing (file still written)")
        sys.exit(0)

    source_path = args[0]
    show_ast    = "--ast"    in args
    show_quads  = "--quads"  in args
    show_tac    = "--no-tac" not in args

    compile_file(
        source_path,
        show_ast   = show_ast,
        show_quads = show_quads,
        show_tac   = show_tac,
    )


if __name__ == "__main__":
    main()
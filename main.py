"""
main.py  —  Mini-C Compiler Driver
Usage:
    python3 main.py <source_file.mc>
    python3 main.py test_program.mc
"""

import sys

from lexer    import tokenize
from parser   import Parser
from semantic import SymbolTable, SemanticAnalyser
from ir_gen   import IRGenerator
from errors   import LexError, ParseError, SemanticError


def compile_file(path: str):
    # ── Read source ──────────────────────────────────────────────────────────
    try:
        with open(path) as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: file '{path}' not found.")
        sys.exit(1)

    print(f"\n{'═'*60}")
    print(f"  Mini-C Compiler  —  {path}")
    print(f"{'═'*60}\n")

    # ── Stage 1: Lexical Analysis ────────────────────────────────────────────
    print("[ Stage 1 ] Lexical Analysis …")
    try:
        tokens = tokenize(source)
    except LexError as e:
        print(f"  {e}")
        sys.exit(1)

    print(f"  {len(tokens)-1} token(s) produced.\n")

    # ── Stage 2: Syntax Analysis ─────────────────────────────────────────────
    print("[ Stage 2 ] Syntax Analysis (parsing) …")
    try:
        parser = Parser(tokens)
        ast    = parser.parse_program()
    except ParseError as e:
        print(f"  {e}")
        sys.exit(1)

    print("  Parse successful — AST constructed.\n")

    # Optional: print AST
    if "--ast" in sys.argv:
        _print_ast(ast)

    # ── Stage 3: Semantic Analysis ───────────────────────────────────────────
    print("[ Stage 3 ] Semantic Analysis …")
    sym_table = SymbolTable()
    analyser  = SemanticAnalyser(sym_table)
    analyser.analyse(ast)

    sym_table.display()

    if analyser.errors:
        print("  Semantic errors detected:")
        for err in analyser.errors:
            print(err)
        print()
        # Print errors but continue to IR so partial output is still useful
        # (remove 'sys.exit(1)' to suppress hard stop on semantic errors)
        sys.exit(1)
    else:
        print("  No semantic errors.\n")

    # ── Stage 4: IR Generation ────────────────────────────────────────────────
    print("[ Stage 4 ] Generating Intermediate Representation (TAC) …")
    ir = IRGenerator()
    ir.generate(ast)

    ir.display()
    ir.display_quads()

    # Optionally write TAC to a file
    tac_path = path.replace(".mc", ".tac")
    with open(tac_path, "w") as f:
        f.write("Three-Address Code\n")
        f.write("=" * 50 + "\n")
        for q in ir.quads:
            f.write(q.pretty().strip() + "\n")
    print(f"  TAC written to '{tac_path}'.\n")

    print("  Compilation complete ✓\n")


def _print_ast(node, depth=0):
    if not isinstance(node, dict):
        return
    pad = "  " * depth
    t = node.get("type", "?")
    extras = []
    for k in ("name", "dtype", "op", "value", "size"):
        if k in node:
            extras.append(f"{k}={node[k]!r}")
    print(f"{pad}{t}({', '.join(extras)})")
    for k in ("body", "then", "els", "cond", "init", "update",
              "left", "right", "expr", "arg", "val", "index"):
        child = node.get(k)
        if child is None:
            continue
        if isinstance(child, list):
            for c in child:
                _print_ast(c, depth + 1)
        else:
            _print_ast(child, depth + 1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 main.py <source.mc> [--ast]")
        sys.exit(1)
    compile_file(sys.argv[1])
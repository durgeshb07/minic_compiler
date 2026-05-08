"""Custom exceptions for the Mini-C compiler."""

class CompilerError(Exception):
    def __init__(self, message, line=None):
        self.line = line
        loc = f" [line {line}]" if line else ""
        super().__init__(f"{message}{loc}")

class LexError(CompilerError):    pass
class ParseError(CompilerError):  pass
class SemanticError(CompilerError): pass
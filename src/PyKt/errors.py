# -*- coding: utf-8 -*-
"""Error classes for the PyKt language interpreter.

Provides a hierarchy of exceptions with source location information
(filename, line, column) for clear error reporting.
"""


class PktError(Exception):
    """Base exception for all PyKt language errors.

    Attributes:
        message: Human-readable error description.
        line: 1-based line number in the source (or None if unknown).
        column: 1-based column number in the source (or None if unknown).
        filename: Path to the source file (or None if stdin/unknown).
    """

    def __init__(self, message, line=None, column=None, filename=None):
        super(PktError, self).__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.filename = filename

    def __str__(self):
        parts = []
        if self.filename:
            parts.append(self.filename)
        if self.line is not None:
            parts.append(u'line {}'.format(self.line))
            if self.column is not None:
                parts.append(u'col {}'.format(self.column))
        loc = u': '.join(parts)
        if loc:
            return u'[{}] Error: {}'.format(loc, self.message)
        return u'Error: {}'.format(self.message)


class LexerError(PktError):
    """Raised when the lexer encounters an invalid character or malformed token."""
    pass


class ParseError(PktError):
    """Raised when the parser encounters a syntax error."""
    pass


class PktRuntimeError(PktError):
    """Raised when a runtime error occurs during interpretation.

    Examples: undefined variable, type mismatch, division by zero,
    calling a non-function value, etc.
    """
    pass


class PktTypeError(PktRuntimeError):
    """Raised specifically for type mismatch errors at runtime."""
    pass

# -*- coding: utf-8 -*-
"""Token type constants and Token class for the PyKt language.

Defines all token types used by the lexer and parser. Token types are
plain string constants on the TokenType class since Python 2.7 has no Enum.
"""


class TokenType(object):
    """Namespace for all token type constants."""

    # --- Keywords ---
    VAL = 'VAL'
    VAR = 'VAR'
    FUN = 'FUN'
    CLASS = 'CLASS'
    IF = 'IF'
    ELSE = 'ELSE'
    WHEN = 'WHEN'
    FOR = 'FOR'
    WHILE = 'WHILE'
    IN = 'IN'
    RETURN = 'RETURN'
    BREAK = 'BREAK'
    CONTINUE = 'CONTINUE'
    TRUE = 'TRUE'
    FALSE = 'FALSE'
    NULL = 'NULL'
    INIT = 'INIT'
    THIS = 'THIS'
    IS = 'IS'
    AND = 'AND'       # soft keyword (used as 'and' in Kotlin)
    OR = 'OR'         # soft keyword
    NOT = 'NOT'       # soft keyword
    STEP = 'STEP'
    TRY = 'TRY'
    CATCH = 'CATCH'
    FINALLY = 'FINALLY'
    THROW = 'THROW'
    OPEN = 'OPEN'
    OVERRIDE = 'OVERRIDE'
    SUPER = 'SUPER'

    # --- Literals ---
    INTEGER = 'INTEGER'
    DOUBLE = 'DOUBLE'
    STRING = 'STRING'
    CHAR = 'CHAR'

    # --- Identifier ---
    IDENTIFIER = 'IDENTIFIER'

    # --- Arithmetic Operators ---
    PLUS = 'PLUS'              # +
    MINUS = 'MINUS'            # -
    STAR = 'STAR'              # *
    SLASH = 'SLASH'            # /
    PERCENT = 'PERCENT'        # %

    # --- Comparison Operators ---
    EQ_EQ = 'EQ_EQ'            # ==
    BANG_EQ = 'BANG_EQ'        # !=
    LT = 'LT'                  # <
    GT = 'GT'                  # >
    LT_EQ = 'LT_EQ'            # <=
    GT_EQ = 'GT_EQ'            # >=

    # --- Logical Operators ---
    AND_AND = 'AND_AND'        # &&
    OR_OR = 'OR_OR'            # ||
    BANG = 'BANG'              # !

    # --- Increment/Decrement ---
    PLUS_PLUS = 'PLUS_PLUS'    # ++
    MINUS_MINUS = 'MINUS_MINUS'  # --

    # --- Assignment Operators ---
    EQ = 'EQ'                  # =
    PLUS_EQ = 'PLUS_EQ'        # +=
    MINUS_EQ = 'MINUS_EQ'      # -=
    STAR_EQ = 'STAR_EQ'        # *=
    SLASH_EQ = 'SLASH_EQ'      # /=
    PERCENT_EQ = 'PERCENT_EQ'  # %=

    # --- Range ---
    DOT_DOT = 'DOT_DOT'        # ..

    # --- Arrow (lambda / when) ---
    ARROW = 'ARROW'            # ->

    # --- Null-Safe and Elvis Operators ---
    QMARK_DOT = 'QMARK_DOT'    # ?.  (null-safe access)
    ELVIS = 'ELVIS'            # ?:  (Elvis operator)
    BANG_BANG = 'BANG_BANG'    # !!  (not-null assertion)
    QMARK = 'QMARK'            # ?   (nullable type annotation marker)

    # --- Punctuation ---
    LPAREN = 'LPAREN'          # (
    RPAREN = 'RPAREN'          # )
    LBRACE = 'LBRACE'          # {
    RBRACE = 'RBRACE'          # }
    LBRACKET = 'LBRACKET'      # [
    RBRACKET = 'RBRACKET'      # ]
    COMMA = 'COMMA'            # ,
    COLON = 'COLON'            # :
    SEMICOLON = 'SEMICOLON'    # ;
    DOT = 'DOT'                # .
    TO = 'TO'                  # to (infix for Pair creation)

    # --- Special ---
    EOF = 'EOF'
    NEWLINE = 'NEWLINE'


# Keyword dictionary: lexeme string -> TokenType constant
KEYWORDS = {
    u'val': TokenType.VAL,
    u'var': TokenType.VAR,
    u'fun': TokenType.FUN,
    u'class': TokenType.CLASS,
    u'if': TokenType.IF,
    u'else': TokenType.ELSE,
    u'when': TokenType.WHEN,
    u'for': TokenType.FOR,
    u'while': TokenType.WHILE,
    u'in': TokenType.IN,
    u'return': TokenType.RETURN,
    u'break': TokenType.BREAK,
    u'continue': TokenType.CONTINUE,
    u'true': TokenType.TRUE,
    u'false': TokenType.FALSE,
    u'null': TokenType.NULL,
    u'init': TokenType.INIT,
    u'this': TokenType.THIS,
    u'is': TokenType.IS,
    u'and': TokenType.AND,
    u'or': TokenType.OR,
    u'not': TokenType.NOT,
    u'step': TokenType.STEP,
    u'to': TokenType.TO,
    u'try': TokenType.TRY,
    u'catch': TokenType.CATCH,
    u'finally': TokenType.FINALLY,
    u'throw': TokenType.THROW,
    u'open': TokenType.OPEN,
    u'override': TokenType.OVERRIDE,
    u'super': TokenType.SUPER,
}


class Token(object):
    """A single lexical token produced by the Lexer.

    Attributes:
        type: One of the TokenType string constants.
        lexeme: The raw source text that produced this token.
        literal: The evaluated Python value (for literals), or None.
        line: 1-based line number in the source file.
        column: 1-based column number in the source file.
    """
    __slots__ = ('type', 'lexeme', 'literal', 'line', 'column')

    def __init__(self, type, lexeme, literal, line, column):
        self.type = type
        self.lexeme = lexeme
        self.literal = literal
        self.line = line
        self.column = column

    def __repr__(self):
        return u"Token({}, {!r}, {!r}, {}:{})".format(
            self.type, self.lexeme, self.literal, self.line, self.column)

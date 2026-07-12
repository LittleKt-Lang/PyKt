# -*- coding: utf-8 -*-
"""Lexer (tokenizer) for the PyKt language.

Converts a raw source string into a list of Token objects.
Handles NEWLINE significance (Kotlin-style), nestable block comments,
string escapes, and all operator longest-match rules.
"""

from __future__ import unicode_literals

from token_types import TokenType, Token, KEYWORDS
from errors import LexerError


class Lexer(object):
    """A single-pass lexer that scans source text into tokens.

    Usage:
        lexer = Lexer(source_code, filename='example.kt')
        tokens = lexer.scan_tokens()
    """

    def __init__(self, source, filename='<unknown>'):
        # Ensure source is unicode
        if isinstance(source, str):
            source = source.decode('utf-8')
        self.source = source
        self.filename = filename
        self.tokens = []
        self.start = 0       # start index of current lexeme
        self.current = 0     # current scan position
        self.line = 1
        self.column = 1
        self.paren_depth = 0  # tracks (), [], {} nesting

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_tokens(self):
        """Scan all tokens from the source and return the list.

        Returns:
            list of Token objects, ending with an EOF token.
        """
        self.tokens = []
        self.start = 0
        self.current = 0
        self.line = 1
        self.column = 1
        self.paren_depth = 0

        while not self._is_at_end():
            self.start = self.current
            self._scan_token()

        self.tokens.append(Token(TokenType.EOF, u'', None, self.line, self.column))
        return self.tokens

    # ------------------------------------------------------------------
    # Internal: main scan dispatch
    # ------------------------------------------------------------------

    def _scan_token(self):
        """Scan a single token based on the current character."""
        c = self._advance()

        # Whitespace (not newline)
        if c in (u' ', u'\r', u'\t', u'\x0c'):
            # skip whitespace silently
            pass

        elif c == u'\n':
            self._handle_newline()

        # Comments
        elif c == u'/' and self._match(u'/'):
            self._line_comment()
        elif c == u'/' and self._match(u'*'):
            self._block_comment()

        # Strings
        elif c == u'"':
            # Check for triple-quoted raw string: """
            if self._peek() == u'"' and self._peek_next() == u'"':
                self._advance()  # second "
                self._advance()  # third "
                self._raw_string()
            else:
                self._string()

        # Digits
        elif self._is_digit(c):
            self._number()

        # Identifiers and keywords
        elif self._is_alpha(c):
            self._identifier()

        # Operators and punctuation
        else:
            self._operator_or_punctuation(c)

    # ------------------------------------------------------------------
    # String template support
    # ------------------------------------------------------------------

    def _parse_template(self, raw_value):
        """Parse a string literal for template expressions $var and ${expr}.

        Returns a Token with type STRING_TEMPLATE and literal set to
        a list of (is_expr, value) tuples for StringTemplateExpr.
        If no templates found, returns a plain STRING token.
        """
        # Quick check: if no unescaped $, return plain string
        if u'$' not in raw_value:
            return self._make_token(TokenType.STRING, raw_value)

        parts = []
        i = 0
        current_literal = []

        while i < len(raw_value):
            c = raw_value[i]
            if c == u'\\':
                # Escape sequence
                if i + 1 < len(raw_value):
                    next_c = raw_value[i + 1]
                    if next_c == u'$':
                        current_literal.append(u'$')
                        i += 2
                        continue
                    elif next_c == u'n':
                        current_literal.append(u'\n')
                        i += 2
                        continue
                    elif next_c == u't':
                        current_literal.append(u'\t')
                        i += 2
                        continue
                    elif next_c == u'\\':
                        current_literal.append(u'\\')
                        i += 2
                        continue
                    elif next_c == u'"':
                        current_literal.append(u'"')
                        i += 2
                        continue
                    elif next_c == u'r':
                        current_literal.append(u'\r')
                        i += 2
                        continue
                    elif next_c == u'u':
                        i += 2
                        hex_str = raw_value[i:i+4]
                        i += 4
                        try:
                            current_literal.append(unichr(int(hex_str, 16)))
                        except (ValueError, OverflowError):
                            current_literal.append(u'\\u' + hex_str)
                        continue
                current_literal.append(c)
                i += 1
            elif c == u'$':
                # Check for $$ (escaping) — produces a literal $
                if i + 1 < len(raw_value) and raw_value[i + 1] == u'$':
                    current_literal.append(u'$')
                    i += 2
                    continue

                # Template expression
                # Flush current literal buffer
                if current_literal:
                    parts.append((False, u''.join(current_literal)))
                    current_literal = []

                i += 1
                if i < len(raw_value):
                    if raw_value[i] == u'{':
                        # ${expression} - find matching }
                        i += 1
                        depth = 1
                        expr_start = i
                        while i < len(raw_value) and depth > 0:
                            if raw_value[i] == u'{':
                                depth += 1
                            elif raw_value[i] == u'}':
                                depth -= 1
                                if depth == 0:
                                    break
                            i += 1
                        expr_text = raw_value[expr_start:i]
                        i += 1  # skip closing }
                        # Parse the expression text to get an AST node
                        from token_types import TokenType as TT
                        sub_lexer = Lexer(expr_text, self.filename)
                        sub_tokens = sub_lexer.scan_tokens()
                        from pkt_parser import Parser as ParserCls
                        # Create a minimal parser with the sub-tokens
                        temp_parser = object.__new__(ParserCls)
                        temp_parser.lexer = sub_lexer
                        temp_parser.tokens = sub_tokens
                        temp_parser.current = 0
                        temp_parser._had_error = False
                        temp_parser._loop_depth = 0
                        # Initialize parselet tables (copied from Parser.__init__)
                        from token_types import TokenType as TT2
                        import ast_nodes as ast2
                        temp_parser._prefix_parselets = {
                            TT2.INTEGER: temp_parser._prefix_literal,
                            TT2.DOUBLE: temp_parser._prefix_literal,
                            TT2.STRING: temp_parser._prefix_literal,
                            TT2.TRUE: temp_parser._prefix_literal,
                            TT2.FALSE: temp_parser._prefix_literal,
                            TT2.NULL: temp_parser._prefix_literal,
                            TT2.IDENTIFIER: temp_parser._prefix_identifier,
                            TT2.MINUS: temp_parser._prefix_unary,
                            TT2.BANG: temp_parser._prefix_unary,
                            TT2.PLUS_PLUS: temp_parser._prefix_unary,
                            TT2.MINUS_MINUS: temp_parser._prefix_unary,
                            TT2.LPAREN: temp_parser._prefix_grouping,
                            TT2.LBRACKET: temp_parser._prefix_list,
                            TT2.FUN: temp_parser._prefix_fun,
                            TT2.THIS: temp_parser._prefix_this,
                            TT2.WHEN: temp_parser._prefix_when,
                        }
                        temp_parser._infix_parselets = {
                            TT2.PLUS:       (temp_parser._infix_binary, 5),
                            TT2.MINUS:      (temp_parser._infix_binary, 5),
                            TT2.STAR:       (temp_parser._infix_binary, 6),
                            TT2.SLASH:      (temp_parser._infix_binary, 6),
                            TT2.PERCENT:    (temp_parser._infix_binary, 6),
                            TT2.EQ_EQ:      (temp_parser._infix_binary, 4),
                            TT2.BANG_EQ:    (temp_parser._infix_binary, 4),
                            TT2.LT:         (temp_parser._infix_binary, 4),
                            TT2.GT:         (temp_parser._infix_binary, 4),
                            TT2.LT_EQ:      (temp_parser._infix_binary, 4),
                            TT2.GT_EQ:      (temp_parser._infix_binary, 4),
                            TT2.AND_AND:    (temp_parser._infix_logical, 2),
                            TT2.OR_OR:      (temp_parser._infix_logical, 1),
                            TT2.DOT_DOT:    (temp_parser._infix_binary, 3),
                            TT2.IS:         (temp_parser._infix_is, 4),
                            TT2.QMARK_DOT:  (temp_parser._infix_null_safe, 8),
                            TT2.ELVIS:      (temp_parser._infix_elvis, 1),
                            TT2.TO:         (temp_parser._infix_to, 3),
                            TT2.LPAREN:     (temp_parser._infix_call, 8),
                            TT2.DOT:        (temp_parser._infix_dot, 8),
                            TT2.LBRACKET:   (temp_parser._infix_index, 8),
                            TT2.PLUS_PLUS:  (temp_parser._infix_postfix, 8),
                            TT2.MINUS_MINUS:(temp_parser._infix_postfix, 8),
                        }
                        try:
                            expr_node = temp_parser._expression()
                            parts.append((True, expr_node))
                        except Exception:
                            # If parsing fails, treat as literal
                            parts.append((False, u'${' + expr_text + u'}'))
                    elif self._is_alpha(raw_value[i]) or raw_value[i] == u'_':
                        # $identifier
                        id_start = i
                        while i < len(raw_value) and (self._is_alnum(raw_value[i])):
                            i += 1
                        var_name = raw_value[id_start:i]
                        # Create an IdentifierExpr for the variable
                        import ast_nodes as ast
                        id_expr = ast.IdentifierExpr(var_name)
                        parts.append((True, id_expr))
                    else:
                        # $ followed by non-identifier char: literal $
                        current_literal.append(u'$')
                else:
                    # $ at end of string: literal $
                    current_literal.append(u'$')
            else:
                current_literal.append(c)
                i += 1

        # Flush remaining literal
        if current_literal:
            parts.append((False, u''.join(current_literal)))

        # If no template parts found (shouldn't happen since we checked for $),
        # return plain string
        if len(parts) == 1 and not parts[0][0]:
            return self._make_token(TokenType.STRING, parts[0][1])

        return self._make_token(TokenType.STRING, parts)

    # ------------------------------------------------------------------
    # Character helpers
    # ------------------------------------------------------------------

    def _advance(self):
        """Consume and return the current character, advancing position."""
        ch = self.source[self.current - 1] if self.current <= len(self.source) else u'\0'
        # Actually: self.current points to next char. We want the char at (current-1).
        # Let's re-think the scanning loop.
        # Standard pattern: self.current is the NEXT character to read.
        # _advance returns the current character and increments.
        c = self.source[self.current]
        self.current += 1
        self.column += 1
        return c

    def _peek(self):
        """Return the current character without consuming it."""
        if self._is_at_end():
            return u'\0'
        return self.source[self.current]

    def _peek_next(self):
        """Return the character after the current one, or '\\0'."""
        if self.current + 1 >= len(self.source):
            return u'\0'
        return self.source[self.current + 1]

    def _match(self, expected):
        """If current char matches expected, consume it and return True."""
        if self._is_at_end():
            return False
        if self.source[self.current] != expected:
            return False
        self.current += 1
        self.column += 1
        return True

    def _is_at_end(self):
        """Return True if we've consumed all characters."""
        return self.current >= len(self.source)

    def _is_digit(self, c):
        """Return True if c is a decimal digit."""
        return u'0' <= c <= u'9'

    def _is_alpha(self, c):
        """Return True if c can start an identifier (letter or underscore)."""
        return (u'a' <= c <= u'z') or (u'A' <= c <= u'Z') or c == u'_'

    def _is_alnum(self, c):
        """Return True if c can appear in an identifier (letter, digit, or underscore)."""
        return self._is_alpha(c) or self._is_digit(c)

    # ------------------------------------------------------------------
    # Token creation
    # ------------------------------------------------------------------

    def _make_token(self, type, literal=None):
        """Create a Token from the current lexeme range."""
        lexeme = self.source[self.start:self.current]
        column = self.column - len(lexeme)
        return Token(type, lexeme, literal, self.line, column)

    def _add_token(self, type, literal=None):
        """Append a token to the list."""
        self.tokens.append(self._make_token(type, literal))

    # ------------------------------------------------------------------
    # Newline handling (Kotlin-style: newlines are significant)
    # ------------------------------------------------------------------

    def _handle_newline(self):
        """Handle a newline character.

        When paren_depth > 0 (inside (), [], {}), newlines are consumed
        silently. When paren_depth == 0, newlines are statement terminators.
        Consecutive blank lines are collapsed.
        """
        self.line += 1
        # Save column for the NEWLINE token (position on previous line)
        newline_column = self.column - 1  # column before _advance incremented it

        # Reset column for the new line (1 = before first char, so first char gets column 1)
        self.column = 1

        if self.paren_depth > 0:
            return  # silently consume newline inside grouping

        # Emit NEWLINE, but collapse consecutive blank lines.
        # Check if the previous token was also a NEWLINE.
        if self.tokens and self.tokens[-1].type == TokenType.NEWLINE:
            return  # skip consecutive NEWLINE

        # Add NEWLINE token with position from previous line
        self.tokens.append(Token(TokenType.NEWLINE, u'\\n', None, self.line - 1, newline_column))

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def _line_comment(self):
        """Consume characters until end of line (// style)."""
        while self._peek() != u'\n' and not self._is_at_end():
            self._advance()
        # Don't consume the newline itself; next scan iteration will handle it.

    def _block_comment(self):
        """Consume a nestable block comment (/* ... */ style).

        Kotlin-style block comments can nest. We track a depth counter
        and only exit when all nested blocks are closed.
        """
        depth = 1
        while depth > 0 and not self._is_at_end():
            if self._peek() == u'\n':
                self.line += 1
                self.column = 0
                self._advance()
            elif self._peek() == u'/' and self._peek_next() == u'*':
                depth += 1
                self._advance()
                self._advance()
            elif self._peek() == u'*' and self._peek_next() == u'/':
                depth -= 1
                self._advance()
                self._advance()
            else:
                self._advance()

        if depth > 0:
            raise LexerError(
                u'Unterminated block comment',
                line=self.line, column=self.column, filename=self.filename)

    # ------------------------------------------------------------------
    # String literals
    # ------------------------------------------------------------------

    def _raw_string(self):
        """Scan a triple-quoted raw string literal: \"\"\"...\"\"\"

        Kotlin-style raw strings:
          - No escape sequences processed
          - Newlines preserved literally
          - Template expressions ($var, ${expr}) ARE processed
          - $$ produces a literal $ character
          - The closing delimiter is three consecutive quotes
        """
        value_parts = []

        while not self._is_at_end():
            # Check for closing """
            if (self._peek() == u'"' and self._peek_next() == u'"'
                    and self.current + 2 < len(self.source)
                    and self.source[self.current + 2] == u'"'):
                self._advance()  # first "
                self._advance()  # second "
                self._advance()  # third "
                break

            c = self._peek()

            if c == u'\n':
                self.line += 1
                self.column = 1
                value_parts.append(c)
                self._advance()
            else:
                value_parts.append(c)
                self._advance()

        if self._is_at_end() and not (len(value_parts) > 0):
            # Actually, check more carefully for unterminated
            pass

        raw_value = u''.join(value_parts)
        # Parse template expressions in the raw string
        template_token = self._parse_template(raw_value)
        self.tokens.append(template_token)

    def _string(self):
        """Scan a double-quoted string literal.

        Handles escape sequences: \\n, \\t, \\\\, \\\", \\$, \\uXXXX.
        Template expressions ($id and ${expr}) are kept as raw text;
        the parser handles template decomposition.
        """
        value_parts = []

        while self._peek() != u'"' and not self._is_at_end():
            c = self._peek()

            if c == u'\n':
                self.line += 1
                self.column = 0
                value_parts.append(c)
                self._advance()
            elif c == u'\\':
                self._advance()  # consume backslash
                esc = self._peek()
                if esc == u'n':
                    value_parts.append(u'\n')
                elif esc == u't':
                    value_parts.append(u'\t')
                elif esc == u'r':
                    value_parts.append(u'\r')
                elif esc == u'\\':
                    value_parts.append(u'\\')
                elif esc == u'"':
                    value_parts.append(u'"')
                elif esc == u'$':
                    # Keep backslash in raw value so _parse_template
                    # can distinguish escaped $ from template $
                    value_parts.append(u'\\$')
                elif esc == u'u':
                    # Unicode escape \uXXXX
                    hex_str = u''
                    for _ in range(4):
                        self._advance()
                        hex_str += self._peek()
                    try:
                        value_parts.append(unichr(int(hex_str, 16)))
                    except (ValueError, OverflowError):
                        raise LexerError(
                            u'Invalid unicode escape \\u{}'.format(hex_str),
                            line=self.line, column=self.column, filename=self.filename)
                else:
                    # Unknown escape: keep as-is (\\ + char)
                    value_parts.append(u'\\')
                    value_parts.append(esc)
                self._advance()
            else:
                value_parts.append(c)
                self._advance()

        if self._is_at_end():
            raise LexerError(
                u'Unterminated string literal',
                line=self.line, column=self.column, filename=self.filename)

        # Consume the closing quote
        self._advance()

        raw_value = u''.join(value_parts)
        # Parse the string for template expressions
        template_token = self._parse_template(raw_value)
        self.tokens.append(template_token)

    # ------------------------------------------------------------------
    # Number literals (Int and Double)
    # ------------------------------------------------------------------

    def _number(self):
        """Scan an integer or floating-point number.

        Supports:
          - Decimal integers: 42, 0, 123
          - Underscore separators: 1_000_000
          - Double with decimal point: 3.14, .5
          - Scientific notation: 1e10, 2.5e-3
        """
        is_double = False
        had_error = False

        # Consume leading digits
        while self._is_digit(self._peek()) or self._peek() == u'_':
            self._advance()

        # Check for decimal point
        if self._peek() == u'.' and self._is_digit(self._peek_next()):
            is_double = True
            self._advance()  # consume the dot
            while self._is_digit(self._peek()) or self._peek() == u'_':
                self._advance()

        # Check for scientific notation
        if self._peek() in (u'e', u'E'):
            is_double = True
            self._advance()
            if self._peek() in (u'+', u'-'):
                self._advance()
            if not self._is_digit(self._peek()):
                raise LexerError(
                    u'Expected digit after exponent',
                    line=self.line, column=self.column, filename=self.filename)
            while self._is_digit(self._peek()):
                self._advance()

        # Parse the numeric value
        lexeme = self.source[self.start:self.current]
        # Remove underscores for parsing
        clean = lexeme.replace(u'_', u'')

        try:
            if is_double:
                value = float(clean)
            else:
                value = int(clean)
        except ValueError:
            raise LexerError(
                u'Invalid number format: {}'.format(lexeme),
                line=self.line, column=self.column, filename=self.filename)

        token_type = TokenType.DOUBLE if is_double else TokenType.INTEGER
        self._add_token(token_type, value)

    # ------------------------------------------------------------------
    # Identifiers and keywords
    # ------------------------------------------------------------------

    def _identifier(self):
        """Scan an identifier or keyword.

        After scanning the identifier, checks the KEYWORDS dictionary
        to determine if it's a reserved word.
        """
        while self._is_alnum(self._peek()):
            self._advance()

        lexeme = self.source[self.start:self.current]
        # Check if it's a keyword
        token_type = KEYWORDS.get(lexeme, TokenType.IDENTIFIER)

        # Set literal values for boolean/null keyword tokens
        literal = None
        if token_type == TokenType.TRUE:
            literal = True
        elif token_type == TokenType.FALSE:
            literal = False
        # null stays as None literal (which represents PktNull)

        self._add_token(token_type, literal)

    # ------------------------------------------------------------------
    # Operators and punctuation
    # ------------------------------------------------------------------

    def _operator_or_punctuation(self, c):
        """Dispatch operator/punctuation scanning based on first character.

        Uses longest-match: e.g., '=' is checked before '==', so '=='
        must be matched first by checking peek().
        """
        # Two-character operators and punctuation
        if c == u'=' and self._match(u'='):
            self._add_token(TokenType.EQ_EQ)
        elif c == u'!' and self._match(u'='):
            self._add_token(TokenType.BANG_EQ)
        elif c == u'<' and self._match(u'='):
            self._add_token(TokenType.LT_EQ)
        elif c == u'>' and self._match(u'='):
            self._add_token(TokenType.GT_EQ)
        elif c == u'&' and self._match(u'&'):
            self._add_token(TokenType.AND_AND)
        elif c == u'|' and self._match(u'|'):
            self._add_token(TokenType.OR_OR)
        elif c == u'+' and self._match(u'+'):
            self._add_token(TokenType.PLUS_PLUS)
        elif c == u'-' and self._match(u'-'):
            self._add_token(TokenType.MINUS_MINUS)
        elif c == u'+' and self._match(u'='):
            self._add_token(TokenType.PLUS_EQ)
        elif c == u'-' and self._match(u'='):
            self._add_token(TokenType.MINUS_EQ)
        elif c == u'*' and self._match(u'='):
            self._add_token(TokenType.STAR_EQ)
        elif c == u'/' and self._match(u'='):
            self._add_token(TokenType.SLASH_EQ)
        elif c == u'%' and self._match(u'='):
            self._add_token(TokenType.PERCENT_EQ)
        elif c == u'.' and self._match(u'.'):
            self._add_token(TokenType.DOT_DOT)
        elif c == u'-' and self._match(u'>'):
            self._add_token(TokenType.ARROW)
        elif c == u'?' and self._match(u'.'):
            self._add_token(TokenType.QMARK_DOT)
        elif c == u'?' and self._match(u':'):
            self._add_token(TokenType.ELVIS)
        elif c == u'!' and self._match(u'!'):
            self._add_token(TokenType.BANG_BANG)
        elif c == u'?':
            self._add_token(TokenType.QMARK)

        # Single-character tokens (with depth tracking)
        elif c == u'(':
            self.paren_depth += 1
            self._add_token(TokenType.LPAREN)
        elif c == u')':
            self.paren_depth -= 1
            self._add_token(TokenType.RPAREN)
        elif c == u'{':
            # NB: { does NOT affect paren_depth because newlines
            # inside blocks are significant (statement separators)
            self._add_token(TokenType.LBRACE)
        elif c == u'}':
            self._add_token(TokenType.RBRACE)
        elif c == u'[':
            self.paren_depth += 1
            self._add_token(TokenType.LBRACKET)
        elif c == u']':
            self.paren_depth -= 1
            self._add_token(TokenType.RBRACKET)
        elif c == u'+':
            self._add_token(TokenType.PLUS)
        elif c == u'-':
            self._add_token(TokenType.MINUS)
        elif c == u'*':
            self._add_token(TokenType.STAR)
        elif c == u'/':
            self._add_token(TokenType.SLASH)
        elif c == u'%':
            self._add_token(TokenType.PERCENT)
        elif c == u'<':
            self._add_token(TokenType.LT)
        elif c == u'>':
            self._add_token(TokenType.GT)
        elif c == u'=':
            self._add_token(TokenType.EQ)
        elif c == u'!':
            self._add_token(TokenType.BANG)
        elif c == u',':
            self._add_token(TokenType.COMMA)
        elif c == u':':
            self._add_token(TokenType.COLON)
        elif c == u';':
            self._add_token(TokenType.SEMICOLON)
        elif c == u'.':
            self._add_token(TokenType.DOT)

        else:
            # Unknown character: emit error but keep going
            raise LexerError(
                u"Unexpected character: '{}'".format(c),
                line=self.line,
                column=self.column - 1,
                filename=self.filename)

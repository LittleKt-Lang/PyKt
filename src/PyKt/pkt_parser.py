# -*- coding: utf-8 -*-
"""Recursive descent + Pratt parser for the PyKt language.

Converts a token stream from the Lexer into an AST (list of Stmt nodes).
"""

from __future__ import print_function, unicode_literals

from token_types import TokenType
from errors import ParseError
import ast_nodes as ast


class Parser(object):
    """Parser for the PyKt language.

    Usage:
        lexer = Lexer(source, filename)
        parser = Parser(lexer)
        statements = parser.parse()
    """

    def __init__(self, lexer):
        self.lexer = lexer
        self.tokens = []
        self.current = 0
        self._had_error = False
        self._loop_depth = 0  # for validating break/continue placement

        # Pratt parser: prefix parselets
        self._prefix_parselets = {
            TokenType.INTEGER: self._prefix_literal,
            TokenType.DOUBLE: self._prefix_literal,
            TokenType.STRING: self._prefix_literal,
            TokenType.TRUE: self._prefix_literal,
            TokenType.FALSE: self._prefix_literal,
            TokenType.NULL: self._prefix_literal,
            TokenType.IDENTIFIER: self._prefix_identifier,
            TokenType.MINUS: self._prefix_unary,
            TokenType.BANG: self._prefix_unary,
            TokenType.PLUS_PLUS: self._prefix_unary,
            TokenType.MINUS_MINUS: self._prefix_unary,
            TokenType.LPAREN: self._prefix_grouping,
            TokenType.LBRACKET: self._prefix_list,
            TokenType.FUN: self._prefix_fun,
            TokenType.TRY: self._prefix_try,
            TokenType.THROW: self._prefix_throw,
            TokenType.THIS: self._prefix_this,
            TokenType.SUPER: self._prefix_super,
            TokenType.WHEN: self._prefix_when,
            TokenType.IF: self._prefix_if,
            TokenType.LBRACE: self._prefix_lambda,
        }

        # Pratt parser: infix parselets
        self._infix_parselets = {
            TokenType.PLUS:       (self._infix_binary, 5),
            TokenType.MINUS:      (self._infix_binary, 5),
            TokenType.STAR:       (self._infix_binary, 6),
            TokenType.SLASH:      (self._infix_binary, 6),
            TokenType.PERCENT:    (self._infix_binary, 6),
            TokenType.EQ_EQ:      (self._infix_binary, 4),
            TokenType.BANG_EQ:    (self._infix_binary, 4),
            TokenType.LT:         (self._infix_binary, 4),
            TokenType.GT:         (self._infix_binary, 4),
            TokenType.LT_EQ:      (self._infix_binary, 4),
            TokenType.GT_EQ:      (self._infix_binary, 4),
            TokenType.AND_AND:    (self._infix_logical, 2),
            TokenType.OR_OR:      (self._infix_logical, 1),
            TokenType.DOT_DOT:    (self._infix_binary, 3),
            TokenType.IS:         (self._infix_is, 4),
            TokenType.LPAREN:     (self._infix_call, 8),
            TokenType.DOT:        (self._infix_dot, 8),
            TokenType.LBRACKET:   (self._infix_index, 8),
            TokenType.QMARK_DOT:  (self._infix_null_safe, 8),
            TokenType.ELVIS:      (self._infix_elvis, 1),
            TokenType.TO:         (self._infix_to, 3),
            TokenType.BANG_BANG:  (self._infix_notnull, 8),
            TokenType.PLUS_PLUS:  (self._infix_postfix, 8),
            TokenType.MINUS_MINUS:(self._infix_postfix, 8),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self):
        """Parse the token stream and return a list of top-level statements."""
        self.tokens = self.lexer.scan_tokens()
        self.current = 0
        self._had_error = False
        self._error_count = 0

        statements = []
        self._skip_newlines()
        while not self._is_at_end():
            try:
                stmt = self._declaration()
                if stmt is not None:
                    statements.append(stmt)
            except ParseError as e:
                self._had_error = True
                self._error_count += 1
                self._report_error(e)
                self._synchronize()
            self._skip_newlines()

        if self._had_error:
            raise ParseError(
                u'{} parse error(s) encountered'.format(
                    self._error_count),
                filename=self.lexer.filename)

        return statements

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _peek(self):
        """Return the current token without consuming it."""
        return self.tokens[self.current]

    def _previous(self):
        """Return the most recently consumed token."""
        return self.tokens[self.current - 1]

    def _advance(self):
        """Consume and return the current token."""
        if not self._is_at_end():
            self.current += 1
        return self._previous()

    def _check(self, *types):
        """Return True if current token is one of the given types."""
        if self._is_at_end():
            return False
        return self._peek().type in types

    def _match(self, *types):
        """If current token matches, consume it and return True."""
        if self._check(*types):
            self._advance()
            return True
        return False

    def _consume(self, type, message):
        """Consume a token of the expected type, or raise ParseError."""
        if self._check(type):
            return self._advance()
        raise self._error(self._peek(), message)

    def _is_at_end(self):
        """Return True if we've reached the EOF token."""
        return self._peek().type == TokenType.EOF

    def _error(self, token, message):
        """Create a ParseError for the given token."""
        return ParseError(
            message,
            line=token.line,
            column=token.column,
            filename=self.lexer.filename)

    def _report_error(self, error):
        """Print a parse error to stderr."""
        import sys
        print(error, file=sys.stderr)

    # ------------------------------------------------------------------
    # Newline / statement boundary handling
    # ------------------------------------------------------------------

    def _skip_newlines(self):
        """Skip past any NEWLINE tokens."""
        while self._match(TokenType.NEWLINE):
            pass

    def _consume_statement_end(self):
        """Ensure current position is at a statement boundary.

        Accepts NEWLINE, EOF, SEMICOLON, RBRACE, or ELSE (which follows
        a when-branch body on the same line).
        If NEWLINE is found, also skip any subsequent NEWLINEs.
        """
        if self._match(TokenType.NEWLINE):
            self._skip_newlines()
            return
        if self._match(TokenType.SEMICOLON):
            self._skip_newlines()
            return
        if self._is_at_end():
            return
        if self._check(TokenType.RBRACE):
            return
        # 'else' terminates a preceding expression-statement (when branches)
        if self._check(TokenType.ELSE):
            return
        raise self._error(self._peek(), u'Expected newline or end of statement')

    # ------------------------------------------------------------------
    # Error recovery
    # ------------------------------------------------------------------

    def _synchronize(self):
        """Skip tokens until we find a statement boundary.

        Looks for NEWLINE, SEMICOLON, or keywords that start declarations.
        """
        self._advance()
        while not self._is_at_end():
            # If we just consumed a NEWLINE, we're at a statement boundary
            if self._previous().type == TokenType.NEWLINE:
                return
            if self._previous().type == TokenType.SEMICOLON:
                return

            # Check if next token starts a new declaration/statement
            t = self._peek().type
            if t in (TokenType.VAL, TokenType.VAR, TokenType.FUN,
                     TokenType.CLASS, TokenType.IF, TokenType.WHEN,
                     TokenType.FOR, TokenType.WHILE, TokenType.RETURN):
                return

            self._advance()

    # ------------------------------------------------------------------
    # Grammar: declarations
    # ------------------------------------------------------------------

    def _declaration(self):
        """Parse a top-level declaration: classDecl | funDecl | varDecl | statement."""
        if self._match(TokenType.VAL, TokenType.VAR):
            return self._var_decl(was_val=(self._previous().type == TokenType.VAL))

        # Check for modifiers: open, override
        is_open = False
        is_override = False
        if self._match(TokenType.OPEN):
            is_open = True
        elif self._match(TokenType.OVERRIDE):
            is_override = True

        if self._match(TokenType.FUN):
            return self._fun_decl(is_open=is_open, is_override=is_override)
        if self._match(TokenType.CLASS):
            return self._class_decl(is_open=is_open)

        # Modifiers without fun/class are invalid
        if is_open or is_override:
            raise self._error(self._previous(),
                              u"'{}' must be followed by 'fun' or 'class'".format(
                                  u'open' if is_open else u'override'))

        return self._statement()

    # ------------------------------------------------------------------
    # Type parameter helpers
    # ------------------------------------------------------------------

    def _parse_type_params(self):
        """Parse optional type parameter list: <T> or <T, U, V>

        Returns a list of type parameter name strings, or an empty list
        when no ``<`` is present.
        """
        if not self._match(TokenType.LT):
            return []

        params = []
        name = self._consume(TokenType.IDENTIFIER,
                             u'Expected type parameter name')
        params.append(name.lexeme)

        while self._match(TokenType.COMMA):
            name = self._consume(TokenType.IDENTIFIER,
                                 u'Expected type parameter name')
            params.append(name.lexeme)

        self._consume(TokenType.GT, u"Expected '>' after type parameters")
        return params

    # ------------------------------------------------------------------
    # Type annotation helper: parses `: Type`, `: Type?`, `: Box<Int>`, etc.
    # ------------------------------------------------------------------

    def _parse_type_annotation(self):
        """Parse an optional type annotation.

        Supports:
          - Simple types:   ``: Int``, ``: String?``
          - Generic types:  ``: Box<Int>``, ``: List<String?>``
          - Function types: ``: (T) -> U``, ``: (Int, String) -> Boolean``
          - Nullable generic: ``: Box<Int>?``

        Returns the full type string (e.g. ``'Box<Int>?'``) or ``None``
        when no colon is present.
        """
        if not self._match(TokenType.COLON):
            return None

        # Function type:  (Params) -> ReturnType
        if self._check(TokenType.LPAREN):
            type_str = u'('
            self._advance()  # consume LPAREN
            if not self._check(TokenType.RPAREN):
                # first param type
                ptype = self._consume(TokenType.IDENTIFIER,
                                      u'Expected type name in function type')
                type_str += ptype.lexeme
                if self._match(TokenType.QMARK):
                    type_str += u'?'
                while self._match(TokenType.COMMA):
                    ptype = self._consume(TokenType.IDENTIFIER,
                                          u'Expected type name in function type')
                    type_str += u', ' + ptype.lexeme
                    if self._match(TokenType.QMARK):
                        type_str += u'?'
            self._consume(TokenType.RPAREN,
                          u"Expected ')' in function type")
            type_str += u')'

            self._consume(TokenType.ARROW, u"Expected '->' in function type")

            rtype = self._consume(TokenType.IDENTIFIER,
                                  u'Expected return type in function type')
            type_str += u' -> ' + rtype.lexeme
            if self._match(TokenType.QMARK):
                type_str += u'?'

            # Nullable function type: ((T) -> U)?
            if self._match(TokenType.QMARK):
                type_str += u'?'

            return type_str

        type_token = self._consume(TokenType.IDENTIFIER, u'Expected type name')
        type_str = type_token.lexeme

        # Generic type arguments:  Type<Arg1, Arg2, ...>
        if self._match(TokenType.LT):
            type_str += '<'
            # first argument
            arg_name = self._consume(TokenType.IDENTIFIER,
                                     u'Expected type argument name')
            type_str += arg_name.lexeme
            if self._match(TokenType.QMARK):
                type_str += '?'

            while self._match(TokenType.COMMA):
                type_str += ','
                arg_name = self._consume(TokenType.IDENTIFIER,
                                         u'Expected type argument name')
                type_str += arg_name.lexeme
                if self._match(TokenType.QMARK):
                    type_str += '?'

            self._consume(TokenType.GT, u"Expected '>' after type arguments")
            type_str += '>'

        # Nullable suffix  (applies to the whole type)
        if self._match(TokenType.QMARK):
            type_str += '?'

        return type_str

    # ------------------------------------------------------------------
    # Variable declaration: val/var name [: Type] [= expr]
    # ------------------------------------------------------------------

    def _var_decl(self, was_val=True):
        """Parse a variable declaration."""
        name_token = self._consume(TokenType.IDENTIFIER, u'Expected variable name')

        type_annotation = self._parse_type_annotation()

        initializer = None
        if self._match(TokenType.EQ):
            initializer = self._expression()

        self._consume_statement_end()

        node = ast.VarDecl(name_token.lexeme, type_annotation, initializer, was_val)
        node.set_position(name_token)
        return node

    # ------------------------------------------------------------------
    # Function declaration: fun [<T>] name(params) [: ReturnType] { body }
    # ------------------------------------------------------------------

    def _fun_decl(self, is_open=False, is_override=False):
        """Parse a function declaration, optionally generic.

        Kotlin syntax:  fun [<T>] name(params): ReturnType { body }
        Type parameters appear **before** the function name.
        """
        # Optional type parameters: fun <T> foo(...)
        type_params = self._parse_type_params()

        name_token = self._consume(TokenType.IDENTIFIER, u'Expected function name')

        self._consume(TokenType.LPAREN, u"Expected '(' after function name")

        params = self._parameters()

        self._consume(TokenType.RPAREN, u"Expected ')' after parameters")

        return_type = self._parse_type_annotation()

        # Expression body:  fun foo(): Type = expr
        if self._match(TokenType.EQ):
            expr = self._expression()
            self._consume_statement_end()
            # Wrap in synthetic block: { return expr }
            ret_stmt = ast.ReturnStmt(name_token, expr)
            ret_stmt.set_position(name_token)
            body = ast.BlockStmt([ret_stmt])
        else:
            body = self._block()

        node = ast.FunDecl(name_token.lexeme, params, return_type, body,
                           is_open=is_open, is_override=is_override,
                           type_params=type_params)
        node.set_position(name_token)
        return node

    def _parameters(self):
        """Parse a parameter list (inside parentheses). Returns list of Param nodes."""
        params = []
        if self._check(TokenType.RPAREN):
            return params

        params.append(self._parameter())
        while self._match(TokenType.COMMA):
            params.append(self._parameter())

        return params

    def _require_param_types(self, params, context):
        """Validate that all parameters have explicit type annotations.

        Kotlin requires explicit type annotations on all function and
        constructor parameters — type inference is not permitted here.

        Args:
            params: List of Param AST nodes to validate.
            context: Human-readable string describing the context (e.g.,
                     "function 'foo'", "constructor of class 'Bar'").

        Raises:
            ParseError: If any parameter lacks a type annotation.
        """
        for param in params:
            if param.type_annotation is None:
                raise self._error(
                    param,
                    u"Parameter '{}' in {} must have an explicit "
                    u"type annotation".format(param.name, context))

    def _parameter(self):
        """Parse a single parameter: [val|var] name [: Type] [= default]"""
        is_val = False
        is_var = False

        if self._match(TokenType.VAL):
            is_val = True
        elif self._match(TokenType.VAR):
            is_var = True

        name_token = self._consume(TokenType.IDENTIFIER, u'Expected parameter name')

        type_annotation = self._parse_type_annotation()

        default_value = None
        if self._match(TokenType.EQ):
            default_value = self._expression()

        node = ast.Param(name_token.lexeme, type_annotation, default_value, is_val, is_var)
        node.set_position(name_token)
        return node

    # ------------------------------------------------------------------
    # Class declaration: class Name [<T>] [(params)] [: SuperClass] { members }
    # ------------------------------------------------------------------

    def _class_decl(self, is_open=False):
        """Parse a class declaration, optionally generic."""
        name_token = self._consume(TokenType.IDENTIFIER, u'Expected class name')

        # Optional type parameters: class Box<T>(...)
        type_params = self._parse_type_params()

        # Constructor parameters: class Foo(val x: Int, var y: String)
        constructor_params = []
        if self._match(TokenType.LPAREN):
            if not self._check(TokenType.RPAREN):
                constructor_params = self._parameters()
            self._consume(TokenType.RPAREN, u"Expected ')' after constructor parameters")

        # Optional superclass: ': ClassName' or ': ClassName(args)'
        superclass = None
        if self._match(TokenType.COLON):
            super_name_token = self._consume(TokenType.IDENTIFIER,
                                             u'Expected superclass name')
            superclass = ast.IdentifierExpr(super_name_token.lexeme)
            superclass.set_position(super_name_token)

            # Check for super constructor arguments: ClassName(args)
            if self._match(TokenType.LPAREN):
                super_args = []
                if not self._check(TokenType.RPAREN):
                    super_args.append(self._expression())
                    while self._match(TokenType.COMMA):
                        super_args.append(self._expression())
                self._consume(TokenType.RPAREN,
                              u"Expected ')' after super constructor arguments")
                # Wrap in a special SuperConstructorCall
                superclass = ast.SuperConstructorCall(
                    superclass, super_args)
                superclass.set_position(super_name_token)

        # Class body
        self._consume(TokenType.LBRACE, u"Expected '{' to start class body")
        self._skip_newlines()

        members = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            member = self._class_member()
            if member is not None:
                members.append(member)
            self._skip_newlines()

        self._consume(TokenType.RBRACE, u"Expected '}' after class body")

        node = ast.ClassDecl(name_token.lexeme, constructor_params, superclass, members,
                            is_open=is_open, type_params=type_params)
        node.set_position(name_token)
        return node

    def _class_member(self):
        """Parse a member declaration inside a class body.

        Supports: open fun, override fun, fun, val/var, init
        """
        # Check for modifiers on class members
        is_open = False
        is_override = False
        if self._match(TokenType.OPEN):
            is_open = True
        elif self._match(TokenType.OVERRIDE):
            is_override = True

        if self._match(TokenType.VAL, TokenType.VAR):
            return self._var_decl(was_val=(self._previous().type == TokenType.VAL))
        if self._match(TokenType.FUN):
            return self._fun_decl(is_open=is_open, is_override=is_override)
        if self._match(TokenType.INIT):
            return self._init_block()

        # Modifiers without valid target
        if is_open or is_override:
            raise self._error(self._previous(),
                              u"'{}' must be followed by 'fun' or val/var".format(
                                  u'open' if is_open else u'override'))

        return self._statement()

    def _init_block(self):
        """Parse an init { ... } block."""
        body = self._block()
        node = ast.InitBlock(body)
        node.set_position(self._previous())
        return node

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _statement(self):
        """Parse a statement."""
        if self._match(TokenType.IF):
            return self._if_stmt()
        if self._match(TokenType.WHEN):
            return self._when_stmt()
        if self._match(TokenType.FOR):
            return self._for_stmt()
        if self._match(TokenType.WHILE):
            return self._while_stmt()
        if self._match(TokenType.TRY):
            return self._try_stmt()
        if self._match(TokenType.RETURN):
            return self._return_stmt()
        if self._match(TokenType.BREAK):
            return self._break_stmt()
        if self._match(TokenType.CONTINUE):
            return self._continue_stmt()
        if self._match(TokenType.LBRACE):
            return self._block_from_open_brace()
        return self._expr_stmt()

    # --- If statement ---

    def _if_stmt(self):
        """Parse if (condition) then_branch [else else_branch]"""
        self._consume(TokenType.LPAREN, u"Expected '(' after 'if'")
        condition = self._expression()
        self._consume(TokenType.RPAREN, u"Expected ')' after if condition")

        then_branch = self._statement()
        else_branch = None
        if self._match(TokenType.ELSE):
            else_branch = self._statement()

        node = ast.IfStmt(condition, then_branch, else_branch)
        node.set_position(self._previous())
        return node

    # --- When statement ---

    def _when_stmt(self):
        """Parse when [(subject)] { branches }"""
        subject = None
        # Check if there's a parenthesized subject expression
        if self._match(TokenType.LPAREN):
            if not self._check(TokenType.RPAREN):
                subject = self._expression()
            self._consume(TokenType.RPAREN, u"Expected ')' after when subject")
        elif self._check(TokenType.LBRACE):
            # when { } without subject
            pass
        else:
            # when x { } without parentheses
            subject = self._expression()

        self._consume(TokenType.LBRACE, u"Expected '{' after when")
        self._skip_newlines()

        branches = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            branches.append(self._when_branch())
            self._skip_newlines()

        self._consume(TokenType.RBRACE, u"Expected '}' after when body")

        node = ast.WhenStmt(subject, branches)
        return node

    def _when_branch(self):
        """Parse a single when branch: conditions -> body"""
        is_else = False
        conditions = []

        if self._match(TokenType.ELSE):
            is_else = True
        else:
            conditions.append(self._expression())
            while self._match(TokenType.COMMA):
                conditions.append(self._expression())

        self._consume(TokenType.ARROW, u"Expected '->' in when branch")
        body = self._statement()

        node = ast.WhenBranch(conditions, is_else, body)
        return node

    # --- For loop ---

    def _for_stmt(self):
        """Parse for (variable in iterable) body"""
        self._consume(TokenType.LPAREN, u"Expected '(' after 'for'")
        var_token = self._consume(TokenType.IDENTIFIER, u'Expected loop variable name')
        self._consume(TokenType.IN, u"Expected 'in' in for loop")
        iterable = self._expression()
        self._consume(TokenType.RPAREN, u"Expected ')' after for loop header")

        self._loop_depth += 1
        body = self._statement()
        self._loop_depth -= 1

        node = ast.ForStmt(var_token.lexeme, iterable, body)
        node.set_position(var_token)
        return node

    # --- While loop ---

    def _while_stmt(self):
        """Parse while (condition) body"""
        self._consume(TokenType.LPAREN, u"Expected '(' after 'while'")
        condition = self._expression()
        self._consume(TokenType.RPAREN, u"Expected ')' after while condition")

        self._loop_depth += 1
        body = self._statement()
        self._loop_depth -= 1

        node = ast.WhileStmt(condition, body)
        return node

    # --- Try-catch-finally ---

    def _try_stmt(self):
        """Parse try-catch-finally statement (delegates to _prefix_try).

        Also updates statement dispatch for try to also handle expression form.
        """
        return self._prefix_try(self._previous())

    def _prefix_try(self, token):
        """Parse try-catch-finally expression: try { } catch(e [: Type]) { } [finally { }]

        try is an expression in Kotlin — can be used in expression context.
        """
        try_block = self._block()
        catch_clauses = []

        # Parse one or more catch clauses
        while self._match(TokenType.CATCH):
            self._consume(TokenType.LPAREN, u"Expected '(' after 'catch'")
            var_token = self._consume(TokenType.IDENTIFIER,
                                      u'Expected exception variable name')

            exception_type = self._parse_type_annotation()

            self._consume(TokenType.RPAREN, u"Expected ')' after catch parameter")

            catch_body = self._block()
            clause = ast.CatchClause(var_token.lexeme, exception_type, catch_body)
            clause.set_position(var_token)
            catch_clauses.append(clause)

        # Optional finally block
        finally_block = None
        if self._match(TokenType.FINALLY):
            finally_block = self._block()

        node = ast.TryExpr(try_block, catch_clauses, finally_block)
        node.set_position(token)
        return node

    # --- Return statement ---

    def _return_stmt(self):
        """Parse return [value]"""
        keyword = self._previous()
        value = None
        # Only parse expression if not at statement boundary
        if not self._check(TokenType.NEWLINE) and not self._check(TokenType.SEMICOLON) \
                and not self._check(TokenType.RBRACE) and not self._check(TokenType.EOF):
            value = self._expression()

        self._consume_statement_end()

        node = ast.ReturnStmt(keyword, value)
        node.set_position(keyword)
        return node

    # --- Break / Continue ---

    def _break_stmt(self):
        """Parse break statement."""
        if self._loop_depth == 0:
            raise self._error(self._previous(), u"'break' is only allowed inside a loop")
        self._consume_statement_end()
        return ast.BreakStmt().set_position(self._previous())

    def _continue_stmt(self):
        """Parse continue statement."""
        if self._loop_depth == 0:
            raise self._error(self._previous(), u"'continue' is only allowed inside a loop")
        self._consume_statement_end()
        return ast.ContinueStmt().set_position(self._previous())

    # --- Expression statement ---

    def _expr_stmt(self):
        """Parse an expression used as a statement."""
        expr = self._expression()
        self._consume_statement_end()
        node = ast.ExprStmt(expr)
        return node

    # --- Block ---

    def _block(self):
        """Parse { statements } -- must start with LBRACE."""
        self._consume(TokenType.LBRACE, u"Expected '{' to start block")
        return self._block_from_open_brace()

    def _block_from_open_brace(self):
        """Parse the inside of a block after LBRACE has been consumed."""
        self._skip_newlines()
        statements = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            stmt = self._declaration()
            if stmt is not None:
                statements.append(stmt)
            self._skip_newlines()

        self._consume(TokenType.RBRACE, u"Expected '}' after block")
        node = ast.BlockStmt(statements)
        return node

    # ==================================================================
    # Pratt Parser: Expressions
    # ==================================================================

    def _expression(self):
        """Parse any expression, starting at the lowest precedence.

        Assignment and trailing lambdas are handled here (lowest precedence)
        rather than as regular infix parselets.
        """
        expr = self._parse_precedence(0)

        # Check for assignment operators (right-associative)
        if self._check(TokenType.EQ, TokenType.PLUS_EQ, TokenType.MINUS_EQ,
                       TokenType.STAR_EQ, TokenType.SLASH_EQ, TokenType.PERCENT_EQ):
            token = self._advance()
            value = self._expression()  # right-associative recursion
            if isinstance(expr, ast.IdentifierExpr):
                if token.type == TokenType.EQ:
                    node = ast.AssignExpr(expr.name, value)
                else:
                    node = ast.CompoundAssignExpr(expr.name, token, value)
                node.set_position(token)
                return node
            elif isinstance(expr, ast.GetExpr):
                # obj.prop = value  →  property assignment
                if token.type == TokenType.EQ:
                    node = ast.SetExpr(expr.object, expr.name, value)
                    node.set_position(token)
                    return node
                else:
                    raise self._error(token,
                                      u'Compound assignment not supported on properties')
            else:
                raise self._error(token, u'Invalid assignment target')

        # Trailing lambda:  expr { lambda }  →  expr({ lambda })
        if self._check(TokenType.LBRACE):
            token = self._advance()
            lambda_expr = self._prefix_lambda(token)
            expr = ast.CallExpr(expr, [lambda_expr])
            expr.set_position(token)

        return expr

    def _parse_precedence(self, precedence):
        """Pratt parser: parse an expression with the given minimum precedence."""
        # Guard against infinite recursion at EOF: when the token stream
        # is exhausted _advance() would return the previous (stale) token,
        # whose prefix parselet could loop back here forever.
        if self._is_at_end():
            raise self._error(self._peek(), u'Expected expression')
        token = self._advance()
        prefix_fn = self._prefix_parselets.get(token.type)
        if prefix_fn is None:
            raise self._error(token, u"Expected expression, got '{}'".format(token.lexeme))

        left = prefix_fn(token)

        while precedence < self._get_infix_precedence():
            token = self._advance()
            infix_entry = self._infix_parselets[token.type]
            infix_fn = infix_entry[0]
            left = infix_fn(left, token)

        return left

    def _get_infix_precedence(self):
        """Get the precedence of the current token as an infix operator, or 0."""
        if self._is_at_end():
            return 0
        entry = self._infix_parselets.get(self._peek().type)
        if entry is None:
            return 0
        return entry[1]

    # --- Prefix parselets ---

    def _prefix_literal(self, token):
        """Parse a literal value.

        For STRING tokens: if the literal is a list of (is_expr, value) tuples,
        it's a string template. Otherwise, it's a plain string literal.
        """
        if token.type == TokenType.STRING and isinstance(token.literal, list):
            # String template: parts from the lexer's _parse_template
            node = ast.StringTemplateExpr(token.literal)
            node.set_position(token)
            return node

        node = ast.LiteralExpr(token.literal)
        node.set_position(token)
        return node

    def _prefix_identifier(self, token):
        """Parse an identifier reference."""
        node = ast.IdentifierExpr(token.lexeme)
        node.set_position(token)
        return node

    def _prefix_unary(self, token):
        """Parse a prefix unary expression: -x, !x, ++x, --x"""
        right = self._parse_precedence(7)  # unary has high precedence
        node = ast.PrefixExpr(token, right)
        node.set_position(token)
        return node

    def _prefix_grouping(self, token):
        """Parse a parenthesized expression: (expr)"""
        expr = self._expression()
        self._consume(TokenType.RPAREN, u"Expected ')' after expression")
        node = ast.GroupingExpr(expr)
        node.set_position(token)
        return node

    def _prefix_list(self, token):
        """Parse a list or map literal: [elem1, elem2, ...] or [key to value, ...]

        Uses precedence cutoff to prevent 'to' from being consumed as
        an infix operator during key parsing.
        """
        if self._check(TokenType.RBRACKET):
            self._advance()
            return ast.ListLiteralExpr([]).set_position(token)

        # Parse first expression with precedence > TO (which is 3).
        # This prevents `_parse_precedence` from consuming `to` as an infix.
        # We use precedence 4 so that `to` (precedence 3) is NOT consumed.
        first = self._parse_precedence(4)

        # Check if this is a map literal: [key to value, ...]
        if self._match(TokenType.TO):
            # Map literal!
            entries = []
            value = self._expression()
            entries.append((first, value))

            while self._match(TokenType.COMMA):
                key = self._parse_precedence(4)  # Same precedence cutoff
                if self._match(TokenType.TO):
                    val = self._expression()
                    entries.append((key, val))
                else:
                    raise self._error(self._previous(),
                                      u"Expected 'to' in map literal entry")

            self._consume(TokenType.RBRACKET, u"Expected ']' after map entries")
            node = ast.MapLiteralExpr(entries)
            node.set_position(token)
            return node

        # Regular list literal
        elements = [first]
        while self._match(TokenType.COMMA):
            elements.append(self._expression())

        self._consume(TokenType.RBRACKET, u"Expected ']' after list elements")
        node = ast.ListLiteralExpr(elements)
        node.set_position(token)
        return node

    def _prefix_fun(self, token):
        """Parse an anonymous function expression: fun [<T>](params) [: Type] { body }"""
        # Optional type parameters for anonymous functions
        type_params = self._parse_type_params()

        self._consume(TokenType.LPAREN, u"Expected '(' after 'fun'")
        params = self._parameters()

        self._consume(TokenType.RPAREN, u"Expected ')' after parameters")

        return_type = self._parse_type_annotation()

        body = self._block()

        # Create a synthetic FunDecl node for the anonymous function
        node = ast.FunDecl(u'<lambda>', params, return_type, body,
                           type_params=type_params)
        node.set_position(token)
        return node

    def _prefix_lambda(self, token):
        """Parse a lambda expression: { [params ->] body }

        Supports:
          - Implicit ``it`` parameter:  ``{ it * 2 }``
          - Explicit parameters:       ``{ a, b -> a + b }``
        The opening brace has already been consumed by the caller.
        """
        # Try explicit-parameter form:  { a, b -> body }
        # Look ahead: if we see one or more identifiers followed by ARROW
        # or COMMA then ARROW, it's the explicit-parameter form.
        params = []
        if (self._check(TokenType.IDENTIFIER) and
                self._peek_next_type() in (TokenType.ARROW, TokenType.COMMA)):
            # Parse parameter name list
            name = self._consume(TokenType.IDENTIFIER, u'Expected parameter name')
            params.append(name.lexeme)
            while self._match(TokenType.COMMA):
                name = self._consume(TokenType.IDENTIFIER,
                                     u'Expected parameter name')
                params.append(name.lexeme)
            self._consume(TokenType.ARROW, u"Expected '->' after lambda parameters")

        body = self._expression()
        self._consume(TokenType.RBRACE, u"Expected '}' after lambda body")
        node = ast.LambdaExpr(params, body)
        node.set_position(token)
        return node

    def _peek_next_type(self):
        """Peek at the type of the token after the current one.
        Returns None if there is no next token.
        """
        if self.current + 1 < len(self.tokens):
            return self.tokens[self.current + 1].type
        return None

    def _prefix_super(self, token):
        """Parse 'super' expression (reference to parent class)."""
        node = ast.SuperExpr()
        node.set_position(token)
        return node

    def _prefix_this(self, token):
        """Parse 'this' expression."""
        node = ast.ThisExpr()
        node.set_position(token)
        return node

    def _prefix_when(self, token):
        """Parse 'when' as an expression (when with branches that return values)."""
        subject = None
        if self._match(TokenType.LPAREN):
            if not self._check(TokenType.RPAREN):
                subject = self._expression()
            self._consume(TokenType.RPAREN, u"Expected ')' after when subject")

        self._consume(TokenType.LBRACE, u"Expected '{' after when")
        self._skip_newlines()

        branches = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            branches.append(self._when_branch())
            self._skip_newlines()

        self._consume(TokenType.RBRACE, u"Expected '}' after when body")

        node = ast.WhenStmt(subject, branches)
        node.set_position(token)
        return node

    def _prefix_if(self, token):
        """Parse an if-expression: if (condition) <then> else <else>

        Kotlin: if is an expression when used with else.
        Each branch may be a single expression or a block ``{...}``
        whose last expression-statement yields the branch value.
        The ``else`` branch is **required** in expression context.

        Newlines are skipped before ``else`` so that else-if chains
        can span multiple lines (matching Kotlin syntax).
        """
        self._consume(TokenType.LPAREN, u"Expected '(' after 'if'")
        condition = self._expression()
        self._consume(TokenType.RPAREN, u"Expected ')' after if condition")

        # Parse then-branch: block or single expression
        if self._check(TokenType.LBRACE):
            then_branch = self._block()
        else:
            then_branch = self._expression()

        # Allow newlines before 'else' for multi-line else-if chains
        self._skip_newlines()

        # 'else' is required for if-expression
        self._consume(TokenType.ELSE, u"Expected 'else' in if-expression")

        # Parse else-branch: block or single expression
        if self._check(TokenType.LBRACE):
            else_branch = self._block()
        else:
            else_branch = self._expression()

        node = ast.IfExpr(condition, then_branch, else_branch)
        node.set_position(token)
        return node

    # --- Infix parselets ---

    def _infix_binary(self, left, token):
        """Parse a binary operator expression."""
        precedence = self._infix_parselets[token.type][1]
        right = self._parse_precedence(precedence)
        node = ast.InfixExpr(left, token, right)
        node.set_position(token)
        return node

    def _infix_logical(self, left, token):
        """Parse a short-circuit logical expression (&&, ||)."""
        precedence = self._infix_parselets[token.type][1]
        right = self._parse_precedence(precedence)
        node = ast.LogicalExpr(left, token, right)
        node.set_position(token)
        return node

    def _infix_is(self, left, token):
        """Parse an 'is' type check expression."""
        type_token = self._consume(TokenType.IDENTIFIER, u'Expected type name after "is"')
        node = ast.IsExpr(left, type_token.lexeme)
        node.set_position(token)
        return node

    def _infix_assign(self, left, token):
        """Parse an assignment expression: name = value"""
        if not isinstance(left, ast.IdentifierExpr):
            raise self._error(token, u'Invalid assignment target')

        value = self._parse_precedence(0)  # right-associative
        node = ast.AssignExpr(left.name, value)
        node.set_position(token)
        return node

    def _infix_compound_assign(self, left, token):
        """Parse a compound assignment: name += value, name -= value, etc."""
        if not isinstance(left, ast.IdentifierExpr):
            raise self._error(token, u'Invalid assignment target')

        value = self._parse_precedence(0)
        node = ast.CompoundAssignExpr(left.name, token, value)
        node.set_position(token)
        return node

    def _infix_call(self, left, token):
        """Parse a function call: callee(arguments)"""
        arguments = []
        if not self._check(TokenType.RPAREN):
            arguments.append(self._expression())
            while self._match(TokenType.COMMA):
                arguments.append(self._expression())

        rparen = self._consume(TokenType.RPAREN, u"Expected ')' after arguments")

        node = ast.CallExpr(left, arguments)
        node.set_position(token)
        return node

    def _infix_dot(self, left, token):
        """Parse a property access or method call: obj.name"""
        name_token = self._consume(TokenType.IDENTIFIER, u'Expected property name after "."')
        node = ast.GetExpr(left, name_token.lexeme)
        node.set_position(token)
        return node

    def _infix_index(self, left, token):
        """Parse an index access: obj[index]"""
        index = self._expression()
        bracket_token = self._consume(TokenType.RBRACKET, u"Expected ']' after index")

        # Check if this is actually an assignment target
        if self._match(TokenType.EQ):
            value = self._expression()
            node = ast.IndexSetExpr(left, index, value)
            node.set_position(token)
        else:
            node = ast.IndexExpr(left, index)
            node.set_position(token)

        return node

    def _infix_postfix(self, left, token):
        """Parse a postfix operator: x++, x--"""
        node = ast.PostfixExpr(left, token)
        node.set_position(token)
        return node

    def _infix_notnull(self, left, token):
        """Parse not-null assertion: expr!!"""
        node = ast.NotNullAssertExpr(left)
        node.set_position(token)
        return node

    def _prefix_throw(self, token):
        """Parse throw expression: throw expr"""
        expr = self._expression()
        node = ast.ThrowExpr(expr)
        node.set_position(token)
        return node

    def _infix_null_safe(self, left, token):
        """Parse a null-safe property access or method call: obj?.name or obj?.method()

        If followed by '(', creates a NullSafeCallExpr.
        Otherwise creates a NullSafeGetExpr.
        """
        name_token = self._consume(TokenType.IDENTIFIER,
                                   u'Expected property name after "?."')

        # Check if this is a null-safe method call: obj?.method(args)
        if self._match(TokenType.LPAREN):
            arguments = []
            if not self._check(TokenType.RPAREN):
                arguments.append(self._expression())
                while self._match(TokenType.COMMA):
                    arguments.append(self._expression())
            self._consume(TokenType.RPAREN, u"Expected ')' after arguments")
            node = ast.NullSafeCallExpr(left, name_token.lexeme, arguments)
            node.set_position(token)
            return node

        node = ast.NullSafeGetExpr(left, name_token.lexeme)
        node.set_position(token)
        return node

    def _infix_elvis(self, left, token):
        """Parse the Elvis operator: left ?: right

        Precedence is between || and && (level 1).
        """
        precedence = self._infix_parselets[TokenType.ELVIS][1]
        right = self._parse_precedence(precedence)
        node = ast.ElvisExpr(left, right)
        node.set_position(token)
        return node

    def _infix_to(self, left, token):
        """Parse the 'to' infix operator: key to value (creates a Pair)

        Used in map literals and as a standalone pair creator.
        """
        right = self._parse_precedence(2)  # lower than range (3), higher than elvis (1)
        node = ast.ToExpr(left, right)
        node.set_position(token)
        return node

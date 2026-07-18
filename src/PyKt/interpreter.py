# -*- coding: utf-8 -*-
"""Tree-walking interpreter for the PyKt language.

Walks the AST produced by the Parser and evaluates/executes each node.
Uses the Environment class for scope management and the PktValue hierarchy
for runtime value representation.
"""

from __future__ import unicode_literals

from environment import Environment
from runtime import (
    PktValue, PktNull, PktBoolean, PktInt, PktDouble, PktString,
    PktList, PktIntRange, PktFunction, PktBuiltinFunction,
    PktClass, PktInstance, BoundMethod, PktArray, PktMap, PktPair,
    PktThrowable, PktException, PktRuntimeException, PktError, PktPythonException,
    PktExceptionClass,
    PktPythonClass, PktPythonInstance, PktPythonMethod,
    _pkt_to_py_raw, _py_to_pkt_value,
    promote_to_double, check_numeric, make_int_or_double,
)
from builtins import Builtins
from token_types import TokenType
from errors import PktRuntimeError, PktTypeError, PktError
import ast_nodes as ast


# =========================================================================
# Internal exceptions for control flow
# =========================================================================

class ReturnException(Exception):
    """Raised to unwind the stack when a 'return' statement is executed."""
    def __init__(self, value):
        super(ReturnException, self).__init__()
        self.value = value


class BreakException(Exception):
    """Raised to exit a loop when 'break' is executed."""
    pass


class ContinueException(Exception):
    """Raised to skip to the next iteration when 'continue' is executed."""
    pass


class ThrowException(Exception):
    """Raised to unwind the stack when a 'throw' statement is executed.

    Carries a PktValue (the thrown exception value).
    """
    def __init__(self, value):
        super(ThrowException, self).__init__()
        self.value = value


# =========================================================================
# Binary operator dispatch table
# =========================================================================

def _binary_add(token, left, right):
    """Handle the + operator.

    String + anything -> string concatenation (via str()).
    Numeric + numeric -> numeric addition.
    """
    # String concatenation
    if isinstance(left, PktString) or isinstance(right, PktString):
        return PktString(unicode(left) + unicode(right))

    # Numeric addition
    left, right = check_numeric(token, left, right)
    if isinstance(left, PktInt) and isinstance(right, PktInt):
        return PktInt(left.value + right.value)
    return PktDouble(float(left.value) + float(right.value))


def _binary_subtract(token, left, right):
    left, right = check_numeric(token, left, right)
    if isinstance(left, PktInt) and isinstance(right, PktInt):
        return PktInt(left.value - right.value)
    return PktDouble(float(left.value) - float(right.value))


def _binary_multiply(token, left, right):
    left, right = check_numeric(token, left, right)
    if isinstance(left, PktInt) and isinstance(right, PktInt):
        return PktInt(left.value * right.value)
    return PktDouble(float(left.value) * float(right.value))


def _binary_divide(token, left, right):
    left, right = check_numeric(token, left, right)
    rval = right.value if isinstance(right, PktInt) else right.value
    if rval == 0:
        raise PktRuntimeError(
            u'Division by zero',
            line=token.line, column=token.column)
    # Kotlin: Int / Int = Int (truncating division)
    if isinstance(left, PktInt) and isinstance(right, PktInt):
        # Python 2.7: / does truncating division for ints
        return PktInt(left.value // right.value)
    return PktDouble(float(left.value) / float(right.value))


def _binary_modulo(token, left, right):
    left, right = check_numeric(token, left, right)
    if isinstance(left, PktInt) and isinstance(right, PktInt):
        rval = right.value
        if rval == 0:
            raise PktRuntimeError(
                u'Modulo by zero',
                line=token.line, column=token.column)
        return PktInt(left.value % rval)
    lval = float(left.value)
    rval = float(right.value)
    if rval == 0.0:
        raise PktRuntimeError(
            u'Modulo by zero',
            line=token.line, column=token.column)
    import math
    return PktDouble(math.fmod(lval, rval))


BINARY_OPS = {
    TokenType.PLUS:     _binary_add,
    TokenType.MINUS:    _binary_subtract,
    TokenType.STAR:     _binary_multiply,
    TokenType.SLASH:    _binary_divide,
    TokenType.PERCENT:  _binary_modulo,
}


def _compare_eq(token, left, right):
    """Structural equality (==)."""
    return PktBoolean(left.equals(right))


def _compare_neq(token, left, right):
    """Structural inequality (!=)."""
    return PktBoolean(not left.equals(right))


def _compare_lt(token, left, right):
    left, right = check_numeric(token, left, right)
    return PktBoolean(float(left.value) < float(right.value))


def _compare_gt(token, left, right):
    left, right = check_numeric(token, left, right)
    return PktBoolean(float(left.value) > float(right.value))


def _compare_lte(token, left, right):
    left, right = check_numeric(token, left, right)
    return PktBoolean(float(left.value) <= float(right.value))


def _compare_gte(token, left, right):
    left, right = check_numeric(token, left, right)
    return PktBoolean(float(left.value) >= float(right.value))


COMPARE_OPS = {
    TokenType.EQ_EQ:   _compare_eq,
    TokenType.BANG_EQ: _compare_neq,
    TokenType.LT:      _compare_lt,
    TokenType.GT:      _compare_gt,
    TokenType.LT_EQ:   _compare_lte,
    TokenType.GT_EQ:   _compare_gte,
}


# =========================================================================
# Interpreter
# =========================================================================

class Interpreter(object):
    """Tree-walking interpreter for the PyKt language.

    Evaluates AST nodes produced by the Parser against an Environment
    chain, producing PktValue results.

    Usage:
        interpreter = Interpreter()
        interpreter.interpret(statements)
    """

    # ------------------------------------------------------------------
    # Type system: maps type annotation base names to acceptable PktValue types
    # ------------------------------------------------------------------
    _TYPE_MAP = {
        u'Int': (PktInt,),
        u'Double': (PktDouble,),
        u'String': (PktString,),
        u'Boolean': (PktBoolean,),
        u'List': (PktList,),
        u'Array': (PktArray,),
        u'Map': (PktMap,),
        u'Pair': (PktPair,),
        u'Function': (PktFunction, PktBuiltinFunction, BoundMethod),
        u'IntRange': (PktIntRange,),
        u'Throwable': (PktThrowable,),
        u'Exception': (PktException,),
        u'RuntimeException': (PktRuntimeException,),
        u'Error': (PktError,),
        u'Any': (PktValue,),
        u'Unit': (PktNull,),
    }

    def __init__(self):
        self.globals = Environment()
        self.environment = self.globals
        self._current_function_return_type = None  # None = not in a function
        Builtins.register(self.globals)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Generic type helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_generic_type(type_str):
        """Split a generic type annotation string into components.

        Examples:
            ``'Int'``           → ``('Int', [], False)``
            ``'String?'``       → ``('String', [], True)``
            ``'Box<Int>'``      → ``('Box', ['Int'], False)``
            ``'(T) -> U'``      → ``('Function', [], False)``
            ``'(Int)->String?'``→ ``('Function', [], True)``

        Returns:
            ``(base_name, type_args, is_nullable)`` tuple.
        """
        if type_str is None:
            return (None, [], False)

        # Function types:  (P1, P2) -> R  or  (P1) -> R
        if type_str.startswith(u'('):
            is_nullable = type_str.endswith('?')
            return (u'Function', [], is_nullable)

        is_nullable = type_str.endswith('?')
        if is_nullable:
            type_str = type_str[:-1]

        # Find generic arguments:  BaseName<...>
        lt_idx = type_str.find('<')
        if lt_idx == -1:
            return (type_str, [], is_nullable)

        base = type_str[:lt_idx]
        inner = type_str[lt_idx + 1:-1]  # strip < and >

        # Split by commas (simple split — nested generics not supported yet)
        args = [a.strip() for a in inner.split(',')]
        return (base, args, is_nullable)

    # ------------------------------------------------------------------
    # Type validation
    # ------------------------------------------------------------------

    def _validate_type(self, value, type_annotation, line, column):
        """Validate that a value matches a type annotation.

        Enforces Kotlin's static type checking rules:
          - Non-nullable types (e.g., 'Int') reject null values.
          - Nullable types (e.g., 'Int?') accept null values.
          - The base type must match the runtime type of the value.
          - Type parameter names (e.g., 'T', 'U') are skipped at runtime
            (type-erasure semantics — generic types are unchecked).

        Args:
            value: The PktValue to check.
            type_annotation: The declared type string (e.g., 'Int', 'String?').
            line, column: Source location for error reporting.

        Raises:
            PktTypeError: If the value does not match the declared type.
        """
        if type_annotation is None:
            return

        # Parse generic type annotation: 'Box<Int>' → base='Box', args=['Int']
        base_type, type_args, is_nullable = self._parse_generic_type(
            type_annotation)

        # null is only allowed for nullable types
        if isinstance(value, PktNull):
            if is_nullable:
                return
            else:
                raise PktTypeError(
                    u"Type mismatch: null cannot be assigned to "
                    u"non-nullable type '{}'".format(base_type),
                    line=line, column=column)

        # Check if the value is a PktInstance whose class name matches
        # BEFORE checking built-in types so that user-defined classes
        # (e.g. a generic class named 'Pair') take priority over
        # same-named built-in types (e.g. the Pair key-value type).
        if isinstance(value, PktInstance):
            if value.type_name == base_type or self._instance_isa(value, base_type):
                # Compare generic type args when both sides have them
                if type_args and value.type_args and type_args != value.type_args:
                    raise PktTypeError(
                        u"Type mismatch: expected '{}<{}>', "
                        u"got '{}<{}>'".format(
                            base_type, u','.join(type_args),
                            base_type, u','.join(value.type_args)),
                        line=line, column=column)
                return

        # Check built-in types
        expected_types = self._TYPE_MAP.get(base_type)
        if expected_types is not None:
            if isinstance(value, expected_types):
                return
            raise PktTypeError(
                u"Type mismatch: expected type '{}', got '{}'".format(
                    type_annotation, value.type_name),
                line=line, column=column)
            if value.type_name == base_type or self._instance_isa(value, base_type):
                # Compare generic type args when both sides have them
                if type_args and value.type_args and type_args != value.type_args:
                    raise PktTypeError(
                        u"Type mismatch: expected '{}<{}>', "
                        u"got '{}<{}>'".format(
                            base_type, u','.join(type_args),
                            base_type, u','.join(value.type_args)),
                        line=line, column=column)
                return

        # Check if the value is a PktPythonInstance whose class name matches
        if isinstance(value, PktPythonInstance):
            if value.type_name == base_type:
                return
            try:
                klass = self.environment.get(base_type)
                if isinstance(klass, PktPythonClass):
                    if isinstance(value._py_instance, klass._py_class):
                        return
            except PktRuntimeError:
                pass

        # Try to resolve the type name as a class in the environment
        try:
            klass = self.environment.get(base_type)
            if isinstance(klass, (PktClass, PktPythonClass, PktExceptionClass)):
                if isinstance(value, PktInstance):
                    current = value.klass
                    while current is not None:
                        if current is klass:
                            return
                        current = (current.parent_class
                                   if hasattr(current, 'parent_class') else None)
                if isinstance(value, PktPythonInstance) and isinstance(klass, PktPythonClass):
                    if isinstance(value._py_instance, klass._py_class):
                        return
        except PktRuntimeError:
            pass

        # If the type name was NOT resolved at all, treat it as a generic
        # type parameter (type-erasure semantics).
        if base_type and not type_args:
            if base_type not in self._TYPE_MAP:
                try:
                    self.environment.get(base_type)
                except PktRuntimeError:
                    return

        raise PktTypeError(
            u"Type mismatch: expected type '{}', got '{}'".format(
                type_annotation, value.type_name),
            line=line, column=column)

    def _instance_isa(self, value, base_type):
        """Check if a PktInstance inherits from a class named base_type."""
        current = value.klass
        while current is not None:
            if current.name == base_type:
                return True
            current = (current.parent_class
                       if hasattr(current, 'parent_class') else None)
        return False

    # ------------------------------------------------------------------
    # Static type inference for if-expression branch validation
    # ------------------------------------------------------------------

    def _type_name_of(self, pkt_value):
        """Return a canonical type name string for a PktValue."""
        if isinstance(pkt_value, PktNull):
            return u'Unit'
        if isinstance(pkt_value, PktInt):
            return u'Int'
        if isinstance(pkt_value, PktDouble):
            return u'Double'
        if isinstance(pkt_value, PktString):
            return u'String'
        if isinstance(pkt_value, PktBoolean):
            return u'Boolean'
        if isinstance(pkt_value, PktList):
            return u'List'
        if isinstance(pkt_value, PktArray):
            return u'Array'
        if isinstance(pkt_value, PktMap):
            return u'Map'
        if isinstance(pkt_value, PktPair):
            return u'Pair'
        if isinstance(pkt_value, PktIntRange):
            return u'IntRange'
        if isinstance(pkt_value, (PktFunction, PktBuiltinFunction, BoundMethod)):
            return u'Function'
        return pkt_value.type_name

    def _static_type_of(self, node):
        """Statically infer the type of an AST expression **without**
        executing it.

        Returns a type name string (e.g. ``'Int'``, ``'String'``,
        ``'Boolean'``), ``'Unit'`` for PktNull, or ``None`` when the
        type cannot be determined statically.
        """
        # --- literals ---
        if isinstance(node, ast.LiteralExpr):
            val = node.value
            if val is None:
                return u'Unit'
            if isinstance(val, bool):
                return u'Boolean'
            if isinstance(val, int):
                return u'Int'
            if isinstance(val, float):
                return u'Double'
            if isinstance(val, (unicode, str)):
                return u'String'
            return None

        # --- blocks ---
        if isinstance(node, ast.BlockStmt):
            for s in reversed(node.statements):
                t = self._static_type_of(s)
                if t is not None:
                    return t
            return u'Unit'

        # --- if-expression ---
        if isinstance(node, ast.IfExpr):
            t_then = self._static_type_of(node.then_branch)
            t_else = self._static_type_of(node.else_branch)
            if t_then == t_else:
                return t_then
            if t_then == u'Unit':
                return t_else
            if t_else == u'Unit':
                return t_then
            return None  # inconsistent — the validator will report it

        # --- if-statement with else (expression form inside a block) ---
        if isinstance(node, ast.IfStmt):
            if node.else_branch is not None:
                return self._static_type_of(
                    ast.IfExpr(node.condition, node.then_branch, node.else_branch))
            return u'Unit'

        # --- variable reference ---
        if isinstance(node, ast.IdentifierExpr):
            try:
                ta = self.environment.get_type_annotation(node.name)
                if ta is not None:
                    return ta
                val = self.environment.get(node.name)
                return self._type_name_of(val)
            except PktRuntimeError:
                return None

        # --- arithmetic / comparison ---
        if isinstance(node, ast.InfixExpr):
            op = node.operator.type
            if op in (TokenType.PLUS, TokenType.MINUS, TokenType.STAR,
                       TokenType.SLASH, TokenType.PERCENT):
                lt = self._static_type_of(node.left)
                rt = self._static_type_of(node.right)
                if lt == u'Double' or rt == u'Double':
                    return u'Double'
                if lt == u'Int' and rt == u'Int':
                    return u'Int'
                if lt == u'String' or rt == u'String':
                    return u'String'
            if op in (TokenType.EQ_EQ, TokenType.BANG_EQ,
                       TokenType.LT, TokenType.GT,
                       TokenType.LT_EQ, TokenType.GT_EQ,
                       TokenType.AND_AND, TokenType.OR_OR):
                return u'Boolean'
            if op == TokenType.DOT_DOT:
                return u'IntRange'
            return None

        # --- logical ---
        if isinstance(node, ast.LogicalExpr):
            return u'Boolean'

        # --- prefix ! ---
        if isinstance(node, ast.PrefixExpr):
            if node.operator.type == TokenType.BANG:
                return u'Boolean'
            if node.operator.type == TokenType.MINUS:
                inner = self._static_type_of(node.right)
                if inner in (u'Int', u'Double'):
                    return inner
            return None

        # --- grouping ---
        if isinstance(node, ast.GroupingExpr):
            return self._static_type_of(node.expression)

        # --- function call ---
        if isinstance(node, ast.CallExpr):
            if isinstance(node.callee, ast.IdentifierExpr):
                try:
                    fn = self.environment.get(node.callee.name)
                    decl = getattr(fn, 'declaration', None)
                    if decl is not None and decl.return_type is not None:
                        return decl.return_type
                    if isinstance(fn, PktClass):
                        return fn.name  # constructor → instance type
                except PktRuntimeError:
                    pass
            return None

        # --- string template → always String ---
        if isinstance(node, ast.StringTemplateExpr):
            return u'String'

        # --- list literal → List ---
        if isinstance(node, ast.ListLiteralExpr):
            return u'List'

        # --- elvis ---
        if isinstance(node, ast.ElvisExpr):
            lt = self._static_type_of(node.left)
            rt = self._static_type_of(node.right)
            if lt == rt:
                return lt
            if lt is not None and lt.endswith(u'?'):
                return lt  # left is nullable, right provides default
            if rt is not None:
                return rt
            return lt

        # --- null-safe access — passthrough ---
        if isinstance(node, ast.NullSafeGetExpr):
            return None  # depends on the object's property type

        # --- expression-statement wrapper ---
        if isinstance(node, ast.ExprStmt):
            return self._static_type_of(node.expression)

        # --- return statement ---
        if isinstance(node, ast.ReturnStmt):
            if node.value is not None:
                return self._static_type_of(node.value)
            return u'Unit'

        # --- anything else: can't determine statically ---
        return None

    def _validate_if_expr_types(self, node):
        """Recursively validate type consistency of all IfExpr nodes
        in an AST subtree.

        For each ``IfExpr`` the static types of the then- and else-branch
        are inferred and compared.  A mismatch raises ``PktTypeError``
        so the error is surfaced before any code executes (matching
        Kotlin's compile-time branch-type unification).
        """
        if node is None:
            return

        # ---- IfExpr: the primary target ----
        if isinstance(node, ast.IfExpr):
            t_then = self._static_type_of(node.then_branch)
            t_else = self._static_type_of(node.else_branch)

            if t_then is not None and t_else is not None:
                if t_then != t_else and t_then != u'Unit' and t_else != u'Unit':
                    raise PktTypeError(
                        u"Type mismatch in if-expression: "
                        u"then branch returns '{}', "
                        u"else branch returns '{}'".format(t_then, t_else),
                        line=node.line, column=node.column)

            # Recurse into branches (handles else-if chains)
            self._validate_if_expr_types(node.then_branch)
            self._validate_if_expr_types(node.else_branch)
            self._validate_if_expr_types(node.condition)
            return

        # ---- IfStmt: if-else in statement position used as expression ----
        if isinstance(node, ast.IfStmt):
            if node.else_branch is not None:
                # Treat as IfExpr for validation purposes
                self._validate_if_expr_types(
                    ast.IfExpr(node.condition, node.then_branch, node.else_branch))
            else:
                self._validate_if_expr_types(node.condition)
                self._validate_if_expr_types(node.then_branch)
            return

        # ---- containers: recurse into children ----
        if isinstance(node, ast.BlockStmt):
            for s in node.statements:
                self._validate_if_expr_types(s)
            return

        if isinstance(node, ast.VarDecl):
            self._validate_if_expr_types(node.initializer)
            return

        if isinstance(node, ast.ExprStmt):
            self._validate_if_expr_types(node.expression)
            return

        if isinstance(node, ast.ReturnStmt):
            self._validate_if_expr_types(node.value)
            return

        if isinstance(node, ast.FunDecl):
            self._validate_if_expr_types(node.body)
            return

        if isinstance(node, ast.ClassDecl):
            for m in node.members:
                self._validate_if_expr_types(m)
            return

        if isinstance(node, ast.InitBlock):
            self._validate_if_expr_types(node.body)
            return

        if isinstance(node, ast.TryExpr):
            self._validate_if_expr_types(node.try_block)
            for c in node.catch_clauses:
                self._validate_if_expr_types(c.body)
            self._validate_if_expr_types(node.finally_block)
            return

        if isinstance(node, ast.WhenStmt):
            for b in node.branches:
                self._validate_if_expr_types(b.body)
            return

        if isinstance(node, ast.ForStmt):
            self._validate_if_expr_types(node.body)
            return

        if isinstance(node, ast.WhileStmt):
            self._validate_if_expr_types(node.body)
            return

        # ---- expression wrappers ---
        if isinstance(node, ast.GroupingExpr):
            self._validate_if_expr_types(node.expression)
            return

        if isinstance(node, ast.PrefixExpr):
            self._validate_if_expr_types(node.right)
            return

        if isinstance(node, ast.PostfixExpr):
            self._validate_if_expr_types(node.left)
            return

        if isinstance(node, ast.InfixExpr):
            self._validate_if_expr_types(node.left)
            self._validate_if_expr_types(node.right)
            return

        if isinstance(node, ast.LogicalExpr):
            self._validate_if_expr_types(node.left)
            self._validate_if_expr_types(node.right)
            return

        if isinstance(node, ast.AssignExpr):
            self._validate_if_expr_types(node.value)
            return

        if isinstance(node, ast.CallExpr):
            self._validate_if_expr_types(node.callee)
            for a in node.arguments:
                self._validate_if_expr_types(a)
            return

        if isinstance(node, ast.ElvisExpr):
            self._validate_if_expr_types(node.left)
            self._validate_if_expr_types(node.right)
            return

        if isinstance(node, ast.NotNullAssertExpr):
            self._validate_if_expr_types(node.expression)
            return

        if isinstance(node, ast.ThrowExpr):
            self._validate_if_expr_types(node.expression)
            return

        # ---- leaf nodes (IdentifierExpr, LiteralExpr, etc.): nothing to do ----
        return

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def interpret(self, statements):
        """Execute a list of top-level statements.

        A static validation pass runs **before** execution to catch
        if-expression branch type mismatches at parse/type-inference time
        (matching Kotlin's compile-time behaviour).

        Args:
            statements: List of Stmt AST nodes.

        Raises:
            PktTypeError: If a static type check (e.g. if-expr branch
                mismatch) fails.
            PktRuntimeError: If a runtime error occurs.
        """
        # ---- Phase 1: static type validation ----
        for stmt in statements:
            self._validate_if_expr_types(stmt)

        # ---- Phase 2: execution ----
        try:
            for stmt in statements:
                self._execute(stmt)
        except ReturnException:
            raise PktRuntimeError(
                u'Cannot return from top-level code')
        except ThrowException as thrown:
            exc = thrown.value
            exc_type = exc.type_name if hasattr(exc, 'type_name') else type(exc).__name__
            msg = unicode(exc) if unicode(exc) else u'(no message)'
            raise PktRuntimeError(
                u'Uncaught {}: {}'.format(exc_type, msg))

    # ------------------------------------------------------------------
    # Statement dispatch
    # ------------------------------------------------------------------

    def _execute(self, stmt):
        """Dispatch a statement for execution based on its type."""
        if stmt is None:
            return None

        class_name = type(stmt).__name__
        method_name = u'_visit_' + class_name
        visitor = getattr(self, method_name, None)
        if visitor is None:
            raise PktRuntimeError(
                u'Unknown statement type: {}'.format(class_name),
                line=stmt.line, column=stmt.column)
        return visitor(stmt)

    def _execute_block(self, block):
        """Execute a BlockStmt (list of statements) directly.

        This is the shared execution path for blocks, used both by
        _visit_BlockStmt and by class init block execution.
        """
        for stmt in block.statements:
            self._execute(stmt)

    # ------------------------------------------------------------------
    # Value unwrapping (delegates to runtime)
    # ------------------------------------------------------------------

    def _unwrap(self, pkt_val):
        """将 PktValue 转为 Python 可用对象。

        委托给 runtime 的 _unwrap_value，它会将 PktFunction 包装为
        Python-callable wrapper、PktList 包装为 list-like proxy 等。
        """
        runtime_ref = getattr(self, '_runtime_ref', None)
        if runtime_ref is not None:
            return runtime_ref._unwrap_value(pkt_val)
        return _pkt_to_py_raw(pkt_val)

    # ------------------------------------------------------------------
    # Expression dispatch
    # ------------------------------------------------------------------

    def _evaluate(self, expr):
        """Dispatch an expression for evaluation based on its type."""
        if expr is None:
            return PktNull()

        class_name = type(expr).__name__
        method_name = u'_visit_' + class_name
        visitor = getattr(self, method_name, None)
        if visitor is None:
            raise PktRuntimeError(
                u'Unknown expression type: {}'.format(class_name),
                line=expr.line, column=expr.column)
        return visitor(expr)

    # ==================================================================
    # Statement visitors
    # ==================================================================

    def _visit_VarDecl(self, stmt):
        """Execute a variable declaration: val/var name [: Type] [= initializer]

        Enforces Kotlin-style static type checking:
          - If a type annotation is present, the initializer must match.
          - Non-nullable types reject null values.
          - Nullable types (e.g., 'Int?') accept null values.
          - Without a type annotation, type is inferred from the initializer.
        """
        value = PktNull()
        if stmt.initializer is not None:
            value = self._evaluate(stmt.initializer)

        # Validate type annotation against the actual value
        if stmt.type_annotation is not None:
            self._validate_type(value, stmt.type_annotation, stmt.line, stmt.column)

        self.environment.define(stmt.name, value, is_val=stmt.is_val,
                               type_annotation=stmt.type_annotation)
        return None

    def _visit_FunDecl(self, stmt):
        """Execute a function declaration (or evaluate an anonymous function).

        For named functions: creates a PktFunction and defines it in the environment.
        For anonymous functions (lambda): just creates and returns the PktFunction.

        Returns the PktFunction in all cases.
        """
        func = PktFunction(stmt, self.environment)
        # Only define in environment if it has a real name
        if stmt.name != u'<lambda>':
            self.environment.define(stmt.name, func, is_val=True)
        return func

    def _visit_ClassDecl(self, stmt):
        """Execute a class declaration.

        Handles inheritance: resolves parent class, validates open/override,
        chains constructors, and sets up method resolution.
        """
        methods = {}
        instance_properties = {}
        init_blocks = []
        overridden_methods = set()

        for member in stmt.members:
            if isinstance(member, ast.FunDecl):
                method_func = PktFunction(member, self.environment)
                methods[member.name] = method_func
                if member.is_override:
                    overridden_methods.add(member.name)

            elif isinstance(member, ast.VarDecl):
                instance_properties[member.name] = {
                    'is_val': member.is_val,
                    'initializer': member.initializer,
                    'type_annotation': member.type_annotation,
                }

            elif isinstance(member, ast.InitBlock):
                init_blocks.append(member)

        # Resolve parent class and super constructor arguments
        parent_class = None
        parent_constructor_arg_asts = []  # AST nodes, evaluated at instantiation

        if stmt.superclass is not None:
            if isinstance(stmt.superclass, ast.SuperConstructorCall):
                # Superclass with constructor args: : Parent(args)
                parent_class = self._evaluate(stmt.superclass.class_expr)
                parent_constructor_arg_asts = stmt.superclass.arguments  # store ASTs
            elif isinstance(stmt.superclass, ast.IdentifierExpr):
                # Superclass without args: : Parent
                parent_class = self._evaluate(stmt.superclass)
            else:
                parent_class = self._evaluate(stmt.superclass)

            if not isinstance(parent_class, (PktClass, PktPythonClass, PktExceptionClass)):
                raise PktRuntimeError(
                    u"Superclass must be a class, got '{}'".format(
                        parent_class.type_name),
                    line=stmt.line, column=stmt.column)

            # Validate: parent class must be open
            if isinstance(parent_class, PktClass) and not parent_class.is_open:
                raise PktRuntimeError(
                    u"Cannot inherit from final class '{}'. "
                    u"Mark the parent class as 'open'.".format(
                        parent_class.name),
                    line=stmt.line, column=stmt.column)

            # Validate overridden methods exist in parent
            if isinstance(parent_class, PktClass):
                for name in overridden_methods:
                    if not parent_class.has_method(name):
                        raise PktRuntimeError(
                            u"Method '{}' overrides nothing in parent class '{}'".format(
                                name, parent_class.name),
                            line=stmt.line, column=stmt.column)

        klass = PktClass(
            name=stmt.name,
            constructor_params=stmt.constructor_params,
            parent_class=parent_class,
            methods=methods,
            instance_properties=instance_properties,
            init_blocks=init_blocks,
            is_open=stmt.is_open,
            parent_constructor_arg_asts=parent_constructor_arg_asts,
            type_params=stmt.type_params,
        )

        self.environment.define(stmt.name, klass, is_val=True)
        return None

    def _visit_ExprStmt(self, stmt):
        """Execute an expression statement (discard the value)."""
        self._evaluate(stmt.expression)
        return None

    def _visit_BlockStmt(self, stmt):
        """Execute a block, creating a new scope."""
        previous = self.environment
        self.environment = Environment(enclosing=previous)
        try:
            self._execute_block(stmt)
        finally:
            self.environment = previous
        return None

    def _visit_IfStmt(self, stmt):
        """Execute an if/else statement."""
        condition = self._evaluate(stmt.condition)
        if condition.is_truthy():
            self._execute(stmt.then_branch)
        elif stmt.else_branch is not None:
            self._execute(stmt.else_branch)
        return None

    def _visit_ForStmt(self, stmt):
        """Execute a for loop.

        Supports:
          - Range iteration: for (i in 1..10)
          - List iteration: for (x in [1, 2, 3])
        """
        iterable = self._evaluate(stmt.iterable)

        # Create the loop scope
        previous = self.environment
        self.environment = Environment(enclosing=previous)

        try:
            if isinstance(iterable, PktIntRange):
                # Range iteration
                for i in iterable.to_list():
                    self.environment.define(stmt.variable, PktInt(i), is_val=False)
                    try:
                        self._execute(stmt.body)
                    except BreakException:
                        break
                    except ContinueException:
                        continue

            elif isinstance(iterable, PktList):
                # List iteration
                for elem in iterable.elements:
                    self.environment.define(stmt.variable, elem, is_val=False)
                    try:
                        self._execute(stmt.body)
                    except BreakException:
                        break
                    except ContinueException:
                        continue

            else:
                raise PktRuntimeError(
                    u"Cannot iterate over '{}'".format(iterable.type_name),
                    line=stmt.line, column=stmt.column)
        finally:
            self.environment = previous
        return None

    def _visit_WhileStmt(self, stmt):
        """Execute a while loop."""
        while True:
            condition = self._evaluate(stmt.condition)
            if not condition.is_truthy():
                break

            try:
                self._execute(stmt.body)
            except BreakException:
                break
            except ContinueException:
                continue
        return None

    def _visit_TryExpr(self, stmt):
        """Execute a try-catch-finally expression.

        try: executes try_block, captures last expression value.
        catch: matches thrown PktException against catch clause types,
               captures last expression value.
        finally: ALWAYS executes (even if return/throw/break/continue).

        As an expression, returns the last value from try or catch block.
        """
        result = PktNull()

        try:
            # Execute try block in its own scope
            previous = self.environment
            self.environment = Environment(enclosing=previous)
            try:
                result = self._execute_block_with_value(stmt.try_block)
            except ReturnException as ret:
                result = ret.value
            finally:
                self.environment = previous

        except ThrowException as thrown:
            # Try to match a catch clause
            caught = False
            exc_val = thrown.value

            for clause in stmt.catch_clauses:
                if self._catch_matches(clause, exc_val):
                    # Execute catch block with exception variable bound
                    previous = self.environment
                    catch_env = Environment(enclosing=previous)
                    catch_env.define(clause.exception_var, exc_val, is_val=True,
                                    type_annotation=clause.exception_type)
                    self.environment = catch_env

                    try:
                        result = self._execute_block_with_value(clause.body)
                        caught = True
                        break
                    except ReturnException as ret:
                        result = ret.value
                        caught = True
                        break
                    finally:
                        self.environment = previous

            if not caught:
                # Re-throw if no catch clause matched
                # Execute finally first, then re-throw
                if stmt.finally_block is not None:
                    previous = self.environment
                    self.environment = Environment(enclosing=previous)
                    try:
                        self._execute_block(stmt.finally_block)
                    finally:
                        self.environment = previous
                raise thrown

        finally:
            # Finally block ALWAYS executes
            if stmt.finally_block is not None:
                previous = self.environment
                self.environment = Environment(enclosing=previous)
                try:
                    self._execute_block(stmt.finally_block)
                except ReturnException:
                    pass  # return in finally suppresses try/catch return
                finally:
                    self.environment = previous

        return result

    def _execute_block_with_value(self, block):
        """Execute a block and return the value of the last expression.

        Walks all statements. For ExprStmt nodes, evaluates directly instead
        of delegating to _execute (to avoid double-evaluation).
        Returns the last captured value, or PktNull() if none.
        """
        last_value = PktNull()
        for s in block.statements:
            if isinstance(s, ast.ExprStmt):
                last_value = self._evaluate(s.expression)
            else:
                self._execute(s)
                last_value = PktNull()  # non-expression resets the value
        return last_value

    def _catch_matches(self, clause, exc_val):
        """Check if an exception value matches a catch clause."""
        exc_type = clause.exception_type

        if exc_type is None:
            return True

        base_type = exc_type.rstrip('?')

        # Handle PktInstance (exception subclass instances)
        if isinstance(exc_val, PktInstance):
            # Check if the instance's class matches the catch type
            if exc_val.type_name == base_type:
                return True
            # Check parent classes
            current = exc_val.klass
            while current is not None:
                if current.name == base_type:
                    return True
                if isinstance(current, PktExceptionClass) and current._exc_name == base_type:
                    return True
                current = current.parent_class if hasattr(current, 'parent_class') else None
            # Also match by parent Throwable types
            if base_type == u'Throwable':
                return self._class_inherits_throwable(exc_val.klass)
            if base_type == u'Exception':
                return self._class_inherits_exception(exc_val.klass)
            return False

        # Throwable hierarchy matching
        if base_type == u'Throwable':
            return isinstance(exc_val, PktThrowable)
        if base_type == u'Exception':
            return isinstance(exc_val, PktException)
        if base_type == u'RuntimeException':
            return isinstance(exc_val, PktRuntimeException)
        if base_type == u'Error':
            return isinstance(exc_val, PktError)

        # For PktPythonException, match by Python exception type name
        if isinstance(exc_val, PktPythonException):
            py_exc_name = type(exc_val.python_exception).__name__
            return unicode(py_exc_name) == base_type

        # For any PktThrowable subclass, match by type_name
        if isinstance(exc_val, PktThrowable):
            return exc_val.type_name == base_type

        return exc_val.type_name == base_type

    def _class_inherits_exception(self, klass):
        """Check if a PktClass inherits from Exception."""
        current = klass
        while current is not None:
            if isinstance(current, PktExceptionClass) and current._exc_name in (u'Exception', u'RuntimeException'):
                return True
            current = current.parent_class if hasattr(current, 'parent_class') else None
        return False

    def _visit_ThrowExpr(self, expr):
        """Evaluate a throw expression: throw expression

        Kotlin semantics: only PktThrowable (or subclass) instances may be thrown.
        Also accepts PktInstance if its class inherits from Exception/Throwable.
        """
        value = self._evaluate(expr.expression)

        if isinstance(value, PktThrowable):
            raise ThrowException(value)

        # Accept PktInstance whose class inherits from an exception class
        if isinstance(value, PktInstance):
            if self._class_inherits_throwable(value.klass):
                raise ThrowException(value)

        # Allow throwing Python exception instances
        if isinstance(value, PktPythonInstance):
            py_obj = value._py_instance
            if isinstance(py_obj, BaseException):
                raise ThrowException(PktPythonException(py_obj))

        raise PktTypeError(
            u"throw requires a Throwable, got '{}' (type: {})".format(
                unicode(value), value.type_name),
            line=expr.line, column=expr.column)

    def _class_inherits_throwable(self, klass):
        """Check if a PktClass inherits from Throwable through its parent chain."""
        current = klass
        while current is not None:
            if isinstance(current, PktExceptionClass):
                return True
            current = current.parent_class if hasattr(current, 'parent_class') else None
        return False

    def _visit_NotNullAssertExpr(self, expr):
        """Evaluate not-null assertion: expr!!

        Returns expr if non-null, otherwise throws a Kotlin-like NullPointerException.
        """
        value = self._evaluate(expr.expression)
        if isinstance(value, PktNull):
            raise ThrowException(PktRuntimeException(
                PktString(u'NullPointerException: expression evaluated to null')))
        return value

    def _visit_ReturnStmt(self, stmt):
        """Execute a return statement.

        Validates the return value against the current function's declared
        or inferred return type (Kotlin semantics):

          - Block body without explicit return type → inferred 'Unit'.
            Only bare ``return`` or ``return`` of a Unit/null value is
            allowed; ``return <expr>`` with a non-Unit value raises
            a type-mismatch error.

          - Explicit return type (e.g., ``: Int``, ``: String?``) →
            the returned value is validated with the standard type check.
        """
        value = PktNull()
        if stmt.value is not None:
            value = self._evaluate(stmt.value)

        # Validate return value against the enclosing function's return type
        if self._current_function_return_type is not None:
            if stmt.value is None:
                # Bare 'return' — only valid for Unit / Any functions
                if self._current_function_return_type not in (u'Unit', u'Any'):
                    raise PktTypeError(
                        u"Type mismatch: function expects return type '{}', "
                        u"but 'return' has no value".format(
                            self._current_function_return_type),
                        line=stmt.line, column=stmt.column)
            elif self._current_function_return_type == u'Unit':
                # Block body w/o return type → inferred Unit
                if not isinstance(value, PktNull):
                    raise PktTypeError(
                        u"Type mismatch: inferred return type is 'Unit', "
                        u"but returned '{}'".format(value.type_name),
                        line=stmt.line, column=stmt.column)
            elif self._current_function_return_type == u'Any':
                # Any accepts any return value — no validation
                pass
            else:
                # Explicit return type → validate via standard type check
                self._validate_type(value, self._current_function_return_type,
                                    stmt.line, stmt.column)

        raise ReturnException(value)

    def _visit_BreakStmt(self, stmt):
        """Execute a break statement."""
        raise BreakException()

    def _visit_ContinueStmt(self, stmt):
        """Execute a continue statement."""
        raise ContinueException()

    def _visit_InitBlock(self, stmt):
        """Execute an init block (called during class construction)."""
        previous = self.environment
        # Init blocks execute in the instance environment, set up by PktClass.call()
        try:
            self._execute_block(stmt.body)
        finally:
            self.environment = previous
        return None

    # ==================================================================
    # Expression visitors
    # ==================================================================

    def _visit_LiteralExpr(self, expr):
        """Evaluate a literal value."""
        value = expr.value
        if value is None:
            return PktNull()
        if isinstance(value, bool):
            return PktBoolean.TRUE if value else PktBoolean.FALSE
        if isinstance(value, int):
            return PktInt(value)
        if isinstance(value, float):
            return PktDouble(value)
        if isinstance(value, (unicode, str)):
            return PktString(value)
        # Fallback
        raise PktRuntimeError(
            u'Unknown literal type: {}'.format(type(value).__name__),
            line=expr.line, column=expr.column)

    def _visit_IdentifierExpr(self, expr):
        """Evaluate a variable reference."""
        return self.environment.get(expr.name)

    def _visit_PrefixExpr(self, expr):
        """Evaluate a prefix unary expression: -x, !x, ++x, --x"""
        right = self._evaluate(expr.right)
        op_type = expr.operator.type

        if op_type == TokenType.MINUS:
            if isinstance(right, PktInt):
                return PktInt(-right.value)
            elif isinstance(right, PktDouble):
                return PktDouble(-right.value)
            else:
                raise PktTypeError(
                    u"Cannot negate type '{}'".format(right.type_name),
                    line=expr.line, column=expr.column)

        elif op_type == TokenType.BANG:
            return PktBoolean(not right.is_truthy())

        elif op_type == TokenType.PLUS_PLUS:
            # ++x: increment and return new value
            if isinstance(expr.right, ast.IdentifierExpr):
                name = expr.right.name
                old = self.environment.get(name)
                if isinstance(old, PktInt):
                    new_val = PktInt(old.value + 1)
                elif isinstance(old, PktDouble):
                    new_val = PktDouble(old.value + 1.0)
                else:
                    raise PktTypeError(
                        u"Cannot increment type '{}'".format(old.type_name),
                        line=expr.line, column=expr.column)
                self.environment.assign(name, new_val)
                return new_val
            else:
                raise PktRuntimeError(
                    u'++ can only be applied to a variable',
                    line=expr.line, column=expr.column)

        elif op_type == TokenType.MINUS_MINUS:
            # --x: decrement and return new value
            if isinstance(expr.right, ast.IdentifierExpr):
                name = expr.right.name
                old = self.environment.get(name)
                if isinstance(old, PktInt):
                    new_val = PktInt(old.value - 1)
                elif isinstance(old, PktDouble):
                    new_val = PktDouble(old.value - 1.0)
                else:
                    raise PktTypeError(
                        u"Cannot decrement type '{}'".format(old.type_name),
                        line=expr.line, column=expr.column)
                self.environment.assign(name, new_val)
                return new_val
            else:
                raise PktRuntimeError(
                    u'-- can only be applied to a variable',
                    line=expr.line, column=expr.column)

        return PktNull()

    def _visit_PostfixExpr(self, expr):
        """Evaluate a postfix expression: x++, x--"""
        op_type = expr.operator.type

        if isinstance(expr.left, ast.IdentifierExpr):
            name = expr.left.name
            old = self.environment.get(name)

            if op_type == TokenType.PLUS_PLUS:
                if isinstance(old, PktInt):
                    new_val = PktInt(old.value + 1)
                elif isinstance(old, PktDouble):
                    new_val = PktDouble(old.value + 1.0)
                else:
                    raise PktTypeError(
                        u"Cannot increment type '{}'".format(old.type_name),
                        line=expr.line, column=expr.column)
                self.environment.assign(name, new_val)
                return old  # return OLD value for postfix

            elif op_type == TokenType.MINUS_MINUS:
                if isinstance(old, PktInt):
                    new_val = PktInt(old.value - 1)
                elif isinstance(old, PktDouble):
                    new_val = PktDouble(old.value - 1.0)
                else:
                    raise PktTypeError(
                        u"Cannot decrement type '{}'".format(old.type_name),
                        line=expr.line, column=expr.column)
                self.environment.assign(name, new_val)
                return old  # return OLD value for postfix
        else:
            raise PktRuntimeError(
                u'Postfix operator can only be applied to a variable',
                line=expr.line, column=expr.column)

        return PktNull()

    def _visit_InfixExpr(self, expr):
        """Evaluate a binary expression.

        Handles arithmetic operators (+, -, *, /, %) and comparison
        operators (==, !=, <, >, <=, >=).
        """
        op_type = expr.operator.type

        # Short-circuit logical operators handled by LogicalExpr, but
        # we handle them here too just in case
        if op_type in (TokenType.AND_AND, TokenType.OR_OR):
            left = self._evaluate(expr.left)
            if op_type == TokenType.AND_AND:
                if not left.is_truthy():
                    return left
                return self._evaluate(expr.right)
            else:  # OR_OR
                if left.is_truthy():
                    return left
                return self._evaluate(expr.right)

        # Range operator
        if op_type == TokenType.DOT_DOT:
            left = self._evaluate(expr.left)
            right = self._evaluate(expr.right)
            if not isinstance(left, PktInt) or not isinstance(right, PktInt):
                raise PktTypeError(
                    u'Range operator (..) requires Int operands',
                    line=expr.line, column=expr.column)
            return PktIntRange(left.value, right.value)

        # Arithmetic operators
        op_func = BINARY_OPS.get(op_type)
        if op_func is not None:
            left = self._evaluate(expr.left)
            right = self._evaluate(expr.right)
            return op_func(expr.operator, left, right)

        # Comparison operators
        op_func = COMPARE_OPS.get(op_type)
        if op_func is not None:
            left = self._evaluate(expr.left)
            right = self._evaluate(expr.right)
            return op_func(expr.operator, left, right)

        raise PktRuntimeError(
            u'Unknown binary operator: {}'.format(expr.operator.lexeme),
            line=expr.line, column=expr.column)

    def _visit_LogicalExpr(self, expr):
        """Evaluate a short-circuit logical expression (&&, ||)."""
        left = self._evaluate(expr.left)

        if expr.operator.type == TokenType.AND_AND:
            # &&: return left if falsey, else evaluate and return right
            if not left.is_truthy():
                return left
            return self._evaluate(expr.right)
        else:
            # ||: return left if truthy, else evaluate and return right
            if left.is_truthy():
                return left
            return self._evaluate(expr.right)

    def _visit_AssignExpr(self, expr):
        """Evaluate an assignment: name = value.

        Enforces type checking: if the variable was declared with a type
        annotation, the new value must be compatible with that type.
        """
        value = self._evaluate(expr.value)

        # Type check against the variable's declared type annotation
        type_annotation = self.environment.get_type_annotation(expr.name)
        if type_annotation is not None:
            self._validate_type(value, type_annotation, expr.line, expr.column)

        self.environment.assign(expr.name, value)
        return value

    def _visit_CompoundAssignExpr(self, expr):
        """Evaluate a compound assignment: name += value, name -= value, etc.

        Desugars to: name = name op value
        """
        old_value = self.environment.get(expr.name)
        right_value = self._evaluate(expr.value)

        op_type = expr.operator.type

        if op_type == TokenType.PLUS_EQ:
            # name += value -> name = name + value
            new_value = _binary_add(expr.operator, old_value, right_value)
        elif op_type == TokenType.MINUS_EQ:
            new_value = _binary_subtract(expr.operator, old_value, right_value)
        elif op_type == TokenType.STAR_EQ:
            new_value = _binary_multiply(expr.operator, old_value, right_value)
        elif op_type == TokenType.SLASH_EQ:
            new_value = _binary_divide(expr.operator, old_value, right_value)
        elif op_type == TokenType.PERCENT_EQ:
            new_value = _binary_modulo(expr.operator, old_value, right_value)
        else:
            raise PktRuntimeError(
                u'Unknown compound assignment operator: {}'.format(expr.operator.lexeme),
                line=expr.line, column=expr.column)

        self.environment.assign(expr.name, new_value)
        return new_value

    def _visit_CallExpr(self, expr):
        """Evaluate a function call: callee(arguments).

        Supports:
          - User-defined functions (PktFunction)
          - Built-in functions (PktBuiltinFunction) — Python exceptions caught
          - Class constructors (PktClass)
          - Python classes (PktPythonClass)
          - Bound methods (BoundMethod)
          - Python method wrappers (PktPythonMethod) — Python exceptions caught
        """
        callee = self._evaluate(expr.callee)

        # Evaluate arguments left-to-right
        arguments = [self._evaluate(arg) for arg in expr.arguments]

        if isinstance(callee, PktBuiltinFunction):
            try:
                return callee.func(self, arguments)
            except ThrowException:
                raise  # re-raise Kotlin exceptions unchanged
            except (PktRuntimeError, PktTypeError):
                raise  # re-raise PyKt runtime errors unchanged
            except Exception as py_exc:
                # Wrap Python exception as PktPythonException (catchable in Kotlin try-catch)
                raise ThrowException(PktPythonException(py_exc))

        elif isinstance(callee, PktFunction):
            return self._call_function(callee, arguments, expr)

        elif isinstance(callee, PktClass):
            return callee.call(self, arguments)

        elif isinstance(callee, PktPythonClass):
            try:
                return callee.call(self, arguments)
            except Exception as py_exc:
                raise ThrowException(PktPythonException(py_exc))

        elif isinstance(callee, BoundMethod):
            return self._call_bound_method(callee, arguments, expr)

        elif isinstance(callee, PktExceptionClass):
            return callee.call(self, arguments)

        elif isinstance(callee, PktPythonMethod):
            raw_args = [self._unwrap(a) for a in arguments]
            try:
                result = callee._method(*raw_args)
            except ThrowException:
                raise
            except Exception as py_exc:
                # Python method exception → catchable in Kotlin try-catch
                raise ThrowException(PktPythonException(py_exc,
                    message=u'{}: {}'.format(type(py_exc).__name__, unicode(py_exc))))
            return _py_to_pkt_value(result)

        else:
            raise PktRuntimeError(
                u"Cannot call value of type '{}'".format(callee.type_name),
                line=expr.line, column=expr.column)

    def _call_function(self, func, arguments, call_expr=None):
        """Invoke a user-defined PktFunction with the given arguments."""
        declaration = func.declaration

        # Check argument count
        if len(arguments) > len(declaration.params):
            raise PktRuntimeError(
                u"Too many arguments for '{}': expected at most {}, got {}".format(
                    declaration.name, len(declaration.params), len(arguments)))

        # Create function scope with closure as parent
        previous = self.environment
        func_env = Environment(enclosing=func.closure)
        self.environment = func_env

        previous_return_type = self._current_function_return_type

        try:
            # ---- Bind parameters ----
            for i, param in enumerate(declaration.params):
                if i < len(arguments):
                    value = arguments[i]
                elif param.default_value is not None:
                    value = self._evaluate(param.default_value)
                else:
                    raise PktRuntimeError(
                        u"No value provided for parameter '{}' in '{}'".format(
                            param.name, declaration.name))

                if param.type_annotation is not None:
                    self._validate_type(value, param.type_annotation,
                                       declaration.line, declaration.column)

                func_env.define(param.name, value, is_val=False,
                               type_annotation=param.type_annotation)

            # ---- Infer generic type bindings & check consistency ----
            type_bindings = {}  # e.g. {'T': 'Int'}
            if declaration.type_params:
                for tp_name in declaration.type_params:
                    bound_type = None
                    for param in declaration.params:
                        if param.type_annotation == tp_name:
                            val = func_env._values.get(param.name)
                            if val is not None:
                                vt = self._type_name_of(val)
                                if bound_type is None:
                                    bound_type = vt
                                elif bound_type != vt:
                                    raise PktTypeError(
                                        u"Type mismatch in generic function "
                                        u"'{}': type parameter '{}' is bound "
                                        u"to both '{}' and '{}'".format(
                                            declaration.name, tp_name,
                                            bound_type, vt),
                                        line=declaration.line,
                                        column=declaration.column)
                    if bound_type is not None:
                        type_bindings[tp_name] = bound_type

            # ---- Substitute type params in return type ----
            effective_return_type = declaration.return_type
            if effective_return_type and type_bindings:
                for tp_name, concrete in type_bindings.items():
                    effective_return_type = effective_return_type.replace(
                        tp_name, concrete)

            if effective_return_type is not None:
                self._current_function_return_type = effective_return_type
            elif declaration.name == u'<lambda>':
                self._current_function_return_type = None
            else:
                self._current_function_return_type = u'Any'

            # ---- Execute body ----
            self._execute_block(declaration.body)
            return PktNull()

        except ReturnException as ret:
            return ret.value
        finally:
            self._current_function_return_type = previous_return_type
            self.environment = previous

    def _call_bound_method(self, bound_method, arguments, call_expr=None):
        """Invoke a method bound to an instance.

        Sets up 'this' in the method environment and calls the function.
        """
        method = bound_method.method
        instance = bound_method.instance
        declaration = method.declaration

        # Check argument count
        if len(arguments) > len(declaration.params):
            raise PktRuntimeError(
                u"Too many arguments for '{}': expected at most {}, got {}".format(
                    declaration.name, len(declaration.params), len(arguments)))

        # Create method scope: instance env as parent, which has 'this' and methods
        instance_env = instance.create_init_environment(self)
        func_env = Environment(enclosing=instance_env)

        previous = self.environment
        self.environment = func_env

        previous_return_type = self._current_function_return_type

        try:
            # ---- Bind parameters ----
            for i, param in enumerate(declaration.params):
                if i < len(arguments):
                    value = arguments[i]
                elif param.default_value is not None:
                    value = self._evaluate(param.default_value)
                else:
                    raise PktRuntimeError(
                        u"No value provided for parameter '{}' in '{}'".format(
                            param.name, declaration.name))

                if param.type_annotation is not None:
                    self._validate_type(value, param.type_annotation,
                                       declaration.line, declaration.column)

                func_env.define(param.name, value, is_val=False,
                               type_annotation=param.type_annotation)

            # ---- Infer generic type bindings & check consistency ----
            type_bindings = {}
            if declaration.type_params:
                for tp_name in declaration.type_params:
                    bound_type = None
                    for param in declaration.params:
                        if param.type_annotation == tp_name:
                            val = func_env._values.get(param.name)
                            if val is not None:
                                vt = self._type_name_of(val)
                                if bound_type is None:
                                    bound_type = vt
                                elif bound_type != vt:
                                    raise PktTypeError(
                                        u"Type mismatch in generic function "
                                        u"'{}': type parameter '{}' is bound "
                                        u"to both '{}' and '{}'".format(
                                            declaration.name, tp_name,
                                            bound_type, vt),
                                        line=declaration.line,
                                        column=declaration.column)
                    if bound_type is not None:
                        type_bindings[tp_name] = bound_type

            # ---- Substitute type params in return type ----
            effective_return_type = declaration.return_type
            if effective_return_type and type_bindings:
                for tp_name, concrete in type_bindings.items():
                    effective_return_type = effective_return_type.replace(
                        tp_name, concrete)

            if effective_return_type is not None:
                self._current_function_return_type = effective_return_type
            elif declaration.name == u'<lambda>':
                self._current_function_return_type = None
            else:
                self._current_function_return_type = u'Any'

            # ---- Execute body ----
            self._execute_block(declaration.body)
            return PktNull()

        except ReturnException as ret:
            return ret.value
        finally:
            self._current_function_return_type = previous_return_type
            self.environment = previous

    def _visit_GetExpr(self, expr):
        """Evaluate a property access: obj.name"""
        obj = self._evaluate(expr.object)
        return obj.get(expr.name)

    def _visit_SetExpr(self, expr):
        """Evaluate a property assignment: obj.name = value"""
        obj = self._evaluate(expr.object)
        value = self._evaluate(expr.value)
        # Type-check against declared property type before setting
        if isinstance(obj, PktInstance):
            type_ann = obj.klass.get_property_type(expr.name)
            if type_ann is not None:
                self._validate_type(value, type_ann, expr.line, expr.column)
        obj.set(expr.name, value, interpreter=self)
        return value

    def _visit_IndexExpr(self, expr):
        """Evaluate an index access: obj[index]"""
        obj = self._evaluate(expr.object)
        index = self._evaluate(expr.index)

        if isinstance(obj, PktList):
            if not isinstance(index, PktInt):
                raise PktTypeError(
                    u'List index must be an Int, got {}'.format(index.type_name),
                    line=expr.line, column=expr.column)
            idx = index.value
            if idx < 0 or idx >= len(obj.elements):
                raise PktRuntimeError(
                    u'List index {} out of bounds (size {})'.format(
                        idx, len(obj.elements)),
                    line=expr.line, column=expr.column)
            return obj.elements[idx]

        elif isinstance(obj, PktArray):
            if not isinstance(index, PktInt):
                raise PktTypeError(
                    u'Array index must be an Int, got {}'.format(index.type_name),
                    line=expr.line, column=expr.column)
            idx = index.value
            if idx < 0 or idx >= obj.size:
                raise PktRuntimeError(
                    u'Array index {} out of bounds (size {})'.format(
                        idx, obj.size),
                    line=expr.line, column=expr.column)
            return obj.elements[idx]

        elif isinstance(obj, PktMap):
            return obj.get_value(index)

        elif isinstance(obj, PktString):
            if not isinstance(index, PktInt):
                raise PktTypeError(
                    u'String index must be an Int, got {}'.format(index.type_name),
                    line=expr.line, column=expr.column)
            idx = index.value
            if idx < 0 or idx >= len(obj.value):
                raise PktRuntimeError(
                    u'String index {} out of bounds (length {})'.format(
                        idx, len(obj.value)),
                    line=expr.line, column=expr.column)
            return PktString(obj.value[idx])

        elif isinstance(obj, PktPythonInstance):
            raw_key = self._unwrap(index)
            try:
                return _py_to_pkt_value(obj._py_instance[raw_key])
            except (KeyError, IndexError, TypeError):
                raise PktRuntimeError(
                    u"Key '{}' not found".format(raw_key),
                    line=expr.line, column=expr.column)

        else:
            raise PktRuntimeError(
                u"Cannot index into type '{}'".format(obj.type_name),
                line=expr.line, column=expr.column)

    def _visit_IndexSetExpr(self, expr):
        """Evaluate an index assignment: obj[index] = value"""
        obj = self._evaluate(expr.object)
        index = self._evaluate(expr.index)
        value = self._evaluate(expr.value)

        if isinstance(obj, PktList):
            if not isinstance(index, PktInt):
                raise PktTypeError(
                    u'List index must be an Int, got {}'.format(index.type_name),
                    line=expr.line, column=expr.column)
            idx = index.value
            if idx < 0 or idx >= len(obj.elements):
                raise PktRuntimeError(
                    u'List index {} out of bounds (size {})'.format(
                        idx, len(obj.elements)),
                    line=expr.line, column=expr.column)
            obj.elements[idx] = value
            if obj._py_backing is not None:
                enc = getattr(getattr(self, '_runtime_ref', None), '_str_encoding', 'unicode')
                obj._py_backing[idx] = _pkt_to_py_raw(value, enc)
            return value

        elif isinstance(obj, PktArray):
            if not isinstance(index, PktInt):
                raise PktTypeError(
                    u'Array index must be an Int, got {}'.format(index.type_name),
                    line=expr.line, column=expr.column)
            idx = index.value
            if idx < 0 or idx >= obj.size:
                raise PktRuntimeError(
                    u'Array index {} out of bounds (size {})'.format(
                        idx, obj.size),
                    line=expr.line, column=expr.column)
            obj.elements[idx] = value
            if obj._py_backing is not None:
                enc = getattr(getattr(self, '_runtime_ref', None), '_str_encoding', 'unicode')
                obj._py_backing[idx] = _pkt_to_py_raw(value, enc)
            return value

        elif isinstance(obj, PktMap):
            obj.put(index, value, interpreter=self)
            return value

        elif isinstance(obj, PktPythonInstance):
            raw_key = self._unwrap(index)
            raw_val = self._unwrap(value)
            try:
                obj._py_instance[raw_key] = raw_val
            except (KeyError, IndexError, TypeError):
                raise PktRuntimeError(
                    u"Cannot set key '{}'".format(raw_key),
                    line=expr.line, column=expr.column)
            return value

        else:
            raise PktRuntimeError(
                u"Cannot assign to index of type '{}'".format(obj.type_name),
                line=expr.line, column=expr.column)

    def _visit_StringTemplateExpr(self, expr):
        """Evaluate a string template: "text $expr text ${expr} text"

        The parser tokenizes the string into parts of literal text and
        embedded expressions. We evaluate the expressions and concatenate.
        """
        parts = []
        for is_expr, value in expr.parts:
            if is_expr:
                # value is an Expr node
                result = self._evaluate(value)
                parts.append(unicode(result))
            else:
                # value is a unicode literal string
                parts.append(value)

        return PktString(u''.join(parts))

    def _visit_RangeExpr(self, expr):
        """Evaluate a range expression: start..end"""
        start = self._evaluate(expr.start)
        end = self._evaluate(expr.end)

        if not isinstance(start, PktInt) or not isinstance(end, PktInt):
            raise PktTypeError(
                u'Range bounds must be Int',
                line=expr.line, column=expr.column)

        return PktIntRange(start.value, end.value)

    def _visit_ListLiteralExpr(self, expr):
        """Evaluate a list literal: [elem1, elem2, ...]"""
        elements = [self._evaluate(elem) for elem in expr.elements]
        return PktList(elements)

    def _visit_NullSafeGetExpr(self, expr):
        """Evaluate null-safe property access: obj?.name

        If obj is null, returns null without error.
        Otherwise, delegates to normal property access.
        """
        obj = self._evaluate(expr.object)
        if isinstance(obj, PktNull):
            return PktNull()
        return obj.get(expr.name)

    def _visit_NullSafeCallExpr(self, expr):
        """Evaluate null-safe method call: obj?.method(args)

        If obj is null, returns null without calling the method.
        Otherwise, evaluates obj.method(args) normally.
        """
        obj = self._evaluate(expr.object)
        if isinstance(obj, PktNull):
            return PktNull()

        # Get the method from the object
        method = obj.get(expr.method_name)

        # Evaluate arguments
        arguments = [self._evaluate(arg) for arg in expr.arguments]

        # Call the method
        if isinstance(method, PktBuiltinFunction):
            return method.func(self, arguments)
        elif isinstance(method, PktFunction):
            return self._call_function(method, arguments, expr)
        elif isinstance(method, BoundMethod):
            return self._call_bound_method(method, arguments, expr)
        else:
            raise PktRuntimeError(
                u"Cannot call value of type '{}'".format(method.type_name),
                line=expr.line, column=expr.column)

    def _visit_ElvisExpr(self, expr):
        """Evaluate Elvis operator: left ?: right

        If left is not null, returns left. Otherwise evaluates and returns right.
        Short-circuits: right is only evaluated if left is null.
        """
        left = self._evaluate(expr.left)
        if not isinstance(left, PktNull):
            return left
        return self._evaluate(expr.right)

    def _visit_ToExpr(self, expr):
        """Evaluate 'to' expression: key to value (creates a Pair)."""
        left = self._evaluate(expr.left)
        right = self._evaluate(expr.right)
        return PktPair(left, right)

    def _visit_MapLiteralExpr(self, expr):
        """Evaluate a map literal: [key to value, ...]"""
        pairs = []
        for key_expr, val_expr in expr.entries:
            key = self._evaluate(key_expr)
            val = self._evaluate(val_expr)
            pairs.append(PktPair(key, val))
        return PktMap(pairs)

    def _visit_SuperExpr(self, expr):
        """Evaluate 'super' expression (reference to parent instance).

        When used as 'super.method()', the GetExpr/CallExpr chain
        resolves through the instance's super lookup.
        """
        this = self.environment.get(u'this')
        if isinstance(this, PktInstance):
            return _SuperProxy(this)
        raise PktRuntimeError(
            u"'super' is only available inside a class",
            line=expr.line, column=expr.column)

    def _visit_ThisExpr(self, expr):
        """Evaluate 'this' expression."""
        return self.environment.get(u'this')

    def _evaluate_branch(self, branch):
        """Evaluate an if/when branch which may be a BlockStmt, an Expr,
        an ExprStmt, or an IfStmt (when used in expression context).

        For a BlockStmt the value is the last expression-statement's result
        (matching Kotlin block-value semantics).  IfStmt with an else branch
        is treated as an expression.  ExprStmt unwraps and evaluates the
        inner expression directly.

        Returns:
            PktValue — the branch result (PktNull if the block has no
            expression statements).
        """
        if isinstance(branch, ast.BlockStmt):
            last = PktNull()
            for s in branch.statements:
                if isinstance(s, ast.ExprStmt):
                    last = self._evaluate(s.expression)
                elif isinstance(s, ast.IfStmt) and s.else_branch is not None:
                    last = self._evaluate_if_as_expr(s)
                else:
                    self._execute(s)
            return last
        elif isinstance(branch, ast.IfStmt):
            return self._evaluate_if_as_expr(branch)
        elif isinstance(branch, ast.ExprStmt):
            # Statement-wrapped expression (common in when branches)
            return self._evaluate(branch.expression)
        else:
            # Plain Expr node
            return self._evaluate(branch)

    def _evaluate_if_as_expr(self, stmt):
        """Evaluate an IfStmt (with else) as an expression.

        This bridges the gap between statement-parsed ``if-else`` inside
        blocks used in expression context and the prefix-parsed ``IfExpr``.
        """
        condition = self._evaluate(stmt.condition)
        if condition.is_truthy():
            return self._evaluate_branch(stmt.then_branch)
        elif stmt.else_branch is not None:
            return self._evaluate_branch(stmt.else_branch)
        else:
            return PktNull()

    def _visit_IfExpr(self, expr):
        """Evaluate an if-expression.

        Kotlin semantics: if is an expression that returns the value of
        the selected branch.  Both branches must be present (the parser
        enforces ``else`` for expression-context if).

        Branch type consistency is validated **statically** before
        execution by ``_validate_if_expr_types``, so only the chosen
        branch is evaluated here — no double-execution side effects.

        Returns:
            The PktValue produced by the chosen branch.
        """
        condition = self._evaluate(expr.condition)
        if condition.is_truthy():
            return self._evaluate_branch(expr.then_branch)
        else:
            return self._evaluate_branch(expr.else_branch)

    def _visit_LambdaExpr(self, expr):
        """Evaluate a lambda expression, returning a PktFunction.

        The lambda captures the current environment as its closure.
        For implicit-``it`` lambdas a single ``it`` parameter is created.
        Explicit-parameter lambdas use the declared parameter names.
        """
        # Build parameter declarations from explicit params or implicit 'it'
        if expr.params:
            params = [ast.Param(name, None, None, False, False)
                      for name in expr.params]
        else:
            params = [ast.Param(u'it', None, None, False, False)]

        # Wrap body expression in a return statement
        ret = ast.ReturnStmt(None, expr.body)
        body_block = ast.BlockStmt([ret])
        # Synthetic function declaration
        decl = ast.FunDecl(u'<lambda>', params, None, body_block)
        func = PktFunction(decl, self.environment)
        return func

    def _visit_GroupingExpr(self, expr):
        """Evaluate a parenthesized expression."""
        return self._evaluate(expr.expression)

    def _visit_IsExpr(self, expr):
        """Evaluate an 'is' type check: expr is Type

        Supported type names: Int, Double, String, Boolean, Null, List, Function
        """
        left = self._evaluate(expr.left)
        type_name = expr.type_name

        type_map = {
            u'Int': PktInt,
            u'Double': PktDouble,
            u'String': PktString,
            u'Boolean': PktBoolean,
            u'Null': PktNull,
            u'List': PktList,
            u'Array': PktArray,
            u'Map': PktMap,
            u'Pair': PktPair,
        }

        expected_type = type_map.get(type_name)
        if expected_type is None:
            raise PktRuntimeError(
                u"Unknown type in 'is' check: '{}'".format(type_name),
                line=expr.line, column=expr.column)

        return PktBoolean(isinstance(left, expected_type))

    def _visit_WhenStmt(self, stmt):
        """Evaluate a when expression, returning the matched branch's value.

        Kotlin semantics: ``when`` is an expression when all branches are
        present (including ``else``).  Each branch's body is evaluated and
        its last expression-statement yields the branch value.
        """
        subject = None
        if stmt.subject is not None:
            subject = self._evaluate(stmt.subject)

        for branch in stmt.branches:
            if branch.is_else:
                try:
                    return self._evaluate_branch(branch.body)
                except ReturnException as ret:
                    return ret.value

            for cond in branch.conditions:
                matched = False
                if subject is not None:
                    cond_val = self._evaluate(cond)
                    if subject.equals(cond_val):
                        matched = True
                else:
                    cond_val = self._evaluate(cond)
                    if cond_val.is_truthy():
                        matched = True

                if matched:
                    try:
                        return self._evaluate_branch(branch.body)
                    except ReturnException as ret:
                        return ret.value

        return PktNull()

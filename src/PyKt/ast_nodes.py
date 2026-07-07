# -*- coding: utf-8 -*-
"""Abstract Syntax Tree node classes for the PyKt language.

All nodes inherit from ASTNode -> Stmt or Expr.
Each node carries line/column for error reporting.
"""

from __future__ import unicode_literals


class ASTNode(object):
    """Base class for all AST nodes."""

    def __init__(self):
        self.line = 0
        self.column = 0

    def set_position(self, token):
        """Set line/column from a Token."""
        self.line = token.line
        self.column = token.column
        return self


# =====================================================================
# Statement nodes
# =====================================================================

class Stmt(ASTNode):
    """Base class for all statement nodes."""
    pass


class VarDecl(Stmt):
    """Variable declaration: val/var name [: Type] [= initializer]

    Attributes:
        name: Variable name (str/unicode).
        type_annotation: Optional type string, or None.
        initializer: Optional initializer expression (Expr), or None.
        is_val: True for 'val' (immutable), False for 'var' (mutable).
    """
    __slots__ = ('name', 'type_annotation', 'initializer', 'is_val')

    def __init__(self, name, type_annotation, initializer, is_val):
        super(VarDecl, self).__init__()
        self.name = name
        self.type_annotation = type_annotation
        self.initializer = initializer
        self.is_val = is_val


class Param(Stmt):
    """Function or constructor parameter.

    Attributes:
        name: Parameter name.
        type_annotation: Optional type string, or None.
        default_value: Optional default value expression (Expr), or None.
        is_val: True if parameter is 'val' (generates property).
        is_var: True if parameter is 'var' (generates mutable property).
    """
    __slots__ = ('name', 'type_annotation', 'default_value', 'is_val', 'is_var')

    def __init__(self, name, type_annotation, default_value, is_val, is_var):
        super(Param, self).__init__()
        self.name = name
        self.type_annotation = type_annotation
        self.default_value = default_value
        self.is_val = is_val
        self.is_var = is_var


class FunDecl(Stmt):
    """Function declaration: fun [<T>] name(params): ReturnType { body }

    Attributes:
        name: Function name.
        type_params: List of type parameter name strings (e.g. ['T']).
        params: List of Param nodes.
        return_type: Optional return type string, or None.
        body: BlockStmt containing the function body.
        is_open: True if 'open' modifier present (method can be overridden).
        is_override: True if 'override' modifier present (overrides parent method).
    """
    __slots__ = ('name', 'type_params', 'params', 'return_type', 'body',
                 'is_open', 'is_override')

    def __init__(self, name, params, return_type, body, is_open=False,
                 is_override=False, type_params=None):
        super(FunDecl, self).__init__()
        self.name = name
        self.type_params = type_params if type_params is not None else []
        self.params = params
        self.return_type = return_type
        self.body = body
        self.is_open = is_open
        self.is_override = is_override


class ClassDecl(Stmt):
    """Class declaration: [open] class Name [<T>] [(ctor_params)] [: Super] { members }

    Attributes:
        name: Class name.
        type_params: List of type parameter name strings (e.g. ['T']).
        constructor_params: List of Param nodes (constructor parameters).
        superclass: Optional superclass expression (Expr), or None.
        members: List of Stmt nodes (method decls, var decls, init blocks).
        is_open: True if 'open' modifier present (class can be inherited).
    """
    __slots__ = ('name', 'type_params', 'constructor_params', 'superclass',
                 'members', 'is_open')

    def __init__(self, name, constructor_params, superclass, members,
                 is_open=False, type_params=None):
        super(ClassDecl, self).__init__()
        self.name = name
        self.type_params = type_params if type_params is not None else []
        self.constructor_params = constructor_params
        self.superclass = superclass
        self.members = members
        self.is_open = is_open


class InitBlock(Stmt):
    """init { ... } block within a class body.

    Attributes:
        body: BlockStmt containing the init body.
    """
    __slots__ = ('body',)

    def __init__(self, body):
        super(InitBlock, self).__init__()
        self.body = body


class ExprStmt(Stmt):
    """An expression used as a statement (e.g., function call).

    Attributes:
        expression: The expression (Expr).
    """
    __slots__ = ('expression',)

    def __init__(self, expression):
        super(ExprStmt, self).__init__()
        self.expression = expression


class BlockStmt(Stmt):
    """A block of statements: { stmt* }

    Attributes:
        statements: List of Stmt nodes.
    """
    __slots__ = ('statements',)

    def __init__(self, statements):
        super(BlockStmt, self).__init__()
        self.statements = statements


class IfStmt(Stmt):
    """If statement: if (condition) then_branch [else else_branch]

    Attributes:
        condition: Expression for the condition (Expr).
        then_branch: Statement for the true branch (Stmt).
        else_branch: Optional statement for the false branch (Stmt), or None.
    """
    __slots__ = ('condition', 'then_branch', 'else_branch')

    def __init__(self, condition, then_branch, else_branch):
        super(IfStmt, self).__init__()
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch


class WhenStmt(Stmt):
    """When expression/statement: when [(subject)] { branches }

    Attributes:
        subject: Optional subject expression (Expr), or None.
        branches: List of WhenBranch nodes.
    """
    __slots__ = ('subject', 'branches')

    def __init__(self, subject, branches):
        super(WhenStmt, self).__init__()
        self.subject = subject
        self.branches = branches


class WhenBranch(Stmt):
    """A single branch of a when expression.

    Attributes:
        conditions: List of Expr conditions (or single 'else' represented as None in conditions).
        is_else: True if this is the else branch.
        body: Statement for the branch body (Stmt).
    """
    __slots__ = ('conditions', 'is_else', 'body')

    def __init__(self, conditions, is_else, body):
        super(WhenBranch, self).__init__()
        self.conditions = conditions
        self.is_else = is_else
        self.body = body


class ForStmt(Stmt):
    """For loop: for (variable in iterable) body

    Attributes:
        variable: Loop variable name.
        iterable: Expression producing the iterable (Expr).
        body: Statement for the loop body (Stmt).
    """
    __slots__ = ('variable', 'iterable', 'body')

    def __init__(self, variable, iterable, body):
        super(ForStmt, self).__init__()
        self.variable = variable
        self.iterable = iterable
        self.body = body


class WhileStmt(Stmt):
    """While loop: while (condition) body

    Attributes:
        condition: Loop condition expression (Expr).
        body: Statement for the loop body (Stmt).
    """
    __slots__ = ('condition', 'body')

    def __init__(self, condition, body):
        super(WhileStmt, self).__init__()
        self.condition = condition
        self.body = body


class ReturnStmt(Stmt):
    """Return statement: return [value]

    Attributes:
        keyword: The 'return' token (for position info).
        value: Optional return value expression (Expr), or None.
    """
    __slots__ = ('keyword', 'value')

    def __init__(self, keyword, value):
        super(ReturnStmt, self).__init__()
        self.keyword = keyword
        self.value = value


class BreakStmt(Stmt):
    """Break statement."""
    __slots__ = ()

    def __init__(self):
        super(BreakStmt, self).__init__()


class ContinueStmt(Stmt):
    """Continue statement."""
    __slots__ = ()

    def __init__(self):
        super(ContinueStmt, self).__init__()


class CatchClause(Stmt):
    """A single catch clause: catch (variable [: Type]) { body }

    Attributes:
        exception_var: The variable name to bind the exception to.
        exception_type: Optional type annotation string, or None.
        body: BlockStmt for the catch body.
    """
    __slots__ = ('exception_var', 'exception_type', 'body')

    def __init__(self, exception_var, exception_type, body):
        super(CatchClause, self).__init__()
        self.exception_var = exception_var
        self.exception_type = exception_type
        self.body = body


# =====================================================================
# Expression nodes
# =====================================================================

class Expr(ASTNode):
    """Base class for all expression nodes."""
    pass


class LiteralExpr(Expr):
    """A literal value: integer, double, string, boolean, null.

    Attributes:
        value: The Python value (int, float, unicode, bool, or None for null).
    """
    __slots__ = ('value',)

    def __init__(self, value):
        super(LiteralExpr, self).__init__()
        self.value = value


class IdentifierExpr(Expr):
    """A variable reference by name.

    Attributes:
        name: The variable name.
    """
    __slots__ = ('name',)

    def __init__(self, name):
        super(IdentifierExpr, self).__init__()
        self.name = name


class PrefixExpr(Expr):
    """A prefix unary expression: !x, -x, ++x, --x

    Attributes:
        operator: The operator Token.
        right: The operand expression (Expr).
    """
    __slots__ = ('operator', 'right')

    def __init__(self, operator, right):
        super(PrefixExpr, self).__init__()
        self.operator = operator
        self.right = right


class PostfixExpr(Expr):
    """A postfix expression: x++, x--

    Attributes:
        left: The operand expression (Expr).
        operator: The operator Token.
    """
    __slots__ = ('left', 'operator')

    def __init__(self, left, operator):
        super(PostfixExpr, self).__init__()
        self.left = left
        self.operator = operator


class InfixExpr(Expr):
    """A binary expression: left op right

    Attributes:
        left: The left operand (Expr).
        operator: The operator Token.
        right: The right operand (Expr).
    """
    __slots__ = ('left', 'operator', 'right')

    def __init__(self, left, operator, right):
        super(InfixExpr, self).__init__()
        self.left = left
        self.operator = operator
        self.right = right


class LogicalExpr(Expr):
    """A short-circuit logical expression: left && right, left || right

    Attributes:
        left: The left operand (Expr).
        operator: The operator Token.
        right: The right operand (Expr).
    """
    __slots__ = ('left', 'operator', 'right')

    def __init__(self, left, operator, right):
        super(LogicalExpr, self).__init__()
        self.left = left
        self.operator = operator
        self.right = right


class AssignExpr(Expr):
    """Assignment expression: name = value

    Attributes:
        name: The variable name being assigned to.
        value: The value expression (Expr).
    """
    __slots__ = ('name', 'value')

    def __init__(self, name, value):
        super(AssignExpr, self).__init__()
        self.name = name
        self.value = value


class CompoundAssignExpr(Expr):
    """Compound assignment: name += value, name -= value, etc.

    Attributes:
        name: The variable name.
        operator: The compound operator Token.
        value: The value expression (Expr).
    """
    __slots__ = ('name', 'operator', 'value')

    def __init__(self, name, operator, value):
        super(CompoundAssignExpr, self).__init__()
        self.name = name
        self.operator = operator
        self.value = value


class CallExpr(Expr):
    """Function or constructor call: callee(arguments)

    Attributes:
        callee: Expression that evaluates to a callable (Expr).
        arguments: List of argument expressions (Expr).
    """
    __slots__ = ('callee', 'arguments')

    def __init__(self, callee, arguments):
        super(CallExpr, self).__init__()
        self.callee = callee
        self.arguments = arguments


class GetExpr(Expr):
    """Property access: object.name

    Attributes:
        object: The object expression (Expr).
        name: The property name.
    """
    __slots__ = ('object', 'name')

    def __init__(self, obj, name):
        super(GetExpr, self).__init__()
        self.object = obj
        self.name = name


class SetExpr(Expr):
    """Property assignment: object.name = value

    Attributes:
        object: The object expression (Expr).
        name: The property name.
        value: The value expression (Expr).
    """
    __slots__ = ('object', 'name', 'value')

    def __init__(self, obj, name, value):
        super(SetExpr, self).__init__()
        self.object = obj
        self.name = name
        self.value = value


class IndexExpr(Expr):
    """Index access: object[index]

    Attributes:
        object: The collection expression (Expr).
        index: The index expression (Expr).
    """
    __slots__ = ('object', 'index')

    def __init__(self, obj, index):
        super(IndexExpr, self).__init__()
        self.object = obj
        self.index = index


class IndexSetExpr(Expr):
    """Index assignment: object[index] = value

    Attributes:
        object: The collection expression (Expr).
        index: The index expression (Expr).
        value: The value expression (Expr).
    """
    __slots__ = ('object', 'index', 'value')

    def __init__(self, obj, index, value):
        super(IndexSetExpr, self).__init__()
        self.object = obj
        self.index = index
        self.value = value


class StringTemplateExpr(Expr):
    """String template: "text $expr text ${expr} text"

    Attributes:
        parts: List of (is_expr, value) tuples.
            is_expr == False: value is a unicode literal string.
            is_expr == True: value is an Expr node to be evaluated.
    """
    __slots__ = ('parts',)

    def __init__(self, parts):
        super(StringTemplateExpr, self).__init__()
        self.parts = parts


class RangeExpr(Expr):
    """Range expression: start..end

    Attributes:
        start: Start value expression (Expr).
        end: End value expression (Expr).
    """
    __slots__ = ('start', 'end')

    def __init__(self, start, end):
        super(RangeExpr, self).__init__()
        self.start = start
        self.end = end


class ListLiteralExpr(Expr):
    """List literal: [element1, element2, ...]

    Attributes:
        elements: List of element expressions (Expr).
    """
    __slots__ = ('elements',)

    def __init__(self, elements):
        super(ListLiteralExpr, self).__init__()
        self.elements = elements


class SuperExpr(Expr):
    """The 'super' expression, referring to the parent class instance."""
    __slots__ = ()

    def __init__(self):
        super(SuperExpr, self).__init__()


class ThisExpr(Expr):
    """The 'this' expression, referring to the current instance."""
    __slots__ = ()

    def __init__(self):
        super(ThisExpr, self).__init__()


class GroupingExpr(Expr):
    """Parenthesized expression: (expression)

    Attributes:
        expression: The inner expression (Expr).
    """
    __slots__ = ('expression',)

    def __init__(self, expression):
        super(GroupingExpr, self).__init__()
        self.expression = expression


class IfExpr(Expr):
    """If expression: if (condition) then_branch else else_branch

    Kotlin: if is an expression when both branches are present.
    Each branch can be a single expression or a BlockStmt (whose
    last expression-statement yields the branch value).

    Attributes:
        condition: Expression for the condition (Expr).
        then_branch: Expression or BlockStmt for the true branch.
        else_branch: Expression or BlockStmt for the false branch.
    """
    __slots__ = ('condition', 'then_branch', 'else_branch')

    def __init__(self, condition, then_branch, else_branch):
        super(IfExpr, self).__init__()
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch


class IsExpr(Expr):
    """Type check expression: expr is Type

    Attributes:
        left: The expression being checked (Expr).
        type_name: The type name being checked against.
    """
    __slots__ = ('left', 'type_name')

    def __init__(self, left, type_name):
        super(IsExpr, self).__init__()
        self.left = left
        self.type_name = type_name


class NullSafeGetExpr(Expr):
    """Null-safe property access: obj?.name

    If obj is null, evaluates to null without calling the property.
    Otherwise, behaves like regular property access (GetExpr).

    Attributes:
        object: The object expression (Expr).
        name: The property name.
    """
    __slots__ = ('object', 'name')

    def __init__(self, obj, name):
        super(NullSafeGetExpr, self).__init__()
        self.object = obj
        self.name = name


class NotNullAssertExpr(Expr):
    """Not-null assertion: expr!!

    If expr is null, throws a runtime error. Otherwise returns expr.
    Kotlin's !! (not-null assertion operator).

    Attributes:
        expression: The expression to assert non-null (Expr).
    """
    __slots__ = ('expression',)

    def __init__(self, expression):
        super(NotNullAssertExpr, self).__init__()
        self.expression = expression


class TryExpr(Expr):
    """Try-catch-finally expression: try { } catch (e [: Type]) { } finally { }

    In Kotlin, try is an expression — it can appear in expression context
    and returns the last value from the try or catch block.

    Attributes:
        try_block: BlockStmt for the try body.
        catch_clauses: List of CatchClause nodes.
        finally_block: Optional BlockStmt for the finally body, or None.
    """
    __slots__ = ('try_block', 'catch_clauses', 'finally_block')

    def __init__(self, try_block, catch_clauses, finally_block):
        super(TryExpr, self).__init__()
        self.try_block = try_block
        self.catch_clauses = catch_clauses
        self.finally_block = finally_block


class ThrowExpr(Expr):
    """Throw expression: throw expression

    In Kotlin, throw is an expression of type Nothing.
    Evaluates the inner expression and throws it as an exception.

    Attributes:
        expression: The expression to evaluate and throw.
    """
    __slots__ = ('expression',)

    def __init__(self, expression):
        super(ThrowExpr, self).__init__()
        self.expression = expression


class SuperConstructorCall(Expr):
    """Super constructor call: ClassName(args) in a class header.

    Used when declaring a class with a superclass: class Child : Parent(args)

    Attributes:
        class_expr: IdentifierExpr for the class name.
        arguments: List of argument expressions.
    """
    __slots__ = ('class_expr', 'arguments')

    def __init__(self, class_expr, arguments):
        super(SuperConstructorCall, self).__init__()
        self.class_expr = class_expr
        self.arguments = arguments


class NullSafeCallExpr(Expr):
    """Null-safe method call: obj?.method(args)

    If obj is null, evaluates to null without calling the method.
    Otherwise, evaluates obj.method(args) normally.

    Attributes:
        object: The object expression (Expr).
        method_name: The method name to call.
        arguments: List of argument expressions (Expr).
    """
    __slots__ = ('object', 'method_name', 'arguments')

    def __init__(self, obj, method_name, arguments):
        super(NullSafeCallExpr, self).__init__()
        self.object = obj
        self.method_name = method_name
        self.arguments = arguments


class LambdaExpr(Expr):
    """Lambda expression: { [params ->] body }

    Kotlin's lambda syntax.  The ``it`` implicit parameter is used when
    no explicit parameter list is present.

    Attributes:
        params: List of parameter name strings (empty = implicit 'it').
        body: The body expression (Expr).
    """
    __slots__ = ('params', 'body')

    def __init__(self, params, body):
        super(LambdaExpr, self).__init__()
        self.params = params   # list of name strings
        self.body = body       # Expr


class ElvisExpr(Expr):
    """Elvis operator: left ?: right

    If left is not null, returns left. Otherwise, evaluates and returns right.
    Short-circuits: right is only evaluated if left is null.

    Attributes:
        left: The left expression (Expr).
        right: The right expression (Expr).
    """
    __slots__ = ('left', 'right')

    def __init__(self, left, right):
        super(ElvisExpr, self).__init__()
        self.left = left
        self.right = right


class MapLiteralExpr(Expr):
    """Map literal: [key1 to value1, key2 to value2, ...]

    Attributes:
        entries: List of (key_expr, value_expr) tuples.
    """
    __slots__ = ('entries',)

    def __init__(self, entries):
        super(MapLiteralExpr, self).__init__()
        self.entries = entries


class ToExpr(Expr):
    """'to' infix expression: key to value (creates a Pair)

    Used within map literals to create key-value pairs.

    Attributes:
        left: The key expression (Expr).
        right: The value expression (Expr).
    """
    __slots__ = ('left', 'right')

    def __init__(self, left, right):
        super(ToExpr, self).__init__()
        self.left = left
        self.right = right

# -*- coding: utf-8 -*-
"""Runtime value types for the PyKt language interpreter.

Defines the PktValue type hierarchy representing Kotlin-like values
at runtime: Int, Double, String, Boolean, Null, List, Function, Class, Instance.
"""

from __future__ import unicode_literals

try:
    unicode
except NameError:
    unicode = str  # Python 3 compatibility

from errors import PktRuntimeError, PktTypeError


class PktValue(object):
    """Abstract base class for all runtime values."""

    @property
    def type_name(self):
        """Return a human-readable type name for error messages."""
        return u'<value>'

    def is_truthy(self):
        """Return True if this value is considered 'true' in boolean context.

        Kotlin-style: only null and false are falsey. Everything else is truthy.
        For Int: 0 is NOT falsey (unlike Python). But we adopt a pragmatic
        approach: null and false are the only falsey values.
        """
        return True

    def equals(self, other):
        """Structural equality (Kotlin ==). Override in subclasses."""
        return self is other

    def __str__(self):
        """Return unicode string representation (for print / string templates)."""
        return self.__repr__()

    def __repr__(self):
        return u'<PktValue>'

    def get(self, name):
        """Get a property by name. Default: raise error."""
        raise PktRuntimeError(
            u"Cannot access property '{}' on {}".format(name, self.type_name))

    def set(self, name, value, interpreter=None):
        """Set a property by name. Default: raise error."""
        raise PktRuntimeError(
            u"Cannot set property '{}' on {}".format(name, self.type_name))


# =========================================================================
# Primitive types
# =========================================================================

class PktNull(PktValue):
    """The null value (singleton)."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PktNull, cls).__new__(cls)
        return cls._instance

    @property
    def type_name(self):
        return u'Null'

    def is_truthy(self):
        return False

    def equals(self, other):
        return isinstance(other, PktNull)

    def __str__(self):
        return u'null'

    def __repr__(self):
        return u'null'


class PktBoolean(PktValue):
    """Boolean value: true or false."""
    TRUE = None   # singleton, set after class definition
    FALSE = None  # singleton, set after class definition

    def __init__(self, value):
        self.value = bool(value)

    @property
    def type_name(self):
        return u'Boolean'

    def is_truthy(self):
        return self.value

    def equals(self, other):
        if isinstance(other, PktBoolean):
            return self.value == other.value
        return False

    def __str__(self):
        return u'true' if self.value else u'false'

    def __repr__(self):
        return u'true' if self.value else u'false'


# Initialize singletons
PktBoolean.TRUE = PktBoolean(True)
PktBoolean.FALSE = PktBoolean(False)


class PktInt(PktValue):
    """Integer value."""

    def __init__(self, value):
        self.value = int(value)

    @property
    def type_name(self):
        return u'Int'

    def is_truthy(self):
        return True  # Even 0 is truthy in Kotlin

    def equals(self, other):
        if isinstance(other, PktInt):
            return self.value == other.value
        if isinstance(other, PktDouble):
            return float(self.value) == other.value
        return False

    def get(self, name):
        """Built-in methods and properties on Int."""
        if name == u'toString':
            return PktString(unicode(self.value))
        if name == u'toDouble':
            return PktDouble(float(self.value))
        raise PktRuntimeError(
            u"Cannot access '{}' on Int".format(name))

    def __str__(self):
        return unicode(self.value)

    def __repr__(self):
        return u'PktInt({})'.format(self.value)


class PktDouble(PktValue):
    """Double (floating-point) value."""

    def __init__(self, value):
        self.value = float(value)

    @property
    def type_name(self):
        return u'Double'

    def is_truthy(self):
        return True

    def equals(self, other):
        if isinstance(other, PktDouble):
            return self.value == other.value
        if isinstance(other, PktInt):
            return self.value == float(other.value)
        return False

    def get(self, name):
        """Built-in methods and properties on Double."""
        if name == u'toString':
            return PktString(unicode(self.value))
        if name == u'toInt':
            return PktInt(int(self.value))
        raise PktRuntimeError(
            u"Cannot access '{}' on Double".format(name))

    def __str__(self):
        return unicode(self.value)

    def __repr__(self):
        return u'PktDouble({})'.format(self.value)


class PktString(PktValue):
    """String value (stores unicode) with Kotlin-like built-in methods."""

    def __init__(self, value):
        if isinstance(value, str):
            value = value.decode('utf-8')
        self.value = unicode(value)

    @property
    def type_name(self):
        return u'String'

    def is_truthy(self):
        return True

    def equals(self, other):
        if isinstance(other, PktString):
            return self.value == other.value
        return False

    def get(self, name):
        """Built-in methods and properties on String."""
        s = self.value

        if name == u'length':
            return PktInt(len(s))

        if name == u'toIntOrNull':
            def _to_int_or_null(interp, args):
                try:
                    return PktInt(int(s.strip()))
                except (ValueError, TypeError):
                    return PktNull()
            return PktBuiltinFunction(u'String.toIntOrNull', _to_int_or_null, 0)

        if name == u'toDoubleOrNull':
            def _to_double_or_null(interp, args):
                try:
                    return PktDouble(float(s.strip()))
                except (ValueError, TypeError):
                    return PktNull()
            return PktBuiltinFunction(u'String.toDoubleOrNull', _to_double_or_null, 0)

        if name == u'substring':
            def _substring(interp, args):
                if len(args) == 0:
                    raise PktRuntimeError(u'substring() requires at least 1 argument')
                start = args[0].value if isinstance(args[0], PktInt) else int(unicode(args[0]))
                if len(args) >= 2:
                    end = args[1].value if isinstance(args[1], PktInt) else int(unicode(args[1]))
                else:
                    end = len(s)
                return PktString(s[start:end])
            return PktBuiltinFunction(u'String.substring', _substring, -1)

        if name == u'contains':
            def _contains(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'contains() requires an argument')
                search = unicode(args[0])
                return PktBoolean(search in s)
            return PktBuiltinFunction(u'String.contains', _contains, 1)

        if name == u'startsWith':
            def _starts_with(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'startsWith() requires an argument')
                prefix = unicode(args[0])
                return PktBoolean(s.startswith(prefix))
            return PktBuiltinFunction(u'String.startsWith', _starts_with, 1)

        if name == u'endsWith':
            def _ends_with(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'endsWith() requires an argument')
                suffix = unicode(args[0])
                return PktBoolean(s.endswith(suffix))
            return PktBuiltinFunction(u'String.endsWith', _ends_with, 1)

        if name == u'replace':
            def _replace(interp, args):
                if len(args) < 2:
                    raise PktRuntimeError(u'replace() requires 2 arguments')
                old = unicode(args[0])
                new = unicode(args[1])
                return PktString(s.replace(old, new))
            return PktBuiltinFunction(u'String.replace', _replace, 2)

        if name == u'toLowerCase':
            def _to_lower(interp, args):
                return PktString(s.lower())
            return PktBuiltinFunction(u'String.toLowerCase', _to_lower, 0)

        if name == u'toUpperCase':
            def _to_upper(interp, args):
                return PktString(s.upper())
            return PktBuiltinFunction(u'String.toUpperCase', _to_upper, 0)

        if name == u'trim':
            def _trim(interp, args):
                return PktString(s.strip())
            return PktBuiltinFunction(u'String.trim', _trim, 0)

        if name == u'isEmpty':
            return PktBoolean(len(s) == 0)

        if name == u'isNotEmpty':
            return PktBoolean(len(s) > 0)

        if name == u'toInt':
            def _to_int(interp, args):
                try:
                    return PktInt(int(s.strip()))
                except (ValueError, TypeError):
                    raise PktRuntimeError(u"Cannot convert '{}' to Int".format(s))
            return PktBuiltinFunction(u'String.toInt', _to_int, 0)

        if name == u'toDouble':
            def _to_double(interp, args):
                try:
                    return PktDouble(float(s.strip()))
                except (ValueError, TypeError):
                    raise PktRuntimeError(u"Cannot convert '{}' to Double".format(s))
            return PktBuiltinFunction(u'String.toDouble', _to_double, 0)

        if name == u'toBoolean':
            return PktBoolean(s.lower() == u'true')

        raise PktRuntimeError(
            u"Cannot access '{}' on String".format(name))

    def __str__(self):
        return self.value

    def __repr__(self):
        return u'PktString({!r})'.format(self.value)


# =========================================================================
# Throwable / Exception hierarchy (Kotlin-aligned)
# =========================================================================

class PktThrowable(PktValue):
    """Base class for all throwable objects in PyKt.

    Kotlin equivalent: kotlin.Throwable
    Only instances of PktThrowable (or subclasses) can be used with `throw`.
    """

    def __init__(self, message=None, cause=None):
        self.message = message           # PktString or None
        self.cause = cause               # PktThrowable or None (inner exception)
        self.stack_trace = []            # could be populated later

    @property
    def type_name(self):
        return u'Throwable'

    def is_truthy(self):
        return True

    def equals(self, other):
        if isinstance(other, PktThrowable):
            return self.message == other.message
        return False

    def __str__(self):
        msg = unicode(self.message) if self.message is not None else u''
        return msg

    def __repr__(self):
        return u'PktThrowable({})'.format(unicode(self))


class PktException(PktThrowable):
    """Checked exception base class.

    Kotlin equivalent: kotlin.Exception (extends Throwable)
    """

    def __init__(self, message=None, cause=None):
        super(PktException, self).__init__(message, cause)

    @property
    def type_name(self):
        return u'Exception'

    def __repr__(self):
        return u'PktException({})'.format(self.message)


class PktRuntimeException(PktException):
    """Unchecked runtime exception.

    Kotlin equivalent: kotlin.RuntimeException (extends Exception)
    """

    def __init__(self, message=None, cause=None):
        super(PktRuntimeException, self).__init__(message, cause)

    @property
    def type_name(self):
        return u'RuntimeException'

    def __repr__(self):
        return u'PktRuntimeException({})'.format(self.message)


class PktError(PktThrowable):
    """Fatal error — typically not caught.

    Kotlin equivalent: kotlin.Error (extends Throwable)
    """

    def __init__(self, message=None, cause=None):
        super(PktError, self).__init__(message, cause)

    @property
    def type_name(self):
        return u'Error'

    def __repr__(self):
        return u'PktError({})'.format(self.message)


class PktPythonException(PktException):
    """Wraps a Python exception as a PyKt throwable.

    Created automatically when an injected Python function raises an exception.
    The original Python exception is stored in `python_exception`.
    """

    def __init__(self, py_exception, message=None):
        if message is None:
            message = unicode(py_exception)
        super(PktPythonException, self).__init__(PktString(message))
        self.python_exception = py_exception  # the original Python exception object

    @property
    def type_name(self):
        exc_name = type(self.python_exception).__name__
        return unicode(exc_name)

    def __str__(self):
        return unicode(self.python_exception)

    def __repr__(self):
        return u'PktPythonException({})'.format(self.message)


class PktExceptionClass(PktValue):
    """A factory that acts as an exception class constructor.

    Used for the global Throwable, Exception, RuntimeException, and Error
    classes. When called (e.g., `Exception("message")`), creates a new
    instance of the corresponding PktThrowable subclass.

    Attributes:
        name: The exception class name (e.g., 'Exception').
        factory: A callable taking (message, cause) and returning a PktThrowable.
    """

    def __init__(self, name, factory):
        self._exc_name = unicode(name)
        self._factory = factory

    @property
    def type_name(self):
        return self._exc_name

    def is_truthy(self):
        return True

    def call(self, interpreter, arguments):
        """Create a new exception instance.

        Supports: Exception(), Exception("msg"), Exception("msg", cause)
        """
        message = None
        cause = None

        if len(arguments) >= 1:
            msg_val = arguments[0]
            if isinstance(msg_val, PktNull):
                message = None
            elif isinstance(msg_val, PktString):
                message = msg_val
            else:
                message = PktString(unicode(msg_val))

        if len(arguments) >= 2:
            cause_val = arguments[1]
            if isinstance(cause_val, PktThrowable):
                cause = cause_val

        return self._factory(message, cause)

    def __str__(self):
        return u'<exception class {}>'.format(self._exc_name)

    def __repr__(self):
        return u'PktExceptionClass({})'.format(self._exc_name)


# =========================================================================
# Collection helper — call a function value from builtin code
# =========================================================================

def _call_func(interp, func, args):
    """Call a PktFunction / PktBuiltinFunction / BoundMethod with arguments.

    Used by higher-order collection builtins (map, filter, etc.) to invoke
    the user-supplied lambda or function reference.
    """
    if isinstance(func, PktFunction):
        return interp._call_function(func, list(args), None)
    elif isinstance(func, PktBuiltinFunction):
        return func.func(interp, list(args))
    elif isinstance(func, BoundMethod):
        return interp._call_bound_method(func, list(args), None)
    else:
        raise PktRuntimeError(
            u"Expected a function, got '{}'".format(func.type_name))


# =========================================================================
# Collection types
# =========================================================================

class PktList(PktValue):
    """List value (mutable, ordered collection) with Kotlin-like methods.

    When ``_py_backing`` is set, every mutation is mirrored back to the
    original Python list so that Python → PyKt → Python round-trips
    preserve identity.
    """

    def __init__(self, elements=None, py_backing=None):
        self.elements = list(elements) if elements is not None else []
        self._py_backing = py_backing  # original Python list, or None

    @property
    def type_name(self):
        return u'List'

    def is_truthy(self):
        return True

    def equals(self, other):
        if isinstance(other, PktList):
            if len(self.elements) != len(other.elements):
                return False
            for a, b in zip(self.elements, other.elements):
                if not a.equals(b):
                    return False
            return True
        return False

    def get(self, name):
        """Built-in methods and properties on List."""
        lst = self.elements

        if name == u'size':
            return PktInt(len(lst))

        if name == u'isEmpty':
            return PktBoolean(len(lst) == 0)

        if name == u'isNotEmpty':
            return PktBoolean(len(lst) > 0)

        if name == u'add':
            def _add(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'add() requires an argument')
                lst.append(args[0])
                if self._py_backing is not None:
                    enc = getattr(interp, '_runtime_ref', None)
                    enc = getattr(enc, '_str_encoding', 'unicode') if enc else 'unicode'
                    self._py_backing.append(_pkt_to_py_raw(args[0], enc))
                return PktBoolean(True)
            return PktBuiltinFunction(u'List.add', _add, 1)

        if name == u'removeAt':
            def _remove_at(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'removeAt() requires an index')
                idx = args[0].value if isinstance(args[0], PktInt) else int(unicode(args[0]))
                if idx < 0 or idx >= len(lst):
                    raise PktRuntimeError(u'Index {} out of bounds (size {})'.format(idx, len(lst)))
                removed = lst.pop(idx)
                if self._py_backing is not None:
                    self._py_backing.pop(idx)
                return removed
            return PktBuiltinFunction(u'List.removeAt', _remove_at, 1)

        if name == u'get':
            def _get(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'get() requires an index')
                idx = args[0].value if isinstance(args[0], PktInt) else int(unicode(args[0]))
                if idx < 0 or idx >= len(lst):
                    raise PktRuntimeError(u'Index {} out of bounds (size {})'.format(idx, len(lst)))
                return lst[idx]
            return PktBuiltinFunction(u'List.get', _get, 1)

        if name == u'contains':
            def _contains(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'contains() requires an argument')
                for e in lst:
                    if e.equals(args[0]):
                        return PktBoolean(True)
                return PktBoolean(False)
            return PktBuiltinFunction(u'List.contains', _contains, 1)

        if name == u'indexOf':
            def _index_of(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'indexOf() requires an argument')
                for i, e in enumerate(lst):
                    if e.equals(args[0]):
                        return PktInt(i)
                return PktInt(-1)
            return PktBuiltinFunction(u'List.indexOf', _index_of, 1)

        # ---- Higher-order functions ----

        if name == u'map':
            def _map(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'map() requires a transform function')
                transform = args[0]
                result = []
                for e in lst:
                    result.append(_call_func(interp, transform, [e]))
                return PktList(result)
            return PktBuiltinFunction(u'List.map', _map, 1)

        if name == u'filter':
            def _filter(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'filter() requires a predicate')
                pred = args[0]
                result = []
                for e in lst:
                    r = _call_func(interp, pred, [e])
                    if r.is_truthy():
                        result.append(e)
                return PktList(result)
            return PktBuiltinFunction(u'List.filter', _filter, 1)

        if name == u'filterNotNull':
            def _filter_notnull(interp, args):
                result = [e for e in lst if not isinstance(e, PktNull)]
                return PktList(result)
            return PktBuiltinFunction(u'List.filterNotNull', _filter_notnull, 0)

        if name == u'forEach':
            def _foreach(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'forEach() requires an action')
                action = args[0]
                for e in lst:
                    _call_func(interp, action, [e])
                return PktNull()
            return PktBuiltinFunction(u'List.forEach', _foreach, 1)

        if name == u'any':
            def _any(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'any() requires a predicate')
                pred = args[0]
                for e in lst:
                    if _call_func(interp, pred, [e]).is_truthy():
                        return PktBoolean.TRUE
                return PktBoolean.FALSE
            return PktBuiltinFunction(u'List.any', _any, 1)

        if name == u'all':
            def _all(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'all() requires a predicate')
                pred = args[0]
                for e in lst:
                    if not _call_func(interp, pred, [e]).is_truthy():
                        return PktBoolean.FALSE
                return PktBoolean.TRUE
            return PktBuiltinFunction(u'List.all', _all, 1)

        if name == u'none':
            def _none(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'none() requires a predicate')
                pred = args[0]
                for e in lst:
                    if _call_func(interp, pred, [e]).is_truthy():
                        return PktBoolean.FALSE
                return PktBoolean.TRUE
            return PktBuiltinFunction(u'List.none', _none, 1)

        if name == u'find':
            def _find(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'find() requires a predicate')
                pred = args[0]
                for e in lst:
                    if _call_func(interp, pred, [e]).is_truthy():
                        return e
                return PktNull()
            return PktBuiltinFunction(u'List.find', _find, 1)

        if name == u'first':
            def _first(interp, args):
                # first() or first(predicate)
                if len(args) >= 1:
                    pred = args[0]
                    for e in lst:
                        if _call_func(interp, pred, [e]).is_truthy():
                            return e
                    raise PktRuntimeError(u'first(): no element matches predicate')
                if not lst:
                    raise PktRuntimeError(u'first(): list is empty')
                return lst[0]
            return PktBuiltinFunction(u'List.first', _first, -1)

        if name == u'firstOrNull':
            def _first_or_null(interp, args):
                if len(args) >= 1:
                    pred = args[0]
                    for e in lst:
                        if _call_func(interp, pred, [e]).is_truthy():
                            return e
                    return PktNull()
                return lst[0] if lst else PktNull()
            return PktBuiltinFunction(u'List.firstOrNull', _first_or_null, -1)

        if name == u'flatMap':
            def _flat_map(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'flatMap() requires a transform')
                transform = args[0]
                result = []
                for e in lst:
                    sub = _call_func(interp, transform, [e])
                    if isinstance(sub, PktList):
                        result.extend(sub.elements)
                    elif isinstance(sub, PktArray):
                        result.extend(sub.elements)
                    else:
                        result.append(sub)
                return PktList(result)
            return PktBuiltinFunction(u'List.flatMap', _flat_map, 1)

        if name == u'fold':
            def _fold(interp, args):
                # fold(initial, operation)  OR  fold(initial) { operation }
                if len(args) < 1:
                    raise PktRuntimeError(u'fold() requires an initial value')
                acc = args[0]
                if len(args) >= 2:
                    op = args[1]
                    for e in lst:
                        acc = _call_func(interp, op, [acc, e])
                    return acc
                # Partial application: return a function that accepts the
                # operation (supports trailing-lambda syntax).
                def _fold_op(interp2, args2):
                    if len(args2) < 1:
                        raise PktRuntimeError(u'fold() requires an operation')
                    a = acc
                    op2 = args2[0]
                    for e in lst:
                        a = _call_func(interp2, op2, [a, e])
                    return a
                return PktBuiltinFunction(u'List.fold$op', _fold_op, 1)
            return PktBuiltinFunction(u'List.fold', _fold, -1)

        if name == u'reduce':
            def _reduce(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'reduce() requires an operation')
                if not lst:
                    raise PktRuntimeError(u'reduce(): list is empty')
                op = args[0]
                acc = lst[0]
                for e in lst[1:]:
                    acc = _call_func(interp, op, [acc, e])
                return acc
            return PktBuiltinFunction(u'List.reduce', _reduce, 1)

        raise PktRuntimeError(
            u"Cannot access '{}' on List".format(name))

    def __str__(self):
        parts = [unicode(e) for e in self.elements]
        return u'[' + u', '.join(parts) + u']'

    def __repr__(self):
        return u'PktList({})'.format(self.__str__())


class PktIntRange(PktValue):
    """Integer range: start..end with optional step."""

    def __init__(self, start, end, step=1):
        self.start = int(start)
        self.end = int(end)
        self.step = int(step)

    @property
    def type_name(self):
        return u'IntRange'

    def is_truthy(self):
        return True

    def equals(self, other):
        if isinstance(other, PktIntRange):
            return (self.start == other.start and
                    self.end == other.end and
                    self.step == other.step)
        return False

    def __str__(self):
        if self.step == 1:
            return u'{}..{}'.format(self.start, self.end)
        return u'{}..{} step {}'.format(self.start, self.end, self.step)

    def to_list(self):
        """Convert the range to a Python iterable of ints."""
        if self.step > 0:
            return range(self.start, self.end + 1, self.step)
        else:
            return range(self.start, self.end - 1, self.step)


class PktPair(PktValue):
    """A key-value pair, created by the 'to' operator: key to value.

    Used primarily for building Map literals.
    """

    def __init__(self, first, second):
        self.first = first    # key
        self.second = second  # value

    @property
    def type_name(self):
        return u'Pair'

    def is_truthy(self):
        return True

    def equals(self, other):
        if isinstance(other, PktPair):
            return self.first.equals(other.first) and self.second.equals(other.second)
        return False

    def __str__(self):
        return u'({} to {})'.format(unicode(self.first), unicode(self.second))


class PktArray(PktValue):
    """Fixed-size mutable array.

    Unlike PktList (which has dynamic size), PktArray has a fixed size
    specified at creation time, similar to Kotlin's Array.
    """

    def __init__(self, size, initial_value=None):
        if isinstance(size, PktInt):
            size = size.value
        self.size = int(size)
        if initial_value is None:
            initial_value = PktNull()
        self.elements = [initial_value] * self.size

    @property
    def type_name(self):
        return u'Array'

    def is_truthy(self):
        return True

    def equals(self, other):
        if isinstance(other, PktArray):
            if self.size != other.size:
                return False
            for a, b in zip(self.elements, other.elements):
                if not a.equals(b):
                    return False
            return True
        return False

    def get(self, name):
        if name == u'size':
            return PktInt(self.size)

        if name == u'get':
            def _get(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'get() requires an index')
                idx = args[0].value if isinstance(args[0], PktInt) else int(unicode(args[0]))
                if idx < 0 or idx >= self.size:
                    raise PktRuntimeError(u'Array index {} out of bounds (size {})'.format(idx, self.size))
                return self.elements[idx]
            return PktBuiltinFunction(u'Array.get', _get, 1)

        if name == u'set':
            def _set(interp, args):
                if len(args) < 2:
                    raise PktRuntimeError(u'set() requires an index and a value')
                idx = args[0].value if isinstance(args[0], PktInt) else int(unicode(args[0]))
                if idx < 0 or idx >= self.size:
                    raise PktRuntimeError(u'Array index {} out of bounds (size {})'.format(idx, self.size))
                self.elements[idx] = args[1]
                return PktNull()
            return PktBuiltinFunction(u'Array.set', _set, 2)

        raise PktRuntimeError(
            u"Cannot access '{}' on Array".format(name))

    def __str__(self):
        parts = [unicode(e) for e in self.elements]
        return u'[' + u', '.join(parts) + u']'

    def __repr__(self):
        return u'PktArray(size={})'.format(self.size)


class PktMap(PktValue):
    """Mutable key-value map, similar to Kotlin's MutableMap.

    Keys can be any hashable PktValue. Values can be any PktValue.

    When ``_py_backing`` is set, every mutation is mirrored back to the
    original Python dict so that Python → PyKt → Python round-trips
    preserve identity.
    """

    def __init__(self, entries=None, py_backing=None):
        self.entries = {}  # Python dict: id-based key storage, with PktValue wrapper refs
        self._py_backing = py_backing  # original Python dict, or None
        if entries:
            for pair in entries:
                if isinstance(pair, PktPair):
                    self._put_raw(pair.first, pair.second)

    def _key_str(self, key):
        """Convert a PktValue to a string key for dict storage."""
        if isinstance(key, PktString):
            return u'S_' + key.value
        elif isinstance(key, PktInt):
            return u'I_' + unicode(key.value)
        elif isinstance(key, PktDouble):
            return u'D_' + unicode(key.value)
        elif isinstance(key, PktBoolean):
            return u'B_' + (u'true' if key.value else u'false')
        elif isinstance(key, PktNull):
            return u'N_null'
        else:
            return u'O_' + unicode(id(key))

    def _put_raw(self, key, value):
        """Store a key-value pair."""
        self.entries[self._key_str(key)] = (key, value)

    def put(self, key, value, interpreter=None):
        """Associate key with value. Returns the previous value or null."""
        k = self._key_str(key)
        old = self.entries.get(k)
        self.entries[k] = (key, value)
        if self._py_backing is not None:
            enc = 'unicode'
            if interpreter and hasattr(interpreter, '_runtime_ref'):
                enc = getattr(interpreter._runtime_ref, '_str_encoding', 'unicode')
            self._py_backing[_pkt_to_py_raw(key, enc)] = _pkt_to_py_raw(value, enc)
        if old is not None:
            return old[1]
        return PktNull()

    def get_value(self, key):
        """Get the value for a key, or null if not found."""
        k = self._key_str(key)
        entry = self.entries.get(k)
        if entry is not None:
            return entry[1]
        return PktNull()

    def contains_key(self, key):
        """Check if a key exists in the map."""
        k = self._key_str(key)
        return k in self.entries

    def remove(self, key, interpreter=None):
        """Remove a key and return its value, or null if not found."""
        k = self._key_str(key)
        entry = self.entries.pop(k, None)
        if self._py_backing is not None:
            enc = 'unicode'
            if interpreter and hasattr(interpreter, '_runtime_ref'):
                enc = getattr(interpreter._runtime_ref, '_str_encoding', 'unicode')
            py_key = _pkt_to_py_raw(key, enc)
            if py_key in self._py_backing:
                del self._py_backing[py_key]
        if entry is not None:
            return entry[1]
        return PktNull()

    def keys(self):
        """Return a PktList of all keys."""
        return PktList([entry[0] for entry in self.entries.values()])

    def values(self):
        """Return a PktList of all values."""
        return PktList([entry[1] for entry in self.entries.values()])

    @property
    def type_name(self):
        return u'Map'

    def is_truthy(self):
        return True

    def equals(self, other):
        if isinstance(other, PktMap):
            return self.entries == other.entries
        return False

    def get(self, name):
        """Built-in methods and properties on Map."""
        if name == u'size':
            return PktInt(len(self.entries))

        if name == u'isEmpty':
            return PktBoolean(len(self.entries) == 0)

        if name == u'get':
            def _get(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'get() requires a key')
                return self.get_value(args[0])
            return PktBuiltinFunction(u'Map.get', _get, 1)

        if name == u'put':
            def _put(interp, args):
                if len(args) < 2:
                    raise PktRuntimeError(u'put() requires a key and a value')
                return self.put(args[0], args[1], interpreter=interp)
            return PktBuiltinFunction(u'Map.put', _put, 2)

        if name == u'containsKey':
            def _contains_key(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'containsKey() requires a key')
                return PktBoolean(self.contains_key(args[0]))
            return PktBuiltinFunction(u'Map.containsKey', _contains_key, 1)

        if name == u'keys':
            return self.keys()

        if name == u'values':
            return self.values()

        if name == u'remove':
            def _remove(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'remove() requires a key')
                return self.remove(args[0], interpreter=interp)
            return PktBuiltinFunction(u'Map.remove', _remove, 1)

        # ---- Higher-order functions ----

        if name == u'mapKeys':
            def _map_keys(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'mapKeys() requires a transform')
                transform = args[0]
                new_map = PktMap()
                for key, val in self.entries.values():
                    new_key = _call_func(interp, transform, [key])
                    new_map.put(new_key, val)
                return new_map
            return PktBuiltinFunction(u'Map.mapKeys', _map_keys, 1)

        if name == u'mapValues':
            def _map_values(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'mapValues() requires a transform')
                transform = args[0]
                new_map = PktMap()
                for key, val in self.entries.values():
                    new_val = _call_func(interp, transform, [val])
                    new_map.put(key, new_val)
                return new_map
            return PktBuiltinFunction(u'Map.mapValues', _map_values, 1)

        if name == u'filter':
            def _map_filter(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'filter() requires a predicate')
                pred = args[0]
                new_map = PktMap()
                for key, val in self.entries.values():
                    r = _call_func(interp, pred, [key, val])
                    if r.is_truthy():
                        new_map.put(key, val)
                return new_map
            return PktBuiltinFunction(u'Map.filter', _map_filter, 1)

        if name == u'filterKeys':
            def _filter_keys(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'filterKeys() requires a predicate')
                pred = args[0]
                new_map = PktMap()
                for key, val in self.entries.values():
                    if _call_func(interp, pred, [key]).is_truthy():
                        new_map.put(key, val)
                return new_map
            return PktBuiltinFunction(u'Map.filterKeys', _filter_keys, 1)

        if name == u'forEach':
            def _map_foreach(interp, args):
                if len(args) < 1:
                    raise PktRuntimeError(u'forEach() requires an action')
                action = args[0]
                for key, val in self.entries.values():
                    _call_func(interp, action, [key, val])
                return PktNull()
            return PktBuiltinFunction(u'Map.forEach', _map_foreach, 1)

        raise PktRuntimeError(
            u"Cannot access '{}' on Map".format(name))

    def __str__(self):
        parts = []
        for key, val in self.entries.values():
            parts.append(unicode(key) + u' to ' + unicode(val))
        return u'{' + u', '.join(parts) + u'}'

    def __repr__(self):
        return u'PktMap({})'.format(self.__str__())


# =========================================================================
# Callable types
# =========================================================================

class PktFunction(PktValue):
    """A user-defined function (closure).

    Attributes:
        declaration: The FunDecl AST node.
        closure: The Environment in which the function was defined.
    """

    def __init__(self, declaration, closure):
        self.declaration = declaration
        self.closure = closure

    @property
    def type_name(self):
        return u'Function'

    def is_truthy(self):
        return True

    def __str__(self):
        return u'<function {}>'.format(self.declaration.name)

    def __repr__(self):
        return u'PktFunction({})'.format(self.declaration.name)


class PktBuiltinFunction(PktValue):
    """A built-in function implemented in Python.

    Attributes:
        name: The function name.
        func: The Python callable implementing the function.
        arity: Expected argument count, or -1 for variadic.
    """

    def __init__(self, name, func, arity):
        self.name = name
        self.func = func
        self.arity = arity

    @property
    def type_name(self):
        return u'BuiltinFunction'

    def is_truthy(self):
        return True

    def __str__(self):
        return u'<builtin {}>'.format(self.name)

    def __repr__(self):
        return u'PktBuiltinFunction({})'.format(self.name)


# =========================================================================
# Class and Instance types
# =========================================================================

class PktClass(PktValue):
    """A class definition at runtime.

    When is_open=True, the class can be inherited from (Kotlin 'open class').
    Default classes are final (is_open=False) and cannot be inherited.

    Attributes:
        name: The class name.
        constructor_params: List of Param AST nodes.
        parent_class: Optional PktClass for the parent class.
        methods: Dict of method_name -> PktFunction.
        instance_properties: Dict of prop_name -> initializer_expr (or None).
        init_blocks: List of InitBlock AST nodes.
        is_open: Whether this class is marked 'open' (can be inherited).
    """

    def __init__(self, name, constructor_params, parent_class, methods,
                 instance_properties, init_blocks, is_open=False,
                 parent_constructor_arg_asts=None, type_params=None):
        self.name = name
        self.constructor_params = constructor_params
        self.parent_class = parent_class      # PktClass or PktPythonClass or None
        self.methods = methods                # name -> PktFunction
        self.instance_properties = instance_properties
        self.init_blocks = init_blocks
        self.is_open = is_open
        self.type_params = type_params if type_params is not None else []
        self.parent_constructor_arg_asts = parent_constructor_arg_asts or []  # AST nodes

    @property
    def type_name(self):
        return self.name

    def is_truthy(self):
        return True

    def resolve_method(self, name):
        """Find a method by name, walking the inheritance chain.

        Returns the PktFunction, or None if not found.
        """
        if name in self.methods:
            return self.methods[name]
        if self.parent_class is not None and isinstance(self.parent_class, PktClass):
            return self.parent_class.resolve_method(name)
        return None

    def get_property_type(self, name):
        """Get the declared type annotation for a property, or None.

        Looks in constructor params first, then instance_properties.
        """
        # Check constructor params (val/var in class header)
        for p in self.constructor_params:
            if p.name == name:
                return p.type_annotation
        # Check class-body properties
        prop = self.instance_properties.get(name)
        if prop:
            return prop.get('type_annotation')
        return None

    def has_method(self, name):
        """Check if a method exists anywhere in the inheritance chain."""
        return self.resolve_method(name) is not None

    def call(self, interpreter, arguments):
        """Create a new instance of this class.

        If there is a parent class, its constructor is called first
        (with the same arguments, then extra args go to the child).
        """
        instance = PktInstance(self)

        # Check arguments
        param_names = [p.name for p in self.constructor_params]
        if len(arguments) > len(param_names):
            raise PktRuntimeError(
                u"Too many arguments for constructor of '{}': expected at most {}, got {}".format(
                    self.name, len(param_names), len(arguments)))

        instance_env = instance.create_init_environment(interpreter)

        # Bind child constructor params FIRST (so parent args can reference them)
        for i, param in enumerate(self.constructor_params):
            if i < len(arguments):
                value = arguments[i]
            elif param.default_value is not None:
                value = interpreter._evaluate(param.default_value)
            else:
                raise PktRuntimeError(
                    u"No value provided for parameter '{}'".format(param.name))
            # Type-check constructor argument
            if param.type_annotation is not None:
                interpreter._validate_type(value, param.type_annotation,
                                          param.line, param.column)
            instance_env.define(param.name, value, is_val=True)
            instance.fields[param.name] = value

        # Now evaluate parent constructor args (with child params in scope)
        if self.parent_class is not None:
            if isinstance(self.parent_class, PktClass):
                if self.parent_constructor_arg_asts:
                    # Evaluate in the instance_env so child params are visible
                    prev_env = interpreter.environment
                    interpreter.environment = instance_env
                    try:
                        parent_args = [interpreter._evaluate(a)
                                      for a in self.parent_constructor_arg_asts]
                    finally:
                        interpreter.environment = prev_env
                else:
                    parent_params = self.parent_class.constructor_params
                    parent_arg_count = len(parent_params)
                    parent_args = arguments[:parent_arg_count]

                self._init_parent(interpreter, instance, parent_args)
            elif isinstance(self.parent_class, PktPythonClass):
                if self.parent_constructor_arg_asts:
                    prev_env = interpreter.environment
                    interpreter.environment = instance_env
                    try:
                        raw_args = [_pkt_to_py_raw(interpreter._evaluate(a))
                                    for a in self.parent_constructor_arg_asts]
                    finally:
                        interpreter.environment = prev_env
                else:
                    raw_args = [_pkt_to_py_raw(a) for a in arguments]
                try:
                    py_instance = self.parent_class._py_class(*raw_args)
                    instance._py_parent_instance = py_instance
                except Exception as e:
                    raise PktRuntimeError(
                        u"Error calling parent '{}' constructor: {}".format(
                            self.parent_class._name, unicode(e)))
            elif isinstance(self.parent_class, PktExceptionClass):
                if self.parent_constructor_arg_asts:
                    prev_env = interpreter.environment
                    interpreter.environment = instance_env
                    try:
                        parent_args = [interpreter._evaluate(a)
                                      for a in self.parent_constructor_arg_asts]
                    finally:
                        interpreter.environment = prev_env
                else:
                    parent_args = arguments
                parent_exc = self.parent_class.call(interpreter, parent_args)
                instance.fields[u'__parent_exc__'] = parent_exc

        # Initialize class-body properties (val / var with initializers)
        for prop_name, prop_info in self.instance_properties.items():
            init_expr = prop_info.get('initializer')
            if init_expr is not None:
                prop_val = interpreter._evaluate(init_expr)
                # Validate against declared type if present
                type_ann = prop_info.get('type_annotation')
                if type_ann is not None:
                    interpreter._validate_type(prop_val, type_ann,
                                              init_expr.line, init_expr.column)
                instance.fields[prop_name] = prop_val
                instance_env.define(prop_name, prop_val,
                                   is_val=prop_info.get('is_val', False))
                # Track val properties for external-assignment protection
                if prop_info.get('is_val'):
                    instance._val_props.add(prop_name)
            elif prop_info.get('is_val') or not prop_info.get('is_val'):
                # Property without initializer (e.g. 'val x: Int' in class body)
                # Still need to track val/var for external access control
                pass

        # Execute init blocks
        previous_env = interpreter.environment
        interpreter.environment = instance_env
        try:
            for init_block in self.init_blocks:
                interpreter._execute_block(init_block.body)
        finally:
            interpreter.environment = previous_env

        # Copy instance values into fields (skip methods)
        for name in instance_env._values:
            if name != u'this':
                val = instance_env._values[name]
                if not isinstance(val, (PktFunction, PktBuiltinFunction)):
                    instance.fields[name] = val

        # Infer concrete type arguments from constructor parameters.
        # For each type parameter name (e.g. 'T'), find the constructor
        # param annotated with that name and record the actual value's type.
        if self.type_params:
            inferred_args = []
            for tp_name in self.type_params:
                arg_type = tp_name  # default: keep the type-param name
                for param in self.constructor_params:
                    if param.type_annotation == tp_name:
                        val = instance.fields.get(param.name)
                        if val is not None:
                            arg_type = interpreter._type_name_of(val)
                            break  # found the matching param
                inferred_args.append(arg_type)
            instance.type_args = inferred_args

        return instance

    def _init_parent(self, interpreter, instance, parent_args):
        """Initialize the parent portion of an instance."""
        parent = self.parent_class

        from environment import InstanceEnvironment
        parent_env = InstanceEnvironment(instance, enclosing=interpreter.globals)
        parent_env.define(u'this', instance, is_val=True)

        # Add parent methods
        for method_name, method_func in parent.methods.items():
            parent_env.define(method_name, method_func, is_val=True)

        # Also add methods from grandparent (if any)
        gp = parent.parent_class
        while gp is not None and isinstance(gp, PktClass):
            for method_name, method_func in gp.methods.items():
                if method_name not in parent_env._values:
                    parent_env.define(method_name, method_func, is_val=True)
            gp = gp.parent_class if isinstance(gp.parent_class, PktClass) else None

        # Bind parent constructor params to instance fields
        for i, param in enumerate(parent.constructor_params):
            if i < len(parent_args):
                value = parent_args[i]
            elif param.default_value is not None:
                value = interpreter._evaluate(param.default_value)
            else:
                raise PktRuntimeError(
                    u"No value provided for parent parameter '{}'".format(param.name))
            parent_env.define(param.name, value, is_val=True)
            instance.fields[param.name] = value

        # Execute parent init blocks in the parent environment
        previous_env = interpreter.environment
        interpreter.environment = parent_env
        try:
            for init_block in parent.init_blocks:
                interpreter._execute_block(init_block.body)
        finally:
            interpreter.environment = previous_env

        # Copy parent-init variables to instance fields (skip methods)
        for name in parent_env._values:
            if name != u'this':
                val = parent_env._values[name]
                if not isinstance(val, (PktFunction, PktBuiltinFunction)):
                    if name not in instance.fields:
                        instance.fields[name] = val

    def __str__(self):
        return u'<class {}>'.format(self.name)

    def __repr__(self):
        return u'PktClass({})'.format(self.name)


class PktInstance(PktValue):
    """An instance of a class.

    Supports method resolution through the inheritance chain.
    Attributes:
        klass: The PktClass this is an instance of.
        fields: Dict of field_name -> PktValue.
        type_args: List of type argument strings (e.g. ['Int'] for Box<Int>).
        _py_parent_instance: Python parent instance (for Python class inheritance).
    """

    def __init__(self, klass, type_args=None):
        self.klass = klass
        self.fields = {}  # instance fields (properties)
        self._val_props = set()  # names of val (immutable) properties
        self.type_args = type_args if type_args is not None else []
        self._py_parent_instance = None  # for Python class inheritance

    @property
    def type_name(self):
        return self.klass.name

    def is_truthy(self):
        return True

    def get(self, name):
        """Get a property or method from this instance.

        Walks the inheritance chain for method resolution.
        """
        # Check instance fields first
        if name in self.fields:
            return self.fields[name]

        # Check methods in the klass hierarchy
        method = self.klass.resolve_method(name)
        if method is not None:
            return BoundMethod(self, method)

        # Check Python parent instance for Python class inheritance
        if self._py_parent_instance is not None:
            uname = unicode(name)
            if hasattr(self._py_parent_instance, uname):
                attr = getattr(self._py_parent_instance, uname)
                if callable(attr):
                    return PktPythonMethod(attr, uname)
                return _py_to_pkt_value(attr)

        raise PktRuntimeError(
            u"Property '{}' not found on instance of '{}'".format(
                name, self.klass.name))

    def set(self, name, value, interpreter=None):
        """Set a property on this instance (val-protected, type checked by caller)."""
        if name in self.fields and name in self._val_props:
            raise PktRuntimeError(
                u"Cannot reassign val property '{}'".format(name))
        self.fields[name] = value

    def get_super_method(self, name):
        """Get a method from the parent class (for super.method() calls)."""
        if self.klass.parent_class is None:
            raise PktRuntimeError(
                u"'{}' has no parent class".format(self.klass.name))
        parent = self.klass.parent_class
        if isinstance(parent, PktClass):
            method = parent.resolve_method(name)
            if method is not None:
                return BoundMethod(self, method)
        elif isinstance(parent, PktPythonClass):
            # Python parent: look up on the Python instance
            if self._py_parent_instance is not None:
                uname = unicode(name)
                if hasattr(self._py_parent_instance, uname):
                    attr = getattr(self._py_parent_instance, uname)
                    if callable(attr):
                        return PktPythonMethod(attr, uname)

        raise PktRuntimeError(
            u"Method '{}' not found in parent class".format(name))

    def create_init_environment(self, interpreter):
        """Create the environment for running init blocks and methods.

        Includes methods from the full inheritance chain.
        """
        from environment import InstanceEnvironment
        env = InstanceEnvironment(self, enclosing=interpreter.globals)
        env.define(u'this', self, is_val=True)

        # Add methods from the full class hierarchy
        klass = self.klass
        while klass is not None:
            for method_name, method_func in klass.methods.items():
                if method_name not in env._values:
                    env.define(method_name, method_func, is_val=True)
            klass = klass.parent_class if isinstance(klass.parent_class, PktClass) else None

        return env

    def bind_method(self, method):
        """Create a BoundMethod that captures 'this'."""
        return BoundMethod(self, method)

    def __str__(self):
        if self.type_args:
            return u'<instance of {}<{}>>'.format(
                self.klass.name, u','.join(self.type_args))
        return u'<instance of {}>'.format(self.klass.name)

    def __repr__(self):
        return u'PktInstance({})'.format(self.klass.name)


class BoundMethod(PktValue):
    """A method bound to a specific instance (captures 'this').

    Attributes:
        instance: The PktInstance that 'this' refers to.
        method: The PktFunction to call.
    """

    def __init__(self, instance, method):
        self.instance = instance
        self.method = method

    @property
    def type_name(self):
        return u'Function'

    def is_truthy(self):
        return True

    def __str__(self):
        return u'<bound method {} of {}>'.format(
            self.method.declaration.name, self.instance.type_name)


class _SuperProxy(PktValue):
    """Proxy for 'super' keyword — redirects method calls to parent class.

    When `super.method()` is called, this proxy's `get()` method looks up
    the method in the parent class rather than the current class.
    """

    def __init__(self, instance):
        self._instance = instance

    @property
    def type_name(self):
        return u'Super'

    def is_truthy(self):
        return True

    def get(self, name):
        return self._instance.get_super_method(name)

    def __str__(self):
        return u'<super>'


# =========================================================================
# Python class adapter (inject Python classes into PyKt)
# =========================================================================

class PktPythonClass(PktValue):
    """A Python class exposed as a PyKt class.

    When instantiated from PyKt code (via ClassName(args)), creates a
    Python instance wrapped in a PktPythonInstance.
    """

    def __init__(self, name, py_class):
        self._name = unicode(name)
        self._py_class = py_class

    @property
    def type_name(self):
        return self._name

    def is_truthy(self):
        return True

    def call(self, interpreter, arguments):
        """Instantiate the Python class from PyKt code."""
        raw_args = []
        for a in arguments:
            if isinstance(a, PktNull):
                raw_args.append(None)
            elif isinstance(a, PktBoolean):
                raw_args.append(a.value)
            elif isinstance(a, PktInt):
                raw_args.append(a.value)
            elif isinstance(a, PktDouble):
                raw_args.append(a.value)
            elif isinstance(a, PktString):
                raw_args.append(a.value)
            elif isinstance(a, PktList):
                raw_args.append([_pkt_to_py_raw(v) for v in a.elements])
            elif isinstance(a, PktMap):
                d = {}
                for k, v in a.entries.values():
                    d[_pkt_to_py_raw(k)] = _pkt_to_py_raw(v)
                raw_args.append(d)
            elif isinstance(a, PktPythonInstance):
                raw_args.append(a._py_instance)
            else:
                raw_args.append(a)
        try:
            py_instance = self._py_class(*raw_args)
        except Exception as e:
            raise PktRuntimeError(
                u"Error in '{}' constructor: {}".format(self._name, unicode(e)))
        return PktPythonInstance(self._py_class, py_instance)

    def __str__(self):
        return u'<Python class {}>'.format(self._name)

    def __repr__(self):
        return u'PktPythonClass({})'.format(self._name)


class PktPythonInstance(PktValue):
    """A Python object wrapped as a PyKt value.

    Supports property access and method calls from PyKt code.
    """

    def __init__(self, py_class, py_instance):
        self._py_class = py_class
        self._py_instance = py_instance

    @property
    def type_name(self):
        return self._py_class.__name__ if hasattr(self._py_class, '__name__') else u'PythonObject'

    def is_truthy(self):
        return self._py_instance is not None

    def get(self, name):
        uname = unicode(name)
        if hasattr(self._py_instance, uname):
            attr = getattr(self._py_instance, uname)
            if isinstance(attr, type):
                return _py_to_pkt_value(attr)
            if callable(attr):
                return PktPythonMethod(attr, uname)
            return _py_to_pkt_value(attr)
        raise PktRuntimeError(
            u"Attribute '{}' not found on Python object '{}'".format(
                uname, self.type_name))

    def set(self, name, value, interpreter=None):
        uname = unicode(name)
        if hasattr(self._py_instance, uname):
            setattr(self._py_instance, uname, _pkt_to_py_raw(value))
        else:
            raise PktRuntimeError(
                u"Cannot set '{}' on Python object".format(uname))

    def __str__(self):
        return unicode(self._py_instance)


class PktPythonMethod(PktValue):
    """Wraps a Python method for calling from PyKt code."""

    def __init__(self, method, name):
        self._method = method
        self._name = name

    @property
    def type_name(self):
        return u'Function'

    def is_truthy(self):
        return True

    def __str__(self):
        return u'<Python method {}>'.format(self._name)


def _pkt_to_py_raw(pkt_val, str_encoding='unicode'):
    """Convert a PktValue to a raw Python value.

    Args:
        str_encoding: ``'unicode'`` returns Python ``unicode``;
            ``'utf8'`` returns UTF-8 encoded ``str`` bytes.
    """
    if isinstance(pkt_val, PktNull):
        return None
    if isinstance(pkt_val, PktBoolean):
        return pkt_val.value
    if isinstance(pkt_val, PktInt):
        return pkt_val.value
    if isinstance(pkt_val, PktDouble):
        return pkt_val.value
    if isinstance(pkt_val, PktString):
        if str_encoding == 'utf8':
            return pkt_val.value.encode('utf-8')
        return pkt_val.value
    if isinstance(pkt_val, PktList):
        if pkt_val._py_backing is not None:
            return pkt_val._py_backing
        return [_pkt_to_py_raw(v, str_encoding) for v in pkt_val.elements]
    if isinstance(pkt_val, PktMap):
        if pkt_val._py_backing is not None:
            return pkt_val._py_backing
        d = {}
        for k, v in pkt_val.entries.values():
            d[_pkt_to_py_raw(k, str_encoding)] = _pkt_to_py_raw(v, str_encoding)
        return d
    if isinstance(pkt_val, PktArray):
        if pkt_val._py_backing is not None:
            return pkt_val._py_backing
        return [_pkt_to_py_raw(v, str_encoding) for v in pkt_val.elements]
    if isinstance(pkt_val, PktPair):
        return (_pkt_to_py_raw(pkt_val.first, str_encoding),
                _pkt_to_py_raw(pkt_val.second, str_encoding))
    if isinstance(pkt_val, PktPythonInstance):
        return pkt_val._py_instance
    return pkt_val


def _py_to_pkt_value(py_val, str_encoding='unicode'):
    """Wrap a Python value as a PktValue.

    List, dict, and tuple arguments keep a ``_py_backing`` reference to
    the original Python object so that mutations from PyKt code are
    reflected back into Python.
    """
    if py_val is None:
        return PktNull()
    if isinstance(py_val, bool):
        return PktBoolean.TRUE if py_val else PktBoolean.FALSE
    if isinstance(py_val, int):
        return PktInt(py_val)
    if isinstance(py_val, float):
        return PktDouble(py_val)
    if isinstance(py_val, unicode):
        return PktString(py_val)
    if isinstance(py_val, str):
        if str_encoding == 'utf8':
            return PktString(py_val.decode('utf-8'))
        return PktString(py_val)
    if isinstance(py_val, list):
        lst = PktList([_py_to_pkt_value(v, str_encoding) for v in py_val],
                      py_backing=py_val)
        return lst
    if isinstance(py_val, dict):
        m = PktMap(py_backing=py_val)
        for k, v in py_val.items():
            m.put(_py_to_pkt_value(k, str_encoding),
                  _py_to_pkt_value(v, str_encoding))
        return m
    if isinstance(py_val, tuple):
        return PktList([_py_to_pkt_value(v, str_encoding) for v in py_val])
    if isinstance(py_val, PktValue):
        return py_val
    # Unknown Python object: wrap in PktPythonInstance
    return PktPythonInstance(type(py_val), py_val)


# =========================================================================
# Operator helpers
# =========================================================================

def promote_to_double(left, right):
    """If either operand is Double, promote both to PktDouble.

    Returns (left, right) potentially wrapped in PktDouble.
    """
    from token_types import TokenType
    if isinstance(left, PktDouble) and isinstance(right, PktInt):
        return (left, PktDouble(float(right.value)))
    elif isinstance(left, PktInt) and isinstance(right, PktDouble):
        return (PktDouble(float(left.value)), right)
    return (left, right)


def check_numeric(token, left, right):
    """Ensure both operands are numeric (Int or Double). Promote if mixed.

    Returns (left, right) after promotion.
    Raises PktTypeError if either operand is non-numeric.
    """
    if not isinstance(left, (PktInt, PktDouble)):
        raise PktTypeError(
            u"Expected numeric type, got '{}'".format(left.type_name),
            line=token.line, column=token.column)
    if not isinstance(right, (PktInt, PktDouble)):
        raise PktTypeError(
            u"Expected numeric type, got '{}'".format(right.type_name),
            line=token.line, column=token.column)
    return promote_to_double(left, right)


def make_int_or_double(value, left, right):
    """Create the appropriate numeric wrapper for a computed value.

    If both operands are Int, result is Int. If either is Double, result is Double.
    """
    if isinstance(left, PktInt) and isinstance(right, PktInt):
        return PktInt(value)
    return PktDouble(float(value))

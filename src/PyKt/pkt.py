# -*- coding: utf-8 -*-
"""Entry point and runtime control API for the PyKt language interpreter.

Design philosophy: "Everything is a variable" (万物皆变量).
  - Functions, classes, and values are all uniformly injected via `inject()`.
  - All are uniformly retrieved via `get()` / `[]`, returning usable Python objects.
  - Retrieved functions are Python-callable.
  - Retrieved classes are Python-callable (instantiate them).
  - Retrieved instances support Python attribute access.
  - Mutable/immutable distinction is enforced at injection time.

Usage:
    # CLI
    python -m PyKt <source_file.kt>

    # Embedded
    rt = PyKt.create_runtime()
    rt.inject('greet', lambda name: print('Hello', name))
    rt.inject('version', 1, mutable=False)
    rt.run('greet("World")')
    fn = rt['greet']        # get as Python-callable
    fn('PyKt')              # call it directly
"""

from __future__ import print_function, unicode_literals

import sys
import os
import codecs

from errors import PktError, PktRuntimeError
from runtime import (
    PktValue, PktNull, PktString, PktInt, PktDouble, PktBoolean,
    PktList, PktMap, PktPair, PktArray, PktIntRange,
    PktFunction, PktBuiltinFunction, PktClass, PktInstance, BoundMethod,
    PktPythonClass, PktPythonInstance, PktPythonMethod,
    PktThrowable, PktException, PktRuntimeException, PktPythonException,
    _pkt_to_py_raw, _py_to_pkt_value,
)
from environment import Environment


# =========================================================================
# Python-callable wrappers for PyKt objects
# =========================================================================

class PktCallable(object):
    """Base for wrappers that make PyKt objects callable from Python.

    Auto-wraps Python arguments into PktValues and auto-unwraps results.
    Kotlin exceptions (ThrowException) are converted to Python exceptions
    so they can be caught by Python code.
    Subclasses override _call_impl to provide the actual call logic.
    """

    def __init__(self, runtime, name):
        self._runtime = runtime
        self._name = name

    def __call__(self, *args):
        pkt_args = [self._runtime._wrap_value(a) for a in args]
        try:
            result = self._call_impl(pkt_args)
            return self._runtime._unwrap_value(result)
        except _PyKtExceptionBridge:
            raise  # already converted, let it propagate to Python
        except Exception as e:
            # Generic error if something else goes wrong
            raise RuntimeError(
                u"Error calling '{}': {}".format(self._name, unicode(e)))

    def _call_impl(self, pkt_args):
        raise NotImplementedError


# =========================================================================
# Exception bridge: Kotlin throwable → Python exception
# =========================================================================

class _PyKtExceptionBridge(Exception):
    """Bridges a Kotlin exception (PktThrowable) into a Python exception.

    When a Kotlin function throws, this exception is raised and can be
    caught by Python code calling into PyKt.

    Attributes:
        kt_throwable: The original PktThrowable from Kotlin code.
    """

    def __init__(self, kt_throwable):
        super(_PyKtExceptionBridge, self).__init__(unicode(kt_throwable))
        self.kt_throwable = kt_throwable
        self.kt_type_name = kt_throwable.type_name if hasattr(kt_throwable, 'type_name') else u'Throwable'

    def __str__(self):
        return u'[PyKt {}] {}'.format(self.kt_type_name, self.kt_throwable)

    def __repr__(self):
        return u'_PyKtExceptionBridge({})'.format(self.kt_throwable)


class PktFunctionWrapper(PktCallable):
    """Wraps a PyKt function (PktFunction) for calling from Python.

    Supports both user-defined PyKt functions and built-in functions.
    Kotlin exceptions (ThrowException) are converted to _PyKtExceptionBridge
    so Python code can catch them.
    """

    def __init__(self, runtime, name, func):
        super(PktFunctionWrapper, self).__init__(runtime, name)
        self._func = func

    def _call_impl(self, pkt_args):
        # Import here to avoid circular dependency
        from interpreter import ThrowException as _ThrowException

        try:
            if isinstance(self._func, PktBuiltinFunction):
                result = self._func.func(self._runtime._interpreter, pkt_args)
            elif isinstance(self._func, PktFunction):
                result = self._runtime._interpreter._call_function(
                    self._func, pkt_args)
            else:
                raise RuntimeError(u"'{}' is not callable".format(self._name))
        except _ThrowException as thrown:
            # Convert Kotlin exception to Python exception
            kt_exc = thrown.value if hasattr(thrown, 'value') else thrown
            raise _PyKtExceptionBridge(kt_exc)

        return result

    def __repr__(self):
        return u'<PyKt function {}>'.format(self._name)


class PktClassWrapper(PktCallable):
    """Wraps a PyKt class (PktClass) so it can be instantiated from Python.

    Calling this wrapper creates a new PyKt instance and returns
    a PktInstanceProxy for interacting with it from Python.
    """

    def __init__(self, runtime, name, klass):
        super(PktClassWrapper, self).__init__(runtime, name)
        self._klass = klass

    def _call_impl(self, pkt_args):
        instance = self._klass.call(self._runtime._interpreter, pkt_args)
        return instance  # Return raw PktInstance; _unwrap_value converts to proxy

    def __repr__(self):
        return u'<PyKt class {}>'.format(self._name)


class PktPythonClassWrapper(PktCallable):
    """Wraps a Python class as a PyKt-compatible class.

    When instantiated from PyKt code, creates a Python instance and wraps it.
    When called from Python (via get()), creates the Python instance directly.
    """

    def __init__(self, runtime, name, pkt_py_class):
        super(PktPythonClassWrapper, self).__init__(runtime, name)
        self._pkt_py_class = pkt_py_class  # PktPythonClass instance
        self._real_py_class = pkt_py_class._py_class  # actual Python type

    def _call_impl(self, pkt_args):
        raw_args = [self._runtime._unwrap_value(a) for a in pkt_args]
        try:
            py_instance = self._real_py_class(*raw_args)
        except Exception as e:
            raise PktRuntimeError(
                u"Error constructing '{}': {}".format(self._name, unicode(e)))
        return py_instance  # Return raw Python object

    def __repr__(self):
        return u'<PyKt python-class {}>'.format(self._name)


class PktInstanceProxy(object):
    """Proxy for a PyKt instance, providing Python attribute access.

    Allows reading/writing properties and calling methods on PyKt instances
    as if they were native Python objects.

    Methods returned from this proxy are callable from Python with
    auto-wrapping/unwrapping of arguments.
    """

    def __init__(self, runtime, instance):
        self._runtime = runtime
        self._instance = instance

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)

        try:
            val = self._instance.get(unicode(name))
        except PktRuntimeError:
            raise AttributeError(
                u"'{}' instance has no attribute '{}'".format(
                    self._instance.type_name, name))

        # If it's a BoundMethod, return a Python-callable wrapper
        if isinstance(val, BoundMethod):
            return _BoundMethodWrapper(self._runtime, val)
        if isinstance(val, PktFunction):
            return PktFunctionWrapper(self._runtime, name, val)
        if isinstance(val, PktBuiltinFunction):
            return PktFunctionWrapper(self._runtime, name, val)

        # Otherwise unwrap and return
        return self._runtime._unwrap_value(val)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super(PktInstanceProxy, self).__setattr__(name, value)
            return
        pkt_val = self._runtime._wrap_value(value)
        self._instance.set(unicode(name), pkt_val)

    def __repr__(self):
        return u'<PyKt instance of {}>'.format(self._instance.type_name)

    def __str__(self):
        return unicode(self._instance)


class _BoundMethodWrapper(object):
    """Python-callable wrapper for a BoundMethod."""

    def __init__(self, runtime, bound_method):
        self._runtime = runtime
        self._bound_method = bound_method

    def __call__(self, *args):
        from interpreter import ThrowException as _ThrowException

        pkt_args = [self._runtime._wrap_value(a) for a in args]
        try:
            result = self._runtime._interpreter._call_bound_method(
                self._bound_method, pkt_args)
        except _ThrowException as thrown:
            kt_exc = thrown.value if hasattr(thrown, 'value') else thrown
            raise _PyKtExceptionBridge(kt_exc)
        except Exception as e:
            raise RuntimeError(
                u"Error calling method: {}".format(unicode(e)))
        return self._runtime._unwrap_value(result)

    def __repr__(self):
        return u'<bound method {}>'.format(
            self._bound_method.method.declaration.name)


class PktListProxy(object):
    """Mutable list proxy — wraps PktList with Python list-like access."""

    def __init__(self, runtime, pkt_list):
        self._runtime = runtime
        self._list = pkt_list

    def __getitem__(self, index):
        return self._runtime._unwrap_value(self._list.elements[index])

    def __setitem__(self, index, value):
        self._list.elements[index] = self._runtime._wrap_value(value)

    def __len__(self):
        return len(self._list.elements)

    def __iter__(self):
        for elem in self._list.elements:
            yield self._runtime._unwrap_value(elem)

    def __contains__(self, item):
        wrapped = self._runtime._wrap_value(item)
        for elem in self._list.elements:
            if elem.equals(wrapped):
                return True
        return False

    def append(self, value):
        self._list.elements.append(self._runtime._wrap_value(value))

    def pop(self, index=-1):
        return self._runtime._unwrap_value(self._list.elements.pop(index))

    def __repr__(self):
        return repr([self._runtime._unwrap_value(e) for e in self._list.elements])

    def __str__(self):
        return unicode(self._list)


class PktMapProxy(object):
    """Mutable map proxy — wraps PktMap with Python dict-like access."""

    def __init__(self, runtime, pkt_map):
        self._runtime = runtime
        self._map = pkt_map

    def __getitem__(self, key):
        result = self._map.get_value(self._runtime._wrap_value(key))
        if isinstance(result, PktNull):
            raise KeyError(key)
        return self._runtime._unwrap_value(result)

    def __setitem__(self, key, value):
        self._map.put(self._runtime._wrap_value(key),
                      self._runtime._wrap_value(value))

    def __delitem__(self, key):
        result = self._map.remove(self._runtime._wrap_value(key))
        if isinstance(result, PktNull):
            raise KeyError(key)

    def __len__(self):
        return len(self._map.entries)

    def __iter__(self):
        for key, _ in self._map.entries.values():
            yield self._runtime._unwrap_value(key)

    def __contains__(self, key):
        return self._map.contains_key(self._runtime._wrap_value(key))

    def keys(self):
        return [self._runtime._unwrap_value(k) for k, _ in self._map.entries.values()]

    def values(self):
        return [self._runtime._unwrap_value(v) for _, v in self._map.entries.values()]

    def items(self):
        return [(self._runtime._unwrap_value(k), self._runtime._unwrap_value(v))
                for k, v in self._map.entries.values()]

    def get(self, key, default=None):
        result = self._map.get_value(self._runtime._wrap_value(key))
        if isinstance(result, PktNull):
            return default
        return self._runtime._unwrap_value(result)

    def __repr__(self):
        return repr(dict(self.items()))

    def __str__(self):
        return unicode(self._map)


# Immutable PktValue types (always treated as val in PyKt)
_IMMUTABLE_PKT_TYPES = (PktNull, PktBoolean, PktInt, PktDouble, PktString)


# =========================================================================
# PyKtRuntime — the main runtime controller
# =========================================================================

class PyKtRuntime(object):
    """Runtime controller for an embedded PyKt interpreter.

    Philosophy: "Everything is a variable" (万物皆变量).

    Core API:
        rt.inject(name, value, mutable=True)  -- inject anything as a global variable
        rt.get(name)   or  rt[name]           -- get a variable as a usable Python object
        rt.run(source) or  rt.run_file(path)  -- execute PyKt source code

    Example:
        rt = PyKtRuntime()
        rt.inject('greet', lambda name: print('Hello', name))
        rt.inject('PI', 3.14159, mutable=False)   # immutable val
        rt.run('greet("World")')

        fn = rt['greet']         # get as Python-callable
        fn('PyKt')               # call directly

        pi = rt['PI']            # get raw Python value (3.14159)
    """

    def __init__(self):
        from interpreter import Interpreter
        self._interpreter = Interpreter()
        self._had_error = False
        self._error_message = u''

        # Register Python-callable wrapper for PktBuiltinFunction.func calls.
        # Each injected Python callable needs access to the interpreter.
        self._interpreter._runtime_ref = self

    # ------------------------------------------------------------------
    # Source execution
    # ------------------------------------------------------------------

    def run(self, source, filename='<string>'):
        """Execute PyKt source code.

        Args:
            source: Source code string (unicode or bytes).
            filename: Source identifier for error messages.

        Returns:
            self (for chaining).
        """
        from lexer import Lexer
        from pkt_parser import Parser

        lexer = Lexer(source, filename)
        parser = Parser(lexer)

        try:
            statements = parser.parse()
            self._interpreter.interpret(statements)
            self._had_error = False
            self._error_message = u''
        except PktError as e:
            self._had_error = True
            self._error_message = unicode(e)
            print(unicode(e), file=sys.stderr)
        except Exception as e:
            self._had_error = True
            self._error_message = unicode(e)
            print(u'Internal error: {}'.format(unicode(e)), file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

        return self

    def run_file(self, filepath):
        """Read and execute a PyKt source file.

        Args:
            filepath: Path to the source file.

        Returns:
            self (for chaining).
        """
        if not os.path.exists(filepath):
            self._had_error = True
            self._error_message = u'File not found: {}'.format(filepath)
            print(self._error_message, file=sys.stderr)
            return self

        try:
            with codecs.open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()
        except IOError as e:
            self._had_error = True
            self._error_message = unicode(e)
            print(u'Error reading file: {}'.format(filepath), file=sys.stderr)
            return self

        return self.run(source, filepath)

    @property
    def had_error(self):
        """Return True if the last run encountered an error."""
        return self._had_error

    @property
    def error_message(self):
        """Return the last error message, or empty string."""
        return self._error_message

    # ------------------------------------------------------------------
    # Unified injection: "Everything is a variable"
    # ------------------------------------------------------------------

    def inject(self, name, value, mutable=True):
        """Inject a value as a global variable in the PyKt runtime.

        This is the SINGLE entry point for making anything available to PyKt code.
        Functions, classes, and plain values are all injected the same way.

        Args:
            name: Variable name visible in PyKt code.
            value: What to inject. Can be:
                - A Python callable (function/lambda)     -> callable from PyKt
                - A Python class (type)                   -> instantiable from PyKt
                - A PktValue instance                     -> used as-is
                - A Python primitive (int, str, etc.)     -> auto-wrapped
                - A Python list                           -> auto-wrapped as PktList
                - A Python dict                           -> auto-wrapped as PktMap
            mutable: Whether the variable can be reassigned (var vs val).
                - True  -> 'var' (mutable, can be reassigned)
                - False -> 'val' (immutable, cannot be reassigned)
                - Immutable types (int, str, bool, float, None) are
                  ALWAYS treated as 'val' regardless of this flag,
                  since their values cannot be modified.
                - Collection types (list, map) are always 'var' since
                  their contents can be modified.

        Returns:
            self (for chaining).

        Example:
            rt.inject('add', lambda a, b: a + b)       # inject a function
            rt.inject('PI', 3.14159, mutable=False)     # inject immutable value
            rt.inject('scores', [95, 87, 92])           # inject mutable list
            rt.inject('config', {'debug': True})        # inject mutable map
        """
        uname = unicode(name)

        # Determine if this should be val (immutable) or var (mutable)
        is_val = not mutable

        if callable(value) and not isinstance(value, (PktValue, type)):
            # Python callable -> PktBuiltinFunction
            pkt_value = PktBuiltinFunction(uname, self._make_callable_func(value), -1)
            is_val = True   # functions cannot be reassigned

        elif isinstance(value, type):
            # Python class -> PktPythonClass
            pkt_value = PktPythonClass(uname, value)
            is_val = True   # classes cannot be reassigned

        elif isinstance(value, PktValue):
            # Already a PktValue
            pkt_value = value
            if isinstance(value, _IMMUTABLE_PKT_TYPES):
                is_val = True   # immutable values are always val
            elif isinstance(value, (PktList, PktMap, PktArray)):
                is_val = False  # collections are always var (contents mutable)
            elif isinstance(value, (PktFunction, PktBuiltinFunction, PktClass)):
                is_val = True   # functions and classes are val

        else:
            # Python primitive -> auto-wrap
            pkt_value = self._wrap_value(value)
            if isinstance(pkt_value, _IMMUTABLE_PKT_TYPES):
                is_val = True
            elif isinstance(pkt_value, (PktList, PktMap)):
                is_val = False

        self._interpreter.globals.define(uname, pkt_value, is_val=is_val)
        return self

    def _make_callable_func(self, python_callable):
        """Create a PktBuiltinFunction-compatible callable from a Python function.

        The returned function has the signature (interpreter, args) expected
        by PktBuiltinFunction, but auto-unwraps args and auto-wraps the result.

        Python exceptions raised by the callable are allowed to propagate
        so that _visit_CallExpr can convert them to PktPythonException
        (catchable in Kotlin try-catch).
        """
        def _wrapper(interpreter, pkt_args):
            raw_args = [self._unwrap_value(a) for a in pkt_args]
            result = python_callable(*raw_args)
            return self._wrap_value(result)
        return _wrapper

    # ------------------------------------------------------------------
    # Unified retrieval: get / __getitem__
    # ------------------------------------------------------------------

    def get(self, name):
        """Get a variable from the PyKt runtime as a usable Python object.

        This is the SINGLE entry point for reading anything from PyKt.
        The return value depends on what was stored:

        - PktFunction / PktBuiltinFunction -> Python-callable wrapper
        - PktClass                            -> Python-callable wrapper (instantiate it)
        - PktPythonClass                      -> Python-callable wrapper
        - PktInstance                         -> PktInstanceProxy (attribute access)
        - PktList                             -> PktListProxy (list-like access)
        - PktMap                              -> PktMapProxy (dict-like access)
        - PktInt / PktDouble / PktString ...  -> raw Python value (int/float/str)

        This enables natural Python usage:
            fn = rt.get('add')        # get a function
            result = fn(5, 7)         # call it directly

            person = rt.get('Person') # get a class
            alice = person('Alice')   # instantiate it
            alice.name                # access properties
            alice.greet()             # call methods

        Args:
            name: Variable name.

        Returns:
            A Python-usable representation of the variable.

        Raises:
            KeyError: If the variable is not found.
        """
        uname = unicode(name)
        try:
            pkt_val = self._interpreter.globals.get(uname)
        except PktRuntimeError:
            raise KeyError(u"Variable '{}' not found".format(name))
        return self._unwrap_value(pkt_val)

    def __getitem__(self, name):
        """Shorthand for get(): rt['name']"""
        return self.get(name)

    def __setitem__(self, name, value):
        """Shorthand for inject() without mutability control.

        Uses default mutable=True (or auto-detects immutability).
        """
        self.inject(name, value, mutable=True)

    def __contains__(self, name):
        """Check if a variable exists: 'name' in rt"""
        uname = unicode(name)
        try:
            self._interpreter.globals.get(uname)
            return True
        except PktRuntimeError:
            return False

    @property
    def variables(self):
        """Return a list of all global variable names."""
        return list(self._interpreter.globals._values.keys())

    # ------------------------------------------------------------------
    # Value wrapping / unwrapping helpers
    # ------------------------------------------------------------------

    def _wrap_value(self, value):
        """Wrap a Python value into a PktValue."""
        return _py_to_pkt_value(value)

    def _unwrap_value(self, pkt_val):
        """Convert a PktValue into a Python-usable representation.

        The unwrapping strategy depends on the type:

        - Primitives (Null, Boolean, Int, Double, String) -> raw Python value
        - PktList -> PktListProxy (list-like mutable wrapper)
        - PktMap  -> PktMapProxy (dict-like mutable wrapper)
        - PktFunction / PktBuiltinFunction -> PktFunctionWrapper (callable)
        - PktClass -> PktClassWrapper (callable)
        - PktPythonClass -> PktPythonClassWrapper (callable)
        - PktInstance -> PktInstanceProxy (attribute access)
        - PktPythonInstance -> raw Python object
        """
        if pkt_val is None or isinstance(pkt_val, PktNull):
            return None
        if isinstance(pkt_val, PktBoolean):
            return pkt_val.value
        if isinstance(pkt_val, PktInt):
            return pkt_val.value
        if isinstance(pkt_val, PktDouble):
            return pkt_val.value
        if isinstance(pkt_val, PktString):
            return pkt_val.value
        if isinstance(pkt_val, PktList):
            return PktListProxy(self, pkt_val)
        if isinstance(pkt_val, PktMap):
            return PktMapProxy(self, pkt_val)
        if isinstance(pkt_val, PktArray):
            return PktListProxy(self, PktList(pkt_val.elements))
        if isinstance(pkt_val, PktIntRange):
            return range(pkt_val.start, pkt_val.end + 1, pkt_val.step)
        if isinstance(pkt_val, PktBuiltinFunction):
            return PktFunctionWrapper(self, pkt_val.name, pkt_val)
        if isinstance(pkt_val, PktFunction):
            return PktFunctionWrapper(
                self, pkt_val.declaration.name, pkt_val)
        if isinstance(pkt_val, PktClass):
            return PktClassWrapper(self, pkt_val.name, pkt_val)
        if isinstance(pkt_val, PktPythonClass):
            return PktPythonClassWrapper(self, pkt_val._name, pkt_val)
        if isinstance(pkt_val, PktInstance):
            return PktInstanceProxy(self, pkt_val)
        if isinstance(pkt_val, PktPythonInstance):
            return pkt_val._py_instance
        if isinstance(pkt_val, PktPair):
            return (self._unwrap_value(pkt_val.first),
                    self._unwrap_value(pkt_val.second))
        return pkt_val


# =========================================================================
# Legacy / convenience API
# =========================================================================

def create_runtime():
    """Create a new PyKtRuntime instance.

    Returns:
        A PyKtRuntime ready for injection and execution.
    """
    return PyKtRuntime()


def run(source, filename='<unknown>'):
    """Execute PyKt source code (simple one-shot API).

    Returns:
        0 on success, 1 on error.
    """
    rt = PyKtRuntime()
    rt.run(source, filename)
    return 1 if rt.had_error else 0


def run_file(filepath):
    """Read and execute a PyKt source file (simple one-shot API).

    Returns:
        0 on success, 1 on error.
    """
    rt = PyKtRuntime()
    rt.run_file(filepath)
    return 1 if rt.had_error else 0


def main():
    """Command-line entry point: python -m PyKt <file.kt>"""
    if len(sys.argv) < 2:
        print(u'PyKt - A Kotlin-like language interpreter in Python 2.7', file=sys.stderr)
        print(u'', file=sys.stderr)
        print(u'Usage: python -m PyKt <source_file>', file=sys.stderr)
        print(u'', file=sys.stderr)
        print(u'Example:', file=sys.stderr)
        print(u'  python -m PyKt examples/hello.kt', file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    exit_code = run_file(filepath)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()

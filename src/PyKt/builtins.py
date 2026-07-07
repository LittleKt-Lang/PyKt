# -*- coding: utf-8 -*-
"""Built-in functions for the PyKt language.

Registers standard library functions like println, print, and readLine
into the global interpreter environment.
"""

from __future__ import unicode_literals, print_function

try:
    unicode
except NameError:
    unicode = str  # Python 3 compatibility

from runtime import (
    PktNull, PktString, PktInt, PktDouble, PktBoolean, PktBuiltinFunction,
    PktList, PktArray, PktMap, PktPair,
    PktThrowable, PktException, PktRuntimeException, PktError,
    PktExceptionClass,
)
from errors import PktRuntimeError


class Builtins(object):
    """Registry of built-in functions.

    Usage:
        Builtins.register(global_environment)
    """

    @staticmethod
    def register(env):
        """Register all built-in functions into the given environment."""
        env.define(u'println', PktBuiltinFunction(u'println', Builtins._println, -1), is_val=True)
        env.define(u'print', PktBuiltinFunction(u'print', Builtins._print, -1), is_val=True)
        env.define(u'readLine', PktBuiltinFunction(u'readLine', Builtins._readLine, 0), is_val=True)
        env.define(u'arrayOf', PktBuiltinFunction(u'arrayOf', Builtins._arrayOf, -1), is_val=True)
        env.define(u'arrayOfNulls', PktBuiltinFunction(u'arrayOfNulls', Builtins._arrayOfNulls, 1), is_val=True)
        env.define(u'mapOf', PktBuiltinFunction(u'mapOf', Builtins._mapOf, -1), is_val=True)
        env.define(u'listOf', PktBuiltinFunction(u'listOf', Builtins._listOf, -1), is_val=True)

        # Throwable / Exception hierarchy
        env.define(u'Throwable', PktExceptionClass(u'Throwable',
            lambda msg, cause: PktThrowable(msg, cause)), is_val=True)
        env.define(u'Exception', PktExceptionClass(u'Exception',
            lambda msg, cause: PktException(msg, cause)), is_val=True)
        env.define(u'RuntimeException', PktExceptionClass(u'RuntimeException',
            lambda msg, cause: PktRuntimeException(msg, cause)), is_val=True)
        env.define(u'Error', PktExceptionClass(u'Error',
            lambda msg, cause: PktError(msg, cause)), is_val=True)

    # ------------------------------------------------------------------
    # println(vararg args) - prints each argument separated by space, then newline
    # ------------------------------------------------------------------

    @staticmethod
    def _println(interpreter, arguments):
        parts = []
        for arg in arguments:
            parts.append(unicode(arg))
        line = u' '.join(parts)
        # Python 2.7: encode to stdout encoding for safe printing
        import sys
        if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding:
            try:
                print(line.encode(sys.stdout.encoding, 'replace'))
            except UnicodeError:
                print(line.encode('utf-8'))
        else:
            print(line.encode('utf-8'))
        return PktNull()

    # ------------------------------------------------------------------
    # print(vararg args) - prints each argument separated by space, no newline
    # ------------------------------------------------------------------

    @staticmethod
    def _print(interpreter, arguments):
        parts = []
        for arg in arguments:
            parts.append(unicode(arg))
        line = u' '.join(parts)
        import sys
        if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding:
            try:
                print(line.encode(sys.stdout.encoding, 'replace'), end='')
            except UnicodeError:
                print(line.encode('utf-8'), end='')
        else:
            print(line.encode('utf-8'), end='')
        # Flush so output appears immediately
        sys.stdout.flush()
        return PktNull()

    # ------------------------------------------------------------------
    # readLine() - reads a line from stdin
    # ------------------------------------------------------------------

    @staticmethod
    def _readLine(interpreter, arguments):
        import sys
        try:
            line = raw_input()
        except EOFError:
            return PktNull()
        # raw_input returns bytes in Python 2; decode to unicode
        if isinstance(line, str):
            line = line.decode(sys.stdin.encoding or 'utf-8')
        return PktString(line)

    # ------------------------------------------------------------------
    # arrayOf(vararg elements) - creates an Array from elements
    # ------------------------------------------------------------------

    @staticmethod
    def _arrayOf(interpreter, arguments):
        size = len(arguments)
        arr = PktArray(size)
        for i, elem in enumerate(arguments):
            arr.elements[i] = elem
        return arr

    # ------------------------------------------------------------------
    # arrayOfNulls(size) - creates an Array of the given size filled with null
    # ------------------------------------------------------------------

    @staticmethod
    def _arrayOfNulls(interpreter, arguments):
        if not isinstance(arguments[0], PktInt):
            raise PktRuntimeError(u'arrayOfNulls() requires an Int argument')
        size = arguments[0].value
        return PktArray(size, PktNull())

    # ------------------------------------------------------------------
    # mapOf(vararg pairs) - creates a Map from Pair arguments
    # ------------------------------------------------------------------

    @staticmethod
    def _mapOf(interpreter, arguments):
        pairs = []
        for arg in arguments:
            if isinstance(arg, PktPair):
                pairs.append(arg)
            else:
                raise PktRuntimeError(
                    u'mapOf() expects Pair arguments, got {}'.format(arg.type_name))
        return PktMap(pairs)

    # ------------------------------------------------------------------
    # listOf(vararg elements) - creates a List from elements (like Kotlin)
    # ------------------------------------------------------------------

    @staticmethod
    def _listOf(interpreter, arguments):
        return PktList(list(arguments))

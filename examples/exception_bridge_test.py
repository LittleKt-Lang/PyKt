# -*- coding: utf-8 -*-
"""Test bidirectional Python-Kotlin exception compatibility.

Tests:
1. Python exceptions caught in Kotlin try-catch
2. Kotlin exceptions propagated to Python
3. Throwing Python exception classes from Kotlin
4. Kotlin throwables passed to Python side
"""
from __future__ import print_function, unicode_literals

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyKt.pkt import create_runtime, _PyKtExceptionBridge


def test_python_exception_caught_in_kotlin():
    """1. When Kotlin calls a Python function that raises, Kotlin can catch it."""
    print("=== 1. Python exception caught in Kotlin try-catch ===")

    rt = create_runtime()

    def raise_value_error():
        raise ValueError("This is a Python ValueError!")

    rt.inject('pythonFunc', raise_value_error)

    rt.run('''
    fun main() {
        try {
            println("Calling Python function that raises...")
            pythonFunc()
        } catch (e: ValueError) {
            println("Kotlin caught ValueError: " + e)
        } catch (e: Exception) {
            println("Kotlin caught Exception (fallback): " + e)
        }
        println("After python exception catch")
    }
    main()
    ''')

    print("  Result: had_error = " + unicode(rt.had_error))


def test_python_exception_uncaught_in_kotlin():
    """1b. When Kotlin can't catch the Python exception type, it propagates."""
    print("=== 1b. Uncaught Python exception propagates ===")

    rt = create_runtime()

    def raise_type_error():
        raise TypeError("Bad type!")

    rt.inject('typeErrFunc', raise_type_error)

    rt.run('''
    fun main() {
        try {
            typeErrFunc()
        } catch (e: ValueError) {
            println("Wrong: caught by ValueError")
        }
    }
    main()
    ''')

    print("  Result: had_error = " + unicode(rt.had_error))
    print("  Error message: " + rt.error_message)


def test_kotlin_exception_propagates_to_python():
    """2. When Python calls a Kotlin function that throws, Python can catch it."""
    print("\n=== 2. Kotlin exception propagates to Python ===")

    rt = create_runtime()

    rt.run('''
    fun throwsRuntimeException() {
        throw RuntimeException("Kotlin threw this!")
    }

    fun safeFunction() {
        println("This one works fine")
    }
    ''')

    # Get the Kotlin function that throws
    throws_fn = rt['throwsRuntimeException']

    try:
        throws_fn()
        print("  ERROR: Should have raised!")
    except _PyKtExceptionBridge as e:
        print("  Python caught Kotlin exception: " + unicode(e))
        print("  Exception type name: " + e.kt_type_name)
        print("  Original throwable: " + unicode(e.kt_throwable))

    # Verify safe function still works
    safe_fn = rt['safeFunction']
    safe_fn()
    print("  Safe Kotlin function call succeeded")


def test_python_method_exception_caught():
    """3. Python method exceptions from injected classes caught in Kotlin."""
    print("\n=== 3. Python method exception caught in Kotlin ===")

    rt = create_runtime()

    class RiskyService(object):
        def do_work(self):
            raise IOError("File not found")

        def safe_work(self):
            return "All good"

    rt.inject('RiskyService', RiskyService)

    rt.run('''
    fun main() {
        val svc = RiskyService()
        try {
            svc.do_work()
        } catch (e: IOError) {
            println("Kotlin caught IOError from Python method: " + e)
        }

        // Safe method should still work
        val result = svc.safe_work()
        println("Safe method result: " + result)
    }
    main()
    ''')

    print("  Result: had_error = " + unicode(rt.had_error))


def test_kotlin_throw_python_exception_class():
    """4. Kotlin can create and throw Python exception types.

    Python exception classes injected into Kotlin can be instantiated
    and thrown, and they produce Python-catchable exceptions.
    """
    print("\n=== 4. Kotlin throws Python-created exception ===")

    rt = create_runtime()

    # Inject Python exception types
    rt.inject('PyValueError', ValueError)
    rt.inject('PyRuntimeError', RuntimeError)

    rt.run('''
    fun main() {
        // Create and throw Python exception instances
        try {
            val exc = PyValueError("Bad value from Kotlin!")
            throw exc
        } catch (e: ValueError) {
            println("Kotlin caught injected ValueError: " + e)
        }

        // Throw a different type
        try {
            throw PyRuntimeError("Runtime issue")
        } catch (e: RuntimeError) {
            println("Kotlin caught injected RuntimeError: " + e)
        }
    }
    main()
    ''')

    print("  Result: had_error = " + unicode(rt.had_error))


def test_full_bidirectional_flow():
    """5. Full bidirectional flow: Python→Kotlin→Python exception chain."""
    print("\n=== 5. Full bidirectional exception chain ===")

    rt = create_runtime()

    # Python function that raises
    def risky_python_func():
        raise LookupError("Python LookupError from injected function")

    rt.inject('riskyPython', risky_python_func)

    # Kotlin function that calls the Python function (catches and re-throws)
    rt.run('''
    fun kotlinWrapper() {
        try {
            riskyPython()
        } catch (e: LookupError) {
            println("Kotlin wrapper caught: " + e)
            // Re-throw as a RuntimeException with context
            throw RuntimeException("Wrapped from Kotlin: " + e)
        }
    }
    ''')

    # Python calls the Kotlin wrapper
    wrapper_fn = rt['kotlinWrapper']

    try:
        wrapper_fn()
        print("  ERROR: Should have raised!")
    except _PyKtExceptionBridge as e:
        print("  Python caught re-thrown exception: " + unicode(e))
        print("  Exception type: " + e.kt_type_name)

    print("\n=== All bidirectional exception tests passed ===")


if __name__ == '__main__':
    test_python_exception_caught_in_kotlin()
    test_python_exception_uncaught_in_kotlin()
    test_kotlin_exception_propagates_to_python()
    test_python_method_exception_caught()
    test_kotlin_throw_python_exception_class()
    test_full_bidirectional_flow()

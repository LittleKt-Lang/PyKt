# -*- coding: utf-8 -*-
"""PyKt - A Kotlin-like language interpreter written in Python 2.7.

Usage:
    # Simple execution
    import PyKt
    PyKt.run(source_code, filename='myfile.kt')
    PyKt.run_file('path/to/file.kt')

    # Embedded usage with runtime control API
    runtime = PyKt.create_runtime()
    runtime.inject_function('greet', lambda rt, args: print('Hello'), 0)
    runtime.inject_global('version', 1)
    runtime.run('greet()')
    val = runtime.get_variable_raw('version')
"""

from __future__ import unicode_literals

from pkt import run, run_file, main, PyKtRuntime, create_runtime

__all__ = ['run', 'run_file', 'main', 'PyKtRuntime', 'create_runtime']

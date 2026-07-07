# -*- coding: utf-8 -*-
"""Scope / environment management for the PyKt interpreter.

Environments form a linked list (parent chain) representing lexical scopes.
Variable lookup walks up the chain until the name is found.
"""

from __future__ import unicode_literals

from errors import PktRuntimeError


class Environment(object):
    """A single lexical scope in the interpreter.

    Environments form a linked list via `_enclosing`. Variable lookup
    walks up the chain until found. Variables are defined in the current
    scope (shadowing outer scopes), while assignment walks up to find
    the existing binding.

    Attributes:
        _enclosing: The parent Environment, or None for global scope.
        _values: Dict mapping variable names to PktValue.
        _mutability: Dict mapping variable names to 'val' or 'var'.
    """

    def __init__(self, enclosing=None):
        self._enclosing = enclosing          # parent scope or None
        self._values = {}                    # name -> PktValue
        self._mutability = {}                # name -> 'val' or 'var'
        self._type_annotations = {}          # name -> type annotation string (or None)

    def define(self, name, value, is_val=False, type_annotation=None):
        """Define a new variable in the CURRENT scope.

        Args:
            name: Variable name (unicode).
            value: The PktValue to bind.
            is_val: If True, the variable is immutable (Kotlin 'val').
            type_annotation: Optional type annotation string (e.g., 'Int', 'String?').
        """
        self._values[name] = value
        self._mutability[name] = 'val' if is_val else 'var'
        if type_annotation is not None:
            self._type_annotations[name] = type_annotation

    def get(self, name):
        """Look up a variable by name, walking up the chain.

        Raises:
            PktRuntimeError: If the variable is not found.
        """
        if name in self._values:
            return self._values[name]
        if self._enclosing is not None:
            return self._enclosing.get(name)
        raise PktRuntimeError(
            u"Undefined variable: '{}'".format(name))

    def assign(self, name, value):
        """Assign a new value to an EXISTING variable, walking up the chain.

        Raises:
            PktRuntimeError: If the variable is not found or is immutable (val).
        """
        if name in self._values:
            if self._mutability.get(name) == 'val':
                raise PktRuntimeError(
                    u"Cannot reassign val '{}'".format(name))
            self._values[name] = value
            return
        if self._enclosing is not None:
            self._enclosing.assign(name, value)
            return
        raise PktRuntimeError(
            u"Undefined variable: '{}'".format(name))

    def assign_at(self, name, value):
        """Assign to a variable in the CURRENT scope only (for init blocks).

        Raises:
            PktRuntimeError: If the variable is not in this scope or is 'val'.
        """
        if name in self._values:
            if self._mutability.get(name) == 'val':
                raise PktRuntimeError(
                    u"Cannot reassign val '{}'".format(name))
            self._values[name] = value
            return
        raise PktRuntimeError(
            u"Variable '{}' not defined in this scope".format(name))

    def get_type_annotation(self, name):
        """Get the type annotation for a variable, walking up the scope chain.

        Returns the type annotation string (e.g., 'Int', 'String?'), or None
        if the variable has no type annotation.
        """
        if name in self._type_annotations:
            return self._type_annotations[name]
        if self._enclosing is not None:
            return self._enclosing.get_type_annotation(name)
        return None

    def __contains__(self, name):
        """Check if a variable exists anywhere in the scope chain."""
        if name in self._values:
            return True
        if self._enclosing is not None:
            return name in self._enclosing
        return False


class InstanceEnvironment(Environment):
    """An environment for class instances.

    Extends Environment to also look up instance fields (class properties)
    when a variable is not found in the normal scope chain.
    """

    def __init__(self, instance, enclosing=None):
        super(InstanceEnvironment, self).__init__(enclosing)
        self._instance = instance

    def get(self, name):
        """Look up a variable: first in env chain, then in instance fields."""
        if name in self._values:
            return self._values[name]
        # Check instance fields
        if name in self._instance.fields:
            return self._instance.fields[name]
        if self._enclosing is not None:
            return self._enclosing.get(name)
        raise PktRuntimeError(
            u"Undefined variable: '{}'".format(name))

    def assign(self, name, value):
        """Assign to a variable: first check env chain, then instance fields."""
        if name in self._values:
            if self._mutability.get(name) == 'val':
                raise PktRuntimeError(
                    u"Cannot reassign val '{}'".format(name))
            self._values[name] = value
            return
        # Check instance fields
        if name in self._instance.fields:
            self._instance.fields[name] = value
            return
        if self._enclosing is not None:
            self._enclosing.assign(name, value)
            return
        raise PktRuntimeError(
            u"Undefined variable: '{}'".format(name))

    def __contains__(self, name):
        if name in self._values:
            return True
        if name in self._instance.fields:
            return True
        if self._enclosing is not None:
            return name in self._enclosing
        return False

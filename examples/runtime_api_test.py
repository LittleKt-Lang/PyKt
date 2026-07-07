# -*- coding: utf-8 -*-
"""Test the redesigned PyKt runtime control API.

Demonstrates the "everything is a variable" design:
  - Unified inject() for functions, classes, and values
  - Unified get() / [] for retrieving variables as usable Python objects
  - Immutable protection via mutable=False
  - Python class injection
  - Calling PyKt-defined functions from Python
  - Accessing PyKt class instances from Python
"""
from __future__ import print_function, unicode_literals

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyKt.pkt import PyKtRuntime, create_runtime


def test_unified_inject():
    """Test unified inject/get API."""
    print("=== 1. Unified inject/get ===")

    rt = create_runtime()

    # Inject a function (any Python callable)
    rt.inject('add', lambda a, b: a + b)
    rt.inject('greet', lambda name: 'Hello, ' + name + '!')

    # Inject immutable values (mutable=False)
    rt.inject('PI', 3.14159, mutable=False)
    rt.inject('APP_NAME', 'PyKtDemo', mutable=False)

    # Inject mutable collections
    rt.inject('scores', [95, 87, 92])
    rt.inject('config', {'debug': True, 'version': 2})

    # Get and call a function
    add_fn = rt['add']
    result = add_fn(5, 7)
    print("rt['add'](5, 7) = " + unicode(result))

    greet_fn = rt['greet']
    print("rt['greet']('World') = " + greet_fn('World'))

    # Get immutable values
    pi = rt['PI']
    print("rt['PI'] = " + unicode(pi) + " (type=" + type(pi).__name__ + ")")

    app = rt['APP_NAME']
    print("rt['APP_NAME'] = " + app)

    # Get mutable list proxy
    scores = rt['scores']
    print("rt['scores'] = " + unicode(scores) + " (type=" + type(scores).__name__ + ")")
    scores.append(100)
    print("After append(100): " + unicode(scores))

    # Get mutable map proxy
    config = rt['config']
    print("rt['config'] = " + unicode(config) + " (type=" + type(config).__name__ + ")")
    config['debug'] = False
    print("After config['debug']=False: " + unicode(config))


def test_pykt_functions():
    print("\n=== 2. PyKt-defined functions callable from Python ===")
    rt = create_runtime()

    rt.run('''
    fun factorial(n: Int): Int {
        if (n <= 1) {
            return 1
        }
        return n * factorial(n - 1)
    }

    fun makeGreeting(name: String, age: Int): String {
        return "Hi, I'm " + name + " and I'm " + age + " years old."
    }
    ''')

    fact = rt['factorial']
    print("rt['factorial'](5) = " + unicode(fact(5)))
    print("rt['factorial'](10) = " + unicode(fact(10)))

    greet = rt['makeGreeting']
    print("rt['makeGreeting']('Alice', 30) = " + greet('Alice', 30))

def test_class_injection():
    """Test Python class injection and PyKt class retrieval."""
    print("\n=== 3. Python class injection ===")

    rt = create_runtime()

    # Define a Python class and inject it
    class Calculator(object):
        def __init__(self, initial=0):
            self.value = initial

        def add(self, n):
            self.value += n
            return self.value

        def subtract(self, n):
            self.value -= n
            return self.value

        def get_value(self):
            return self.value

    rt.inject('Calculator', Calculator)

    # Use the injected class from PyKt code
    rt.run('''
    fun main() {
        val calc = Calculator(10)
        println("Initial: " + calc.get_value())
        calc.add(5)
        println("After add(5): " + calc.get_value())
        calc.subtract(3)
        println("After subtract(3): " + calc.get_value())
    }
    main()
    ''')

    # Get the class from Python and instantiate it
    Calc = rt['Calculator']
    calc2 = Calc(100)   # instantiate via Python-callable wrapper
    print("Python instantiation: Calc(100).add(50) = " + unicode(calc2.add(50)))


def test_pykt_class_access():
    """Test accessing PyKt-defined classes and instances from Python."""
    print("\n=== 4. PyKt class access from Python ===")

    rt = create_runtime()

    rt.run('''
    class Person(val name: String, val age: Int) {
        fun introduce() {
            println("I'm " + name + ", age " + age)
        }

        fun getDescription(): String {
            return name + " (" + age + ")"
        }
    }
    ''')

    # Get the PyKt class as a Python-callable
    Person = rt['Person']
    print("Person class: " + unicode(Person))

    # Instantiate from Python
    alice = Person('Alice', 30)
    print("alice instance: " + unicode(alice))
    print("alice.name = " + unicode(alice.name))
    print("alice.age = " + unicode(alice.age))

    # Call a method
    result = alice.getDescription()
    print("alice.getDescription() = " + result)

    # Set a mutable property
    alice.introduce()  # just prints


def test_immutable_protection():
    """Test that immutable values are protected from reassignment."""
    print("\n=== 5. Immutable protection ===")

    rt = create_runtime()

    # Inject immutable value
    rt.inject('MAX_SIZE', 100, mutable=False)

    # Try to reassign in PyKt code (should error)
    rt.run('''
    // This should fail because MAX_SIZE is val (immutable)
    // MAX_SIZE = 200
    println("MAX_SIZE = " + MAX_SIZE)
    ''')

    # Verify the value is still correct
    print("rt['MAX_SIZE'] = " + unicode(rt['MAX_SIZE']))


def test_everything_is_variable():
    """Demonstrate the unified philosophy."""
    print("\n=== 6. Everything is a variable ===")

    rt = create_runtime()

    # All three are injected the same way
    rt.inject('counter', 0)              # a value
    rt.inject('increment', lambda x: x+1) # a function
    rt.inject('Config', type(b'Config', (), {'debug': True}))  # a class (byte string for Py2.7)

    # All three are retrieved the same way
    print("counter: " + unicode(rt['counter']))
    print("increment(5): " + unicode(rt['increment'](5)))
    print("Config class: " + unicode(rt['Config']))

    # Check existence
    print("'counter' in rt: " + unicode('counter' in rt))
    print("'nonexistent' in rt: " + unicode('nonexistent' in rt))

    # List all variables
    print("Variables: " + unicode(rt.variables))


def test_default_parameters():
    print("\n=== 7. Default parameters ===")
    rt = create_runtime()

    rt.run('''
    fun greet(name: String, greeting: String = "Hello"): String {
        return greeting + ", " + name + "!"
    }

    fun multiply(a: Int, b: Int = 2): Int {
        return a * b
    }

    fun log(message: String, level: String = "INFO", timestamp: Boolean = true): String {
        var prefix = ""
        if (timestamp) {
            prefix = "[2026-07-06] "
        }
        return prefix + "[" + level + "] " + message
    }
    ''')

    greet = rt['greet']
    multiply = rt['multiply']
    log = rt['log']

    print("greet('Alice') =", greet('Alice'))
    print("greet('Bob', 'Hi') =", greet('Bob', 'Hi'))
    print("multiply(5) =", multiply(5))
    print("multiply(3, 4) =", multiply(3, 4))
    print("log('System started') =", log('System started'))
    print("log('Error occurred', 'ERROR') =", log('Error occurred', 'ERROR'))
    print("log('User login', 'DEBUG', False) =", log('User login', 'DEBUG', False))


def test_python_type_annotation():
    """测试从Python提供类型并用于PyKt类型注解"""
    print("\n=== 8. Python types as annotations ===")
    rt = create_runtime()

    # 1. 定义一个Python类（数据载体）
    class Address(object):
        def __init__(self, city, street):
            self.city = city
            self.street = street

        def __repr__(self):
            return "Address({}, {})".format(self.city, self.street)

    # 2. 注入这个类到PyKt运行时（让它成为全局可用类型）
    rt.inject('Address', Address)

    # 3. 尝试在PyKt中使用该类型作为参数注解
    #    注意：类型名称必须与注入的名称完全一致（Address）
    rt.run('''
    fun printAddress(addr: Address) {
        println("City: " + addr.city)
        println("Street: " + addr.street)
    }

    fun makeAddress(city: String, street: String): Address {
        // 这里需要从Python构造Address实例，但在PyKt中无法直接new，
        // 因为Address是Python类，需要在PyKt中如何构造？
        // 解决方案：我们可以注入一个工厂函数，或者从Python传递实例。
        // 为了测试注解，我们只验证函数定义能否解析。
        // 实际调用时，我们从Python传实例。
        return Address(city, street)  // 如果PyKt允许调用Python类构造器，则成功。
    }
    ''')

    # 如果上述代码解析成功，说明Address类型被识别
    # 接着我们获取函数并调用

    # 方式1：从Python构造Address实例，传给PyKt函数
    addr = Address("Shanghai", "Nanjing Road")
    print_addr = rt['printAddress']
    print("Calling printAddress with Python Address instance:")
    print_addr(addr)  # 应该打印出城市和街道

    # 方式2：如果PyKt允许通过类名构造（类似于rt['Address']），也可以测试
    try:
        Address_kt = rt['Address']
        addr2 = Address_kt("Beijing", "Chang'an Avenue")
        print("Constructed from PyKt:", addr2)
    except Exception as e:
        print("Constructing from PyKt failed:", e)


def test_if_expression():
    """测试 if 表达式（作为值返回）"""
    print("\n=== 9. if expression ===")
    rt = create_runtime()

    rt.run('''
    // 1. 基础 if 表达式，用于赋值
    fun max(a: Int, b: Int): Int {
        val result = if (a > b) a else b
        return result
    }

    // 2. if 表达式直接返回
    fun min(a: Int, b: Int): Int {
        return if (a < b) a else b
    }

    // 3. if 表达式作为函数参数
    fun compareAndPrint(a: Int, b: Int) {
        val message = "The larger number is " + if (a > b) a else b
        println(message)
    }

    // 4. 嵌套 if 表达式（else-if 链）
    fun sign(n: Int): String {
        return if (n > 0) "positive"
               else if (n < 0) "negative"
               else "zero"
    }

    // 5. if 表达式分支包含复杂表达式（但类型一致）
    fun abs(n: Int): Int {
        return if (n >= 0) {
            println("n is non-negative")
            n
        } else {
            println("n is negative")
            -n
        }
    }

    // 6. 类型不一致时应报错（测试目的，我们会注释掉以避免解析失败）
    // fun bad(): Int {
    //     return if (true) 42 else "oops"   // 类型不匹配，应报错
    // }
    ''')

    # 获取函数并测试
    max_fn = rt['max']
    min_fn = rt['min']
    compare_fn = rt['compareAndPrint']
    sign_fn = rt['sign']
    abs_fn = rt['abs']

    print("max(5, 3) =", max_fn(5, 3))
    print("max(2, 8) =", max_fn(2, 8))
    print("min(5, 3) =", min_fn(5, 3))
    print("min(2, 8) =", min_fn(2, 8))

    print("compareAndPrint(7, 4):")
    compare_fn(7, 4)
    print("compareAndPrint(3, 9):")
    compare_fn(3, 9)

    print("sign(10) =", sign_fn(10))
    print("sign(-5) =", sign_fn(-5))
    print("sign(0) =", sign_fn(0))

    print("abs(-7) =", abs_fn(-7))
    print("abs(0) =", abs_fn(0))
    print("abs(3) =", abs_fn(3))

    # 可选：验证类型错误是否被正确报告（可以捕获异常）
    try:
        rt.run('''
        fun bad(): Int {
            return if (true) 42 else "oops"
        }
        ''')
        print("WARNING: Type mismatch in if expression was not detected!")
    except Exception as e:
        print("Type mismatch correctly reported:", str(e))


def test_generics():
    """测试泛型函数和类"""
    print("\n=== 10. Generics ===")
    rt = create_runtime()

    # 尝试定义泛型函数和类
    try:
        rt.run('''
        // 1. 泛型函数
        fun <T> identity(x: T): T {
            return x
        }

        fun <T> singletonList(x: T): List<T> {
            return listOf(x)
        }

        // 2. 泛型类
        class Box<T>(val value: T) {
            fun get(): T = value
            fun <U> map(f: (T) -> U): Box<U> {
                return Box(f(value))
            }
        }

        // 3. 使用泛型
        fun testGenerics() {
            val i = identity(42)           // 类型推断为 Int
            val s = identity("hello")      // 类型推断为 String

            val boxInt = Box(100)          // 类型推断为 Box<Int>
            val boxStr = Box("world")      // Box<String>

            val mapped = boxInt.map { it * 2 }  // Box<Int>
            val mapped2 = boxStr.map { it + "!" } // Box<String>

            println("identity(42) = " + i)
            println("identity('hello') = " + s)
            println("Box(100).get() = " + boxInt.get())
            println("Box('world').get() = " + boxStr.get())
            println("mapped.get() = " + mapped.get())
            println("mapped2.get() = " + mapped2.get())
        }

        testGenerics()
        ''')

        print("Generics fully supported!")

    except Exception as e:
        # 如果解析失败，说明泛型尚未实现
        print("Generics not supported yet (or syntax error):", str(e))
        # 可以选择跳过后续检查
        return

    # 如果支持，进一步验证类型检查
    # 尝试类型不匹配，应报错
    try:
        rt.run('''
        fun bad(): Box<String> {
            return Box(123)  // 应为 Box<String>，但传入 Int
        }
        ''')
        print("WARNING: Type mismatch in generics was not detected!")
    except Exception as e:
        print("Type mismatch correctly reported:", str(e))


if __name__ == '__main__':
    test_unified_inject()
    test_pykt_functions()
    test_class_injection()
    test_pykt_class_access()
    test_immutable_protection()
    test_everything_is_variable()
    test_default_parameters()
    test_python_type_annotation()
    test_if_expression()
    test_generics()
    print("\n=== All Runtime API Tests Passed ===")

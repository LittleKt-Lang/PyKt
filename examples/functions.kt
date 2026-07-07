// Functions: definitions, parameters, recursion, closures
fun add(a, b) {
    return a + b
}

fun multiply(a, b) {
    return a * b
}

fun greet(name) {
    println("Hello, " + name + "!")
}

fun factorial(n) {
    if (n <= 1) {
        return 1
    }
    return n * factorial(n - 1)
}

// Function with default parameter would be nice but not supported yet
fun makeAdder(x) {
    // Return a function (closure)
    return fun(y) {
        return x + y
    }
}

fun main() {
    println("=== Basic Functions ===")
    val sum = add(3, 4)
    println("3 + 4 = " + sum)

    val product = multiply(6, 7)
    println("6 * 7 = " + product)

    greet("PyKt")

    println("=== Recursion ===")
    val fact5 = factorial(5)
    println("5! = " + fact5)

    println("=== Closures ===")
    val add5 = makeAdder(5)
    val result = add5(10)
    println("add5(10) = " + result)

    val add10 = makeAdder(10)
    println("add10(3) = " + add10(3))
    println("add10(7) = " + add10(7))
}

main()

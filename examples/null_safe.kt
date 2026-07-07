// Null-safe operators: ?. and ?:
class Person(val name) {
    fun greet() {
        println("Hello, I'm " + name)
    }
}

fun main() {
    println("=== Null-Safe Call ( ?. ) ===")

    val person = Person("Alice")
    val nullPerson = null

    // Safe call on non-null object
    person?.greet()

    // Safe call on null object (no error, no output)
    nullPerson?.greet()
    println("No crash after calling method on null!")

    // Safe property access
    println("Name via safe access: " + person?.name)
    val nullName = nullPerson?.name
    println("Null name is: " + nullName)

    println("=== Elvis Operator ( ?: ) ===")

    val a = null
    val b = a ?: "default value"
    println("null ?: default = " + b)

    val c = "actual value"
    val d = c ?: "fallback"
    println("'actual' ?: fallback = " + d)

    val x = null
    val y = x ?: 42
    println("null ?: 42 = " + y)
}

main()

// Variables: val and var
fun main() {
    // Immutable variable
    val name = "PyKt"
    println("Hello from " + name)

    // Mutable variable
    var count = 0
    count = count + 1
    count = count + 1
    println("Count: " + count)

    // Type annotation
    val age: Int = 25
    println("Age: " + age)

    // Double
    val pi = 3.14159
    println("Pi: " + pi)

    // Boolean
    val isGreat = true
    println("Is great: " + isGreat)

    // Null
    val nothing = null
    println("Null: " + nothing)

    // String template-like concatenation
    val greeting = "Hello, " + name + "!"
    println(greeting)

    // Compound assignment
    var x = 10
    x += 5
    println("x += 5 = " + x)
    x -= 3
    println("x -= 3 = " + x)
    x *= 2
    println("x *= 2 = " + x)
    x /= 4
    println("x /= 4 = " + x)
}

main()

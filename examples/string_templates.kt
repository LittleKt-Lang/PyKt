// String Templates: $var and ${expr}
fun main() {
    val name = "PyKt"
    val version = 2
    val items = [1, 2, 3]

    // Simple $variable interpolation
    println("Hello, $name!")

    // Expression interpolation with ${}
    println("Version: ${version}")
    println("Next version: ${version + 1}")

    // Multiple templates in one string
    println("$name version $version")

    // Complex expressions
    println("Array size: ${items.size}")
    println("Sum: ${1 + 2 + 3}")

    // Escaped dollar sign
    println("Price: \$99.99")

    // Mixed literal and expression
    println("Info: name=$name, ver=${version}")

    // Nested properties work
    val s = "hello"
    println("Length of '$s' is ${s.length}")
}

main()

// Multi-line raw strings (""") and $$ escaping
fun main() {
    println("=== Multi-line Raw Strings ===")

    val poem = """Roses are red,
Violets are blue,
This is a raw string
With multiple lines!"""

    println(poem)

    println("=== Raw string with templates ===")
    val name = "PyKt"
    val greeting = """Hello, $name!
Welcome to raw strings.
You can still use ${"$"}name templates."""

    println(greeting)

    println("=== $$$$ escaping ===")
    // $$ produces a literal dollar sign
    val price = """The price is $$99.99"""
    println(price)

    val dollars = "Cost: $$50"
    println(dollars)

    println("=== Expression templates in raw strings ===")
    val a = 10
    val b = 20
    val math = """Sum: ${a + b}
Product: ${a * b}"""

    println(math)

    println("=== All raw string tests passed ===")
}

main()

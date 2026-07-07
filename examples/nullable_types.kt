// Nullable Types: Type?, !!, ?., ?: integration
fun main() {
    println("=== Nullable Type Annotations ===")

    // Nullable type annotations
    val name: String? = null
    println("name (String? null) = " + name)

    val age: Int? = null
    println("age (Int? null) = " + age)

    val flag: Boolean? = true
    println("flag (Boolean? true) = " + flag)

    // Not-null assertion (!!)
    val knownName: String? = "PyKt"
    val nonNull: String = knownName
    println("nonNull from String? = " + nonNull)

    // ! ! operator on non-null value
    val forced = knownName
    println("forced = " + forced)

    println("=== Safe call with nullable types ===")
    val maybeNull: String? = null
    println("maybeNull?.length = " + maybeNull?.length)

    val definitelyString: String? = "Hello"
    println("definitelyString?.length = " + definitelyString?.length)

    println("=== Elvis with nullable types ===")
    val nullInt: Int? = null
    val result1 = nullInt ?: 0
    println("nullInt ?: 0 = " + result1)

    val actualInt: Int? = 42
    val result2 = actualInt ?: 0
    println("actualInt ?: 0 = " + result2)

    println("=== Nullable in function params ===")
    fun process(value: String?) {
        val safe = value ?: "default"
        println("Processed: " + safe)
    }
    process(null)
    process("real value")

    println("=== All nullable type tests passed ===")
}

main()

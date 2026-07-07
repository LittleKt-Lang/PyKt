// Try-Catch-Finally: exception handling with Throwable hierarchy
fun main() {
    println("=== Basic Try-Catch ===")
    try {
        println("In try block")
        throw Exception("Something went wrong!")
    } catch (e: Exception) {
        println("Caught: " + e)
    }
    println("After try-catch")

    println("=== Try-Catch with RuntimeException ===")
    try {
        throw RuntimeException("This is a runtime exception")
    } catch (e: RuntimeException) {
        println("Caught RuntimeException: " + e)
    }
    println("After second try-catch")

    println("=== Try-Catch-Finally ===")
    try {
        println("Try: doing work")
        throw Exception("Error!")
    } catch (e: Exception) {
        println("Catch: " + e)
    } finally {
        println("Finally: this always runs!")
    }

    println("=== Try-Finally (no catch) ===")
    try {
        println("In try block without catch")
    } finally {
        println("Finally runs even without error")
    }

    println("=== Nested try-catch ===")
    try {
        println("Outer try")
        try {
            println("Inner try")
            throw Exception("Inner error")
        } catch (e: Exception) {
            println("Inner catch: " + e)
        }
        println("After inner try")
    } catch (e: Exception) {
        println("Outer catch: " + e)
    }

    println("=== Try as expression (return value) ===")
    val result = try {
        val x = 10
        val y = 20
        x + y
    } catch (e: Exception) {
        0
    }
    println("Try result: " + result)

    println("=== Catch by Throwable (catches everything) ===")
    try {
        throw Error("A fatal error")
    } catch (e: Throwable) {
        println("Caught by Throwable: " + e)
    }

    println("=== Finally runs on return ===")
    try {
        println("About to return...")
        return
    } finally {
        println("Finally runs before return!")
    }
}

main()

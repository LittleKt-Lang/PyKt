// Exception system: Throwable hierarchy + bidirectional Python compatibility
fun testKotlinExceptions() {
    println("=== 1. Throw Exception with message ===")
    try {
        throw Exception("This is an exception message")
    } catch (e: Exception) {
        println("Caught Exception: " + e)
    }

    println("=== 2. Throw RuntimeException ===")
    try {
        throw RuntimeException("Runtime error occurred")
    } catch (e: RuntimeException) {
        println("Caught RuntimeException: " + e)
    }

    println("=== 3. Catch by Throwable (catches everything) ===")
    try {
        throw Error("Fatal error")
    } catch (e: Throwable) {
        println("Caught by Throwable: " + e)
    }

    println("=== 4. Multiple catch clauses (typed matching) ===")
    try {
        throw Exception("Test")
    } catch (e: RuntimeException) {
        println("Wrong: caught by RuntimeException")
    } catch (e: Exception) {
        println("Correct: caught by Exception")
    }

    println("=== 5. Try as expression with exception ===")
    val result = try {
        val a = 10
        throw Exception("Abort!")
        a + 1
    } catch (e: Exception) {
        999
    }
    println("Expression result: " + result)

    println("=== 6. Unqualified catch catches everything ===")
    try {
        throw RuntimeException("Oops")
    } catch (e) {
        println("Caught any: " + e)
    }
}

fun testPythonExceptionBridging() {
    // Python exceptions from injected functions will be tested
    // separately via the runtime API test
    println("Python exception bridge test: see runtime API test")
}

fun main() {
    testKotlinExceptions()
    testPythonExceptionBridging()
}

main()

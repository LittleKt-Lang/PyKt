// Control flow: if/else, when, for, while
fun main() {
    println("=== If/Else ===")
    val x = 10
    if (x > 5) {
        println("x is greater than 5")
    } else {
        println("x is not greater than 5")
    }

    if (x > 20) {
        println("x > 20")
    } else {
        println("x <= 20")
    }

    println("=== When ===")
    val color = "red"
    when (color) {
        "red" -> println("Color is red")
        "blue" -> println("Color is blue")
        else -> println("Unknown color")
    }

    when (color) {
        "green" -> println("It's green")
        "blue" -> println("It's blue")
        else -> println("Not green or blue")
    }

    // When without subject (like if-else chain)
    when {
        x > 100 -> println("x > 100")
        x > 5 -> println("x > 5 (matched in second branch)")
        else -> println("x is small")
    }

    println("=== For Loop ===")
    // Range iteration
    var sum = 0
    for (i in 1..5) {
        sum = sum + i
    }
    println("Sum of 1..5 = " + sum)

    // List iteration
    val items = [10, 20, 30]
    for (item in items) {
        println("Item: " + item)
    }

    println("=== While Loop ===")
    var count = 3
    while (count > 0) {
        println("Countdown: " + count)
        count = count - 1
    }

    println("=== Break and Continue ===")
    for (i in 1..10) {
        if (i > 5) {
            break
        }
        if (i == 3) {
            continue
        }
        println("i = " + i)
    }
}

main()

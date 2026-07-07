fun main() {
    print("请输入 n: ")
    val input = readLine()
    val n = input.toIntOrNull()
    if (n != null && n >= 0) {
        println("res: " + fibIterative(n))
    } else {
        println("请输入有效的非负整数")
    }
}

fun fibRecursive(n: Int): Long {
    if (n == 0) {
        return 0
    }
    if (n == 1) {
        return 1
    }
    return fibRecursive(n - 1) + fibRecursive(n - 2)
}

fun fibIterative(n: Int): Long {
    if (n == 0) {
        return 0
    }
    if (n == 1) {
        return 1
    }
    var prev = 0
    var curr = 1
    for (i in 2..n) {
        val next = prev + curr
        prev = curr
        curr = next
    }
    return curr
}

main()

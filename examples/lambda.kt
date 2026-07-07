fun main() {
    // 隐式 it 参数
    val square: (Int) -> Int = { it * it }
    println(square(4))

    // 结合集合 filter（使用隐式 it）
    val nums = listOf(1, 2, 3, 4)
    val even = nums.filter { it % 2 == 0 }
    println(even)
}

main()

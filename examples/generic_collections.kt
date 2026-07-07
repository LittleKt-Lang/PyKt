// 测试泛型集合（基于现有 API）
fun main() {
    // 列表（可变）
    val list: List<String> = listOf("apple", "banana", "cherry")
    println("list = " + list)
    println("list[1] = " + list[1])
    println("list.size = " + list.size)
    list.add("date")
    println("after add: " + list)
    list.removeAt(0)
    println("after removeAt(0): " + list)

    // 映射（可变）
    val map: Map<String, Int> = mapOf("one" to 1, "two" to 2, "three" to 3)
    println("map = " + map)
    println("map['two'] = " + map["two"])
    map.put("four", 4)
    println("after put: " + map)

    // 数组
    val arr: Array<Int> = arrayOf(10, 20, 30)
    println("arr = " + arr)
    println("arr[2] = " + arr[2])

    // 高阶函数：map, filter
    val lengths = list.map { it.length }
    println("lengths = " + lengths)
    val longWords = list.filter { it.length > 5 }
    println("longWords = " + longWords)

    // 类型推断
    val nums = listOf(1, 2, 3)
    println("nums = " + nums)

    // 空安全（List<String?>）
    val nullableList: List<String?> = listOf("a", null, "c")
    println("nullableList = " + nullableList)
    val nonNullLengths = nullableList.filterNotNull().map { it.length }
    println("nonNullLengths = " + nonNullLengths)

    // 泛型函数定义与调用
    fun firstElement(list: List<String>): String = list[0]
    println("first = " + firstElement(list))
}

main()

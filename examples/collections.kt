// Collections: Array, Map, List with built-in methods
fun main() {
    println("=== Arrays ===")
    val arr = arrayOf(10, 20, 30)
    println("Array: " + arr)
    println("Size: " + arr.size)
    println("Element at 1: " + arr.get(1))

    // Array of nulls
    val nulls = arrayOfNulls(3)
    println("Nulls array size: " + nulls.size)

    println("=== Maps ===")
    val map = mapOf("a" to 1, "b" to 2, "c" to 3)
    println("Map: " + map)
    println("Map size: " + map.size)
    println("Key 'b' value: " + map.get("b"))
    println("Contains 'a': " + map.containsKey("a"))
    println("Keys: " + map.keys)
    println("Values: " + map.values)
    map.put("d", 4)
    println("After put d=4, size: " + map.size)

    println("=== Map Index Access ===")
    println("map['c'] = " + map["c"])

    println("=== List with built-in methods ===")
    val list = listOf("apple", "banana", "cherry")
    println("List: " + list)
    println("Size: " + list.size)
    println("isEmpty: " + list.isEmpty)
    println("Contains 'banana': " + list.contains("banana"))
    println("IndexOf 'cherry': " + list.indexOf("cherry"))
    list.add("date")
    println("After add: " + list)
    println("removed: " + list.removeAt(0))
    println("After removeAt(0): " + list)

    println("=== String methods ===")
    val s = "  Hello World  "
    println("Original: '$s'")
    println("trim: '" + s.trim() + "'")
    println("toUpperCase: " + s.toUpperCase())
    println("toLowerCase: " + s.toLowerCase())
    println("length: " + s.length)
    println("substring(2, 7): '" + s.substring(2, 7) + "'")
    println("startsWith('  He'): " + s.startsWith("  He"))
    println("endsWith('ld  '): " + s.endsWith("ld  "))
    println("contains('World'): " + s.contains("World"))
    println("replace('World', 'PyKt'): '" + s.replace("World", "PyKt") + "'")

    println("=== String conversion ===")
    val numStr = "42"
    println("'42'.toIntOrNull() = " + numStr.toIntOrNull())
    val badStr = "not a number"
    println("'not a number'.toIntOrNull() = " + badStr.toIntOrNull())
    val piStr = "3.14"
    println("'3.14'.toDoubleOrNull() = " + piStr.toDoubleOrNull())

    println("=== Int method ===")
    val num = 255
    println("toString: " + num.toString)

    println("=== Map literal ===")
    val literalMap = ["x" to 100, "y" to 200]
    println("Literal map: " + literalMap)
    println("Size: " + literalMap.size)
}

main()

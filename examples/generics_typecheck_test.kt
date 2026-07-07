// ===== 泛型类定义 =====
class Box<T>(val value: T) {
    fun get(): T = value
    fun <U> map(f: (T) -> U): Box<U> = Box(f(value))
}

// ===== 正常情况：类型匹配 =====
fun testCorrect(): Box<String> {
    return Box("hello")   // 正确，Box<String>
}

// ===== 错误情况：返回类型不匹配 =====
// 期望报错：返回类型声明为 Box<String>，实际返回 Box<Int>
fun testWrong(): Box<String> {
    return Box(123)       // 此处应触发类型错误
}

// ===== 使用泛型函数，返回值类型推断 =====
fun <T> identity(x: T): T = x

fun testIdentity(): Int = identity(42) // 正确

fun testIdentityWrong(): String = identity(42) // 错误：期望 String，实际 Int

// ===== 调用测试函数以触发类型检查（若在调用时检查） =====
fun main() {
    val b1 = testCorrect()
    val b2 = testWrong()   // 如果之前未报错，这里会报错
    val i = testIdentity()
    val s = testIdentityWrong()
    println(b1.get())
    println(b2.get())
    println(i)
    println(s)
}

main()

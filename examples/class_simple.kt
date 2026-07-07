class Greeter(val msg) {
    fun say() {
        println(msg)
    }
}

fun main() {
    val g = Greeter("Hello from class!")
    g.say()
}

main()

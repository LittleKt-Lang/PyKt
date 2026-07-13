class Person(val name: String, val age: Int) {
    fun introduce(): Unit {
        println("Hi, I'm " + name + ", " + age + " years old")
    }
}

class Counter {
    var value: Int = 0

    init {
        println("Counter created!")
    }

    fun increment(): Unit {
        value = value + 1
    }
}

fun main(): Unit {
    val alice: Person = Person("Alice", 30)
    alice.introduce()

    val ctr: Counter = Counter()
    ctr.increment()
    ctr.increment()
    println("Counter: " + ctr.value)
    ctr.value = 114514
    println("Counter: " + ctr.value)
}

main()
// Classes: definition, constructor, methods, properties
class Person(val name: String, val age: Int) {
    fun introduce(): Unit {
        println("Hi, I'm " + this.name + " and I'm " + age + " years old.")
    }

    fun haveBirthday(): Unit {
        println("Happy birthday, " + name + "!")
    }
}

class Counter {
    init {
        println("Counter created!")
    }

    fun increment(x: Int): Int {
        return x + 1
    }

    fun decrement(x: Int): Int {
        return x - 1
    }
}

class Rectangle(val width: Int, val height: Int) {
    fun area(): Int {
        return width * height
    }

    fun perimeter(): Int {
        return 2 * (width + height)
    }
}

fun main() {
    println("=== Classes and Objects ===")

    val person = Person("Alice", 30)
    person.introduce()
    person.haveBirthday()

    println("=== Counter ===")
    val ctr = Counter()
    println("increment(5) = " + ctr.increment(5))
    println("decrement(10) = " + ctr.decrement(10))

    println("=== Rectangle ===")
    val rect = Rectangle(5, 3)
    println("Rectangle " + rect.width + "x" + rect.height)
    println("Area = " + rect.area())
    println("Perimeter = " + rect.perimeter())
}

main()

open class Animal(val species) {
    fun describe() {
        println("I am a " + species)
    }
}

class Dog(val name) : Animal("dog") {
    fun bark() {
        println(name + " barks!")
    }
}

fun main() {
    val dog = Dog("Buddy")
    dog.describe()
    dog.bark()
}

main()

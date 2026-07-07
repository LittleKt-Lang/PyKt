// Class Inheritance: open class, open fun, override, super
open class Animal(val species: String) {
    fun describe() {
        println("I am a " + species)
    }

    open fun sound() {
        println(species + " makes a sound")
    }
}

class Dog(val name) : Animal("dog") {
    override fun sound() {
        println(name + " barks!")
    }

    fun wagTail() {
        println(name + " wags tail happily")
    }
}

class Cat(val name) : Animal("cat") {
    override fun sound() {
        println(name + " meows!")
    }
}

// Inheriting from Throwable (demonstrates exception inheritance)
open class AppException(val code) : Exception("App error code " + code) {
    open fun getCode() {
        return code
    }
}

fun main() {
    println("=== Basic Inheritance ===")
    val dog = Dog("Buddy")
    dog.describe()
    dog.sound()
    dog.wagTail()

    val cat = Cat("Whiskers")
    cat.describe()
    cat.sound()

    println("=== Exception Inheritance ===")
    try {
        throw AppException(404)
    } catch (e: AppException) {
        println("Caught AppException: " + e)
        println("Code: " + e.getCode())
    } catch (e: Exception) {
        println("Fallback: " + e)
    }

    println("=== Inheritance with Method Chaining ===")
    // Dog inherits describe() from Animal
    // and overrides sound()
    val animal = Animal("generic")
    animal.sound()

    println("=== All inheritance tests passed ===")
}

main()

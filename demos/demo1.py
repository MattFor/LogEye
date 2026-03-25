from logeye import log, l


@log
def total(a, b):
	result = a + b
	result = result * 2
	result = result + 5
	return result


if __name__ == "__main__":
	answer = total(3, 4)

	x = "xyz" | l

	x = 10
	x = {"a": 1, "b": 2}
	x = "xyz"

	log("test is $x")

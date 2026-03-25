from logeye import log, l
from functools import lru_cache


#
# Here I just post whatever is fun to try, or to test new features!
#


# @log(mode="educational")
# def fib(n):
# 	if n <= 1:
# 		return n
# 	return fib(n - 1) + fib(n - 2)
#
#
# fib(5)

l("CACHE MODE")


@log(mode="educational", show_wrapper_locals=True)
@lru_cache(maxsize=None)
def fib(n):
	if n <= 1:
		return n
	return fib(n - 1) + fib(n - 2)


fib(5)

# log("FACTORIAL", show_file=False)


# @log(mode="edu")
# def factorial(n):
# 	if n == 1:
# 		return 1
# 	return n * factorial(n - 1)
#
#
# factorial(5)

# from logeye import log, l
#
# x = log(10)
# message = log("Hello from {name}", name="Matt")
#
#
# @log(level="call")
# def add(a, b):
# 	something = 2 + 2
# 	return a + b
#
#
# add(2, 2)
#
# name = "Matt"
# message2 = log("Hello from $name")
#
# config = log({"debug": True, "port": 8080})
# config.port = 9090
# config["debug"] = False
#
# obj = log({
# 	"x": 4,
# 	"y": {
# 		"z": 5
# 	}
# })
#
# obj.x = 4
# obj.y.z = 5
#
# a, b = log("x"), log("y")
#
# c = log("z")
#
# f = lambda: log("inside lambda")
# f()
#
# email = "mattfor@relaxy.xyz"
# log("\nCurrent user: $name\nEmail: $email")
#
# log("\nCurrent user: {}\nEmail: {}", "Matt", "mattfor@relaxy.xyz")
#
#
# @log
# class User:
# 	def __init__(self):
# 		self.name = "Matt"
# 		self.active = True
#
#
# user = l(User())
# user.name = "For"
#
# q = log(10)
# w = l(20)
# e = 30 | l
#
# r, t = log("hello"), log("world")
#
# f = (10 + 5) | l
# g = l(100 + 200)
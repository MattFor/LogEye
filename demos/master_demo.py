from logeye import (
	log,
	l,
	set_path_mode,
	toggle_logs,
	reset_output_formatter,
	set_output_formatter,
)

log("=== BASIC MESSAGES ===", show_time=False, show_file=False, show_lineno=False)

x = 5
log("value is {}", x)
log("value via template: $x")
log("file absolute: $apath")
log("file relative: $rpath")
log("file name: $fpath")

log("\n=== ASSIGNMENTS ===", show_time=False, show_file=False, show_lineno=False)

a = log(10)
b = l(20)
c = 30 | l

# tuple unpacking
d, e = log("hello"), log("world")

log("\n=== EXPRESSIONS ===", show_time=False, show_file=False, show_lineno=False)

f = (10 + 5) | l
g = l(100 + 200)

log("\n=== FUNCTIONS ===", show_time=False, show_file=False, show_lineno=False)


@log
def add(a, b):
	total = a + b
	total = total * 2
	return total


res = add(3, 4)

log("\n=== NESTED FUNCTIONS ===", show_time=False, show_file=False, show_lineno=False)


@log
def outer(x):
	def inner(y):
		z = y + 1
		return z

	return inner(x)


outer(10)

log("\n=== LAMBDAS ===", show_time=False, show_file=False, show_lineno=False)

f = lambda: log("lambda called")
f()

g = lambda v: v * 2
g = l(g)  # wrap lambda
g(5)

log("\n=== OBJECT TRACKING ===", show_time=False, show_file=False, show_lineno=False)

obj = log({"x": 1, "nested": {"y": 2}})

obj.x = 10
obj.nested.y = 20
obj["x"] = 30

log("\n=== CLASS TRACKING ===", show_time=False, show_file=False, show_lineno=False)


@log
class User:
	def __init__(self, name):
		self.name = name
		self.active = True


user = l(User("Matt"))
user.name = "For"
user.active = False

log("\n=== PATH MODES ===", show_time=False, show_file=False, show_lineno=False)

set_path_mode("absolute")
log("absolute path mode")

set_path_mode("project")
log("project path mode")

set_path_mode("file")
log("file path mode")

log("\n=== CUSTOM FORMATTER ===", show_time=False, show_file=False, show_lineno=False)


def simple_formatter(elapsed, kind, name, value, filename, lineno):
	return f"{kind.upper()} -> {name}: {value}"


set_output_formatter(simple_formatter)

x = log(123)
log("formatted message")

reset_output_formatter()

log("\n=== ENABLE / DISABLE ===", show_time=False, show_file=False, show_lineno=False)

log("this should appear")

toggle_logs(False)
log("this should NOT appear")

toggle_logs(True)
log("logging back on")

log("\n=== MIXED USAGE ===", show_time=False, show_file=False, show_lineno=False)

value = (5 | l) * (10 | l)
log("final value is $value")

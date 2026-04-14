from helpers import (
	count,
	capture,
	assert_has,
	assert_args,
	assert_values,
	assert_has_set,
	assert_not_has,
	assert_has_call,
	assert_set_order,
	assert_has_return,
	assert_line_order,
	assert_has_change,
	assert_nested_order,
	assert_no_call_noise,
	assert_no_return_noise,
	assert_no_internal_leaks,
)

from logeye import log


@log
def add(a, b):
	result = a + b
	return result


def test_logged_function(capsys):
	res = add(2, 3)
	out, ls = capture(capsys)

	assert res == 5

	assert_has_call(out, "add")
	assert_args(out, 2, 3)
	assert_has_return(out, "add", 5)

	# call + args(set) + result(set) + return
	assert count(ls, "(call)") == 1
	assert count(ls, "(return)") == 1

	# At least:
	# - a
	# - b
	# - result
	assert count(ls, "(set)") >= 3

	assert_line_order(ls, "(call)", "(return)")

	assert_no_call_noise(out)
	assert_no_return_noise(out)


def test_function_arguments_logged(capsys):
	@log
	def f(a, b):
		return a * b

	f(4, 5)
	out, ls = capture(capsys)

	assert_has_call(out, "f")
	assert_args(out, 4, 5)
	assert_has_return(out, "f", 20)

	assert count(ls, "(call)") == 1
	assert count(ls, "(return)") == 1

	assert_has_set(out, "a", 4)
	assert_has_set(out, "b", 5)


def test_return_value_logged(capsys):
	@log
	def f():
		return 123

	f()
	out, _ = capture(capsys)

	assert_has_return(out, "f", 123)


def test_multiple_calls_increment_ids(capsys):
	@log
	def f(x):
		return x

	f(1)
	f(2)

	out, ls = capture(capsys)

	assert count(ls, "(call)") == 2
	assert count(ls, "(return)") == 2

	assert_values(out, 1, 2)


def test_variable_reassignment(capsys):
	@log
	def f():
		x = 1
		x = 2
		x = 3
		return x

	f()
	out, ls = capture(capsys)

	assert_has_set(out, "x", 1)
	assert_has_change(out, "x", 2)
	assert_has_change(out, "x", 3)

	assert_set_order(ls, "x", 1, 2)
	assert_set_order(ls, "x", 2, 3)


def test_multiple_variables(capsys):
	@log
	def f():
		a = 1
		b = 2
		c = a + b
		return c

	f()
	out, ls = capture(capsys)

	assert_has_set(out, "a", 1)
	assert_has_set(out, "b", 2)
	assert_has_set(out, "c", 3)

	assert_nested_order(ls, "a", 1, "c", 3)
	assert_nested_order(ls, "b", 2, "c", 3)


def test_if_branch(capsys):
	@log
	def f(x):
		if x > 0:
			y = 1
		else:
			y = -1
		return y

	f(5)
	out, ls = capture(capsys)

	assert_has_set(out, "y", 1)
	assert_not_has(out, "-1")


def test_loop_tracking(capsys):
	@log
	def f():
		total = 0
		for i in range(3):
			total += i
		return total

	f()
	out, ls = capture(capsys)

	assert_has(out, "total")
	assert_has_return(out, "f", 3)

	# Ensure the total evolves (not just final)
	assert count(ls, "total") >= 2


def inner():
	return log("inner")


def outer():
	return inner()


def test_nested_calls(capsys):
	x = outer()
	out, _ = capture(capsys)

	assert x == "inner"
	assert_has(out, "inner")


def test_nested_function_call(capsys):
	@log
	def outer():
		def inner():
			return 7

		return inner()

	outer()
	out, _ = capture(capsys)

	assert_has(out, "inner")
	assert_has(out, "7")


def test_recursive_function(capsys):
	@log
	def fib(n):
		if n <= 1:
			return n
		return fib(n - 1) + fib(n - 2)

	fib(4)
	out, ls = capture(capsys)

	assert_has_call(out, "fib")
	assert_has_return(out)

	assert count(ls, "(call)") >= 5
	assert count(ls, "(return)") >= 5

	assert_values(out, 0, 1, 2, 3)


def test_exception_does_not_crash_logger(capsys):
	@log
	def f():
		x = 1
		raise ValueError("fail")

	try:
		f()
	except ValueError:
		pass

	out, ls = capture(capsys)

	assert_has_set(out, "x", 1)

	# Ensure logger didn't explode
	assert len(ls) >= 1


def test_call_return_pairing(capsys):
	@log
	def f():
		return 1

	f()
	out, ls = capture(capsys)

	assert count(ls, "(call)") == 1
	assert count(ls, "(return)") == 1

	assert_line_order(ls, "(call)", "(return)")


def test_no_duplicate_set(capsys):
	@log
	def f():
		x = 1
		x = 1
		return x

	f()
	out, ls = capture(capsys)

	assert any("(set)" in l and "x = 1" in l for l in ls)  # noqa: E741


def test_return_after_last_change(capsys):
	@log
	def f():
		x = 1
		x = 2
		return x

	f()
	out, ls = capture(capsys)

	assert_set_order(ls, "x", 1, 2)
	assert_line_order(ls, "x = 2", "(return)")


def test_kwargs_logging(capsys):
	@log
	def f(a, b=10):
		return a + b

	f(5, b=7)
	out, _ = capture(capsys)

	assert_has_set(out, "b", 7)
	assert_has(out, "kwargs={'b': 7}")
	assert_has_return(out, "f", 12)


def test_no_internal_leaks(capsys):
	@log
	def f():
		x = 1
		return x

	f()
	out, _ = capture(capsys)

	assert_no_internal_leaks(out)

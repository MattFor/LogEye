from logeye import log


# Outside of the test
@log
def add(a, b):
	result = a + b
	return result


def test_logged_function(capsys):
	res = add(2, 3)

	out = capsys.readouterr().out
	assert "call" in out
	assert "return" in out
	assert res == 5


# Inside of the test
def test_function_arguments_logged(capsys):
	@log
	def f(a, b):
		return a * b

	f(4, 5)

	out = capsys.readouterr().out
	assert "4" in out and "5" in out


def test_return_value_logged(capsys):
	@log
	def f():
		return 123

	f()

	out = capsys.readouterr().out
	assert "123" in out


def test_multiple_calls_increment_ids(capsys):
	@log
	def f(x):
		return x

	f(1)
	f(2)

	out = capsys.readouterr().out
	assert "f#2" in out or out.count("call") >= 2


def test_variable_reassignment(capsys):
	@log
	def f():
		x = 1
		x = 2
		x = 3
		return x

	f()

	out = capsys.readouterr().out
	assert "x = 1" in out
	assert "x = 2" in out
	assert "x = 3" in out


def test_multiple_variables(capsys):
	@log
	def f():
		a = 1
		b = 2
		c = a + b
		return c

	f()

	out = capsys.readouterr().out
	assert "a = 1" in out
	assert "b = 2" in out
	assert "c = 3" in out


def test_if_branch(capsys):
	@log
	def f(x):
		if x > 0:
			y = 1
		else:
			y = -1
		return y

	f(5)

	out = capsys.readouterr().out
	assert "y = 1" in out


def test_loop_tracking(capsys):
	@log
	def f():
		total = 0
		for i in range(3):
			total += i
		return total

	f()

	out = capsys.readouterr().out
	assert "total" in out


# Outside
def inner():
	return log("inner")


def outer():
	return inner()


def test_nested_calls(capsys):
	x = outer()

	out = capsys.readouterr().out

	assert "inner" in out
	assert x == "inner"


# Inside
def test_nested_function_call(capsys):
	@log
	def outer():
		def inner():
			return 7

		return inner()

	outer()

	out = capsys.readouterr().out
	assert "inner" in out


def test_recursive_function(capsys):
	@log
	def fib(n):
		if n <= 1:
			return n
		return fib(n - 1) + fib(n - 2)

	fib(4)

	out = capsys.readouterr().out
	assert "fib" in out
	assert "return" in out


def test_exception_does_not_crash_logger(capsys):
	@log
	def f():
		x = 1
		raise ValueError("fail")

	try:
		f()
	except ValueError:
		pass

	out = capsys.readouterr().out
	assert "x = 1" in out

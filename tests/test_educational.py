import re
import pytest
from logeye import log, set_mode


@pytest.fixture
def out(capsys):
	def _get():
		raw = capsys.readouterr().out
		return "\n".join(
			re.sub(r'(?:\btest_[a-zA-Z0-9_]*\.)+', '', line)
			for line in raw.splitlines()
		)

	return _get


def test_call_formatting(out):
	@log(mode="edu")
	def foo(x):
		return x

	foo(5)

	out = out()

	assert "Calling foo(5)" in out
	assert "(call)" not in out
	assert "test_" not in out


def test_return_formatting(out):
	@log(mode="edu")
	def foo():
		return 123

	foo()

	out = out()

	assert "foo() returned 123" in out
	assert "(return)" not in out


def test_args_and_kwargs(out):
	@log(mode="edu")
	def foo(a, b=2):
		return a + b

	foo(1, b=3)

	out = out()

	assert "Calling foo(1, b=3)" in out


def test_no_kwargs_noise(out):
	@log(mode="edu")
	def foo(x):
		return x

	foo(10)

	out = out()

	assert "{}" not in out
	assert "kwargs" not in out


def test_nested_function_name(out):
	@log(mode="edu")
	def outer():
		def inner():
			return 5

		return inner()

	outer()

	out = out()

	assert "Calling outer.inner()" in out


def test_append_human_readable(out):
	@log(mode="edu")
	def foo():
		arr = []
		arr.append(5)

	foo()

	out = out()

	assert "Added 5 to the end of arr" in out


def test_extend_single_value(out):
	@log(mode="edu")
	def foo():
		arr = []
		arr.extend([7])

	foo()

	out = out()

	assert "Added 7 to arr" in out


def test_extend_multiple_values(out):
	@log(mode="edu")
	def foo():
		arr = []
		arr.extend([1, 2, 3])

	foo()

	out = out()

	assert "Added [1, 2, 3] to arr" in out


def test_no_set_prefix(out):
	@log(mode="edu")
	def foo():
		x = 10
		return x

	foo()

	out = out()

	assert "(set)" not in out


def test_variable_visible(out):
	@log(mode="edu")
	def foo():
		x = 42
		return x

	foo()

	out = out()

	assert "x = 42" in out or "foo.x = 42" in out


def test_log_inside_function_inherits_mode(out):
	@log(mode="edu")
	def foo():
		x = 5
		log("Value is $x")

	foo()

	out = out()

	assert "Value is 5" in out
	assert "test_" not in out


def test_no_file_info(out):
	@log(mode="edu")
	def foo():
		x = 1

	foo()

	out = out()

	assert ".py:" not in out


def test_time_present(out):
	@log(mode="edu")
	def foo():
		pass

	foo()

	out = out()

	assert "[" in out and "s]" in out


def test_algorithm_like_flow(out):
	@log(mode="edu")
	def simple():
		arr = []
		arr.append(3)
		arr.append(1)
		arr.extend([2])

		log("Final: $arr")

		return arr

	simple()

	out = out()

	assert "Added 3 to the end of arr" in out
	assert "Added 1 to the end of arr" in out
	assert "Added 2 to arr" in out
	assert "Final: [3, 1, 2]" in out


def test_global_mode_full(out):
	set_mode("full")

	try:

		@log
		def foo():
			return 1

		foo()

		out = out()

		assert "(call)" in out
		assert "Calling" not in out
	finally:
		set_mode("full")


def test_global_mode_edu(out):
	set_mode("edu")

	try:

		@log
		def foo():
			return 1

		foo()

		out = out()

		assert "Calling foo()" in out
		assert "(call)" not in out
	finally:
		set_mode("full")


def test_mode_toggle_mid_execution(out):
	set_mode("full")

	try:

		@log
		def foo():
			a = 1  # full mode
			set_mode("edu")
			b = 2  # edu mode
			set_mode("full")
			c = 3  # back to full

		foo()

		out = out()

		assert "(set)" in out or "foo.a" in out
		assert "(set)" in out or "foo.c" in out
		assert "b = 2" in out

	finally:
		set_mode("full")


def test_default_arg_emitted_once(out):
	@log(mode="edu")
	def outer():
		def inner(x=10):
			x = 20
			return x

		return inner()

	outer()
	out = out()

	assert "Defined outer.inner(x=10)" in out
	assert "x = 10" in out
	assert "x = 20" in out


def test_nested_function_locals_are_tracked(out):
	@log(mode="edu")
	def outer():
		def inner(var="test"):
			var = 42
			return 5

		return inner()

	outer()
	out = out()

	assert "var = 'test'" in out
	assert "var = 42" in out

	assert "Calling outer.inner()" in out
	assert "Defined outer.inner(var='test')" in out
	assert "Defined outer.inner()" not in out

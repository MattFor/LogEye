import pytest

from helpers import capture, assert_has, assert_args, assert_return_value

from logeye import log
from functools import lru_cache, wraps


@log
def add(a, b):
	result = a + b
	return result


def simple_wrapper(func):
	@wraps(func)
	def inner(*args, **kwargs):
		return func(*args, **kwargs)

	return inner


def test_log_with_single_wrapper(capsys):
	@log
	@simple_wrapper
	def f(x):
		return x + 1

	f(5)

	out, ls = capture(capsys)

	assert_has(out, "(call)")
	assert_has(out, "(return)")

	assert_has(out, "f")
	assert_args(out, 5)
	assert_return_value(out, 6)


def test_log_inside_wrapper(capsys):
	@simple_wrapper
	@log
	def f(x):
		return x * 2

	f(3)

	out, ls = capture(capsys)

	assert_has(out, "(call)")
	assert_has(out, "(return)")


def test_multiple_wrappers(capsys):
	def wrapper_a(func):
		@wraps(func)
		def inner(*args, **kwargs):
			return func(*args, **kwargs)

		return inner

	def wrapper_b(func):
		@wraps(func)
		def inner(*args, **kwargs):
			return func(*args, **kwargs)

		return inner

	@log
	@wrapper_a
	@wrapper_b
	def f(x):
		y = x + 1
		return y

	f(10)

	out, ls = capture(capsys)

	assert_has(out, "(call)")
	assert_has(out, "(return)")
	assert_has(out, "y = 11")


def test_nested_inside_wrapped_function(capsys):
	@log
	@simple_wrapper
	def outer():
		def inner():
			return 42

		return inner()

	outer()

	out, ls = capture(capsys)

	assert_has(out, "inner")  # call should be visible


def test_recursive_with_wrapper(capsys):
	@log
	@simple_wrapper
	def fib(n):
		if n <= 1:
			return n
		return fib(n - 1) + fib(n - 2)

	fib(4)

	out, ls = capture(capsys)

	assert_has(out, "(call)")
	assert_has(out, "(return)")
	assert_has(out, "fib")


@pytest.mark.xfail(
	reason="C decorators like lru_cache are not traceable via sys.settrace - TODO"
)
def test_lru_cache_not_traced(capsys):
	@log(show_wrapper_locals=True)
	@lru_cache(maxsize=None)
	def fib(n):
		if n <= 1:
			return n
		return fib(n - 1) + fib(n - 2)

	fib(5)

	out, ls = capture(capsys)

	# What we WANT (but currently can't get :( )
	assert "inner" in out or "fib(" in out

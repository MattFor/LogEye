from logeye import log
from functools import lru_cache, wraps
import pytest


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

	out = capsys.readouterr().out

	assert "call" in out
	assert "return" in out
	assert "f(5)" in out or "f#1(5)" in out


def test_log_inside_wrapper(capsys):
	@simple_wrapper
	@log
	def f(x):
		return x * 2

	f(3)

	out = capsys.readouterr().out

	assert "call" in out
	assert "return" in out


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

	out = capsys.readouterr().out

	assert "call" in out
	assert "return" in out
	assert "y = 11" in out


def test_nested_inside_wrapped_function(capsys):
	@log
	@simple_wrapper
	def outer():
		def inner():
			return 42

		return inner()

	outer()

	out = capsys.readouterr().out

	assert "inner" in out  # call should be visible


def test_recursive_with_wrapper(capsys):
	@log
	@simple_wrapper
	def fib(n):
		if n <= 1:
			return n
		return fib(n - 1) + fib(n - 2)

	fib(4)

	out = capsys.readouterr().out

	assert "call" in out
	assert "return" in out
	assert "fib" in out


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

	out = capsys.readouterr().out

	# What we WANT (but currently can't get :( )
	assert "inner" in out or "fib(" in out

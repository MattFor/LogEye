from helpers import (
	capture,
	assert_has,
	assert_not_has,
	assert_line_count,
	assert_line_contains,
	assert_no_internal_leaks,
)
from logeye import log, set_mode


def test_call_formatting(capsys):
	@log(mode="edu")
	def foo(x):
		return x

	result = foo(5)
	out, ls = capture(capsys)

	assert result == 5
	assert_has(out, "Calling foo(5)")
	assert_not_has(out, "(call)")
	assert_not_has(out, "test_")
	assert_no_internal_leaks(out)

	assert_line_count(ls, 3)
	assert_line_contains(ls, "Calling foo(5)")
	assert_line_contains(ls, "Defined foo.x = 5")
	assert_line_contains(ls, "returned 5")


def test_return_formatting(capsys):
	@log(mode="edu")
	def foo():
		return 123

	result = foo()
	out, ls = capture(capsys)

	assert result == 123
	assert_has(out, "foo() returned 123")
	assert_not_has(out, "(return)")
	assert_no_internal_leaks(out)

	assert_line_count(ls, 2)
	assert_line_contains(ls, "Calling foo()")
	assert_line_contains(ls, "returned 123")


def test_args_and_kwargs(capsys):
	@log(mode="edu")
	def foo(a, b=2):
		return a + b

	result = foo(1, b=3)
	out, ls = capture(capsys)

	assert result == 4
	assert_has(out, "Calling foo(1, b=3)")
	assert_not_has(out, "kwargs")
	assert_no_internal_leaks(out)


def test_no_kwargs_noise(capsys):
	@log(mode="edu")
	def foo(x):
		return x

	result = foo(10)
	out, ls = capture(capsys)

	assert result == 10
	assert_not_has(out, "{}")
	assert_not_has(out, "kwargs")
	assert_no_internal_leaks(out)


def test_nested_function_name(capsys):
	@log(mode="edu")
	def outer():
		def inner():
			return 5

		return inner()

	result = outer()
	out, ls = capture(capsys)

	assert result == 5
	assert_has(out, "Calling outer.inner()")
	assert_no_internal_leaks(out)


def test_append_human_readable(capsys):
	@log(mode="edu")
	def foo():
		arr = []
		arr.append(5)
		return arr

	result = foo()
	out, ls = capture(capsys)

	assert result == [5]
	assert_has(out, "Added 5 to the end of arr")
	assert_no_internal_leaks(out)


def test_extend_single_value(capsys):
	@log(mode="edu")
	def foo():
		arr = []
		arr.extend([7])
		return arr

	result = foo()
	out, ls = capture(capsys)

	assert result == [7]
	assert_has(out, "Added 7 to arr")
	assert_no_internal_leaks(out)


def test_extend_multiple_values(capsys):
	@log(mode="edu")
	def foo():
		arr = []
		arr.extend([1, 2, 3])
		return arr

	result = foo()
	out, ls = capture(capsys)

	assert result == [1, 2, 3]
	assert_has(out, "Added [1, 2, 3] to arr")
	assert_no_internal_leaks(out)


def test_no_set_prefix(capsys):
	@log(mode="edu")
	def foo():
		x = 10
		return x

	result = foo()
	out, ls = capture(capsys)

	assert result == 10
	assert_not_has(out, "(set)")
	assert "Defined foo = 10" in out or "x = 10" in out or "foo.x = 10" in out, (
		f"Expected variable assignment in:\n{out}"
	)
	assert_no_internal_leaks(out)


def test_variable_visible(capsys):
	@log(mode="edu")
	def foo():
		x = 42
		return x

	result = foo()
	out, ls = capture(capsys)

	assert result == 42
	assert_has(out, "x = 42")
	assert_no_internal_leaks(out)


def test_log_inside_function_inherits_mode(capsys):
	@log(mode="edu")
	def foo():
		x = 5
		log("Value is $x")
		return x

	result = foo()
	out, ls = capture(capsys)

	assert result == 5
	assert_has(out, "Value is 5")
	assert_not_has(out, "test_")
	assert_no_internal_leaks(out)


def test_no_file_info(capsys):
	@log(mode="edu")
	def foo():
		x = 1
		return x

	result = foo()
	out, ls = capture(capsys)

	assert result == 1
	assert_not_has(out, ".py:")
	assert_no_internal_leaks(out)


def test_time_present(capsys):
	@log(mode="edu")
	def foo():
		pass

	foo()
	out, ls = capture(capsys)

	assert "[" in out and "s]" in out
	assert_no_internal_leaks(out)


def test_algorithm_like_flow(capsys):
	@log(mode="edu")
	def simple():
		arr = []
		arr.append(3)
		arr.append(1)
		arr.extend([2])
		log("Final: $arr")
		return arr

	result = simple()
	out, ls = capture(capsys)

	assert result == [3, 1, 2]
	assert_has(out, "Added 3 to the end of arr")
	assert_has(out, "Added 1 to the end of arr")
	assert_has(out, "Added 2 to arr")
	assert_has(out, "Final: [3, 1, 2]")
	assert_no_internal_leaks(out)


def test_global_mode_full(capsys):
	set_mode("full")
	try:

		@log
		def foo():
			return 1

		result = foo()
		out, ls = capture(capsys)

		assert result == 1
		assert_has(out, "(call)")
		assert_not_has(out, "Calling")
		assert_no_internal_leaks(out)
	finally:
		set_mode("full")


def test_global_mode_edu(capsys):
	set_mode("edu")
	try:

		@log
		def foo():
			return 1

		result = foo()
		out, ls = capture(capsys)

		assert result == 1
		assert_has(out, "Calling foo()")
		assert_not_has(out, "(call)")
		assert_no_internal_leaks(out)
	finally:
		set_mode("full")


def test_mode_toggle_mid_execution(capsys):
	set_mode("full")
	try:

		@log
		def foo():
			a = 1  # full mode
			set_mode("edu")
			b = 2  # edu mode
			set_mode("full")
			c = 3  # back to full
			return a + b + c

		result = foo()
		out, ls = capture(capsys)

		assert result == 6
		assert_has(out, "(set)")
		assert_has(out, "b = 2")
		assert_has(out, "c = 3")
		assert_no_internal_leaks(out)
	finally:
		set_mode("full")


def test_default_arg_emitted_once(capsys):
	@log(mode="edu")
	def outer():
		def inner(x=10):
			x = 20
			return x

		return inner()

	result = outer()
	out, ls = capture(capsys)

	assert result == 20
	assert_has(out, "Defined outer.inner(x=10)")
	assert_has(out, "x = 10")
	assert_has(out, "x = 20")
	assert_no_internal_leaks(out)


def test_nested_function_locals_are_tracked(capsys):
	@log(mode="edu")
	def outer():
		def inner(var="test"):
			var = 42
			return 5

		return inner()

	result = outer()
	out, ls = capture(capsys)

	assert result == 5
	assert_has(out, "var = 'test'")
	assert_has(out, "var = 42")
	assert_has(out, "Calling outer.inner()")
	assert_has(out, "Defined outer.inner(var='test')")
	assert_not_has(out, "Defined outer.inner()")
	assert_no_internal_leaks(out)

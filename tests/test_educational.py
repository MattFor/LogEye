from helpers import assert_has, assert_not_has, assert_no_internal_leaks
from logeye import log, set_mode


def test_call_formatting(out):
	@log(mode="edu")
	def foo(x):
		return x

	result = foo(5)
	text = out()

	assert result == 5
	assert_has(text, "Calling foo(5)")
	assert_not_has(text, "(call)")
	assert_not_has(text, "test_")
	assert_no_internal_leaks(text)

	ls = lines_from_text(text)

	assert len(ls) == 3
	assert "Calling foo(5)" in ls[0]
	assert "Defined foo.x = 5" in ls[1]
	assert "returned 5" in ls[2]


def test_return_formatting(out):
	@log(mode="edu")
	def foo():
		return 123

	result = foo()
	text = out()

	assert result == 123
	assert_has(text, "foo() returned 123")
	assert_not_has(text, "(return)")
	assert_no_internal_leaks(text)

	ls = lines_from_text(text)

	assert len(ls) == 2
	assert "Calling foo()" in ls[0]
	assert "returned 123" in ls[1]


def test_args_and_kwargs(out):
	@log(mode="edu")
	def foo(a, b=2):
		return a + b

	result = foo(1, b=3)
	text = out()

	assert result == 4
	assert_has(text, "Calling foo(1, b=3)")
	assert_not_has(text, "kwargs")
	assert_no_internal_leaks(text)


def test_no_kwargs_noise(out):
	@log(mode="edu")
	def foo(x):
		return x

	result = foo(10)
	text = out()

	assert result == 10
	assert_not_has(text, "{}")
	assert_not_has(text, "kwargs")
	assert_no_internal_leaks(text)


def test_nested_function_name(out):
	@log(mode="edu")
	def outer():
		def inner():
			return 5

		return inner()

	result = outer()
	text = out()

	assert result == 5
	assert_has(text, "Calling outer.inner()")
	assert_no_internal_leaks(text)


def test_append_human_readable(out):
	@log(mode="edu")
	def foo():
		arr = []
		arr.append(5)
		return arr

	result = foo()
	text = out()

	assert result == [5]
	assert_has(text, "Added 5 to the end of arr")
	assert_no_internal_leaks(text)


def test_extend_single_value(out):
	@log(mode="edu")
	def foo():
		arr = []
		arr.extend([7])
		return arr

	result = foo()
	text = out()

	assert result == [7]
	assert_has(text, "Added 7 to arr")
	assert_no_internal_leaks(text)


def test_extend_multiple_values(out):
	@log(mode="edu")
	def foo():
		arr = []
		arr.extend([1, 2, 3])
		return arr

	result = foo()
	text = out()

	assert result == [1, 2, 3]
	assert_has(text, "Added [1, 2, 3] to arr")
	assert_no_internal_leaks(text)


def test_no_set_prefix(out):
	@log(mode="edu")
	def foo():
		x = 10
		return x

	result = foo()
	text = out()

	assert result == 10
	assert_not_has(text, "(set)")
	assert "Defined foo = 10" in text or "x = 10" in text or "foo.x = 10" in text, (
		f"Expected variable assignment in:\n{text}"
	)
	assert_no_internal_leaks(text)


def test_variable_visible(out):
	@log(mode="edu")
	def foo():
		x = 42
		return x

	result = foo()
	text = out()

	assert result == 42
	assert_has(text, "x = 42")
	assert_no_internal_leaks(text)


def test_log_inside_function_inherits_mode(out):
	@log(mode="edu")
	def foo():
		x = 5
		log("Value is $x")
		return x

	result = foo()
	text = out()

	assert result == 5
	assert_has(text, "Value is 5")
	assert_not_has(text, "test_")
	assert_no_internal_leaks(text)


def test_no_file_info(out):
	@log(mode="edu")
	def foo():
		x = 1
		return x

	result = foo()
	text = out()

	assert result == 1
	assert_not_has(text, ".py:")
	assert_no_internal_leaks(text)


def test_time_present(out):
	@log(mode="edu")
	def foo():
		pass

	foo()
	text = out()

	assert "[" in text and "s]" in text
	assert_no_internal_leaks(text)


def test_algorithm_like_flow(out):
	@log(mode="edu")
	def simple():
		arr = []
		arr.append(3)
		arr.append(1)
		arr.extend([2])
		log("Final: $arr")
		return arr

	result = simple()
	text = out()

	assert result == [3, 1, 2]
	assert_has(text, "Added 3 to the end of arr")
	assert_has(text, "Added 1 to the end of arr")
	assert_has(text, "Added 2 to arr")
	assert_has(text, "Final: [3, 1, 2]")
	assert_no_internal_leaks(text)


def test_global_mode_full(out):
	set_mode("full")
	try:

		@log
		def foo():
			return 1

		result = foo()
		text = out()

		assert result == 1
		assert_has(text, "(call)")
		assert_not_has(text, "Calling")
		assert_no_internal_leaks(text)
	finally:
		set_mode("full")


def test_global_mode_edu(out):
	set_mode("edu")
	try:

		@log
		def foo():
			return 1

		result = foo()
		text = out()

		assert result == 1
		assert_has(text, "Calling foo()")
		assert_not_has(text, "(call)")
		assert_no_internal_leaks(text)
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
			return a + b + c

		result = foo()
		text = out()

		assert result == 6
		assert_has(text, "(set)")
		assert_has(text, "b = 2")
		assert_has(text, "c = 3")
		assert_no_internal_leaks(text)
	finally:
		set_mode("full")


def test_default_arg_emitted_once(out):
	@log(mode="edu")
	def outer():
		def inner(x=10):
			x = 20
			return x

		return inner()

	result = outer()
	text = out()

	assert result == 20
	assert_has(text, "Defined outer.inner(x=10)")
	assert_has(text, "x = 10")
	assert_has(text, "x = 20")
	assert_no_internal_leaks(text)


def test_nested_function_locals_are_tracked(out):
	@log(mode="edu")
	def outer():
		def inner(var="test"):
			var = 42
			return 5

		return inner()

	result = outer()
	text = out()

	assert result == 5
	assert_has(text, "var = 'test'")
	assert_has(text, "var = 42")
	assert_has(text, "Calling outer.inner()")
	assert_has(text, "Defined outer.inner(var='test')")
	assert_not_has(text, "Defined outer.inner()")
	assert_no_internal_leaks(text)


def lines_from_text(text):
	return [line.strip() for line in text.splitlines() if line.strip()]

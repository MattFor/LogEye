import pytest

from helpers import (
	count,
	capture,
	assert_has,
	assert_values,
	assert_has_set,
	assert_not_has,
	assert_line_order,
	assert_line_count,
	assert_line_contains,
	assert_no_internal_leaks,
)

from logeye import log, set_path_mode


def test_inline_expression(capsys):
	x = "a" + log("b")

	raw, ls = capture(capsys)

	assert x == "ab"
	assert_has(raw, "b")
	assert_not_has(raw, "ab")
	assert_line_count(ls, 1)


def test_nested_inline_expression(capsys):
	x = log("a") + log("b") + log("c")

	raw, ls = capture(capsys)

	assert x == "abc"
	assert_values(raw, "a", "b", "c")
	assert_line_count(ls, 3)
	assert_line_contains(ls, "a")
	assert_line_contains(ls, "b")
	assert_line_contains(ls, "c")


def test_expression_order(capsys):
	x = log("a") + "b"

	raw, ls = capture(capsys)

	assert x == "ab"
	assert_has(raw, "a")
	assert_line_count(ls, 1)
	assert_line_contains(ls, "a")


def test_tuple_unpacking(capsys):
	a, b = log("x"), log("y")

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)
	assert_has_set(raw, "a", "x")
	assert_has_set(raw, "b", "y")
	assert_line_order(ls, "a = 'x'", "b = 'y'")


@pytest.mark.xfail(reason="Nested unpacking not fully supported yet", strict=False)
def test_nested_unpacking(capsys):
	(a, (b, c)) = log("x"), (log("y"), log("z"))

	raw, ls = capture(capsys)

	assert_line_contains(ls, "a")
	assert_line_contains(ls, "b")
	assert_line_contains(ls, "c")
	assert_has(raw, "x")
	assert_has(raw, "y")
	assert_has(raw, "z")


def test_reassignment_same_line(capsys):
	# fmt: off
	# @formatter:off
	x = log("a"); x = log("b")  # noqa: E702, E703
	# @formatter:on
	# fmt: on

	raw, ls = capture(capsys)

	assert_has(raw, "a")
	assert_has(raw, "b")
	assert_line_count(ls, 2)
	assert_line_order(ls, "x = 'a'", "x = 'b'")


def test_inline_expression_error():
	with pytest.raises(TypeError):
		1 + log("a")


def test_invalid_path_mode():
	with pytest.raises(ValueError):
		set_path_mode("invalid")


def test_if_branch_logging(capsys):
	if True:
		x = log("yes")

	raw, ls = capture(capsys)

	assert_has(raw, "yes")
	assert_line_count(ls, 1)
	assert_has_set(raw, "x", "yes")


def test_if_else_branch(capsys):
	if False:
		log("no")
	else:
		log("yes")

	raw, ls = capture(capsys)

	assert_has(raw, "yes")
	assert_not_has(raw, "no")
	assert_line_count(ls, 1)


def test_loop_logging(capsys):
	for _ in range(3):
		log("loop")

	raw, ls = capture(capsys)

	assert count(ls, "loop") == 3
	assert_line_count(ls, 3)


def test_loop_variable_assignment(capsys):
	for i in range(2):
		x = log(i)

	raw, ls = capture(capsys)

	assert_has(raw, "0")
	assert_has(raw, "1")
	assert_line_count(ls, 2)
	assert_line_order(ls, "0", "1")


def test_inside_function(capsys):
	def f():
		x = log("inner")

	f()

	raw, ls = capture(capsys)

	assert_has(raw, "inner")
	assert_line_count(ls, 1)
	assert_has_set(raw, "x", "inner")


def test_nested_functions(capsys):
	def outer():
		def inner():
			return log("deep")

		return inner()

	outer()

	raw, ls = capture(capsys)

	assert_has(raw, "deep")
	assert_line_count(ls, 1)


def test_lambda_usage(capsys):
	f = lambda: log("lambda")
	f()

	raw, ls = capture(capsys)

	assert_has(raw, "lambda")
	assert_line_count(ls, 1)


def test_multiple_calls_same_var(capsys):
	x = log("a")
	x = log("b")
	x = log("c")

	raw, ls = capture(capsys)

	assert_has(raw, "a")
	assert_has(raw, "b")
	assert_has(raw, "c")
	assert_line_count(ls, 3)
	assert_line_order(ls, "a", "b")
	assert_line_order(ls, "b", "c")


def test_reuse_variable_name(capsys):
	x = log("a")

	def f():
		x = log("b")
		return x

	f()

	raw, ls = capture(capsys)

	assert_has(raw, "a")
	assert_has(raw, "b")
	assert_line_count(ls, 2)


def test_log_none(capsys):
	x = log(None)

	raw, ls = capture(capsys)

	assert x is None
	assert_has(raw, "None")
	assert_line_count(ls, 1)


def test_log_bool(capsys):
	x = log(True)

	raw, ls = capture(capsys)

	assert x is True
	assert_has(raw, "True")
	assert_line_count(ls, 1)


def test_log_large_number(capsys):
	x = log(10**10)

	raw, ls = capture(capsys)

	assert x == 10**10
	assert_has(raw, "10000000000")
	assert_line_count(ls, 1)


def test_empty_string(capsys):
	log("")

	raw, ls = capture(capsys)

	assert raw.strip() != ""
	assert_line_count(ls, 1)


def test_whitespace_string(capsys):
	log("   ")

	raw, ls = capture(capsys)

	assert_has(raw, "   ")
	assert_line_count(ls, 1)


def test_special_characters(capsys):
	log("!@#$%^&*()")

	raw, ls = capture(capsys)

	assert_has(raw, "!@#$%^&*()")
	assert_line_count(ls, 1)


def test_no_assignment_context(capsys):
	log("standalone")

	raw, ls = capture(capsys)

	assert_has(raw, "standalone")
	assert_line_count(ls, 1)


def test_shadow_builtin_name(capsys):
	str = log("test")  # shadowing built-in

	raw, ls = capture(capsys)

	assert str == "test"
	assert_has(raw, "test")
	assert_line_count(ls, 1)


def test_chained_calls(capsys):
	x = log(log("inner"))

	raw, ls = capture(capsys)

	assert x == "inner"
	assert_has(raw, "inner")
	assert_line_count(ls, 2)


def test_log_in_list(capsys):
	arr = [log("a"), log("b")]

	raw, ls = capture(capsys)

	assert arr == ["a", "b"]
	assert_values(raw, "a", "b")
	assert_line_count(ls, 2)


def test_log_in_dict(capsys):
	d = {"a": log("x")}

	raw, ls = capture(capsys)

	assert d == {"a": "x"}
	assert_has(raw, "x")
	assert_line_count(ls, 1)


def test_log_in_comprehension(capsys):
	arr = [log(i) for i in range(3)]

	raw, ls = capture(capsys)

	assert arr == [0, 1, 2]
	assert_values(raw, 0, 1, 2)
	assert_line_count(ls, 3)


def test_no_wrapper_internal_leak(capsys):
	@log(show_wrapper_locals=True)
	def f(x):
		return x + 1

	f(1)

	raw, ls = capture(capsys)

	assert_has(raw, "(call)")
	assert_has(raw, "(return)")
	assert_has_set(raw, "x", 1)

	assert_no_internal_leaks(raw)

	assert_line_count(ls, 3)
	assert_line_order(ls, "(call)", "x = 1")
	assert_line_order(ls, "x = 1", "(return)")

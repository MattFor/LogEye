from helpers import (
	capture,
	count,
	assert_value,
	assert_has_set,
	assert_line_order,
	assert_line_count,
	assert_no_call_noise,
	assert_no_return_noise,
)

from logeye import log


def test_basic_assignment(capsys):
	x = log("world")

	out, ls = capture(capsys)

	assert_line_count(ls, 1)
	assert_has_set(out, "x", "world")
	assert x == "world"


def test_numeric_assignment(capsys):
	x = log(42)

	out, ls = capture(capsys)

	assert_line_count(ls, 1)
	assert_has_set(out, "x", 42)


def test_multiple_assignments(capsys):
	a = log("a")
	b = log("b")

	out, ls = capture(capsys)

	assert count(ls, "(set)") == 2

	assert count(ls, "(set) a = 'a'") == 1
	assert count(ls, "(set) b = 'b'") == 1


def test_tuple_unpacking(capsys):
	a, b = log("x"), log("y")

	out, ls = capture(capsys)

	assert_line_count(ls, 2)
	assert_has_set(out, "a", "x")
	assert_has_set(out, "b", "y")


def test_reassignment(capsys):
	x = log(1)
	x = log(2)

	out, ls = capture(capsys)

	assert_line_count(ls, 2)
	assert_has_set(out, "x", 1)
	assert_has_set(out, "x", 2)
	assert_line_order(ls, "1", "2")


def test_string_quotes_consistency(capsys):
	x = log("abc")

	out, _ = capture(capsys)

	assert_value(out, "abc")
	assert '"abc"' not in out


def test_no_extra_noise(capsys):
	x = log("test")

	out, _ = capture(capsys)

	assert_no_call_noise(out)
	assert_no_return_noise(out)


def test_expression_assignment(capsys):
	x = log(10 + 5)

	out, _ = capture(capsys)

	assert_has_set(out, "x", 15)


def test_chained_calls(capsys):
	x = log(log(5))

	out, ls = capture(capsys)

	assert_line_count(ls, 2)
	assert_has_set(out, "x", 5)


def test_no_duplicate_emission(capsys):
	x = log(1)

	_, ls = capture(capsys)

	assert_line_count(ls, 1)

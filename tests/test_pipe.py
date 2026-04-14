from helpers import (
	capture,
	assert_has,
	assert_values,
	assert_not_has,
	assert_has_set,
	assert_set_order,
	assert_has_change,
)

from logeye import l


def test_pipe_basic(capsys):
	x = 10 | l

	out, ls = capture(capsys)
	assert_has_set(out, "x", 10)


def test_pipe_expression(capsys):
	x = (5 + 5) | l

	out, ls = capture(capsys)
	assert_has(out, "10")


def test_callable_l(capsys):
	x = l(20)

	out, ls = capture(capsys)
	assert_has_set(out, "x", 20)


def test_pipe_tracks_change(capsys):
	x = 1 | l
	x = 2

	out, ls = capture(capsys)
	assert_has_change(out, "x", 2)


def test_pipe_multiple_changes(capsys):
	x = "a" | l
	x = "b"
	x = "c"

	out, ls = capture(capsys)
	assert_has_change(out, "x", "b")
	assert_has_change(out, "x", "c")
	assert_set_order(ls, "x", "b", "c")


def test_pipe_no_duplicate_on_same_value(capsys):
	x = "same" | l
	x = "same"

	out, ls = capture(capsys)

	assert "(set) x = 'same'" in out


def test_pipe_back_to_original_value(capsys):
	x = "a" | l
	x = "b"
	x = "a"

	out, ls = capture(capsys)
	assert_has_change(out, "x", "b")
	assert_has_change(out, "x", "a")
	assert_set_order(ls, "x", "b", "a")


def test_pipe_multiple_variables(capsys):
	x = 1 | l
	y = 2 | l

	x = 10
	y = 20

	out, ls = capture(capsys)
	assert_has_change(out, "x", 10)
	assert_has_change(out, "y", 20)


def test_pipe_independent_tracking(capsys):
	x = 1 | l
	y = 2

	x = 3
	y = 4

	out, ls = capture(capsys)
	assert_has_change(out, "x", 3)
	assert_not_has(out, "y = 4")


def test_pipe_inline_usage(capsys):
	def f():
		return (3 * 3) | l

	f()

	out, ls = capture(capsys)
	assert_has(out, "9")


def test_pipe_in_list_context(capsys):
	arr = [(1 | l), (2 | l)]

	out, ls = capture(capsys)
	assert_values(out, 1, 2)


def test_pipe_in_dict_context(capsys):
	d = {"a": (5 | l)}

	out, ls = capture(capsys)
	assert_has(out, "5")


def test_pipe_dict(capsys):
	x = {"a": 1} | l
	x = {"a": 2}

	out, ls = capture(capsys)
	assert_has_change(out, "x", {"a": 2})


def test_pipe_list(capsys):
	x = [1, 2] | l
	x = [3, 4]

	out, ls = capture(capsys)
	assert_has_change(out, "x", [3, 4])


def test_pipe_bool(capsys):
	x = True | l
	x = False

	out, ls = capture(capsys)
	assert_has_change(out, "x", False)


def test_pipe_without_assignment(capsys):
	10 | l

	out, ls = capture(capsys)
	assert_has(out, "10")


def test_pipe_reassignment_chain(capsys):
	x = 1 | l
	x = 2 | l
	x = 3

	out, ls = capture(capsys)
	assert_has_set(out, "x", 2)
	assert_has_change(out, "x", 3)
	assert_set_order(ls, "x", 2, 3)


def test_pipe_inside_function_scope(capsys):
	def f():
		x = "start" | l
		x = "end"

	f()

	out, ls = capture(capsys)
	assert_has_change(out, "x", "end")


def test_pipe_shadowing_variable(capsys):
	x = 1 | l

	def f():
		x = 2 | l
		x = 3

	f()
	x = 4

	out, ls = capture(capsys)

	assert_has_change(out, "x", 3)  # Inner
	assert_has_change(out, "x", 4)  # Outer

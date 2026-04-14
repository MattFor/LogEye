import pytest

from helpers import (
	count,
	capture,
	assert_args,
	assert_value,
	assert_has_set,
	assert_has_call,
	assert_set_order,
	assert_has_return,
	assert_has_change,
)

from logeye import log, l


def test_plain_message(capsys):
	log("hello")

	out, _ = capture(capsys)

	assert_value(out, "hello")
	assert "(set)" not in out


def test_format_args(capsys):
	x = 5
	log("value is {}", x)

	out, _ = capture(capsys)

	assert_value(out, "value is 5")


def test_template_expand(capsys):
	x = 10
	log("x is $x")

	out, _ = capture(capsys)

	assert_value(out, "x is 10")


def test_log_sets_variable(capsys):
	x = log("abc")

	out, _ = capture(capsys)

	assert_has_set(out, "x", "abc")


def test_log_tracks_changes(capsys):
	x = log("start")
	x = 10
	x = 20

	out, ls = capture(capsys)

	assert_has_set(out, "x", "start")
	assert_has_change(out, "x", 10)
	assert_has_change(out, "x", 20)
	assert_set_order(ls, "x", "start", 10)
	assert_set_order(ls, "x", 10, 20)


def test_log_ignores_same_value(capsys):
	x = log("same")
	x = "same"

	out, _ = capture(capsys)

	assert "(set) x = 'same'" in out


def test_pipe_basic(capsys):
	x = "abc" | l

	out, _ = capture(capsys)

	assert_has_set(out, "x", "abc")


def test_pipe_tracks_changes(capsys):
	x = "abc" | l
	x = 123

	out, _ = capture(capsys)

	assert_has_change(out, "x", 123)


def test_pipe_multiple_changes(capsys):
	x = "a" | l
	x = "b"
	x = "c"

	out, ls = capture(capsys)

	assert_has_change(out, "x", "b")
	assert_has_change(out, "x", "c")
	assert_set_order(ls, "x", "b", "c")


def test_l_direct_call(capsys):
	x = l("hello")

	out, _ = capture(capsys)

	assert_has_set(out, "x", "hello")


def test_l_direct_change_tracking(capsys):
	x = l("start")
	x = 42

	out, _ = capture(capsys)

	assert_has_change(out, "x", 42)


def test_log_decorator_call_and_return(capsys):
	@log
	def add(a, b):
		return a + b

	add(2, 3)

	out, _ = capture(capsys)

	assert_has_call(out, "add")
	assert_args(out, 2, 3)
	assert_has_return(out, "add", 5)


def test_log_decorator_variable_tracking(capsys):
	@log
	def f():
		x = 1
		x = 2
		return x

	f()

	out, _ = capture(capsys)

	assert_value(out, "x = 1")
	assert_value(out, "x = 2")


def test_mix_log_and_pipe(capsys):
	x = log("a")
	x = "b" | l
	x = "c"

	out, ls = capture(capsys)

	assert_has_set(out, "x", "a")
	assert_has_set(out, "x", "b")
	assert_has_change(out, "x", "c")
	assert_set_order(ls, "x", "a", "b")
	assert_set_order(ls, "x", "b", "c")


def test_multiple_variables(capsys):
	x = "a" | l
	y = 10 | l

	x = "b"
	y = 20

	out, _ = capture(capsys)

	assert_has_change(out, "x", "b")
	assert_has_change(out, "y", 20)


def test_dict_tracking(capsys):
	x = {"a": 1} | l
	x = {"a": 2}

	out, _ = capture(capsys)

	assert_has_change(out, "x", {"a": 2})


def test_list_tracking(capsys):
	x = [1, 2] | l
	x = [3, 4]

	out, _ = capture(capsys)

	assert_has_change(out, "x", [3, 4])


def test_reassign_to_original_value(capsys):
	x = "abc" | l
	x = "def"
	x = "abc"

	out, ls = capture(capsys)

	assert_has_change(out, "x", "def")
	assert_has_change(out, "x", "abc")
	assert_set_order(ls, "x", "def", "abc")


def test_watch_inside_function(capsys):
	def f():
		x = "start" | l
		x = "end"

	f()

	out, _ = capture(capsys)

	assert_has_change(out, "x", "end")


@pytest.mark.xfail(
	reason="TODO: decide semantics for same-value reassignment (set vs change)",
	strict=False,
)
def test_multiple_lines_same_value_not_spammed(capsys):
	# TODO: only emits once, we need to do it 3 times...

	x = "a" | l
	x = "a"
	x = "a"

	out, ls = capture(capsys)

	assert count(ls, "(set) x = 'a'") == 1
	assert count(ls, "(change) x = 'a'") == 2

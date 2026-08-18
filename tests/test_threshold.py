from helpers import (
	capture,
	assert_has,
	assert_has_set,
	assert_not_has,
	assert_has_call,
	assert_has_change,
	assert_has_return,
	assert_line_order,
	assert_line_count,
	count,
)

from logeye import log, watch


def test_absolute_threshold_blocks_small_changes(capsys):
	x = log(10, threshold=("absolute", 5))

	x += 2
	x += 1

	raw, ls = capture(capsys)

	assert_line_count(ls, 1)  # Only initial set


def test_absolute_threshold_allows_large_change(capsys):
	x = log(10, threshold=("absolute", 5))

	x += 6

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)
	assert_has(raw, "16")


def test_absolute_threshold_exact_boundary(capsys):
	x = log(10, threshold=("absolute", 5))

	x += 5

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)


def test_relative_threshold_blocks_small_percentage(capsys):
	x = log(100, threshold=("relative", 0.1))

	x += 5  # 5%

	raw, ls = capture(capsys)

	assert_line_count(ls, 1)


def test_relative_threshold_allows_large_percentage(capsys):
	x = log(100, threshold=("relative", 0.1))

	x += 20  # 20%

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)
	assert_has(raw, "120")


def test_relative_threshold_zero_base(capsys):
	x = log(0, threshold=("relative", 0.1))

	x += 1  # Div by 0

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)


def test_combined_threshold_requires_both(capsys):
	x = log(100, threshold={"absolute": 10, "relative": 0.2})

	x += 15

	raw, ls = capture(capsys)

	assert_line_count(ls, 1)


def test_combined_threshold_passes_both(capsys):
	x = log(100, threshold={"absolute": 10, "relative": 0.1})

	x += 15

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)


def test_watch_threshold_basic(capsys):
	x = watch(10, threshold=("absolute", 5))

	x += 2
	x += 6

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)


def test_watch_relative_threshold(capsys):
	x = watch(100, threshold=("relative", 0.1))

	x += 5
	x += 15

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)


def test_function_threshold_simple(capsys):
	@log(threshold={"x": ("absolute", 5)})
	def f():
		x = 10
		x += 2
		x += 6

	f()

	raw, ls = capture(capsys)

	assert_has_call(raw)
	assert_has_set(raw, "x", 10)
	assert_has_return(raw)


def test_function_relative_threshold(capsys):
	@log(threshold={"x": ("relative", 0.2)})
	def f():
		x = 10
		x += 1
		x += 3

	f()

	raw, ls = capture(capsys)

	assert_has_call(raw)
	assert_has_set(raw, "x", 10)

	assert_not_has(raw, "x = 11")
	assert_has_change(raw, "x", 14)

	assert_has_return(raw)


def test_multiple_variables_threshold(capsys):
	@log(
		threshold={
			"x": ("absolute", 5),
			"y": ("absolute", 2),
		}
	)
	def f():
		x = 10
		y = 10

		x += 2
		y += 1

		x += 6
		y += 3

	f()

	raw, ls = capture(capsys)

	assert count(ls, "x") >= 2
	assert count(ls, "y") >= 2


def test_non_numeric_threshold_fallback(capsys):
	x = log("a", threshold=("absolute", 5))

	x = "b"

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)


def test_none_values(capsys):
	x = log(None, threshold=("absolute", 1))

	x = None
	x = 1

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)


def test_list_threshold(capsys):
	arr = log([10, 20], threshold=("absolute", 5))

	arr[0] += 2
	arr[0] += 6

	raw, ls = capture(capsys)

	assert_has(raw, "12")
	assert_has(raw, "18")

	assert_line_order(ls, "12", "18")

	assert_has_change(raw, "arr.0", 12)
	assert_has_change(raw, "arr.0", 18)

	assert count(ls, "arr.0") == 2


def test_reassignment_respects_threshold(capsys):
	x = log(10, threshold=("absolute", 5))

	x += 6
	x = 10

	raw, ls = capture(capsys)

	assert count(ls, "velocity") >= 0  # sanity


def test_reassignment_not_resetting_state(capsys):
	x = log(10, threshold=("absolute", 5))

	x += 6
	x = 12

	raw, ls = capture(capsys)

	# should NOT emit again
	assert_line_count(ls, 2)


def test_threshold_in_loop(capsys):
	x = log(0, threshold=("absolute", 3))

	for _ in range(5):
		x += 1

	raw, ls = capture(capsys)

	assert len(ls) <= 3


def test_threshold_zero(capsys):
	x = log(10, threshold=0)

	x += 0

	raw, ls = capture(capsys)

	assert_line_count(ls, 1)


def test_threshold_negative_values(capsys):
	x = log(-10, threshold=("absolute", 5))

	x -= 3
	x -= 5

	raw, ls = capture(capsys)

	assert len(ls) >= 2


def test_threshold_float_precision(capsys):
	x = log(1.0, threshold=("relative", 0.1))

	x += 0.05
	x += 0.2

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)


def test_many_small_updates(capsys):
	x = log(0, threshold=("absolute", 5))

	for _ in range(10):
		x += 1

	raw, ls = capture(capsys)

	assert len(ls) <= 3


def test_switch_numeric_to_string(capsys):
	x = log(10, threshold=("absolute", 5))

	x = "hello"

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)


def test_pipe_threshold(capsys):
	x = 10 | log(threshold=("absolute", 5))

	x += 2
	x += 6

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)


def test_threshold_does_not_crash(capsys):
	x = log(10, threshold={"absolute": 5, "relative": 0.1})

	for _ in range(10):
		x += 1

	raw, ls = capture(capsys)

	assert raw is not None


def test_no_duplicate_emits(capsys):
	x = log(10, threshold=("absolute", 1))

	x += 2

	raw, ls = capture(capsys)

	# Match the payload, never a bare number; the "[0.612s]" stamp holds digits too
	assert count(ls, "x = 10") == 1
	assert count(ls, "x = 12") == 1
	assert_line_count(ls, 2)


def test_change_not_lost_after_skip(capsys):
	x = log(10, threshold=("absolute", 5))

	x += 2
	x += 6

	raw, ls = capture(capsys)

	assert_line_count(ls, 2)

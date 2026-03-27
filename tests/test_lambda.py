from helpers import (
	count,
	capture,
	assert_has,
	assert_has_call,
	assert_has_return,
	assert_line_count,
	assert_no_call_noise,
	assert_no_return_noise,
)
from logeye import log, l


def test_lambda_direct(capsys):
	f = lambda: log("lambda")

	result = f()
	out, ls = capture(capsys)

	assert result == "lambda"
	assert_line_count(ls, 1)
	assert_has(out, "lambda")
	assert_no_call_noise(out)
	assert_no_return_noise(out)


def test_lambda_assignment(capsys):
	f = lambda: log("inside")
	x = f()

	out, ls = capture(capsys)

	assert x == "inside"
	assert_line_count(ls, 1)
	assert_has(out, "inside")


def test_nested_lambda(capsys):
	f = lambda: (lambda: log("deep"))()

	result = f()
	out, ls = capture(capsys)

	assert result == "deep"
	assert_line_count(ls, 1)
	assert_has(out, "deep")


def test_lambda_returning_lambda(capsys):
	f = lambda: lambda: log("inner")

	inner = f()
	result = inner()

	out, ls = capture(capsys)

	assert result == "inner"
	assert_line_count(ls, 1)
	assert_has(out, "inner")


def test_nested_lambda_assignment(capsys):
	f = lambda: (lambda: log("nested"))()

	x = f()
	out, ls = capture(capsys)

	assert x == "nested"
	assert_line_count(ls, 1)
	assert_has(out, "nested")


def test_complex_nested_lambda(capsys):
	f = lambda: (lambda x: log(f"value {x}"))(5)

	result = f()
	out, ls = capture(capsys)

	assert result == "value 5"
	assert_line_count(ls, 1)
	assert_has(out, "value 5")


def test_lambda_wrapped_call(capsys):
	f = lambda x: x * 2
	f = l(f)

	result = f(3)
	out, ls = capture(capsys)

	assert result == 6

	# Now behaves like a traced function
	assert_has_call(out, "<lambda>")
	assert_has_return(out, "<lambda>", 6)
	assert_has(out, "x")
	assert_has(out, "3")

	assert len(ls) >= 3  # call + set + return


def test_lambda_no_duplicate_logs(capsys):
	f = lambda: log("once")

	f()
	out, ls = capture(capsys)

	assert_line_count(ls, 1)
	assert_has(out, "once")


def test_lambda_multiple_calls(capsys):
	f = lambda: log("repeat")

	f()
	f()

	out, ls = capture(capsys)

	assert_line_count(ls, 2)
	assert count(ls, "repeat") == 2


def test_lambda_argument_passthrough(capsys):
	f = lambda x: log(x)

	result = f(123)
	out, ls = capture(capsys)

	assert result == 123
	assert_line_count(ls, 1)
	assert_has(out, "123")


def test_lambda_closure_capture(capsys):
	val = "captured"
	f = lambda: log(val)

	result = f()
	out, ls = capture(capsys)

	assert result == "captured"
	assert_line_count(ls, 1)
	assert_has(out, "captured")


def test_lambda_chain(capsys):
	f = lambda: log(log("chain"))

	result = f()
	out, ls = capture(capsys)

	assert result == "chain"
	assert_line_count(ls, 2)
	assert count(ls, "chain") == 2


def test_lambda_return_value_integrity(capsys):
	f = lambda: log(999)

	result = f()
	out, ls = capture(capsys)

	assert result == 999
	assert_line_count(ls, 1)
	assert_has(out, "999")


def test_lambda_no_call_noise(capsys):
	f = lambda: log("quiet")

	f()
	out, ls = capture(capsys)

	assert_no_call_noise(out)
	assert_no_return_noise(out)


def test_lambda_multiple_variables(capsys):
	f = lambda: (log("a"), log("b"))

	result = f()
	out, ls = capture(capsys)

	assert result == ("a", "b")
	assert_line_count(ls, 2)
	assert_has(out, "a")
	assert_has(out, "b")


def test_lambda_nested_multiple_levels(capsys):
	f = lambda: (lambda: (lambda: log("deepest"))())()

	result = f()
	out, ls = capture(capsys)

	assert result == "deepest"
	assert_line_count(ls, 1)
	assert_has(out, "deepest")

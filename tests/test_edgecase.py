import pytest
from logeye import log


def test_inline_expression(capsys):
	x = "a" + log("b")

	out = capsys.readouterr().out

	assert "b" in out
	assert x == "ab"


def test_nested_inline_expression(capsys):
	x = log("a") + log("b") + log("c")

	out = capsys.readouterr().out

	assert "a" in out
	assert "b" in out
	assert "c" in out
	assert x == "abc"


def test_expression_order(capsys):
	x = log("a") + "b"

	out = capsys.readouterr().out
	assert "a" in out
	assert x == "ab"


def test_tuple_unpacking(capsys):
	a, b = log("x"), log("y")

	out = capsys.readouterr().out

	assert "(set) a =" in out
	assert "(set) b =" in out


# TODO: Multiple tuple nested unpacking support - basically gotta make a mini-parser just for them
@pytest.mark.xfail(reason="Nested unpacking not fully supported yet", strict=False)
def test_nested_unpacking(capsys):
	(a, (b, c)) = log("x"), (log("y"), log("z"))

	out = capsys.readouterr().out

	assert "(set) a =" in out
	assert "(set) b =" in out
	assert "(set) c =" in out


def test_reassignment_same_line(capsys):
	# fmt: off
	# @formatter:off
	x = log("a"); x = log("b")  # noqa: E702, E703
	# @formatter:on
	# fmt: off

	out = capsys.readouterr().out
	assert "a" in out
	assert "b" in out


def test_inline_expression_error():
	with pytest.raises(TypeError):
		x = 1 + log("a")


def test_invalid_path_mode():
	from logeye import set_path_mode

	with pytest.raises(ValueError):
		set_path_mode("invalid")


def test_if_branch_logging(capsys):
	if True:
		x = log("yes")

	out = capsys.readouterr().out
	assert "yes" in out


def test_if_else_branch(capsys):
	if False:
		log("no")
	else:
		log("yes")

	out = capsys.readouterr().out
	assert "yes" in out
	assert "no" not in out


def test_loop_logging(capsys):
	for _ in range(3):
		log("loop")

	out = capsys.readouterr().out
	assert out.count("loop") == 3


def test_loop_variable_assignment(capsys):
	for i in range(2):
		x = log(i)

	out = capsys.readouterr().out
	assert "0" in out
	assert "1" in out


def test_inside_function(capsys):
	def f():
		x = log("inner")

	f()

	out = capsys.readouterr().out
	assert "inner" in out


def test_nested_functions(capsys):
	def outer():
		def inner():
			return log("deep")

		return inner()

	outer()

	out = capsys.readouterr().out
	assert "deep" in out


def test_lambda_usage(capsys):
	f = lambda: log("lambda")
	f()

	out = capsys.readouterr().out
	assert "lambda" in out


def test_multiple_calls_same_var(capsys):
	x = log("a")
	x = log("b")
	x = log("c")

	out = capsys.readouterr().out
	assert "a" in out
	assert "b" in out
	assert "c" in out


def test_reuse_variable_name(capsys):
	x = log("a")

	def f():
		x = log("b")
		return x

	f()

	out = capsys.readouterr().out
	assert "a" in out
	assert "b" in out


def test_log_none(capsys):
	x = log(None)

	out = capsys.readouterr().out
	assert "None" in out


def test_log_bool(capsys):
	x = log(True)

	out = capsys.readouterr().out
	assert "True" in out


def test_log_large_number(capsys):
	x = log(10 ** 10)

	out = capsys.readouterr().out
	assert "10000000000" in out


def test_empty_string(capsys):
	log("")

	out = capsys.readouterr().out
	assert out.strip() != ""  # Still logs something


def test_whitespace_string(capsys):
	log("   ")

	out = capsys.readouterr().out
	assert "   " in out


def test_special_characters(capsys):
	log("!@#$%^&*()")

	out = capsys.readouterr().out
	assert "!@#$%^&*()" in out


def test_no_assignment_context(capsys):
	log("standalone")

	out = capsys.readouterr().out
	assert "standalone" in out


def test_shadow_builtin_name(capsys):
	str = log("test")  # shadowing built-in

	out = capsys.readouterr().out
	assert "test" in out


def test_chained_calls(capsys):
	x = log(log("inner"))

	out = capsys.readouterr().out
	assert "inner" in out


def test_log_in_list(capsys):
	arr = [log("a"), log("b")]

	out = capsys.readouterr().out
	assert "a" in out
	assert "b" in out


def test_log_in_dict(capsys):
	d = {"a": log("x")}

	out = capsys.readouterr().out
	assert "x" in out


def test_log_in_comprehension(capsys):
	arr = [log(i) for i in range(3)]

	out = capsys.readouterr().out
	assert "0" in out
	assert "1" in out
	assert "2" in out


def test_no_wrapper_internal_leak(capsys):
	@log(show_wrapper_locals=True)
	def f(x):
		return x + 1

	f(1)

	out = capsys.readouterr().out

	# If internals are leaking, it must be terrible
	forbidden = [
		"args",
		"kwargs",
		"call_counter",
		"allowed_codes",
		"target_func",
		"prev_mode",
		"prev_time",
		"prev_file",
		"prev_lineno",
		"call_frame",
		"call_filename",
		"call_lineno",
		"last_values",
		"tracer",
		"old_trace",
		"_should_emit",
	]

	for name in forbidden:
		assert f".{name} =" not in out, f"Leaked internal variable: {name}"



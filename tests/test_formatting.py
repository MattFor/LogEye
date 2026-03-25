from logeye import log


def test_format_multiple_args(capsys):
	log("a={}, b={}", 1, 2)

	out = capsys.readouterr().out
	assert "a=1, b=2" in out


def test_format_with_kwargs(capsys):
	log("x={x}, y={y}", x=3, y=4)

	out = capsys.readouterr().out
	assert "x=3, y=4" in out


def test_format_mixed_args_kwargs(capsys):
	log("a={}, b={b}", 1, b=2)

	out = capsys.readouterr().out
	assert "a=1, b=2" in out


def test_format_repr_types(capsys):
	log("list: {}, dict: {}", [1, 2], {"a": 1})

	out = capsys.readouterr().out
	assert "[1, 2]" in out
	assert "{'a': 1}" in out


def test_template_multiple_vars(capsys):
	x = 1
	y = 2

	log("x=$x, y=$y")

	out = capsys.readouterr().out
	assert "x=1, y=2" in out


def test_template_repeated_var(capsys):
	x = 7

	log("$x + $x = $x")

	out = capsys.readouterr().out
	assert "7 + 7 = 7" in out


def test_template_missing_var_safe(capsys):
	log("missing: $does_not_exist")

	out = capsys.readouterr().out
	# Should not crash
	assert "missing:" in out


def test_special_paths(capsys):
	log("file: $fpath")

	out = capsys.readouterr().out
	assert ".py" in out


def test_special_lineno(capsys):
	log("line: $lineno")

	out = capsys.readouterr().out
	assert "line:" in out


def test_fstring_basic(capsys):
	x = 10
	log(f"x is {x}")

	out = capsys.readouterr().out
	assert "x is 10" in out


def test_fstring_multiple(capsys):
	x = 2
	y = 3

	log(f"{x} + {y} = {x + y}")

	out = capsys.readouterr().out
	assert "2 + 3 = 5" in out


def test_fstring_with_object(capsys):
	obj = {"a": 1}

	log(f"obj = {obj}")

	out = capsys.readouterr().out
	assert "{'a': 1}" in out


def test_mixed_template_and_format(capsys):
	x = 5

	log("value: {} and $x", x)

	out = capsys.readouterr().out
	assert "value: 5 and 5" in out


def test_mixed_template_and_fstring(capsys):
	x = 10

	log(f"value is {x} and also $x")

	out = capsys.readouterr().out
	assert "value is 10 and also 10" in out


def test_empty_string(capsys):
	log("")

	out = capsys.readouterr().out
	assert out.strip() != ""  # still emits something


def test_only_variable_template(capsys):
	x = 42
	log("$x")

	out = capsys.readouterr().out
	assert "42" in out


def test_braces_literal(capsys):
	log("{{}}")

	out = capsys.readouterr().out
	assert "{}" in out


def test_large_string(capsys):
	log("x=" + "a" * 1000)

	out = capsys.readouterr().out
	assert "a" * 50 in out  # partial check


def test_non_string_input(capsys):
	log(123)

	out = capsys.readouterr().out
	assert "123" in out


def test_none_input(capsys):
	log(None)

	out = capsys.readouterr().out
	assert "None" in out


def test_bool_input(capsys):
	log(True)

	out = capsys.readouterr().out
	assert "True" in out

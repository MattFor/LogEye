from logeye import log, l


def _lines(out):
	return [line.strip() for line in out.strip().splitlines() if line.strip()]


def _value(line):
	return line.split()[-1]


def test_lambda_direct(capsys):
	f = lambda: log("lambda")

	result = f()
	out = _lines(capsys.readouterr().out)

	assert result == "lambda"
	assert len(out) == 1
	assert _value(out[0]) == "lambda"


def test_lambda_assignment(capsys):
	f = lambda: log("inside")
	x = f()

	out = _lines(capsys.readouterr().out)

	assert x == "inside"
	assert len(out) == 1
	assert _value(out[0]) == "inside"


def test_nested_lambda(capsys):
	f = lambda: (lambda: log("deep"))()

	result = f()
	out = _lines(capsys.readouterr().out)

	assert result == "deep"
	assert len(out) == 1
	assert _value(out[0]) == "deep"


def test_lambda_returning_lambda(capsys):
	f = lambda: lambda: log("inner")

	inner = f()
	result = inner()

	out = _lines(capsys.readouterr().out)

	assert result == "inner"
	assert len(out) == 1
	assert _value(out[0]) == "inner"


def test_nested_lambda_assignment(capsys):
	f = lambda: (lambda: log("nested"))()

	x = f()
	out = _lines(capsys.readouterr().out)

	assert x == "nested"
	assert len(out) == 1
	assert _value(out[0]) == "nested"


def test_complex_nested_lambda(capsys):
	f = lambda: (lambda x: log(f"value {x}"))(5)

	result = f()
	out = _lines(capsys.readouterr().out)

	assert result == "value 5"
	assert len(out) == 1
	assert "value 5" in out[0]


def test_lambda_wrapped_call(capsys):
	f = lambda x: x * 2
	f = l(f)

	result = f(3)
	out = _lines(capsys.readouterr().out)

	assert result == 6
	assert len(out) >= 1


def test_lambda_no_duplicate_logs(capsys):
	f = lambda: log("once")

	f()
	out = _lines(capsys.readouterr().out)

	assert len(out) == 1


def test_lambda_multiple_calls(capsys):
	f = lambda: log("repeat")

	f()
	f()

	out = _lines(capsys.readouterr().out)

	assert len(out) == 2
	assert all(_value(line) == "repeat" for line in out)


def test_lambda_argument_passthrough(capsys):
	f = lambda x: log(x)

	result = f(123)
	out = _lines(capsys.readouterr().out)

	assert result == 123
	assert len(out) == 1
	assert _value(out[0]) == "123"


def test_lambda_closure_capture(capsys):
	val = "captured"
	f = lambda: log(val)

	result = f()
	out = _lines(capsys.readouterr().out)

	assert result == "captured"
	assert len(out) == 1
	assert _value(out[0]) == "captured"


def test_lambda_chain(capsys):
	f = lambda: log(log("chain"))

	result = f()
	out = _lines(capsys.readouterr().out)

	assert result == "chain"
	assert len(out) == 2


def test_lambda_return_value_integrity(capsys):
	f = lambda: log(999)

	result = f()
	out = _lines(capsys.readouterr().out)

	assert result == 999
	assert len(out) == 1
	assert _value(out[0]) == "999"


def test_lambda_no_call_noise(capsys):
	f = lambda: log("quiet")

	f()
	out = "\n".join(_lines(capsys.readouterr().out))

	assert "Calling" not in out
	assert "returned" not in out


def test_lambda_multiple_variables(capsys):
	f = lambda: (log("a"), log("b"))

	result = f()
	out = _lines(capsys.readouterr().out)

	assert result == ("a", "b")
	assert len(out) == 2
	assert _value(out[0]) == "a"
	assert _value(out[1]) == "b"


def test_lambda_nested_multiple_levels(capsys):
	f = lambda: (lambda: (lambda: log("deepest"))())()

	result = f()
	out = _lines(capsys.readouterr().out)

	assert result == "deepest"
	assert len(out) == 1
	assert _value(out[0]) == "deepest"

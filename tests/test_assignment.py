from logeye import log


def test_basic_assignment(capsys):
	x = log("world")

	out = capsys.readouterr().out.strip().splitlines()

	assert len(out) == 1
	assert out[0].endswith("(set) x = 'world'")
	assert x == "world"


def test_numeric_assignment(capsys):
	x = log(42)

	out = capsys.readouterr().out.strip().splitlines()

	assert len(out) == 1
	assert out[0].endswith("(set) x = 42")


def test_multiple_assignments(capsys):
	a = log("a")
	b = log("b")

	out = capsys.readouterr().out.strip().splitlines()

	assert len(out) == 2
	assert out[0].endswith("(set) a = 'a'")
	assert out[1].endswith("(set) b = 'b'")


def test_tuple_unpacking(capsys):
	a, b = log("x"), log("y")

	out = capsys.readouterr().out.strip().splitlines()

	assert len(out) == 2
	assert out[0].endswith("(set) a = 'x'")
	assert out[1].endswith("(set) b = 'y'")


def test_reassignment(capsys):
	x = log(1)
	x = log(2)

	out = capsys.readouterr().out.strip().splitlines()

	assert len(out) == 2
	assert out[0].endswith("(set) x = 1")
	assert out[1].endswith("(set) x = 2")


def test_string_quotes_consistency(capsys):
	x = log("abc")

	out = capsys.readouterr().out.strip()

	assert "'abc'" in out
	assert '"abc"' not in out


def test_no_extra_noise(capsys):
	x = log("test")

	out = capsys.readouterr().out.strip()

	assert "Calling" not in out
	assert "returned" not in out


def test_expression_assignment(capsys):
	x = log(10 + 5)

	out = capsys.readouterr().out.strip()

	assert "(set) x = 15" in out


def test_chained_calls(capsys):
	x = log(log(5))

	out = capsys.readouterr().out.strip().splitlines()

	assert len(out) == 2
	assert out[0].endswith("(set) x = 5") or out[1].endswith("(set) x = 5")


def test_no_duplicate_emission(capsys):
	x = log(1)

	out = capsys.readouterr().out.strip().splitlines()

	assert len(out) == 1

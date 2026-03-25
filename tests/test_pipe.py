from logeye import l


def test_pipe_basic(capsys):
	x = 10 | l

	out = capsys.readouterr().out
	assert "(set) x =" in out
	assert "10" in out


def test_pipe_expression(capsys):
	x = (5 + 5) | l

	out = capsys.readouterr().out
	assert "10" in out


def test_callable_l(capsys):
	x = l(20)

	out = capsys.readouterr().out
	assert "(set) x =" in out
	assert "20" in out


def test_pipe_tracks_change(capsys):
	x = 1 | l
	x = 2

	out = capsys.readouterr().out
	assert "(change) x = 2" in out


def test_pipe_multiple_changes(capsys):
	x = "a" | l
	x = "b"
	x = "c"

	out = capsys.readouterr().out
	assert "(change) x = 'b'" in out
	assert "(change) x = 'c'" in out


def test_pipe_no_duplicate_on_same_value(capsys):
	x = "same" | l
	x = "same"

	out = capsys.readouterr().out
	assert out.count("same") == 1


def test_pipe_back_to_original_value(capsys):
	x = "a" | l
	x = "b"
	x = "a"

	out = capsys.readouterr().out
	assert "(change) x = 'b'" in out
	assert "(change) x = 'a'" in out


def test_pipe_multiple_variables(capsys):
	x = 1 | l
	y = 2 | l

	x = 10
	y = 20

	out = capsys.readouterr().out
	assert "(change) x = 10" in out
	assert "(change) y = 20" in out


def test_pipe_independent_tracking(capsys):
	x = 1 | l
	y = 2

	x = 3
	y = 4  # should NOT be tracked

	out = capsys.readouterr().out
	assert "(change) x = 3" in out
	assert "y = 4" not in out


def test_pipe_inline_usage(capsys):
	def f():
		return (3 * 3) | l

	f()

	out = capsys.readouterr().out
	assert "9" in out


def test_pipe_in_list_context(capsys):
	arr = [(1 | l), (2 | l)]

	out = capsys.readouterr().out
	assert "1" in out
	assert "2" in out


def test_pipe_in_dict_context(capsys):
	d = {"a": (5 | l)}

	out = capsys.readouterr().out
	assert "5" in out


def test_pipe_dict(capsys):
	x = {"a": 1} | l
	x = {"a": 2}

	out = capsys.readouterr().out
	assert "(change) x = {'a': 2}" in out


def test_pipe_list(capsys):
	x = [1, 2] | l
	x = [3, 4]

	out = capsys.readouterr().out
	assert "(change) x = [3, 4]" in out


def test_pipe_bool(capsys):
	x = True | l
	x = False

	out = capsys.readouterr().out
	assert "(change) x = False" in out


def test_pipe_without_assignment(capsys):
	10 | l

	out = capsys.readouterr().out
	assert "10" in out  # Should log message-style


def test_pipe_reassignment_chain(capsys):
	x = 1 | l
	x = 2 | l  # Seed the watcher again
	x = 3

	out = capsys.readouterr().out
	assert "(set) x = 2" in out
	assert "(change) x = 3" in out


def test_pipe_inside_function_scope(capsys):
	def f():
		x = "start" | l
		x = "end"

	f()

	out = capsys.readouterr().out
	assert "(change) x = 'end'" in out


def test_pipe_shadowing_variable(capsys):
	x = 1 | l

	def f():
		x = 2 | l
		x = 3

	f()
	x = 4

	out = capsys.readouterr().out

	assert "(change) x = 3" in out  # Inner
	assert "(change) x = 4" in out  # Outer

from logeye import log, l


def test_plain_message(capsys):
	log("hello")

	out = capsys.readouterr().out
	assert "hello" in out
	assert "(set)" not in out


def test_format_args(capsys):
	x = 5
	log("value is {}", x)

	out = capsys.readouterr().out
	assert "value is 5" in out


def test_template_expand(capsys):
	x = 10
	log("x is $x")

	out = capsys.readouterr().out
	assert "x is 10" in out


def test_log_sets_variable(capsys):
	x = log("abc")

	out = capsys.readouterr().out
	assert "(set) x = 'abc'" in out


def test_log_tracks_changes(capsys):
	x = log("start")
	x = 10
	x = 20

	out = capsys.readouterr().out

	assert "(set) x = 'start'" in out
	assert "(change) x = 10" in out
	assert "(change) x = 20" in out


def test_log_ignores_same_value(capsys):
	x = log("same")
	x = "same"

	out = capsys.readouterr().out

	# Should not emit duplicate change
	assert out.count("same") == 1


def test_pipe_basic(capsys):
	x = "abc" | l

	out = capsys.readouterr().out
	assert "(set) x = 'abc'" in out


def test_pipe_tracks_changes(capsys):
	x = "abc" | l
	x = 123

	out = capsys.readouterr().out
	assert "(change) x = 123" in out


def test_pipe_multiple_changes(capsys):
	x = "a" | l
	x = "b"
	x = "c"

	out = capsys.readouterr().out
	assert "(change) x = 'b'" in out
	assert "(change) x = 'c'" in out


def test_l_direct_call(capsys):
	x = l("hello")

	out = capsys.readouterr().out
	assert "(set) x = 'hello'" in out


def test_l_direct_change_tracking(capsys):
	x = l("start")
	x = 42

	out = capsys.readouterr().out
	assert "(change) x = 42" in out


def test_log_decorator_call_and_return(capsys):
	@log
	def add(a, b):
		return a + b

	add(2, 3)

	out = capsys.readouterr().out

	assert "call" in out.lower()
	assert "return" in out.lower()
	assert "5" in out


def test_log_decorator_variable_tracking(capsys):
	@log
	def f():
		x = 1
		x = 2
		return x

	f()

	out = capsys.readouterr().out

	assert "x = 1" in out
	assert "x = 2" in out


def test_mix_log_and_pipe(capsys):
	x = log("a")
	x = "b" | l
	x = "c"

	out = capsys.readouterr().out

	assert "(set) x = 'a'" in out
	assert "(set) x = 'b'" in out
	assert "(change) x = 'c'" in out


def test_multiple_variables(capsys):
	x = "a" | l
	y = 10 | l

	x = "b"
	y = 20

	out = capsys.readouterr().out

	assert "(change) x = 'b'" in out
	assert "(change) y = 20" in out


def test_dict_tracking(capsys):
	x = {"a": 1} | l
	x = {"a": 2}

	out = capsys.readouterr().out
	assert "(change) x = {'a': 2}" in out


def test_list_tracking(capsys):
	x = [1, 2] | l
	x = [3, 4]

	out = capsys.readouterr().out
	assert "(change) x = [3, 4]" in out


def test_reassign_to_original_value(capsys):
	x = "abc" | l
	x = "def"
	x = "abc"

	out = capsys.readouterr().out

	assert "(change) x = 'def'" in out
	assert "(change) x = 'abc'" in out  # must still log


def test_watch_inside_function(capsys):
	def f():
		x = "start" | l
		x = "end"

	f()

	out = capsys.readouterr().out
	assert "(change) x = 'end'" in out


def test_multiple_lines_same_value_not_spammed(capsys):
	x = "a" | l
	x = "a"
	x = "a"

	out = capsys.readouterr().out

	assert out.count("x = 'a'") == 1

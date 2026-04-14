import os

from helpers import capture, assert_has, assert_not_has

from logeye import log, set_path_mode, toggle_logs, toggle_decorator_log_only


def test_logoff(capsys):
	toggle_logs(False)
	toggle_decorator_log_only(False)

	log("hidden")

	out, ls = capture(capsys)
	assert out == ""


def test_logon(capsys):
	toggle_logs(True)
	toggle_decorator_log_only(False)

	log("visible")

	out, ls = capture(capsys)
	assert_has(out, "visible")


def test_path_modes(capsys):
	toggle_logs(True)
	toggle_decorator_log_only(False)

	set_path_mode("absolute")
	log("test")

	out, ls = capture(capsys)

	if os.name == "nt":
		assert_has(out, "\\")
	else:
		assert_has(out, "/")


def test_decorator_only_blocks_normal_logs(capsys):
	toggle_logs(True)
	toggle_decorator_log_only(True)

	log("should not appear")

	out, ls = capture(capsys)
	assert out == ""


def test_decorator_only_allows_decorated(capsys):
	toggle_logs(True)
	toggle_decorator_log_only(True)

	@log
	def foo():
		x = 10
		return x

	foo()

	out, ls = capture(capsys)
	assert_has(out, "foo")


def test_level_call_only(capsys):
	toggle_logs(True)
	toggle_decorator_log_only(False)

	@log(level="call")
	def foo():
		x = 10
		return x

	foo()

	out, ls = capture(capsys)

	assert_has(out, "(call)")
	assert_has(out, "(return)")
	assert_not_has(out, "(set)")


def test_level_state(capsys):
	toggle_logs(True)
	toggle_decorator_log_only(False)

	@log(level="state")
	def foo():
		x = 10
		return x

	foo()

	out, ls = capture(capsys)

	assert_has(out, "(set)")
	assert_not_has(out, "(call)")


def test_filter_variables(capsys):
	toggle_logs(True)
	toggle_decorator_log_only(False)

	@log(filter=["x"])
	def foo():
		x = 10
		y = 20
		return x + y

	foo()

	out, ls = capture(capsys)

	assert_has(out, "foo.x")
	assert_not_has(out, "foo.y")

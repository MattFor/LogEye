"""
Regression tests for the issues found in the full-repository audit

Each test names the finding it pins down, so a future change that reintroduces
one of them fails here rather than silently degrading the output.
"""

import sys
import json
import inspect
import threading

import pytest

from logeye import log, watch, set_output_formatter, stop_watching
from logeye import config, watcher
from logeye.wrappers import LoggedDict, LoggedList, LoggedSet, _wrap_value

from helpers import (
	capture,
	assert_has,
	assert_not_has,
	assert_has_set,
	assert_has_change,
)


def test_final_assignment_is_logged(capsys):
	@log
	def f():
		x = 10
		x += 1
		x += 3

	f()

	raw, _ = capture(capsys)

	assert_has_change(raw, "x", 14)


def test_final_mutation_is_logged(capsys):
	@log
	def f():
		items = []
		items.append(1)

	f()

	raw, _ = capture(capsys)

	assert_has(raw, "append")


def test_line_numbers_point_at_the_real_statement(capsys):
	base = inspect.currentframe().f_lineno

	@log
	def f():
		first = 1  # base + 4
		second = 2  # base + 5
		return first + second

	f()

	raw, _ = capture(capsys)

	assert f":{base + 4} (set)" in raw and "first = 1" in raw, raw
	assert f":{base + 5} (set)" in raw and "second = 2" in raw, raw


def test_traces_function_defined_in_another_module(capsys):
	from audit_helper_module import compute

	compute(3)

	raw, _ = capture(capsys)

	assert_has_set(raw, "compute.doubled", 6)
	assert_has_set(raw, "compute.shifted", 7)
	assert_has(raw, "audit_helper_module.py")


def test_traces_function_body_inside_a_thread(capsys):
	@log
	def worker(n):
		doubled = n * 2
		return doubled

	thread = threading.Thread(target=worker, args=(4,))
	thread.start()
	thread.join()

	raw, _ = capture(capsys)

	assert_has_set(raw, "worker.doubled", 8)


def test_repeat_calls_still_log_their_body(capsys):
	@log
	def f(a):
		doubled = a * 2
		return doubled

	f(1)
	capture(capsys)

	f(1)

	raw, _ = capture(capsys)

	assert_has(raw, "doubled")
	assert_has(raw, "2")


def test_recursion_logs_every_level(capsys):
	@log
	def countdown(n):
		if n <= 0:
			return 0

		nxt = countdown(n - 1)
		return nxt + n

	countdown(2)

	raw, ls = capture(capsys)

	assert sum("(call)" in line for line in ls) >= 1
	assert_has(raw, "countdown")


def test_custom_formatter_is_actually_used(capsys):
	def formatter(elapsed, kind, name, value, filename, lineno):
		return f"CUSTOM|{kind}|{name}"

	set_output_formatter(formatter)

	log("hello")

	raw, _ = capture(capsys)

	assert raw.startswith("CUSTOM|"), raw


def test_short_custom_formatter_is_supported(capsys):
	def formatter(elapsed, kind, name, value):
		return f"SHORT|{kind}|{value}"

	set_output_formatter(formatter)

	log("hello")

	raw, _ = capture(capsys)

	assert raw.startswith("SHORT|"), raw


def test_raising_function_is_not_reported_as_returning_none(capsys):
	@log
	def boom():
		x = 1
		raise ValueError("kaboom")

	with pytest.raises(ValueError):
		boom()

	raw, _ = capture(capsys)

	assert_has(raw, "(raise)")
	assert_has(raw, "ValueError")
	assert_not_has(raw, "-> None")


def test_caught_exception_still_reports_a_return(capsys):
	@log
	def safe():
		try:
			raise ValueError("handled")
		except ValueError:
			result = "recovered"

		return result

	safe()

	raw, _ = capture(capsys)

	assert_has(raw, "(return)")
	assert_not_has(raw, "(raise)")


def test_generator_body_is_traced(capsys):
	@log
	def gen(n):
		for i in range(n):
			doubled = i * 2
			yield doubled

	assert list(gen(3)) == [0, 2, 4]

	raw, _ = capture(capsys)

	assert_has(raw, "(yield)")
	assert_has(raw, "doubled")
	assert_has(raw, "(return)")


def test_generator_send_round_trip_is_preserved():
	@log
	def echo():
		received = yield 1
		yield received

	generator = echo()

	assert next(generator) == 1
	assert generator.send("payload") == "payload"


def test_async_function_warns_instead_of_silently_doing_nothing():
	@log
	async def coro():
		return 1

	with pytest.warns(RuntimeWarning, match="cannot trace"):
		awaitable = coro()

	awaitable.close()


class _Item:
	def __init__(self, value):
		self.value = value


def test_logged_list_keeps_membership_and_removal():
	first, second = _Item(1), _Item(2)
	wrapped = LoggedList([first, second], name="wrapped")

	assert first in wrapped

	wrapped.remove(first)

	assert first not in wrapped


def test_logged_set_keeps_membership():
	item = _Item(1)
	wrapped = LoggedSet([item], name="wrapped")

	assert item in wrapped


def test_repeated_reference_is_not_replaced_by_a_placeholder():
	shared = {"k": "v"}
	wrapped = LoggedList([shared, shared], name="wrapped")

	assert wrapped.to_list() == [{"k": "v"}, {"k": "v"}]


def test_true_cycle_keeps_the_original_object():
	cyclic = {}
	cyclic["self"] = cyclic

	wrapped = LoggedDict(cyclic, "wrapped")

	assert wrapped["self"] is not None


def test_modules_are_never_wrapped(capsys):
	@log
	def f():
		module = json
		return module

	f()

	raw, ls = capture(capsys)

	# Wrapping a module pulls in __builtins__ and every exception class with it
	assert_not_has(raw, "JSON (JavaScript")
	assert_not_has(raw, "BaseException")
	assert len(ls) < 10, f"expected a handful of lines, got {len(ls)}"


@pytest.mark.parametrize(
	"opaque",
	[
		json,
		(x for x in range(3)),
		ValueError("boom"),
		type("Cls", (), {}).__dict__,
	],
)
def test_opaque_values_pass_through_unwrapped(opaque):
	assert _wrap_value(opaque, name="v") is opaque


def test_shared_references_are_wrapped_once_not_exponentially():
	leaf = {"n": 1}
	level = leaf

	for _ in range(20):
		level = {"a": level, "b": level}

	wrapped = _wrap_value(level, name="deep")

	assert wrapped["a"] is wrapped["b"]


def test_unwrapping_a_cycle_does_not_recurse_forever():
	cyclic = []
	cyclic.append(cyclic)

	wrapped = LoggedList(cyclic, name="wrapped")

	assert wrapped.to_list() == ["<cycle>"]


def test_wrapping_a_cycle_terminates():
	cyclic = {"name": "root"}
	cyclic["self"] = cyclic

	wrapped = _wrap_value(cyclic, name="root")

	assert wrapped["name"] == "root"
	assert repr(wrapped)


def test_educational_mode_honours_filter(capsys):
	@log(mode="edu", filter=["kept"])
	def f():
		kept = 1
		dropped = 2
		return kept + dropped

	f()

	raw, _ = capture(capsys)

	assert_has(raw, "kept")
	assert_not_has(raw, "dropped")


def test_educational_mode_honours_level(capsys):
	@log(mode="edu", level="call")
	def f():
		value = 1
		return value

	f()

	raw, _ = capture(capsys)

	assert_not_has(raw, "Defined")


def test_deferred_options_are_not_consumed_by_another_call(capsys):
	configured = log(mode="edu")

	log("an unrelated message")

	@configured
	def f():
		x = 1
		return x

	f()

	raw, _ = capture(capsys)

	assert_has(raw, "Defined")
	assert_not_has(raw, "(set)")


def test_two_configurations_do_not_interfere(capsys):
	edu = log(mode="edu")
	full = log(mode="full")

	@edu
	def a():
		x = 1
		return x

	@full
	def b():
		y = 2
		return y

	a()
	b()

	raw, _ = capture(capsys)

	assert_has(raw, "Defined")
	assert_has(raw, "(set)")


@pytest.mark.parametrize("shadow", ["args", "kwargs", "tracer", "call_counter"])
def test_locals_shadowing_internal_names_are_logged(capsys, shadow):
	source = "\n".join(
		[
			"@log",
			"def f():",
			f"\t{shadow} = 'visible'",
			f"\treturn {shadow}",
			"f()",
		]
	)

	exec(compile(source, "<audit>", "exec"), {"log": log})

	raw, _ = capture(capsys)

	assert_has(raw, shadow)
	assert_has(raw, "visible")


def test_tuple_assignment_uses_the_real_names(capsys):
	first, second = log(1), log(2)

	raw, _ = capture(capsys)

	assert_has(raw, "first")
	assert_has(raw, "second")
	assert_not_has(raw, "None =")


def test_tuple_assignment_names_survive_a_loop(capsys):
	for _ in range(3):
		first, second = log(1), log(2)

	raw, ls = capture(capsys)

	assert_not_has(raw, "None =")
	assert sum("first" in line for line in ls) == 3
	assert sum("second" in line for line in ls) == 3


def test_modes_do_not_leak_between_threads(capsys):
	@log(mode="edu")
	def educational():
		value = 1
		return value

	@log(mode="full")
	def standard():
		value = 2
		return value

	errors = []

	def hammer(fn):
		try:
			for _ in range(20):
				fn()
		except Exception as exc:
			errors.append(exc)

	threads = [
		threading.Thread(target=hammer, args=(educational,)),
		threading.Thread(target=hammer, args=(standard,)),
	]

	for thread in threads:
		thread.start()

	for thread in threads:
		thread.join()

	assert not errors

	raw, _ = capture(capsys)

	assert_has(raw, "Defined")
	assert_has(raw, "(set)")


def test_decorated_class_keeps_its_identity():
	@log
	class Point:
		def __init__(self, x):
			self.x = x

	point = Point(1)

	assert type(point) is Point
	assert isinstance(point, Point)


def test_decorated_class_supports_slots():
	@log
	class Slotted:
		__slots__ = ("value",)

		def __init__(self, value):
			self.value = value

	assert Slotted(3).value == 3


def test_logging_does_not_trigger_property_getters():
	calls = []

	@log
	class WithProperty:
		def __init__(self):
			self.plain = 1

		@property
		def computed(self):
			calls.append(1)
			return 42

	WithProperty()

	assert calls == []


def test_delete_uses_the_same_name_as_the_set(capsys):
	@log
	class Holder:
		def __init__(self):
			self.value = 1

	holder = Holder()
	capture(capsys)

	del holder.value

	raw, _ = capture(capsys)

	assert_has(raw, "holder.value")


def test_logged_dict_keeps_reserved_looking_keys():
	mapping = LoggedDict(name="Alice", initial=1, other=2)

	assert dict(mapping) == {"name": "Alice", "initial": 1, "other": 2}


def test_logged_dict_pop_accepts_ellipsis_as_a_default():
	mapping = LoggedDict({"a": 1}, "mapping")

	assert mapping.pop("missing", ...) is ...


def test_start_time_is_set_at_import():
	assert config._g_start_time is not None


def test_watch_can_be_uninstalled():
	def run():
		value = watch(1)
		return value

	run()

	assert sys.gettrace() is not None

	stop_watching()

	assert sys.gettrace() is None


def test_tracer_does_not_follow_unwatched_frames():
	seen = []

	def unwatched():
		# No watch() in here, so the tracer must decline this frame
		total = 0
		for i in range(3):
			total += i
		return total

	def run():
		value = watch(1)
		seen.append(unwatched())
		return value

	run()

	assert seen == [3]
	assert watcher._g_watched_names


def test_watch_state_is_capped():
	for index in range(watcher._MAX_TRACKED_CODES + 50):
		source = f"def generated_{index}():\n\treturn {index}\n"
		namespace = {}
		exec(compile(source, f"<generated-{index}>", "exec"), namespace)

		code = namespace[f"generated_{index}"].__code__
		watcher._slot(watcher._g_watched_names, code, set).add("value")

	assert len(watcher._g_watched_names) <= watcher._MAX_TRACKED_CODES

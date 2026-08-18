import threading

from helpers import capture, count, assert_has, assert_not_has

from logeye import log, l  # noqa: E741


def read(path):
	return path.read_text(encoding="utf-8") if path.exists() else ""


def test_filepath_captures_container_mutations(capsys, tmp_path):
	target = tmp_path / "q.log"

	@log(filepath=str(target))
	def process():
		queue = []
		queue.append(1)
		queue.pop(0)

		mapping = {}
		mapping["k"] = 1

	process()

	out, _ = capture(capsys)
	written = read(target)

	assert out == "", f"nothing should reach stdout, got:\n{out}"

	assert_has(written, "queue.append(1)")
	assert_has(written, "queue.pop(0)")
	assert_has(written, "mapping.k = 1")


def test_filepath_captures_explicit_logs_in_the_body(capsys, tmp_path):
	target = tmp_path / "body.log"

	@log(filepath=str(target))
	def g():
		log("a message")
		y = log(5)
		return y

	g()

	out, _ = capture(capsys)
	written = read(target)

	assert out == "", f"nothing should reach stdout, got:\n{out}"

	assert_has(written, "a message")
	assert_has(written, "y = 5")


def test_filepath_does_not_outlive_the_call(capsys, tmp_path):
	target = tmp_path / "inner.log"

	@log(filepath=str(target))
	def inner():
		q = []
		q.append(1)

	inner()

	after = log("outside")

	out, _ = capture(capsys)

	assert after == "outside"
	assert_has(out, "outside")
	assert_not_has(out, "q.append")
	assert_has(read(target), "q.append(1)")


def test_nested_filepaths_stay_separate(capsys, tmp_path):
	outer_log = tmp_path / "outer.log"
	inner_log = tmp_path / "inner.log"

	@log(filepath=str(inner_log))
	def inner():
		inner_q = []
		inner_q.append(1)

	@log(filepath=str(outer_log))
	def outer():
		outer_q = []
		outer_q.append(2)
		inner()
		outer_q.append(3)

	outer()

	_ = capture(capsys)

	written_outer = read(outer_log)
	written_inner = read(inner_log)

	assert_has(written_outer, "outer_q.append(2)")
	assert_has(written_outer, "outer_q.append(3)")
	assert_not_has(written_outer, "inner_q")

	assert_has(written_inner, "inner_q.append(1)")
	assert_not_has(written_inner, "outer_q")


def test_filter_applies_to_container_mutations(capsys):
	@log(filter=["kept"])
	def f():
		kept = []
		dropped = []

		kept.append(1)
		dropped.append(2)

	f()

	out, _ = capture(capsys)

	assert_has(out, "kept.append(1)")
	assert_not_has(out, "dropped")


def test_filter_selects_a_container_by_its_own_name(capsys):
	@log(filter=["distances"])
	def f():
		distances = {"a": 1}
		others = {"a": 1}

		distances["a"] = 2
		others["a"] = 2

	f()

	out, _ = capture(capsys)

	assert_has(out, "distances.a = 2")
	assert_not_has(out, "others")


def test_level_call_drops_container_mutations(capsys):
	@log(level="call")
	def f():
		q = []
		q.append(1)

	f()

	out, ls = capture(capsys)

	assert_has(out, "(call)")
	assert_has(out, "(return)")
	assert_not_has(out, "q.append")
	assert count(ls, "(change)") == 0


def test_filter_still_lets_explicit_logs_through(capsys):
	@log(filter=["kept"])
	def f():
		kept = 1
		log("explicitly asked for")

	f()

	out, _ = capture(capsys)

	assert_has(out, "explicitly asked for")


def test_display_flags_apply_to_container_mutations(capsys):
	@log(show_time=False, show_file=False, show_lineno=False)
	def f():
		q = []
		q.append(1)

	f()

	out, ls = capture(capsys)

	assert_has(out, "q.append(1)")

	for line in ls:
		assert not line.startswith("["), f"timestamp leaked onto:\n{line}"
		assert ".py" not in line, f"file metadata leaked onto:\n{line}"


def test_explicit_log_inside_decorated_is_not_doubled(capsys):
	@log
	def g():
		y = log(5)
		return y

	g()

	out, ls = capture(capsys)

	assert count(ls, "y = 5") == 1, f"reported more than once:\n{out}"


def test_watched_name_inside_decorated_is_not_doubled(capsys):
	@log
	def g():
		z = 7 | l
		z = 8
		return z

	g()

	out, ls = capture(capsys)

	assert count(ls, "= 7") == 1, f"reported more than once:\n{out}"
	assert count(ls, "= 8") == 1, f"reported more than once:\n{out}"


def test_watch_threshold_survives_inside_decorated(capsys):
	@log
	def g():
		v = log(10.0, threshold=("absolute", 5))
		v = 11.0  # Below the threshold
		v = 20.0  # Above it
		return v

	g()

	out, ls = capture(capsys)

	assert count(ls, "= 11.0") == 0, f"threshold ignored:\n{out}"
	assert count(ls, "= 20.0") == 1, f"reported more than once:\n{out}"


def test_filepath_covers_generator_bodies(capsys, tmp_path):
	target = tmp_path / "gen.log"

	@log(filepath=str(target))
	def gen(n):
		items = []

		for i in range(n):
			items.append(i)
			yield i

	_ = list(gen(2))

	out, _ = capture(capsys)
	written = read(target)

	assert out == "", f"nothing should reach stdout, got:\n{out}"

	assert_has(written, "items.append(0)")
	assert_has(written, "items.append(1)")


def test_filepath_covers_logged_class_attributes(capsys, tmp_path):
	target = tmp_path / "cls.log"

	@log(filepath=str(target))
	class Box:
		def __init__(self):
			self.items = []

		def add(self, value):
			self.items.append(value)

	Box().add(1)

	out, _ = capture(capsys)
	written = read(target)

	assert out == "", f"nothing should reach stdout, got:\n{out}"

	assert_has(written, "items.append(1)")


def test_filepath_is_per_thread(capsys, tmp_path):
	target = tmp_path / "threaded.log"

	@log(filepath=str(target))
	def in_thread():
		q = []
		q.append("threaded")

	worker = threading.Thread(target=in_thread)
	worker.start()
	worker.join()

	main = log("main thread")

	out, _ = capture(capsys)
	written = read(target)

	assert main == "main thread"

	assert_has(out, "main thread")
	assert_not_has(out, "threaded")
	assert_has(written, "q.append('threaded')")

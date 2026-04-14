from helpers import (
	count,
	lines,
	capture,
	assert_has,
	assert_line_count,
	assert_has_change,
	assert_nested_order,
)

from logeye import log


def test_object_tracking(capsys):
	obj = log({"x": 1})
	lines(capsys)

	obj.x = 10

	out, ls = capture(capsys)

	assert_has_change(out, "obj.x", 10)
	assert_line_count(ls, 1)


def test_nested_object(capsys):
	obj = log({"a": {"b": 1}})
	lines(capsys)

	obj.a.b = 5

	out, ls = capture(capsys)

	assert_has_change(out, "a.b", 5)
	assert_line_count(ls, 1)


def test_deep_nested_change(capsys):
	obj = log({"a": {"b": {"c": 1}}})
	lines(capsys)

	obj.a.b.c = 99

	out, ls = capture(capsys)

	assert_has_change(out, "a.b.c", 99)
	assert_line_count(ls, 1)


def test_multiple_nested_branches(capsys):
	obj = log({"a": {"b": 1}, "x": {"y": 2}})
	lines(capsys)

	obj.a.b = 10
	obj.x.y = 20

	out, ls = capture(capsys)

	assert_has_change(out, "a.b", 10)
	assert_has_change(out, "x.y", 20)
	assert count(ls, "a.b") == 1
	assert len(ls) == 2


def test_list_inside_object(capsys):
	obj = log({"arr": [1, 2, 3]})
	lines(capsys)

	obj.arr[0] = 99

	out, ls = capture(capsys)

	assert_has(out, "arr")
	assert_has(out, "99")
	assert_line_count(ls, 1)


def test_nested_list_of_dicts(capsys):
	obj = log({"items": [{"x": 1}, {"x": 2}]})
	lines(capsys)

	obj["items"][1]["x"] = 42

	out, ls = capture(capsys)

	assert_has(out, "items")
	assert_has(out, "42")
	assert_line_count(ls, 1)


def test_dict_in_list_in_dict(capsys):
	obj = log({"a": [{"b": {"c": 1}}]})
	lines(capsys)

	obj.a[0].b.c = 7

	out, ls = capture(capsys)

	assert_has(out, "a")
	assert_has(out, "c")
	assert_has(out, "7")
	assert_line_count(ls, 1)


def test_replace_nested_object(capsys):
	obj = log({"a": {"b": 1}})
	lines(capsys)

	obj.a = {"b": 999}

	out, ls = capture(capsys)

	assert_has_change(out, "a", {"b": 999})
	assert_line_count(ls, 1)


def test_reassign_top_level_object(capsys):
	obj = log({"x": 1})
	lines(capsys)

	obj = {"x": 2}

	out, ls = capture(capsys)

	# Reassignment should NOT be tracked anymore
	assert out == ""


def test_reassign_nested_then_modify(capsys):
	obj = log({"a": {"b": 1}})
	lines(capsys)

	obj.a = {"b": 2}
	obj.a.b = 3

	out, ls = capture(capsys)

	assert_has_change(out, "a", {"b": 2})
	assert_has_change(out, "a.b", 3)
	assert_nested_order(ls, "a", {"b": 2}, "a.b", 3)


def test_multiple_objects(capsys):
	obj1 = log({"x": 1})
	obj2 = log({"y": 2})
	lines(capsys)

	obj1.x = 10
	obj2.y = 20

	out, ls = capture(capsys)

	assert_has_change(out, "x", 10)
	assert_has_change(out, "y", 20)
	assert len(ls) == 2


def test_cascade_mutation(capsys):
	obj = log({"a": {"b": {"c": 1}}})
	lines(capsys)

	obj.a.b = {"c": 2}
	obj.a.b.c = 3

	out, ls = capture(capsys)

	assert_has_change(out, "a.b", {"c": 2})
	assert_has_change(out, "a.b.c", 3)
	assert_nested_order(ls, "a.b", {"c": 2}, "a.b.c", 3)


def test_shared_reference_mutation(capsys):
	shared = {"val": 1}
	obj = log({"a": shared, "b": shared})
	lines(capsys)

	obj.a.val = 5

	out, ls = capture(capsys)

	assert_has(out, "val")
	assert_has(out, "5")
	assert_line_count(ls, 1)  # Should NOT double emit


def test_self_reference(capsys):
	obj = {}
	obj["self"] = obj

	wrapped = log(obj)
	lines(capsys)

	wrapped["self"] = {}

	out, ls = capture(capsys)

	assert_has(out, "self")
	assert len(ls) <= 2  # Must not explode


def test_large_nested_structure(capsys):
	obj = log(
		{
			"a": {"b": {"c": [1, 2, {"d": 4}]}},
			"x": [{"y": 10}, {"z": 20}],
		}
	)
	lines(capsys)

	obj.a.b.c[2]["d"] = 999
	obj.x[1].z = 777

	out, ls = capture(capsys)

	assert_has_change(out, "d", 999)
	assert_has_change(out, "z", 777)
	assert len(ls) == 2

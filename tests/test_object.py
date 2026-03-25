from logeye import log


def test_object_tracking(capsys):
	obj = log({"x": 1})

	obj.x = 10

	out = capsys.readouterr().out
	assert "obj.x" in out
	assert "10" in out


def test_nested_object(capsys):
	obj = log({"a": {"b": 1}})

	obj.a.b = 5

	out = capsys.readouterr().out
	assert "a.b" in out


def test_deep_nested_change(capsys):
	obj = log({"a": {"b": {"c": 1}}})

	obj.a.b.c = 99

	out = capsys.readouterr().out
	assert "a.b.c" in out
	assert "99" in out


def test_multiple_nested_branches(capsys):
	obj = log({"a": {"b": 1}, "x": {"y": 2}})

	obj.a.b = 10
	obj.x.y = 20

	out = capsys.readouterr().out
	assert "a.b" in out
	assert "x.y" in out


def test_list_inside_object(capsys):
	obj = log({"arr": [1, 2, 3]})

	obj.arr[0] = 99

	out = capsys.readouterr().out
	assert "arr" in out
	assert "99" in out


def test_nested_list_of_dicts(capsys):
	obj = log({"items": [{"x": 1}, {"x": 2}]})

	obj["items"][1]["x"] = 42

	out = capsys.readouterr().out
	assert "items" in out
	assert "42" in out


def test_dict_in_list_in_dict(capsys):
	obj = log({"a": [{"b": {"c": 1}}]})

	obj.a[0].b.c = 7

	out = capsys.readouterr().out
	assert "a" in out
	assert "c" in out
	assert "7" in out


def test_replace_nested_object(capsys):
	obj = log({"a": {"b": 1}})

	obj.a = {"b": 999}

	out = capsys.readouterr().out
	assert "a" in out
	assert "999" in out


def test_reassign_top_level_object(capsys):
	obj = log({"x": 1})

	obj = {"x": 2}

	out = capsys.readouterr().out
	# Depending on design, this may not track anymore
	assert "x" in out


def test_reassign_nested_then_modify(capsys):
	obj = log({"a": {"b": 1}})

	obj.a = {"b": 2}
	obj.a.b = 3

	out = capsys.readouterr().out
	assert "3" in out


def test_multiple_objects(capsys):
	obj1 = log({"x": 1})
	obj2 = log({"y": 2})

	obj1.x = 10
	obj2.y = 20

	out = capsys.readouterr().out
	assert "obj1.x" in out or "x" in out
	assert "obj2.y" in out or "y" in out


def test_cascade_mutation(capsys):
	obj = log({"a": {"b": {"c": 1}}})

	obj.a.b = {"c": 2}
	obj.a.b.c = 3

	out = capsys.readouterr().out
	assert "2" in out
	assert "3" in out


def test_shared_reference_mutation(capsys):
	shared = {"val": 1}
	obj = log({"a": shared, "b": shared})

	obj.a.val = 5

	out = capsys.readouterr().out

	# Depending on implementation, both may reflect
	assert "val" in out
	assert "5" in out


def test_self_reference(capsys):
	obj = {}
	obj["self"] = obj

	wrapped = log(obj)

	# Avoid infinite recursion issues
	wrapped["self"] = {}

	out = capsys.readouterr().out
	assert "self" in out


def test_large_nested_structure(capsys):
	obj = log({
		"a": {"b": {"c": [1, 2, {"d": 4}]}},
		"x": [{"y": 10}, {"z": 20}]
	})

	obj.a.b.c[2]["d"] = 999
	obj.x[1].z = 777

	out = capsys.readouterr().out
	assert "999" in out
	assert "777" in out

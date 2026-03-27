import pytest
from logeye import log, l


def _lines(capsys):
	return [line.strip() for line in capsys.readouterr().out.splitlines() if line.strip()]


def _count(lines, needle):
	return sum(needle in line for line in lines)


@log
class User:
	def __init__(self):
		self.name = "Matt"
		self.active = True

	def rename(self, new_name):
		self.name = new_name
		return self.name

	def toggle(self):
		self.active = not self.active
		return self.active


@log
class Counter:
	def __init__(self):
		self.value = 0

	def inc(self):
		self.value += 1
		return self.value

	def inc_twice(self):
		self.inc()
		self.inc()
		return self.value

	def countdown(self, n):
		if n <= 0:
			return 0
		return self.countdown(n - 1) + 1


@log
class Calc:
	def add(self, a, b):
		return a + b

	def make_adder(self, n):
		return lambda x: x + n

	def outer(self, x):
		def inner(y):
			return x + y

		return inner(3)

	def chain(self, x):
		return (lambda y: (lambda z: x + y + z)(2))(1)


@log
class Profile:
	def __init__(self):
		self.user = {"name": "Matt"}
		self.items = []


@log
class Base:
	def __init__(self):
		self.base = 1


@log
class Child(Base):
	def __init__(self):
		super().__init__()
		self.child = 2


@log
class Empty:
	pass


@log
class SelfRef:
	def __init__(self):
		self.me = self


@log
class WithDict:
	def __init__(self):
		self.data = {"a": 1}


@log
class WithFunc:
	def __init__(self):
		self.func = lambda x: x + 1


@log
class WithList:
	def __init__(self):
		self.items = []


@log
class WithProperty:
	def __init__(self):
		self._x = 1

	@property
	def x(self):
		return self._x

	@x.setter
	def x(self, value):
		self._x = value


@log
class WithStatic:
	@staticmethod
	def ping(x):
		return x + 1


@log
class WithClassMethod:
	value = 10

	@classmethod
	def bump(cls, n):
		return cls.value + n


def test_class_init_emits_once(capsys):
	user = l(User())
	lines = _lines(capsys)

	assert user.name == "Matt"
	assert user.active is True
	assert _count(lines, "User.__init__") == 1
	assert _count(lines, "name") >= 1
	assert _count(lines, "active") >= 1
	assert any("Matt" in line for line in lines)
	assert any("True" in line for line in lines)


def test_class_attribute_assignment(capsys):
	user = l(User())
	_lines(capsys)

	user.name = "For"
	lines = _lines(capsys)

	assert user.name == "For"
	assert len(lines) == 1
	assert _count(lines, "name") == 1
	assert any("For" in line for line in lines)


def test_class_attribute_reassign_order(capsys):
	user = l(User())
	_lines(capsys)

	user.name = "A"
	user.name = "B"
	lines = _lines(capsys)

	assert user.name == "B"
	assert _count(lines, "name") >= 2
	assert any("A" in line for line in lines)
	assert any("B" in line for line in lines)
	first_a = next(i for i, line in enumerate(lines) if "A" in line)
	first_b = next(i for i, line in enumerate(lines) if "B" in line)
	assert first_a < first_b


def test_dynamic_attribute_creation(capsys):
	user = l(User())
	_lines(capsys)

	user.new_field = 123
	lines = _lines(capsys)

	assert hasattr(user, "new_field")
	assert user.new_field == 123
	assert _count(lines, "new_field") == 1
	assert any("123" in line for line in lines)


def test_delete_attribute_emits_deleted_once(capsys):
	user = l(User())
	_lines(capsys)

	del user.name
	lines = _lines(capsys)

	assert not hasattr(user, "name")
	assert _count(lines, "deleted") == 1
	assert _count(lines, "name") == 1


def test_private_attribute_is_marked(capsys):
	user = l(User())
	_lines(capsys)

	user._hidden = 42
	lines = _lines(capsys)

	assert user._hidden == 42
	assert _count(lines, "_hidden") == 1
	assert _count(lines, "<priv>") == 0
	assert _count(lines, "42") == 1


def test_multiple_instances_stay_separate(capsys):
	u1 = l(User())
	u2 = l(User())
	_lines(capsys)

	u1.name = "A"
	u2.name = "B"
	lines = _lines(capsys)

	assert u1.name == "A"
	assert u2.name == "B"
	assert any("A" in line for line in lines)
	assert any("B" in line for line in lines)
	assert _count(lines, "name") >= 2


def test_multiple_attributes(capsys):
	user = l(User())
	_lines(capsys)

	user.age = 20
	user.city = "NY"
	lines = _lines(capsys)

	assert user.age == 20
	assert user.city == "NY"
	assert _count(lines, "age") == 1
	assert _count(lines, "city") == 1
	assert any("20" in line for line in lines)
	assert any("NY" in line for line in lines)


def test_method_mutation(capsys):
	c = l(Counter())
	_lines(capsys)

	result = c.inc()
	lines = _lines(capsys)

	assert result == 1
	assert c.value == 1
	assert _count(lines, "value") >= 1
	assert any("1" in line for line in lines)
	assert any("(call)" in line and "inc" in line for line in lines)
	assert any("(return)" in line and "inc" in line for line in lines)


def test_multiple_method_calls(capsys):
	c = l(Counter())
	_lines(capsys)

	c.inc()
	c.inc()
	lines = _lines(capsys)

	assert c.value == 2
	assert _count(lines, "inc") >= 2
	assert any("2" in line for line in lines)


def test_method_mutation_strict_order(capsys):
	c = l(Counter())
	_lines(capsys)

	c.inc()
	lines = _lines(capsys)

	assert len(lines) >= 1
	assert any("value" in line for line in lines)
	assert any("1" in line for line in lines)


def test_recursive_method_tracking(capsys):
	c = l(Counter())
	_lines(capsys)

	result = c.countdown(3)
	lines = _lines(capsys)

	assert result == 3
	assert _count(lines, "countdown") >= 3
	assert any("3" in line for line in lines)
	assert any("2" in line for line in lines)
	assert any("1" in line for line in lines)


def test_recursive_method_zero_base_case(capsys):
	c = l(Counter())
	_lines(capsys)

	result = c.countdown(0)
	lines = _lines(capsys)

	assert result == 0
	assert any("0" in line for line in lines)


def test_method_return(capsys):
	c = l(Calc())
	_lines(capsys)

	res = c.add(2, 3)
	lines = _lines(capsys)

	assert res == 5
	assert any("2" in line for line in lines)
	assert any("3" in line for line in lines)
	assert any("5" in line for line in lines)
	assert any("(call)" in line and "add" in line for line in lines)
	assert any("(return)" in line and "add" in line for line in lines)


def test_method_return_lambda(capsys):
	c = l(Calc())
	_lines(capsys)

	f = c.make_adder(4)
	result = f(3)
	lines = _lines(capsys)

	assert result == 7
	assert any("make_adder" in line for line in lines)
	assert any("4" in line for line in lines)


def test_nested_method_definition(capsys):
	c = l(Calc())
	_lines(capsys)

	res = c.outer(5)
	lines = _lines(capsys)

	assert res == 8
	assert any("outer" in line for line in lines)
	assert any("inner" in line for line in lines)
	assert any("5" in line for line in lines)
	assert any("8" in line for line in lines)


def test_nested_lambda_in_method(capsys):
	c = l(Calc())
	_lines(capsys)

	res = c.chain(5)
	lines = _lines(capsys)

	assert res == 8
	assert any("chain" in line for line in lines)
	assert len(lines) >= 1


def test_method_chaining_logs_multiple_steps(capsys):
	c = l(Calc())
	_lines(capsys)

	a = c.add(1, 2)
	b = c.add(a, 3)
	lines = _lines(capsys)

	assert a == 3
	assert b == 6
	assert any("1" in line for line in lines)
	assert any("2" in line for line in lines)
	assert any("3" in line for line in lines)
	assert any("6" in line for line in lines)
	assert sum("(call)" in line and "add" in line for line in lines) == 2
	assert sum("(return)" in line and "add" in line for line in lines) == 2


def test_method_override(capsys):
	@log
	class A:
		def foo(self):
			return 1

	@log
	class B(A):
		def foo(self):
			return 2

	b = l(B())
	_lines(capsys)

	res = b.foo()
	lines = _lines(capsys)

	assert res == 2
	assert any("2" in line for line in lines)
	assert any("(call)" in line and "foo" in line for line in lines)
	assert any("(return)" in line and "foo" in line for line in lines)


def test_inheritance(capsys):
	c = l(Child())
	lines = _lines(capsys)

	assert c.base == 1
	assert c.child == 2
	assert _count(lines, "base") >= 1
	assert _count(lines, "child") >= 1


def test_property_setter(capsys):
	obj = l(WithProperty())
	_lines(capsys)

	obj.x = 10
	lines = _lines(capsys)

	assert obj.x == 10
	assert any("x" in line for line in lines)
	assert any("10" in line for line in lines)


def test_callable_attribute(capsys):
	obj = l(WithFunc())
	_lines(capsys)

	obj.func = lambda x: x + 2
	lines = _lines(capsys)

	assert callable(obj.func)
	assert _count(lines, "func") >= 1
	assert any("<func" in line for line in lines)


def test_nested_object_mutation_is_logged(capsys):
	p = l(Profile())
	_lines(capsys)

	p.user["name"] = "For"
	lines = _lines(capsys)

	assert p.user["name"] == "For"
	assert any("user" in line for line in lines)
	assert any("name" in line for line in lines)
	assert any("For" in line for line in lines)


def test_list_mutation(capsys):
	obj = l(WithList())
	_lines(capsys)

	obj.items.append(1)
	lines = _lines(capsys)

	assert obj.items == [1]
	assert any("append" in line.lower() for line in lines)
	assert any("1" in line for line in lines)


def test_dict_mutation(capsys):
	obj = l(WithDict())
	_lines(capsys)

	obj.data["a"] = 2
	lines = _lines(capsys)

	assert obj.data["a"] == 2
	assert any("data" in line for line in lines)
	assert any("2" in line for line in lines)


def test_overwrite_method(capsys):
	u = l(User())
	_lines(capsys)

	u.name = lambda: "test"
	lines = _lines(capsys)

	assert callable(u.name)
	assert _count(lines, "name") == 1
	assert any("<func" in line for line in lines)


def test_class_without_init_tracks_new_attrs(capsys):
	e = l(Empty())
	_lines(capsys)

	e.x = 1
	lines = _lines(capsys)

	assert e.x == 1
	assert _count(lines, "x") == 1
	assert any("1" in line for line in lines)


def test_self_reference_does_not_explode(capsys):
	obj = l(SelfRef())
	lines = _lines(capsys)

	assert obj.me is obj
	assert _count(lines, "me") == 1
	assert len(lines) < 20


def test_static_method_called_on_instance(capsys):
	obj = l(WithStatic())
	_lines(capsys)

	res = obj.ping(5)
	lines = _lines(capsys)

	assert res == 6
	assert any("ping" in line for line in lines)


def test_static_method_called_on_class(capsys):
	_lines(capsys)

	res = WithStatic.ping(7)
	lines = _lines(capsys)

	assert res == 8
	assert any("ping" in line for line in lines)


def test_class_method_called_on_instance(capsys):
	obj = l(WithClassMethod())
	_lines(capsys)

	res = obj.bump(5)
	lines = _lines(capsys)

	assert res == 15
	assert any("bump" in line for line in lines)


def test_class_method_called_on_class(capsys):
	_lines(capsys)

	res = WithClassMethod.bump(5)
	lines = _lines(capsys)

	assert res == 15
	assert any("bump" in line for line in lines)


def test_method_local_lambda_tracing(capsys):
	@log
	class LocalLambda:
		def outer(self, n):
			f = lambda x: x + n
			return f(3)

	obj = l(LocalLambda())
	_lines(capsys)

	res = obj.outer(4)
	lines = _lines(capsys)

	assert res == 7
	assert any("outer" in line for line in lines)
	assert any("lambda" in line.lower() or "f" in line for line in lines)


def test_deep_nested_method_definitions(capsys):
	@log
	class Nested:
		def outer(self, x):
			def mid(y):
				def inner(z):
					return x + y + z

				return inner(3)

			return mid(2)

	obj = l(Nested())
	_lines(capsys)

	res = obj.outer(1)
	lines = _lines(capsys)

	assert res == 6
	assert any("outer" in line for line in lines)
	assert any("mid" in line for line in lines)
	assert any("inner" in line for line in lines)

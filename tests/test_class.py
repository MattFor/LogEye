from logeye import log, l


@log
class User:
	def __init__(self):
		self.name = "Matt"


def test_class_logging(capsys):
	user = l(User())
	user.name = "For"

	out = capsys.readouterr().out
	assert "name" in out
	assert "For" in out


def test_multiple_attributes(capsys):
	user = l(User())
	user.age = 20
	user.city = "NY"

	out = capsys.readouterr().out
	assert "age" in out
	assert "city" in out


@log
class Counter:
	def __init__(self):
		self.value = 0

	def inc(self):
		self.value += 1


def test_method_mutation(capsys):
	c = l(Counter())
	c.inc()

	out = capsys.readouterr().out
	assert "value" in out
	assert "1" in out


def test_multiple_method_calls(capsys):
	c = l(Counter())
	c.inc()
	c.inc()

	out = capsys.readouterr().out
	assert "2" in out


@log
class Calc:
	def add(self, a, b):
		return a + b


def test_method_return(capsys):
	c = l(Calc())
	res = c.add(2, 3)

	out = capsys.readouterr().out
	assert "call" in out.lower()
	assert res == 5


@log
class Profile:
	def __init__(self):
		self.user = {"name": "Matt"}


def test_nested_object_attribute(capsys):
	p = l(Profile())
	p.user["name"] = "For"

	out = capsys.readouterr().out
	assert "name" in out
	assert "For" in out


def test_attribute_reassign(capsys):
	user = l(User())
	user.name = "A"
	user.name = "B"

	out = capsys.readouterr().out
	assert "A" in out
	assert "B" in out


def test_dynamic_attribute_creation(capsys):
	user = l(User())
	user.new_field = 123

	out = capsys.readouterr().out
	assert "new_field" in out
	assert "123" in out


def test_delete_attribute(capsys):
	user = l(User())
	del user.name

	out = capsys.readouterr().out
	assert "deleted" in out.lower()


@log
class Base:
	def __init__(self):
		self.base = 1


@log
class Child(Base):
	def __init__(self):
		super().__init__()
		self.child = 2


def test_inheritance(capsys):
	c = l(Child())

	out = capsys.readouterr().out
	assert "base" in out
	assert "child" in out


@log
class A:
	def foo(self):
		return 1


@log
class B(A):
	def foo(self):
		return 2


def test_method_override(capsys):
	b = l(B())
	res = b.foo()

	out = capsys.readouterr().out
	assert res == 2


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


def test_property_setter(capsys):
	obj = l(WithProperty())
	obj.x = 10

	out = capsys.readouterr().out
	assert "10" in out


@log
class WithFunc:
	def __init__(self):
		self.func = lambda x: x + 1


def test_callable_attribute(capsys):
	obj = l(WithFunc())
	obj.func = lambda x: x + 2

	out = capsys.readouterr().out
	assert "<func" in out


def test_multiple_instances(capsys):
	u1 = l(User())
	u2 = l(User())

	u1.name = "A"
	u2.name = "B"

	out = capsys.readouterr().out
	assert "A" in out
	assert "B" in out


@log
class WithList:
	def __init__(self):
		self.items = []


def test_list_mutation(capsys):
	obj = l(WithList())
	obj.items.append(1)

	out = capsys.readouterr().out
	assert "append" in out


@log
class WithDict:
	def __init__(self):
		self.data = {"a": 1}


def test_dict_mutation(capsys):
	obj = l(WithDict())
	obj.data["a"] = 2

	out = capsys.readouterr().out
	assert "2" in out


def test_setting_private_attr(capsys):
	user = l(User())
	user._hidden = 42

	out = capsys.readouterr().out

	assert "_hidden" in out
	assert "<priv>" in out
	assert "42" in out


def test_overwrite_method(capsys):
	u = l(User())
	u.name = lambda: "test"

	out = capsys.readouterr().out
	assert "<func" in out


def test_class_without_init(capsys):
	@log
	class Empty:
		pass

	e = l(Empty())
	e.x = 1

	out = capsys.readouterr().out
	assert "x" in out


def test_self_reference(capsys):
	@log
	class SelfRef:
		def __init__(self):
			self.me = self

	obj = l(SelfRef())

	out = capsys.readouterr().out
	assert "me" in out

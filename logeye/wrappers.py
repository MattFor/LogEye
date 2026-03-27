from __future__ import annotations
from collections.abc import (
	Callable,
	ItemsView,
	Iterable,
	KeysView,
	Mapping,
	ValuesView,
	Iterator,
)

from . import config
from .emmiter import _emit
from .formatting import _path
from .introspection import _caller_frame, _get_location
from typing import Generic, ParamSpec, SupportsIndex, TypeVar, overload


class _BaseLogged:
	_log_name: str


P = ParamSpec("P")

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
L = TypeVar("L", bound=_BaseLogged)


@overload
def _unwrap_value(value: LoggedObject[T]) -> dict[str, object]: ...


@overload
def _unwrap_value(value: LoggedList[T]) -> list[T]: ...


@overload
def _unwrap_value(value: LoggedDict[K, V] | dict[K, V]) -> dict[K, V]: ...


@overload
def _unwrap_value(value: LoggedSet[T] | set[T]) -> set[T]: ...


@overload
def _unwrap_value(value: tuple[T, ...]) -> tuple[T, ...]: ...


@overload
def _unwrap_value(value: object) -> object: ...


def _unwrap_value(value: object):
	"""
	Recursively unwrap logged containers into plain Python values.
	Used for log payloads so mutation logs stay readable
	"""

	if isinstance(value, LoggedObject):
		return value.to_dict()

	if isinstance(value, LoggedList):
		return [_unwrap_value(v) for v in list(value)]

	if isinstance(value, LoggedDict):
		return {k: _unwrap_value(v) for k, v in dict.items(value)}

	if isinstance(value, LoggedSet):
		return {_unwrap_value(v) for v in set(value)}

	if isinstance(value, list):
		return [_unwrap_value(v) for v in value]

	if isinstance(value, tuple):
		return tuple(_unwrap_value(v) for v in value)

	if isinstance(value, set):
		return {_unwrap_value(v) for v in value}

	if isinstance(value, dict):
		return {k: _unwrap_value(v) for k, v in value.items()}

	return value


def _emit_change(
		name: str,
		op: str,
		state: object = None,
		filename: str | None = None,
		lineno: int | None = None,
		**details: object,
):
	"""
	Emit a mutation event with a readable payload
	"""

	if not config._g_enabled:
		return

	payload: dict[str, object] = {"op": op}

	for key, value in details.items():
		payload[key] = _unwrap_value(value)

	if state is not None:
		payload["state"] = _unwrap_value(state)

	_emit("change", name, payload, filename=filename, lineno=lineno)


@overload
def _wrap_value(
		value: Callable[P, T], name: str | None = None, seen: set[int] | None = None
) -> Callable[P, T]: ...


@overload
def _wrap_value(
		value: list[T], name: str | None = ..., seen: set[int] | None = None
) -> LoggedList[T]: ...


@overload
def _wrap_value(
		value: Mapping[K, V], name: str | None = ..., seen: set[int] | None = None
) -> LoggedDict[K, V]: ...


@overload
def _wrap_value(
		value: set[T], name: str | None = ..., seen: set[int] | None = None
) -> LoggedSet[T]: ...


@overload
def _wrap_value(value: L, name: str | None = ..., seen: set[int] | None = None) -> L: ...


@overload
def _wrap_value(value: T, name: str | None = ..., seen: set[int] | None = None) -> T: ...


# TODO: Maybe use a memoization map for recursive calls so we can maintain the actual values?
# TODO: Kind of hard to do but may be worth it later
def _wrap_value(
		value: object, name: str | None = None, seen: set[int] | None = None
) -> object:
	"""
	Recursively wrap values so nested structures are tracked

	- mappings -> LoggedDict
	- lists    -> LoggedList
	- sets     -> LoggedSet
	- objects with __dict__ -> LoggedObject
	- already wrapped -> returned as-is
	"""

	if seen is None:
		seen = set()

	obj_id = id(value)

	# Break the cycle immediately!!!
	# We have entered a recursive object call!
	if obj_id in seen:
		return "<recursive self>"  # Can also be value

	seen.add(obj_id)

	safe_name = name or "NO_NAME_ERR"

	if callable(value):
		return value

	if isinstance(value, _BaseLogged):
		return value

	if isinstance(value, dict):
		return LoggedDict(value, name=safe_name, _seen=seen)

	if isinstance(value, Mapping):
		return LoggedDict(dict(value), name=safe_name, _seen=seen)

	if isinstance(value, list):
		return LoggedList(value, name=safe_name, _seen=seen)

	if isinstance(value, dict):
		return LoggedDict(value, name=safe_name, _seen=seen)

	if isinstance(value, Mapping):
		return LoggedDict(dict(value), name=safe_name, _seen=seen)

	if isinstance(value, set):
		return LoggedSet(value, name=safe_name, _seen=seen)

	if hasattr(value, "__dict__") and not isinstance(value, type):
		return LoggedObject(value, name=safe_name, _seen=seen)

	return value


class LoggedObject(_BaseLogged, Generic[T]):
	"""
	A wrapper around mappings / objects that logs all mutations

	- Stores data internally in `_data`
	- Tracks attribute and item changes
	- Recursively wraps nested values
	"""

	_data: dict[str, object]

	def __init__(
			self, initial: T = None, name: str = "set", _seen: set[int] | None = None
	) -> None:
		# Prevent recursive self-calls expanding into an infinite recursion chain
		if _seen is None:
			_seen = set()

		object.__setattr__(self, "_seen", _seen)

		# NOTE: why setattr? is there a specific reason? regular assignment
		# is both faster and type safe.
		# NOTE:  I defined __setattr__, so every normal assignment would
		# trigger wrapping / logging during init and that could potentially recurse away or corrupt some internal state
		# at least that's how I understand it, so I just use __setattr__ to bypass the custom logic
		object.__setattr__(self, "_data", {})
		object.__setattr__(self, "_log_name", name)

		if initial is None:
			return

		if isinstance(initial, Mapping):
			items = initial.items()
		elif hasattr(initial, "__dict__"):
			items = vars(initial).items()
		else:
			raise TypeError(
				"LoggedObject can only wrap mappings or objects with __dict__"
			)

		for key, value in items:
			self._data[key] = _wrap_value(value, name=f"{name}.{key}", seen=_seen)

	def __getattr__(self, name: str) -> object:
		data = object.__getattribute__(self, "_data")

		if name in data:
			return data[name]

		raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

	# WARN: Too dangerous, but we might get confident enough to work with this in the future
	# obj.items[1].x = 42 exposes the failure
	# def __getattribute__(self, name: str):
	# 	if name.startswith("_"):
	# 		return object.__getattribute__(self, name)
	#
	# 	data = object.__getattribute__(self, "_data")
	#
	# 	if name in data:
	# 		return data[name]
	#
	# 	return object.__getattribute__(self, name)

	def __setattr__(self, name: str, value: object) -> None:
		if name.startswith("_"):
			object.__setattr__(self, name, value)
			return

		data = object.__getattribute__(self, "_data")
		log_name = object.__getattribute__(self, "_log_name")

		wrapped = _wrap_value(value, name=f"{log_name}.{name}")
		data[name] = wrapped

		frame = _caller_frame()
		try:
			filename, lineno = _get_location(frame)

			if callable(wrapped):
				_emit_change(
					f"{log_name}.{name}",
					"setattr",
					state=wrapped,
					filename=filename,
					lineno=lineno,
					value=f"<func {_path(wrapped)}>",
				)
			else:
				_emit_change(
					f"{log_name}.{name}",
					"setattr",
					state=wrapped,
					filename=filename,
					lineno=lineno,
					value=wrapped,
				)
		finally:
			del frame

	def __getitem__(self, key: str) -> object:
		return self._data[key]

	def __setitem__(self, key, value: object) -> None:
		log_name = object.__getattribute__(self, "_log_name")
		wrapped = _wrap_value(value, name=f"{log_name}.{key}")
		self._data[key] = wrapped

		frame = _caller_frame()
		try:
			filename, lineno = _get_location(frame)

			_emit_change(
				f"{log_name}.{key}",
				"setitem",
				state=wrapped,
				filename=filename,
				lineno=lineno,
				value=_unwrap_value(value),
			)
		finally:
			del frame

	def __delattr__(self, name: str) -> None:
		if name.startswith("_"):
			raise AttributeError(name)

		data = object.__getattribute__(self, "_data")
		log_name = object.__getattribute__(self, "_log_name")

		if name not in data:
			raise AttributeError(name)

		del data[name]

		frame = _caller_frame()
		try:
			filename, lineno = _get_location(frame)
			_emit(
				"set", f"{log_name}.{name}", "<deleted>", filename=filename, lineno=lineno
			)
		finally:
			del frame

	def __delitem__(self, key: str) -> None:
		log_name = object.__getattribute__(self, "_log_name")
		del self._data[key]

		frame = _caller_frame()
		try:
			filename, lineno = _get_location(frame)
			_emit(
				"set", f"{log_name}.{key}", "<deleted>", filename=filename, lineno=lineno
			)
		finally:
			del frame

	def __iter__(self) -> Iterator[str]:
		return iter(self._data)

	def __len__(self) -> int:
		return len(self._data)

	def __contains__(self, key: str) -> bool:
		return key in self._data

	def get(self, key: str, default: T = None) -> object | T:
		return self._data.get(key, default)

	def keys(self) -> KeysView[object]:
		return self._data.keys()

	def values(self) -> ValuesView[object]:
		return self._data.values()

	def items(self) -> ItemsView[str, object]:
		return self._data.items()

	def to_dict(self) -> dict[str, object]:
		def unwrap(v):
			return _unwrap_value(v)

		return {k: unwrap(v) for k, v in self._data.items()}

	def __repr__(self) -> str:
		return repr(self.to_dict())  # f"{type(self).__name__}({self._data!r})"

	def __dir__(self) -> list[str]:
		return sorted(set(super().__dir__()) | set(self._data.keys()))


class LoggedList(list[T], _BaseLogged, Generic[T]):
	"""
	List wrapper that logs mutations like append, sort, pop, extend, etc
	"""

	def __init__(
			self,
			initial: Iterable[T] | None = None,
			name: str = "set",
			_seen: set[int] | None = None,
	):
		# Prevent recursive self-calls expanding into an infinite recursion chain
		if _seen is None:
			_seen = set()

		object.__setattr__(self, "_seen", _seen)
		object.__setattr__(self, "_log_name", name)

		if initial is None:
			initial: list[T] = []

		items = [
			_wrap_value(v, name=f"{name}[{i}]", seen=_seen)
			for i, v in enumerate(initial or [])
		]
		super().__init__(items)

	def _emit(self, op: str, **details: object) -> None:
		frame = _caller_frame()
		try:
			filename, lineno = _get_location(frame)
			_emit_change(
				self._log_name,
				op,
				state=self,
				filename=filename,
				lineno=lineno,
				**details,
			)
		finally:
			del frame

	def __setitem__(self, key: int | slice, value: T) -> None:
		if isinstance(key, slice):
			wrapped = [
				_wrap_value(v, name=f"{self._log_name}[{i}]") for i, v in enumerate(value)
			]
			super().__setitem__(key, wrapped)
			self._emit("setitem", key=str(key), value=value)
			return

		wrapped = _wrap_value(value, name=f"{self._log_name}[{key}]")
		super().__setitem__(key, wrapped)

		frame = _caller_frame()
		try:
			filename, lineno = _get_location(frame)

			full_name = f"{self._log_name}.{key}"

			_emit(
				"change",
				full_name,
				{
					"op": "setitem",
					"value": _unwrap_value(value),
					"state": _unwrap_value(self),
				},
				filename=filename,
				lineno=lineno,
			)
		finally:
			del frame

	def __delitem__(self, key: int | slice) -> None:
		super().__delitem__(key)
		self._emit("delitem", key=key)

	def append(self, value: T) -> None:
		wrapped = _wrap_value(value, name=f"{self._log_name}[{len(self)}]")
		super().append(wrapped)
		self._emit("append", value=value)

	def extend(self, iterable: Iterable[T]) -> None:
		items = list(iterable)
		wrapped = [
			_wrap_value(v, name=f"{self._log_name}[{len(self) + i}]")
			for i, v in enumerate(items)
		]
		super().extend(wrapped)
		self._emit("extend", value=items)

	def insert(self, index: int, value: T) -> None:
		wrapped = _wrap_value(value, name=f"{self._log_name}[{index}]")
		super().insert(index, wrapped)
		self._emit("insert", index=index, value=value)

	def pop(self, index: SupportsIndex = -1) -> T:
		value = super().pop(index)
		self._emit("pop", index=index, value=value)
		return value

	def remove(self, value: T) -> None:
		super().remove(value)
		self._emit("remove", value=value)

	def clear(self) -> None:
		super().clear()
		self._emit("clear")

	def sort(self, *args, **kwargs) -> None:
		super().sort(*args, **kwargs)
		self._emit("sort", args=args, kwargs=kwargs)

	def reverse(self) -> None:
		super().reverse()
		self._emit("reverse")

	def __iadd__(self, other: Iterable[T]) -> LoggedList[T]:
		self.extend(other)
		return self

	def __imul__(self, other):
		super().__imul__(other)
		self._emit("imul", factor=other)
		return self

	def to_list(self):
		# NOTE: very inefficient, will copy the list 2x each time, which is not needed just to get an Iterable
		# NOTE: Thanks, I realised just self without list(self) is good enough
		return [_unwrap_value(v) for v in self]

	def __repr__(self) -> str:
		return repr(self.to_list())  # f"{type(self).__name__}({list(self)!r})"


class LoggedDict(dict[K, V], _BaseLogged, Generic[K, V]):
	"""
	Dict wrapper that logs mutations like setitem, update, pop, clear, etc
	"""

	def __init__(
			self,
			initial: Mapping[K, V] | Iterable[tuple[K, V]] | None = None,
			name: str = "set",
			_seen: set[int] | None = None,
			**kwargs: object,
	):
		# Prevent recursive self-calls expanding into an infinite recursion chain
		if _seen is None:
			_seen = set()

		object.__setattr__(self, "_seen", _seen)
		object.__setattr__(self, "_log_name", name)

		if initial is None:
			initial = {}

		# NOTE: Inefficient, will copy the mapping even tough mapping does support items
		# and in case of an Iterable, will copy it to the dict, to at the end re-copy it again.
		# NOTE: Hey I modified it, it should be now
		if isinstance(initial, Mapping):
			items = initial.items()
		else:
			items = dict(initial).items()

		items = list(items) + list(kwargs.items())

		super().__init__()
		for k, v in items:
			dict.__setitem__(self, k, _wrap_value(v, name=f"{name}.{k}", seen=_seen))

	def _emit(self, op: str, **details) -> None:
		frame = _caller_frame()
		try:
			filename, lineno = _get_location(frame)
			_emit_change(
				self._log_name,
				op,
				state=self,
				filename=filename,
				lineno=lineno,
				**details,
			)
		finally:
			del frame

	def __setitem__(self, key: K, value: V) -> None:
		wrapped = _wrap_value(value, name=f"{self._log_name}.{key}")
		super().__setitem__(key, wrapped)
		frame = _caller_frame()

		try:
			filename, lineno = _get_location(frame)

			full_name = f"{self._log_name}.{key}"

			_emit(
				"change",
				full_name,
				{
					"op": "setitem",
					"value": _unwrap_value(value),
					"state": _unwrap_value(self),
				},
				filename=filename,
				lineno=lineno,
			)
		finally:
			del frame

	def __delitem__(self, key: K) -> None:
		super().__delitem__(key)
		self._emit("delitem", key=key)

	def __getattr__(self, name: K) -> V:
		try:
			return self[name]
		except KeyError as e:
			raise AttributeError(name) from e

	def __setattr__(self, name: str, value: V) -> None:
		if name.startswith("_"):
			object.__setattr__(self, name, value)
			return

		self[name] = value

	def __delattr__(self, name: str) -> None:
		if name.startswith("_"):
			raise AttributeError(name)

		del self[name]

	def update(self, *args: V, **kwargs: V) -> None:
		data = dict(*args, **kwargs)
		for k, v in data.items():
			dict.__setitem__(self, k, _wrap_value(v, name=f"{self._log_name}.{k}"))
		self._emit("update", value=data)

	def setdefault(self, key: K, default: V = None) -> V:
		if key in self:
			return self[key]

		wrapped = _wrap_value(default, name=f"{self._log_name}.{key}")
		super().__setitem__(key, wrapped)
		self._emit("setdefault", key=key, value=default)
		return wrapped

	def pop(self, key: K, default: V = ...) -> V:
		if default is ...:
			value = super().pop(key)
			self._emit("pop", key=key, value=value)
			return value

		value = super().pop(key, default)
		self._emit("pop", key=key, value=value)
		return value

	def popitem(self) -> tuple[K, V]:
		item = super().popitem()
		self._emit("popitem", value=item)
		return item

	def clear(self) -> None:
		super().clear()
		self._emit("clear")

	def to_dict(self):
		return {k: _unwrap_value(v) for k, v in dict.items(self)}

	def __repr__(self):
		return repr(self.to_dict())  # f"{type(self).__name__}({dict(self)!r})"


class LoggedSet(set[T], _BaseLogged, Generic[T]):
	"""
	Set wrapper that logs mutations like add, remove, update, clear, etc
	"""

	def __init__(
			self,
			initial: Iterable[T] | None = None,
			name: str = "set",
			_seen: set[int] | None = None,
	) -> None:
		# Prevent recursive self-calls expanding into an infinite recursion chain
		if _seen is None:
			_seen = set()

		object.__setattr__(self, "_seen", _seen)
		object.__setattr__(self, "_log_name", name)

		if initial is None:
			initial = set()

		wrapped = {_wrap_value(v, name=f"{name}.item") for v in initial}
		super().__init__(wrapped)

	def _emit(self, op: str, **details):
		frame = _caller_frame()
		try:
			filename, lineno = _get_location(frame)
			_emit_change(
				self._log_name,
				op,
				state=self,
				filename=filename,
				lineno=lineno,
				**details,
			)
		finally:
			del frame

	def add(self, element: T) -> None:
		wrapped = _wrap_value(element, name=f"{self._log_name}.item")
		super().add(wrapped)
		self._emit("add", value=element)

	def update(self, *others: Iterable[T]) -> None:
		values = []
		# NOTE: inefficient, extend can work with any Iterable.
		# NOTE: Thanks again, your're right
		for other in others:
			values.extend(other)

		wrapped = {_wrap_value(v, name=f"{self._log_name}.item") for v in values}
		super().update(wrapped)
		self._emit("update", value=values)

	def discard(self, element: T) -> None:
		super().discard(element)
		self._emit("discard", value=element)

	def remove(self, element: T) -> None:
		super().remove(element)
		self._emit("remove", value=element)

	def pop(self) -> T:
		value = super().pop()
		self._emit("pop", value=value)
		return value

	def clear(self) -> None:
		super().clear()
		self._emit("clear")

	def difference_update(self, *others: Iterable[T]) -> None:
		super().difference_update(*others)
		self._emit("difference_update", value=[list(o) for o in others])

	def intersection_update(self, *others: Iterable[T]) -> None:
		super().intersection_update(*others)
		self._emit("intersection_update", value=[list(o) for o in others])

	def symmetric_difference_update(self, other: Iterable[T]) -> None:
		super().symmetric_difference_update(other)
		self._emit("symmetric_difference_update", value=list(other))

	def __ior__(self, other: Iterable[T]) -> LoggedSet[T]:
		self.update(other)
		return self

	def __iand__(self, other: Iterable[T]) -> LoggedSet[T]:
		super().__iand__(other)
		self._emit("iand", value=list(other))
		return self

	def __isub__(self, other: Iterable[T]) -> LoggedSet[T]:
		super().__isub__(other)
		self._emit("isub", value=list(other))
		return self

	def __ixor__(self, other: Iterable[T]) -> LoggedSet[T]:
		super().__ixor__(other)
		self._emit("ixor", value=list(other))
		return self

	def to_set(self):
		return {_unwrap_value(v) for v in set(self)}

	def __repr__(self) -> str:
		return repr(self.to_set())  # f"{type(self).__name__}({set(self)!r})"


__all__ = [
	"LoggedObject",
	"LoggedList",
	"LoggedDict",
	"LoggedSet",
	"_wrap_value"
]

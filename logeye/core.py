from __future__ import annotations

import sys
import inspect
import warnings
import functools

from types import CellType, CodeType, FrameType
from dataclasses import dataclass
from collections.abc import Callable, Generator, Iterable, Mapping
from typing import TYPE_CHECKING, Literal, TypeVar, ParamSpec, cast, overload

from . import config
from .emmiter import _emit
from .formatting import _format_message, _path
from .introspection.ast import (
	_infer_name_from_frame,
	_get_assignment_target_for_call,
)
from .introspection.templates import _expand_template
from .wrappers import (
	_wrap_value,
	LoggedSet,
	LoggedList,
	LoggedDict,
	LoggedObject,
)
from .introspection.frames import (
	_caller_frame,
	_get_location,
	_is_library_file,
	_is_external_code,
)
from .watcher import (
	_differs,
	_mark_emitted,
	_mark_watched,
	_passes_threshold,
	_watched_names,
	_was_just_emitted,
	_install_global_trace,
	_resolve_threshold_for_name,
)

if TYPE_CHECKING:
	from _typeshed import TraceFunction
	from .config import Mode

_NO_VALUE: object = object()


@dataclass
class _CallState:
	"""What one traced invocation needs to report its own exit"""

	tracer: TraceFunction
	name: str
	signature: str
	should_emit: Callable[[str, str], bool]

	# Line the frame last stopped on, filled in as a generator suspends
	exit_line: int | None = None

	# Where the call was written, for exits the tracer never gets to see
	call_filename: str | None = None
	call_lineno: int | None = None

	# Did sys.settrace ever hand a frame for this call?
	traced: bool = False


T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
P = ParamSpec("P")

Level = Literal["call", "state", "full"]
Kind = Literal["change", "message", "set", "call", "return", "raise", "yield"]

# Not user logic
_SKIPPED_NESTED_NAMES = frozenset({"currentframe", "abspath", "join", "parse"})

# Set on C types, which reject attribute assignment
_Py_TPFLAGS_IMMUTABLETYPE = 1 << 8


def _resolve_filepath(file: str | None = None, filepath: str | None = None) -> str | None:
	if file is not None and filepath is not None:
		raise TypeError("Use only one of 'file' or 'filepath'")
	return file if file is not None else filepath


# ===============
#  CLASS LOGGING
# ===============


def _wrap_class_methods(
	cls: type,
	logged_cls: type,
	*,
	filepath: str | None,
	level: Level,
	mode: Mode,
	show_time: bool,
	show_file: bool,
	show_lineno: bool,
) -> None:
	# noinspection PyUnnecessaryCast
	members = cast("dict[str, object]", dict(cls.__dict__))

	for attr_name, attr_value in members.items():
		if attr_name in {
			"__module__",
			"__doc__",
			"__annotations__",
			"__dict__",
			"__weakref__",
			"__init__",
		}:
			continue

		if attr_name.startswith("__") and attr_name.endswith("__"):
			continue

		wrapped: object

		if isinstance(attr_value, staticmethod):
			wrapped = staticmethod(
				_log_function(
					attr_value.__func__,
					filepath=filepath,
					level=level,
					mode=mode,
					show_time=show_time,
					show_file=show_file,
					show_lineno=show_lineno,
				)
			)
		elif isinstance(attr_value, classmethod):
			# noinspection PyUnnecessaryCast
			wrapped = classmethod(
				_log_function(
					cast("classmethod[object, ..., object]", attr_value).__func__,
					filepath=filepath,
					level=level,
					mode=mode,
					show_time=show_time,
					show_file=show_file,
					show_lineno=show_lineno,
				)
			)
		elif inspect.isfunction(attr_value):
			wrapped = _log_function(
				cast("Callable[..., object]", attr_value),
				filepath=filepath,
				level=level,
				mode=mode,
				show_time=show_time,
				show_file=show_file,
				show_lineno=show_lineno,
			)
		else:
			continue

		setattr(logged_cls, attr_name, wrapped)


def _instance_label(instance: object) -> str:
	return getattr(instance, "_logeye_name", None) or type(instance).__name__.lower()


def _is_patchable(cls: type) -> bool:
	"""C types carry Py_TPFLAGS_IMMUTABLETYPE and reject attribute assignment"""

	return not cls.__flags__ & _Py_TPFLAGS_IMMUTABLETYPE


def _user_stacklevel() -> int:
	"""How far `warnings.warn` must climb to blame the caller's line"""

	try:
		frame = sys._getframe(1)
	except ValueError:
		return 1

	try:
		level = 1

		while frame is not None:
			if not _is_library_file(frame.f_code.co_filename):
				return level

			frame = frame.f_back
			level += 1

		return 1
	finally:
		del frame


def _log_class(
	cls: type,
	*,
	filepath: str | None = None,
	level: Level = "full",
	mode: Mode = "full",
	show_time: bool = True,
	show_file: bool = True,
	show_lineno: bool = True,
) -> type:
	"""
	Instrument a class so instances report construction and attribute changes
	Patched in place rather than subclassed, so `type(obj) is cls` keeps holding
	"""

	if not _is_patchable(cls):
		warnings.warn(
			f"logeye cannot instrument the C type {cls.__qualname__!r}; it is returned unchanged",
			RuntimeWarning,
			stacklevel=_user_stacklevel(),
		)
		return cls

	original_init = cast("Callable[..., None]", cls.__init__)
	original_setattr = cast(
		"Callable[[object, str, object], None]", cast(object, cls.__setattr__)
	)
	original_delattr = cast(
		"Callable[[object, str], None]", cast(object, cls.__delattr__)
	)

	qualname = cls.__qualname__.replace(".<locals>.", ".")

	# __slots__ classes have nowhere to park the display name
	supports_instance_dict = any(
		"__dict__" in vars(base) or "__slots__" not in vars(base)
		for base in cls.__mro__
		if base is not object
	)

	@functools.wraps(original_init)
	def __init__(self: object, *args: object, **kwargs: object) -> None:
		if not config._g_enabled:
			original_init(self, *args, **kwargs)
			return

		call_frame = _caller_frame()
		call_filename, call_lineno = _get_location(call_frame)

		instance_name = (
			_get_assignment_target_for_call(call_frame) or type(self).__name__.lower()
		)

		if supports_instance_dict:
			try:
				object.__setattr__(self, "_logeye_name", instance_name)
			except AttributeError:
				pass

		previous = config._push_display(mode, show_time, show_file, show_lineno, filepath)

		try:
			_emit(
				"call",
				f"{qualname}.__init__",
				{
					"type": "class_init",
					"class_name": qualname,
					"target": instance_name,
					"instance_name": instance_name,
					"args": args,
					"kwargs": kwargs,
				},
				filename=call_filename,
				lineno=call_lineno,
				filepath=filepath,
				show_time=show_time,
				show_file=show_file,
				show_lineno=show_lineno,
			)
		finally:
			config._pop_display(previous)

		original_init(self, *args, **kwargs)

	def __setattr__(self: object, name: str, value: object) -> None:
		is_private = name.startswith("_")
		instance_name = _instance_label(self)

		already_exists = name in getattr(self, "__dict__", ())

		if value is self:
			wrapped = value
		else:
			wrapped = _wrap_value(value, name=f"{instance_name}.{name}")

		original_setattr(self, name, wrapped)

		if not config._g_enabled or is_private and name == "_logeye_name":
			return

		frame = _caller_frame()
		try:
			display_value = value
			filename, lineno = _get_location(frame)

			if is_private:
				display_value = {"type": "private", "value": value}

			kind = "change" if already_exists else "set"

			previous = config._push_display(
				mode, show_time, show_file, show_lineno, filepath
			)

			try:
				_emit(
					kind,
					f"{instance_name}.{name}",
					display_value,
					filename=filename,
					lineno=lineno,
					filepath=filepath,
					show_time=show_time,
					show_file=show_file,
					show_lineno=show_lineno,
				)
			finally:
				config._pop_display(previous)

			if frame is not None:
				_mark_emitted(frame, f"{instance_name}.{name}")
		finally:
			del frame

	def __delattr__(self: object, name: str) -> None:
		instance_name = _instance_label(self)

		original_delattr(self, name)

		if not config._g_enabled:
			return

		frame = _caller_frame()
		try:
			filename, lineno = _get_location(frame)

			previous = config._push_display(
				mode, show_time, show_file, show_lineno, filepath
			)

			try:
				_emit(
					"set",
					f"{instance_name}.{name}",
					"<deleted>",
					filename=filename,
					lineno=lineno,
					filepath=filepath,
					show_time=show_time,
					show_file=show_file,
					show_lineno=show_lineno,
				)
			finally:
				config._pop_display(previous)

			if frame is not None:
				_mark_emitted(frame, f"{instance_name}.{name}")
		finally:
			del frame

	_wrap_class_methods(
		cls,
		cls,
		filepath=filepath,
		level=level,
		mode=mode,
		show_time=show_time,
		show_file=show_file,
		show_lineno=show_lineno,
	)

	setattr(cls, "__init__", __init__)
	setattr(cls, "__setattr__", __setattr__)
	setattr(cls, "__delattr__", __delattr__)

	return cls


def _emit_named_or_message(
	name: str | None,
	value: object,
	*,
	frame: FrameType | None,
	filename: str | None,
	lineno: int | None,
	show_time: bool,
	show_file: bool,
	show_lineno: bool,
) -> None:
	"""
	Log a value under the name it was assigned to, or as a bare message
	A bare `log(value)` statement has no target, so there is nothing to name
	"""

	if not name:
		_emit(
			"message",
			"message",
			value,
			filename=filename,
			lineno=lineno,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
		)
		return

	_emit(
		"set",
		name,
		value,
		filename=filename,
		lineno=lineno,
		show_time=show_time,
		show_file=show_file,
		show_lineno=show_lineno,
	)

	if frame is not None:
		_mark_emitted(frame, name)


# =====================
# WATCH (value logging)
# =====================


@overload
def watch(
	value: Callable[P, T],
	name: str | None = ...,
	*,
	threshold: object | None = ...,
	show_time: bool = ...,
	show_file: bool = ...,
	show_lineno: bool = ...,
) -> Callable[P, T]: ...


@overload
def watch(
	value: T,
	name: str | None = ...,
	*,
	threshold: object | None = ...,
	show_time: bool = ...,
	show_file: bool = ...,
	show_lineno: bool = ...,
) -> T: ...


def watch(
	value: object,
	name: str | None = None,
	*,
	threshold: object | None = None,
	show_time: bool = True,
	show_file: bool = True,
	show_lineno: bool = True,
) -> object:
	"""Log without changing behaviour; callables come back wrapped, rest untouched"""

	if not config._g_enabled or config._g_deco_only:
		return value

	frame = _caller_frame()

	if name is None:
		name = _infer_name_from_frame(frame)

	if name and frame is not None:
		_mark_watched(frame, name, threshold=threshold)
		_install_global_trace(frame)

	filename, lineno = _get_location(frame)

	if callable(value) and not inspect.isclass(value):
		wrapped = _log_function(
			value,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
		)

		_emit_named_or_message(
			name,
			f"<func {_path(value)}>",
			frame=frame,
			filename=filename,
			lineno=lineno,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
		)

		return wrapped

	_emit_named_or_message(
		name,
		value,
		frame=frame,
		filename=filename,
		lineno=lineno,
		show_time=show_time,
		show_file=show_file,
		show_lineno=show_lineno,
	)

	return value


# ========================
#     FUNCTION LOGGING
# ========================


# Helpers
def _format_call_signature(
	name: str, args: tuple[object, ...], kwargs: Mapping[str, object]
) -> str:
	arg_parts = [", ".join(repr(a) for a in args)] if args else []
	kw_parts = [", ".join(f"{k}={v!r}" for k, v in kwargs.items())] if kwargs else []
	joined = ", ".join([p for p in arg_parts + kw_parts if p])
	return f"{name}({joined})"


def _collect_code_objects(func: object) -> set[CodeType]:
	codes: set[CodeType] = set()
	seen: set[int] = set()

	def walk(f: object) -> None:
		if id(f) in seen:
			return
		seen.add(id(f))

		code = getattr(f, "__code__", None)
		if isinstance(code, CodeType):
			codes.add(code)

		# noinspection PyUnnecessaryCast
		wrapped = cast(object, getattr(f, "__wrapped__", None))
		if wrapped is not None:
			walk(wrapped)

		# lru_cache & co. expose no __code__ for settrace to attach to

		# Closures, for stacked decorators
		# noinspection PyUnnecessaryCast
		closure = cast("tuple[CellType, ...] | None", getattr(f, "__closure__", None))
		if closure:
			for cell in closure:
				try:
					obj = cast(object, cell.cell_contents)
				except ValueError:
					continue

				if callable(obj):
					walk(obj)

	walk(func)
	return codes


def _unwrap_callable(func: Callable[..., object]) -> Callable[..., object]:
	unwrapped = cast(object, inspect.unwrap(func))
	return unwrapped if callable(unwrapped) else func


def _callable_display_name(obj: object) -> str:
	"""Best available name for a callable, including ones carrying no __qualname__

	functools.partial objects and instances of a class defining __call__ have
	neither __qualname__ nor __name__, and used to log as an empty name.
	"""
	for attr in ("__qualname__", "__name__"):
		# noinspection PyUnnecessaryCast
		candidate = cast(object, getattr(obj, attr, None))
		if isinstance(candidate, str) and candidate:
			return candidate

	inner = cast(object, getattr(obj, "func", None))
	if inner is not None and callable(inner):
		return f"partial({_callable_display_name(inner)})"

	return type(obj).__qualname__


def _log_function(
	func: Callable[P, T],
	*,
	filepath: str | None = None,
	level: Level = "full",
	filter_set: set[str] | None = None,
	mode: Mode = "full",
	threshold: object | None = None,
	show_time: bool = True,
	show_file: bool = True,
	show_lineno: bool = True,
	show_wrapper_locals: bool = False,
) -> Callable[P, T]:
	"""Wrap a function so sys.settrace reports its calls, locals, returns and raises"""

	target_func = _unwrap_callable(func)

	# noinspection PyUnnecessaryCast
	raw_code = cast(object, getattr(target_func, "__code__", None))
	target_code = raw_code if isinstance(raw_code, CodeType) else None

	is_method_like = bool(
		target_code
		and target_code.co_varnames
		and target_code.co_varnames[0] in {"self", "cls"}
	)

	# noinspection PyUnnecessaryCast
	qualname = cast(object, getattr(target_func, "__qualname__", None))
	if not isinstance(qualname, str) or not qualname:
		qualname = _callable_display_name(func)

	func_path = qualname.replace(".<locals>.", ".")

	allowed_codes: set[CodeType]

	if show_wrapper_locals:
		allowed_codes = _collect_code_objects(func)
	else:
		allowed_codes = {target_code} if target_code is not None else set()

	is_generator = inspect.isgeneratorfunction(target_func)
	is_async = inspect.iscoroutinefunction(target_func) or inspect.isasyncgenfunction(
		target_func
	)

	call_counter = 0

	def should_emit(kind: str, name: str) -> bool:
		if level == "call" and kind not in ("call", "return", "raise", "yield"):
			return False

		if level == "state" and kind == "call":
			return False

		if filter_set:
			parts = name.split(".")
			candidates = parts[1:] if len(parts) > 1 else parts

			if not any(part in filter_set for part in candidates):
				return False

		# Educational narrows further after level and filter
		if mode == "educational" and kind == "set":
			var = name.split(".")[-1]

			if var in ("_", "i", "j", "k", "idx", "tmp", "val"):
				return False

		return True

	# With nothing to narrow change tracking need not ask on every line
	emit_gate = should_emit if level != "full" or filter_set or mode != "full" else None

	def _enter_call() -> config.DisplayState:
		"""Make this call's settings the ones every nested emit reads"""

		return config._push_display(
			mode, show_time, show_file, show_lineno, filepath, emit_gate
		)

	def _build_tracer(
		display_call_name: str,
		call_signature: str,
		args: tuple[object, ...],
		kwargs: dict[str, object],
		should_emit: Callable[[str, str], bool],
	) -> _CallState:
		tracked: dict[FrameType, str] = {}
		baseline: dict[FrameType, dict[str, object]] = {}
		previous_line: dict[FrameType, int] = {}
		pending_exception: dict[FrameType, object] = {}

		lambda_counter = 0

		def _sample_locals(frame: FrameType, frame_name: str, lineno: int) -> None:
			code = frame.f_code
			filename = code.co_filename
			known = baseline[frame]

			# noinspection PyUnnecessaryCast
			locals_view = cast("dict[str, object]", frame.f_locals)

			# Fetched once; the loop below runs per local per line event
			watched = _watched_names(code)

			value: object

			for key, value in list(locals_view.items()):
				if key == "_":
					continue

				if key in {"self", "cls"}:
					known[key] = value
					continue

				if is_method_like and key in code.co_varnames[: code.co_argcount]:
					known[key] = value
					continue

				old = known.get(key, _NO_VALUE)

				# Already reported by an explicit log() / watch()
				if _was_just_emitted(code, key, lineno):
					known[key] = value
					continue

				# An explicit watch() / `| l` owns this name for the whole frame
				if watched is not None and key in watched:
					known[key] = value
					continue

				already_wrapped = isinstance(
					value, (LoggedObject, LoggedList, LoggedDict, LoggedSet)
				)

				if not already_wrapped:
					wrapped = _wrap_value(value, name=f"{frame_name}.{key}")
					if wrapped is not value:
						try:
							locals_view[key] = wrapped
						except (TypeError, ValueError):
							pass
						value = wrapped

				if callable(value):
					continue

				name = f"{frame_name}.{key}"

				kind: Kind

				if old is _NO_VALUE:
					kind = "set"
				elif _differs(old, value):
					kind = "change"
				else:
					continue

				threshold_spec = _resolve_threshold_for_name(name, threshold)
				if not _passes_threshold(old, value, threshold_spec):
					continue

				if should_emit(kind, name):
					_emit(
						kind,
						name,
						value,
						filename=filename,
						lineno=lineno,
						filepath=filepath,
						show_time=show_time,
						show_file=show_file,
						show_lineno=show_lineno,
					)

					known[key] = value

		def _register(frame: FrameType, name: str) -> None:
			# Resuming a generator re-fires "call"; keep the baseline
			if frame in tracked:
				return

			tracked[frame] = name
			baseline[frame] = {}
			previous_line[frame] = frame.f_lineno

		def _release(frame: FrameType) -> None:
			_ = tracked.pop(frame, None)
			_ = baseline.pop(frame, None)
			_ = previous_line.pop(frame, None)
			_ = pending_exception.pop(frame, None)

		def tracer(frame: FrameType, event: str, arg: object) -> TraceFunction | None:
			nonlocal lambda_counter

			code = frame.f_code

			if event == "call":
				filename = code.co_filename

				if _is_library_file(filename):
					return None

				if code in allowed_codes:
					_register(frame, display_call_name)
					state.traced = True
					return tracer

				parent = frame.f_back
				parent_name = tracked.get(parent) if parent is not None else None

				if parent_name is None:
					return None

				# Stop at the edge of user code, the stdlib is pages of noise
				if _is_external_code(filename):
					return None

				nested_name = code.co_name

				if nested_name == "<lambda>":
					lambda_counter += 1
					nested_name = f"lambda#{lambda_counter}"
					nested_full_name = f"{display_call_name}.{nested_name}"
				else:
					if nested_name == getattr(target_func, "__name__", None):
						return None

					if nested_name.startswith("__"):
						return None

					if nested_name in _SKIPPED_NESTED_NAMES:
						return None

					nested_full_name = f"{parent_name}.{nested_name}"

				_register(frame, nested_full_name)

				lineno = frame.f_lineno
				# noinspection PyUnnecessaryCast
				locals_snapshot = cast("dict[str, object]", frame.f_locals)

				defaults = {
					name: locals_snapshot[name]
					for name in code.co_varnames[: code.co_argcount]
					if name in locals_snapshot
				}

				if should_emit("call", nested_full_name):
					_emit(
						"call",
						nested_full_name,
						{"args": (), "kwargs": {}},
						filename=filename,
						lineno=lineno,
						filepath=filepath,
						show_time=show_time,
						show_file=show_file,
						show_lineno=show_lineno,
					)

				_emit(
					"set",
					nested_full_name,
					{
						"type": "function",
						"path": nested_full_name,
						"defaults": defaults,
					},
					filename=filename,
					lineno=lineno,
					filepath=filepath,
					show_time=show_time,
					show_file=show_file,
					show_lineno=show_lineno,
				)

				for key, value in locals_snapshot.items():
					if key in {"self", "cls"} or key not in code.co_varnames:
						continue

					name = f"{nested_full_name}.{key}"
					if should_emit("set", name):
						_emit(
							"set",
							name,
							value,
							filename=filename,
							lineno=lineno,
							filepath=filepath,
							show_time=show_time,
							show_file=show_file,
							show_lineno=show_lineno,
						)
						_mark_emitted(frame, key)
						baseline[frame][key] = value

				return tracer

			frame_name = tracked.get(frame)
			if frame_name is None:
				return None

			if event == "line":
				# More lines in this frame means it was caught here
				_ = pending_exception.pop(frame, None)

				_sample_locals(
					frame, frame_name, previous_line.get(frame, frame.f_lineno)
				)
				previous_line[frame] = frame.f_lineno
				return tracer

			if event == "exception":
				pending_exception[frame] = arg
				return tracer

			if event == "return":
				lineno = previous_line.get(frame, frame.f_lineno)

				# The final statement's values are only visible here
				_sample_locals(frame, frame_name, lineno)

				raised = pending_exception.pop(frame, None)

				if raised is not None and arg is None:
					if should_emit("raise", frame_name):
						# An "exception" event's arg is (type, value, traceback)
						exc_info = cast(
							"tuple[type[BaseException], BaseException, object]", raised
						)
						exc_type, exc_value = exc_info[0], exc_info[1]

						_emit(
							"raise",
							frame_name,
							{
								"exception": exc_value,
								"exception_type": getattr(
									exc_type, "__name__", str(exc_type)
								),
								"args": args,
								"kwargs": kwargs,
								"call_signature": call_signature,
							},
							filename=frame.f_code.co_filename,
							lineno=lineno,
							filepath=filepath,
							show_time=show_time,
							show_file=show_file,
							show_lineno=show_lineno,
						)
				elif is_generator:
					# A generator's "return" is really a yield
					state.exit_line = lineno
					return tracer
				elif should_emit("return", frame_name):
					payload: dict[str, object] = {
						"value": arg,
						"args": args,
						"kwargs": kwargs,
					}

					if not is_method_like:
						payload["call_signature"] = call_signature

					_emit(
						"return",
						frame_name,
						payload,
						filename=frame.f_code.co_filename,
						lineno=lineno,
						filepath=filepath,
						show_time=show_time,
						show_file=show_file,
						show_lineno=show_lineno,
					)

				_release(frame)

			return tracer

		state = _CallState(
			tracer=tracer,
			name=display_call_name,
			signature=call_signature,
			should_emit=should_emit,
		)

		return state

	def _prepare(args: tuple[object, ...], kwargs: dict[str, object]) -> _CallState:
		"""Per-call setup: naming, the call record and the tracer"""

		nonlocal call_counter

		call_counter += 1
		call_id = call_counter
		call_name = f"{func_path}{'' if call_id == 1 else f'#{call_id}'}"

		call_frame = _caller_frame()
		call_filename, call_lineno = _get_location(call_frame)

		bound_name = None
		if is_method_like and args:
			bound_name = getattr(args[0], "_logeye_name", None)

		display_call_name = call_name
		if bound_name:
			method_name = func_path.split(".")[-1]
			display_call_name = f"{bound_name}.{method_name}"

		call_signature = _format_call_signature(
			display_call_name, args[1:] if bound_name else args, kwargs
		)

		if should_emit("call", display_call_name):
			target = _get_assignment_target_for_call(call_frame)

			_emit(
				"call",
				display_call_name,
				{"target": target, "args": args, "kwargs": kwargs},
				filename=call_filename,
				lineno=call_lineno,
				filepath=filepath,
				show_time=show_time,
				show_file=show_file,
				show_lineno=show_lineno,
			)

		state = _build_tracer(
			display_call_name, call_signature, args, kwargs, should_emit
		)

		state.call_filename = call_filename
		state.call_lineno = call_lineno

		return state

	def _emit_untraced_exit(
		state: _CallState,
		kind: Kind,
		payload: dict[str, object],
		args: tuple[object, ...],
		kwargs: dict[str, object],
	) -> None:
		"""Report an exit sys.settrace never saw"""

		if state.traced or not state.should_emit(kind, state.name):
			return

		payload["args"] = args
		payload["kwargs"] = kwargs

		_emit(
			kind,
			state.name,
			payload,
			filename=state.call_filename,
			lineno=state.call_lineno,
			filepath=filepath,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
		)

	if target_code is None:
		# C callables don't have a Python frame; tracer can't see the exit
		@functools.wraps(func)
		def native_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
			if not config._g_enabled:
				return func(*args, **kwargs)

			previous = _enter_call()
			try:
				state = _prepare(args, kwargs)

				try:
					result = func(*args, **kwargs)
				except BaseException as caught:
					_emit_untraced_exit(
						state,
						"raise",
						{
							"exception": caught,
							"exception_type": type(caught).__name__,
							"call_signature": state.signature,
						},
						args,
						kwargs,
					)
					raise

				_emit_untraced_exit(
					state,
					"return",
					{"value": result, "call_signature": state.signature},
					args,
					kwargs,
				)
				return result
			finally:
				config._pop_display(previous)

		return native_wrapper

	if is_async:
		# settrace cannot follow a coroutine across an await, so warn instead
		@functools.wraps(func)
		def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
			if config._g_enabled:
				warnings.warn(
					f"logeye cannot trace the body of async function {func_path!r};"
					+ " only the call itself is logged",
					RuntimeWarning,
					stacklevel=2,
				)

				previous = _enter_call()
				try:
					_ = _prepare(args, kwargs)
				finally:
					config._pop_display(previous)

			return func(*args, **kwargs)

		return async_wrapper

	if is_generator:
		# noinspection PyUnnecessaryCast
		gen_func = cast("Callable[..., Generator[object, object, object]]", func)

		@functools.wraps(func)
		def generator_wrapper(
			*args: object, **kwargs: object
		) -> Generator[object, object, object]:
			if not config._g_enabled:
				yield from gen_func(*args, **kwargs)
				return

			previous = _enter_call()
			try:
				state = _prepare(args, kwargs)
			finally:
				config._pop_display(previous)

			tracer = state.tracer
			generator = gen_func(*args, **kwargs)

			def _emit_exit(kind: Kind, value: object) -> None:
				if not state.should_emit(kind, state.name):
					return

				payload: dict[str, object] = {
					"value": value,
					"args": args,
					"kwargs": kwargs,
				}

				if not is_method_like:
					payload["call_signature"] = state.signature

				_emit(
					kind,
					state.name,
					payload,
					filename=target_code.co_filename if target_code else None,
					lineno=state.exit_line,
					filepath=filepath,
					show_time=show_time,
					show_file=show_file,
					show_lineno=show_lineno,
				)

			def _resume(step: Callable[[], object]) -> object:
				"""
				Run one step of the generator with tracing installed
				The body only runs between next()/send(), long after the wrapper returned
				"""

				previous = _enter_call()
				old_trace = sys.gettrace()
				sys.settrace(tracer)

				try:
					return step()
				finally:
					sys.settrace(old_trace)
					config._pop_display(previous)

			to_send: object = None

			while True:
				try:
					item = _resume(lambda: generator.send(to_send))
				except StopIteration as stop:
					_emit_exit("return", cast(object, stop.value))
					return

				_emit_exit("yield", item)

				try:
					to_send = yield item
				except GeneratorExit:
					_ = generator.close()
					raise
				except BaseException as caught:
					# Python clears the `except` name at block end
					thrown = caught

					try:
						item = _resume(lambda: generator.throw(thrown))
					except StopIteration as stop:
						_emit_exit("return", cast(object, stop.value))
						return

					_emit_exit("yield", item)
					to_send = yield item

		# noinspection PyUnnecessaryCast
		return cast("Callable[P, T]", generator_wrapper)

	@functools.wraps(func)
	def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
		if not config._g_enabled:
			return func(*args, **kwargs)

		previous = _enter_call()

		try:
			state = _prepare(args, kwargs)

			old_trace = sys.gettrace()
			sys.settrace(state.tracer)

			try:
				result = func(*args, **kwargs)
			except BaseException as caught:
				sys.settrace(old_trace)

				# A C decorator in between may have raised before the body ran
				_emit_untraced_exit(
					state,
					"raise",
					{
						"exception": caught,
						"exception_type": type(caught).__name__,
						"call_signature": state.signature,
					},
					args,
					kwargs,
				)
				raise
			finally:
				sys.settrace(old_trace)

			# Nothing was traced when a C decorator answered on its own
			_emit_untraced_exit(
				state,
				"return",
				{"value": result, "call_signature": state.signature},
				args,
				kwargs,
			)
			return result
		finally:
			config._pop_display(previous)

	return wrapper


# ========================
# OBJECT / MESSAGE LOGGING
# ========================


def _log_object(
	obj: T | Mapping[K, V],
	name: str | None = None,
	*,
	show_time: bool = True,
	show_file: bool = True,
	show_lineno: bool = True,
) -> T | LoggedObject[T | Mapping[K, V]] | Mapping[K, V]:
	if not config._g_enabled or config._g_deco_only:
		return obj

	frame = _caller_frame()

	try:
		if name is None:
			name = _get_assignment_target_for_call(frame)

		if not name:
			name = "set"

		wrapped = LoggedObject(obj, name=name)

		filename, lineno = _get_location(frame)

		value: dict[object, object]

		if isinstance(obj, Mapping):
			# noinspection PyUnnecessaryCast
			value = dict(cast("Mapping[object, object]", obj))
		else:
			value = cast("dict[object, object]", cast(object, vars(obj)))

		_emit(
			"set",
			name,
			value,
			filename=filename,
			lineno=lineno,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
		)

		if frame is not None:
			_mark_emitted(frame, name)
	finally:
		del frame

	return wrapped


def _log_message(
	text: str,
	*args: object,
	show_time: bool = True,
	show_file: bool = True,
	show_lineno: bool = True,
	**kwargs: object,
) -> str:
	frame = _caller_frame()

	try:
		if args or kwargs:
			rendered = _format_message(text, *args, **kwargs)
		else:
			rendered = _expand_template(text)

		# $var expansion always runs
		try:
			rendered = _expand_template(rendered)
		except Exception:
			pass

		if not config._g_enabled or config._g_deco_only:
			return rendered

		name = _get_assignment_target_for_call(frame)

		filename, lineno = _get_location(frame)

		if name and frame is not None:
			_mark_watched(frame, name)
			_install_global_trace(frame)

			_emit(
				"set",
				name,
				rendered,
				filename=filename,
				lineno=lineno,
				show_time=show_time,
				show_file=show_file,
				show_lineno=show_lineno,
			)

			_mark_emitted(frame, name)
		else:
			_emit(
				"message",
				"message",
				rendered,
				filename=filename,
				lineno=lineno,
				show_time=show_time,
				show_file=show_file,
				show_lineno=show_lineno,
			)

	finally:
		del frame

	return rendered


# =====================
#   PUBLIC ENTRYPOINT
# =====================


@overload
def _dispatch_log(
	obj: str,
	*args: object,
	file: str | None = ...,
	filepath: str | None = ...,
	level: Level = ...,
	filter: Iterable[str] | None = ...,
	mode: Mode | None = ...,
	threshold: object | None = None,
	show_time: bool | None = ...,
	show_file: bool | None = ...,
	show_lineno: bool | None = ...,
	show_wrapper_locals: bool | None = None,
	**kwargs: object,
) -> str: ...


@overload
def _dispatch_log(
	*,
	file: str | None = ...,
	filepath: str | None = ...,
	level: Level = ...,
	filter: Iterable[str] | None = ...,
	mode: Mode | None = ...,
	threshold: object | None = None,
	show_time: bool | None = ...,
	show_file: bool | None = ...,
	show_lineno: bool | None = ...,
	show_wrapper_locals: bool | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


@overload
def _dispatch_log(
	obj: Mapping[K, V],
	*args: object,
	file: str | None = ...,
	filepath: str | None = ...,
	level: Level = ...,
	filter: Iterable[str] | None = ...,
	mode: Mode | None = ...,
	threshold: object | None = None,
	show_time: bool | None = ...,
	show_file: bool | None = ...,
	show_lineno: bool | None = ...,
	show_wrapper_locals: bool | None = None,
	**kwargs: object,
) -> LoggedDict[K, V]: ...


@overload
def _dispatch_log(
	obj: Callable[P, T],
	*args: object,
	file: str | None = ...,
	filepath: str | None = ...,
	level: Level = ...,
	filter: Iterable[str] | None = ...,
	mode: Mode | None = ...,
	threshold: object | None = None,
	show_time: bool | None = ...,
	show_file: bool | None = ...,
	show_lineno: bool | None = ...,
	show_wrapper_locals: bool | None = None,
	**kwargs: object,
) -> Callable[P, T]: ...


@overload
def _dispatch_log(
	obj: T,
	*args: object,
	file: str | None = ...,
	filepath: str | None = ...,
	level: Level = ...,
	filter: Iterable[str] | None = ...,
	mode: Mode | None = ...,
	threshold: object | None = None,
	show_time: bool | None = ...,
	show_file: bool | None = ...,
	show_lineno: bool | None = ...,
	show_wrapper_locals: bool | None = None,
	**kwargs: object,
) -> T: ...


def _dispatch_log(
	obj: Callable[P, T] | Mapping[K, V] | object = _NO_VALUE,
	*args: object,
	file: str | None = None,
	filepath: str | None = None,
	level: Level = "full",
	filter: Iterable[str] | None = None,
	mode: Mode | None = None,
	threshold: object | None = None,
	show_time: bool | None = None,
	show_file: bool | None = None,
	show_lineno: bool | None = None,
	show_wrapper_locals: bool | None = None,
	**kwargs: object,
) -> object:
	"""
	Dispatch on input type
	class -> patch __init__ | function -> trace | str -> message mapping/object -> LoggedObject | other -> value logging
	"""

	if show_wrapper_locals is None:
		show_wrapper_locals = False

	if mode is None:
		mode = config._mode()
	else:
		mode = config._normalize_mode(mode)

	filter_set = set(filter) if filter else None
	deco_path = _resolve_filepath(file=file, filepath=filepath)

	if show_time is None:
		show_time = config._show_time()

	if show_file is None:
		show_file = config._show_file()

	if show_lineno is None:
		show_lineno = config._show_lineno()

	if mode == "educational":
		show_file = False
		show_lineno = False

	if inspect.isclass(obj):
		return _log_class(
			obj,
			filepath=deco_path,
			level=level,
			mode=mode,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
		)

	if callable(obj):
		return _log_function(
			obj,
			filepath=deco_path,
			level=level,
			filter_set=filter_set,
			mode=mode,
			threshold=threshold,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
			show_wrapper_locals=show_wrapper_locals,
		)

	if isinstance(obj, str):
		return _log_message(
			obj,
			*args,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
			**kwargs,
		)

	# Do NOT wrap class instances
	if isinstance(obj, Mapping):
		return _log_object(
			cast("Mapping[object, object]", obj),
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
		)

	# Plain objects return as-is; @log on the class already handled them
	if hasattr(obj, "__dict__"):
		return obj

	if isinstance(obj, list):
		frame = _caller_frame()

		try:
			name = _get_assignment_target_for_call(frame) or "set"

			if frame is not None:
				_mark_watched(frame, name, threshold=threshold)
				_install_global_trace(frame)

			# noinspection PyUnnecessaryCast
			return _wrap_value(cast("list[object]", obj), name=name)
		finally:
			del frame

	return watch(
		obj,
		threshold=threshold,
		show_time=show_time,
		show_file=show_file,
		show_lineno=show_lineno,
	)


_dispatch_untyped = cast("Callable[..., object]", _dispatch_log)


class _BoundLog:
	"""
	A log(...) call that carried options but no value yet
	Each configuration gets its own object, so an unrelated call cannot consume it
	"""

	__slots__: tuple[str, ...] = ("_options",)

	_options: dict[str, object]

	def __init__(self, options: dict[str, object]) -> None:
		self._options = options

	def __call__(
		self,
		obj: Callable[P, T] | Mapping[K, V] | object = _NO_VALUE,
		*args: object,
		**kwargs: object,
	) -> object:
		merged = {**self._options, **kwargs}

		if obj is _NO_VALUE:
			return _BoundLog(merged)

		return _dispatch_untyped(obj, *args, **merged)

	def __ror__(self, other: object) -> object:
		return _dispatch_untyped(other, **self._options)


class _LogAPI:
	def __call__(
		self,
		obj: Callable[P, T] | Mapping[K, V] | object = _NO_VALUE,
		*args: object,
		file: str | None = None,
		filepath: str | None = None,
		level: Level = "full",
		filter: Iterable[str] | None = None,
		mode: Mode | None = None,
		threshold: object | None = None,
		show_time: bool | None = None,
		show_file: bool | None = None,
		show_lineno: bool | None = None,
		show_wrapper_locals: bool | None = None,
		**kwargs: object,
	) -> object:
		options: dict[str, object] = {
			"file": file,
			"filepath": filepath,
			"level": level,
			"filter": filter,
			"mode": mode,
			"threshold": threshold,
			"show_time": show_time,
			"show_file": show_file,
			"show_lineno": show_lineno,
			"show_wrapper_locals": show_wrapper_locals,
			**kwargs,
		}

		if obj is _NO_VALUE:
			return _BoundLog(options)

		return _dispatch_untyped(obj, *args, **options)

	def __ror__(self, other: object) -> object:
		return _log_pipe_value(other)


def _log_pipe_value(other: object) -> object:
	frame = _caller_frame()

	try:
		name = _infer_name_from_frame(frame)
		filename, lineno = _get_location(frame)

		if name and frame is not None:
			_mark_watched(frame, name)
			_install_global_trace(frame)

			_emit("set", name, other, filename=filename, lineno=lineno)

			_mark_emitted(frame, name)
		else:
			_emit("message", "message", other, filename=filename, lineno=lineno)
	finally:
		del frame

	return other


__all__ = [
	"Kind",
	"Level",
	"watch",
	"_LogAPI",
	"_BoundLog",
	"_dispatch_log",
	"_log_class",
	"_log_function",
	"_log_object",
	"_log_message",
	"_log_pipe_value",
]

from __future__ import annotations

import sys
import inspect
import functools

from types import FrameType
from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING, Literal, TypeVar, ParamSpec, overload

from . import config
from .emmiter import _emit
from .formatting import _format_message
from .introspection.ast import (
	_infer_name_from_frame,
	_get_assignment_target_for_call,
)
from .introspection.templates import _expand_template
from .wrappers import (
	_path,
	_wrap_value,
	LoggedSet,
	LoggedList,
	LoggedDict,
	LoggedObject,
)
from .introspection.frames import _caller_frame, _get_location
from .watcher import (
	_g_last_seen,
	_mark_emitted,
	_mark_watched,
	_g_watched_names,
	_passes_threshold,
	_recently_emitted,
	_install_global_trace,
	_resolve_threshold_for_name
)

if TYPE_CHECKING:
	from .config import Mode

_NO_VALUE = object()

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
P = ParamSpec("P")

Level = Literal["call", "state", "full"]
Kind = Literal["change", "message", "set", "call", "return"]


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
	for attr_name, attr_value in list(cls.__dict__.items()):
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
			wrapped = classmethod(
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
		elif inspect.isfunction(attr_value):
			wrapped = _log_function(
				attr_value,
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
	Wrap a class so its instances become LoggedObjects

	Overrides __init__ to:

	- replace `self` with a LoggedObject wrapper
	- preserve original initialization logic
	"""

	original_init = cls.__init__
	qualname = cls.__qualname__.replace(".<locals>.", ".")

	class LoggedClass(cls):
		@functools.wraps(original_init)
		def __init__(self, *args: object, **kwargs: object):
			if not config._g_enabled:
				original_init(self, *args, **kwargs)
				return

			call_frame = _caller_frame()
			call_filename, call_lineno = _get_location(call_frame)

			instance_name = (
					_get_assignment_target_for_call(call_frame) or type(self).__name__.lower()
			)

			# Store the display name without triggering __setattr__
			object.__setattr__(self, "_logeye_name", instance_name)

			prev_mode = config._g_log_mode
			config._g_log_mode = mode
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
				config._g_log_mode = prev_mode

			original_init(self, *args, **kwargs)

		def __setattr__(self, name: str, value: object) -> None:
			is_private = name.startswith("_")
			instance_name = getattr(self, "_logeye_name", type(self).__name__.lower())
			already_exists = hasattr(self, name)

			# Wrap for nested tracking, self-references as self
			if value is self:
				wrapped = value
			else:
				wrapped = _wrap_value(value, name=f"{instance_name}.{name}")

			object.__setattr__(self, name, wrapped)

			if not config._g_enabled:
				return

			frame = _caller_frame()
			try:
				display_value = value
				filename, lineno = _get_location(frame)

				if is_private:
					display_value = {"type": "private", "value": value}

				kind = "change" if already_exists else "set"

				prev_mode = config._g_log_mode
				config._g_log_mode = mode
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
					config._g_log_mode = prev_mode

				_mark_emitted(frame, f"{instance_name}.{name}")
			finally:
				del frame

		def __delattr__(self, name: str) -> None:
			c_name = type(self).__name__.lower()

			if not hasattr(self, name):
				raise AttributeError(name)

			object.__delattr__(self, name)

			if not config._g_enabled:
				return

			frame = _caller_frame()
			try:
				filename, lineno = _get_location(frame)

				prev_mode = config._g_log_mode
				config._g_log_mode = mode
				try:
					_emit(
						"set",
						f"{c_name}.{name}",
						"<deleted>",
						filename=filename,
						lineno=lineno,
					)
				finally:
					config._g_log_mode = prev_mode

				_mark_emitted(frame, f"{c_name}.{name}")
			finally:
				del frame

	LoggedClass.__name__ = cls.__name__
	LoggedClass.__qualname__ = cls.__qualname__
	LoggedClass.__module__ = cls.__module__

	_wrap_class_methods(
		cls,
		LoggedClass,
		filepath=filepath,
		level=level,
		mode=mode,
		show_time=show_time,
		show_file=show_file,
		show_lineno=show_lineno,
	)

	return LoggedClass


# =====================
# WATCH (value logging)
# =====================


def watch(
		value: T,
		name: str | None = None,
		*,
		threshold: object | None = None,
		show_time: bool = True,
		show_file: bool = True,
		show_lineno: bool = True,
) -> T:
	"""
	Log without changing behaviour
	"""

	if not config._g_enabled or config._g_deco_only:
		return value

	frame = _caller_frame()

	if name is None:
		name = _infer_name_from_frame(frame)

	_mark_watched(frame, name, threshold=threshold)
	_install_global_trace(frame)

	filename, lineno = _get_location(frame)

	# Lambdas
	if callable(value):
		wrapped = _log_function(
			value, show_time=show_time, show_file=show_file, show_lineno=show_lineno
		)

		_emit(
			"set",
			name,
			f"<func {_path(value)}>",
			filename=filename,
			lineno=lineno,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
		)

		_mark_emitted(frame, name)

		return wrapped

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

	if name:
		_mark_emitted(frame, name)

	return value


# ========================
#     FUNCTION LOGGING
# ========================


# Helpers
def _format_call_signature(name, args, kwargs):
	arg_parts = [", ".join(repr(a) for a in args)] if args else []
	kw_parts = [", ".join(f"{k}={v!r}" for k, v in kwargs.items())] if kwargs else []
	joined = ", ".join([p for p in arg_parts + kw_parts if p])
	return f"{name}({joined})"


def _shorten_name(name: str) -> str:
	parts = [p for p in name.split(".") if not p.startswith("test_")]
	return ".".join(parts[-2:]) if len(parts) >= 2 else parts[-1]


def _collect_code_objects(func: object) -> set[object]:
	codes: set[object] = set()
	seen: set[object] = set()

	def walk(f):
		if f in seen:
			return
		seen.add(f)

		# Collect this function's code
		code = getattr(f, "__code__", None)
		if code is not None:
			codes.add(code)

		# Unwrap decorators
		wrapped = getattr(f, "__wrapped__", None)
		if wrapped is not None:
			walk(wrapped)

		# TODO: Here, our way of working fails.
		# TODO: There is no way to look inside C libs
		# TODO: We need to find a way to get the code of the inner function
		# TODO:  This is a problem for all the C decorators, like @lru_cache f.e
		# TODO: I will work on it this weekend, it's going to be pretty hard to be honest

		# Catch closures (multi-deco support)
		closure = getattr(f, "__closure__", None)
		if closure:
			for cell in closure:
				try:
					obj = cell.cell_contents
				except ValueError:
					continue

				if callable(obj):
					walk(obj)

	walk(func)
	return codes


def _unwrap_callable(func: Callable[..., object]) -> Callable[..., object]:
	unwrapped = inspect.unwrap(func)
	return unwrapped if callable(unwrapped) else func


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
	"""
	Wrap a function to trace:
	- calls (arguments)
	- local variable changes
	- return values

	Uses sys.settrace to monitor execution line-by-line
	"""

	target_func = _unwrap_callable(func)
	target_code = getattr(target_func, "__code__", None)

	is_method_like = bool(
		target_code
		and target_code.co_varnames
		and target_code.co_varnames[0] in {"self", "cls"}
	)

	func_path = getattr(
		target_func, "__qualname__", getattr(func, "__qualname__", "")
	).replace(".<locals>.", ".")

	if show_wrapper_locals:
		allowed_codes = _collect_code_objects(func)
	else:
		allowed_codes = {target_code} if target_code is not None else set()

	call_counter = 0

	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		nonlocal call_counter

		prev_mode = config._g_log_mode
		prev_time = config._g_show_time
		prev_file = config._g_show_file
		prev_lineno = config._g_show_lineno

		config._g_log_mode = mode
		config._g_show_time = show_time
		config._g_show_file = show_file
		config._g_show_lineno = show_lineno

		if not config._g_enabled:
			return func(*args, **kwargs)

		# Track multiple calls f.e recursion / repeat calls
		call_counter += 1
		call_id = call_counter
		call_name = f"{func_path}{'' if call_counter == 1 else f'#{call_id}'}"

		def _should_emit(kind: Kind, name: str) -> bool:
			if mode == "educational":
				var = name.split(".")[-1]

				# Always allow meaningful structural events
				if kind in ("change", "message"):
					return True

				# Only allow SOME "set" events
				if kind == "set":
					# Ignore obvious noise
					if var in ("_",):
						return False

					# Ignore loop counters
					# if len(var) == 1 and var.isalpha():
					# 	return False

					# Ignore frequently changing temp vars
					if var in ("i", "j", "k", "idx", "tmp", "val"):
						return False

					# Should work for basic scalars
					return True

			# LEVEL CONTROL
			if level == "call" and kind not in ("call", "return"):
				return False

			if level == "state" and kind == "call":
				return False

			# FILTER CONTROL
			if filter_set:
				var_name = name.split(".")[-1]
				if var_name not in filter_set:
					return False

			return True

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

		if _should_emit("call", display_call_name):
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

		last_values = {}
		active_names: dict[FrameType, str] = {}

		lambda_counter: int = 0

		try:

			def tracer(frame: FrameType, event: str, arg: object):
				code = frame.f_code
				filename = code.co_filename

				# For safety
				if __name__.split(".")[0] in filename:
					return tracer

				lineno = frame.f_lineno

				# Filter noise
				# if (
				# 		not filename.startswith(call_filename)
				# 		or "site-packages" in filename
				# 		or "/lib/python" in filename
				# ):
				# 	return tracer
				if not filename.startswith(call_filename) and not show_wrapper_locals:
					return tracer

				if frame.f_code is target_code and frame not in active_names:
					active_names[frame] = display_call_name

				if event == "call":
					parent = frame.f_back
					if not parent:
						return tracer

					parent_name = active_names.get(parent)

					# First nested call inside the traced function
					if parent.f_code is target_code and parent_name is None:
						parent_name = display_call_name

					# Deeper nesting: only trace if we already know the parent chain
					if parent_name is None:
						return tracer

					nested_name = code.co_name

					if nested_name == "<lambda>":
						nonlocal lambda_counter
						lambda_counter += 1
						nested_name = f"lambda#{lambda_counter}"

					if nested_name == target_func.__name__:
						return tracer

					if nested_name.startswith("__"):
						return tracer

					if nested_name in ("currentframe", "abspath", "join", "parse"):
						return tracer

					if nested_name.startswith("lambda#"):
						root_name = display_call_name
						nested_full_name = f"{root_name}.{nested_name}"
					else:
						nested_full_name = f"{parent_name}.{nested_name}"

					active_names[frame] = nested_full_name

					defaults = {}
					if frame.f_locals:
						for name in code.co_varnames[: code.co_argcount]:
							if name in frame.f_locals:
								defaults[name] = frame.f_locals[name]

					if _should_emit("call", nested_full_name):
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

					if frame.f_locals:
						for key, value in frame.f_locals.items():
							if key in {"self", "cls"}:
								continue
							if key in code.co_varnames:
								name = f"{nested_full_name}.{key}"
								if _should_emit("set", name):
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

					return tracer

				if frame.f_code in allowed_codes or (
						frame.f_back and frame.f_back.f_code in allowed_codes
				):
					if event == "line":
						current = dict(frame.f_locals)
						for key, value in current.items():
							if key == "_":
								continue

							if key in {"self", "cls"}:
								last_values[key] = value
								continue

							if (
									is_method_like
									and key in code.co_varnames[: code.co_argcount]
							):
								last_values[key] = value
								continue

							if (
									mode == "educational" and key in "_"
									or key in {
								"args",
								"kwargs",
								"allowed_codes",
								"call_counter",
								"tracer",
							}
							):
								continue

							# last_values and _g_last_seen did not talk to each other
							# This means that repeat calls of log on the same function in many places
							# Caused it to display set again, when it should've been change in reality
							global_last = _g_last_seen.setdefault(frame.f_code, {})
							old = global_last.get(key, last_values.get(key, _NO_VALUE))

							if (frame.f_code, key) in _recently_emitted:
								_recently_emitted.remove((frame.f_code, key))
								last_values[key] = value
								continue

							if not isinstance(
									value, (LoggedObject, LoggedList, LoggedDict, LoggedSet)
							):
								wrapped = _wrap_value(
									value, name=f"{display_call_name}.{key}"
								)
								if wrapped is not value:
									frame.f_locals[key] = wrapped
									value = wrapped

							frame_name = active_names.get(frame, display_call_name)
							name = f"{frame_name}.{key}"

							if callable(value):
								continue

							if old is _NO_VALUE:
								kind = "set"
							elif old != value:
								kind = "change"
							else:
								if key not in _g_watched_names.get(frame.f_code, set()):
									continue
								kind = "change"

							if kind in {"set", "change"}:
								threshold_spec = _resolve_threshold_for_name(name, threshold)
								if not _passes_threshold(old, value, threshold_spec):
									continue

							if _should_emit(kind, name):
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

								last_values[key] = value
								global_last[key] = value
					elif event == "return":
						if _should_emit("return", display_call_name):
							return_name = active_names.get(frame, display_call_name)

							payload = {
								"value": arg,
								"args": args,
								"kwargs": kwargs,
							}
							if not is_method_like:
								payload["call_signature"] = payload["call_signature"] = (
									call_signature
								)

							# 	(
							# 	call_signature
							# 	if return_name == display_call_name
							# 	else f"{return_name}()"
							# )

							_emit(
								"return",
								return_name,
								payload,
								filename=filename,
								lineno=lineno,
								filepath=filepath,
								show_time=show_time,
								show_file=show_file,
								show_lineno=show_lineno,
							)

							active_names.pop(frame, None)

				return tracer

			old_trace = sys.gettrace()
			sys.settrace(tracer)

			try:
				return func(*args, **kwargs)
			finally:
				sys.settrace(old_trace)

		finally:
			config._g_log_mode = prev_mode
			config._g_show_time = prev_time
			config._g_show_file = prev_file
			config._g_show_lineno = prev_lineno

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

	if name is None:
		frame = _caller_frame()
		try:
			name = _get_assignment_target_for_call(frame)
		finally:
			del frame

	if not name:
		name = "set"

	wrapped = LoggedObject(obj, name=name)

	frame = _caller_frame()
	filename, lineno = _get_location(frame)

	if isinstance(obj, Mapping):
		value = dict(obj)
	else:
		value = vars(obj)

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

	_mark_emitted(frame, name)

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
		# 1. Apply {} formatting if needed
		if args or kwargs:
			rendered = _format_message(text, *args, **kwargs)
		else:
			# Try template expansion first ($x style)
			rendered = _expand_template(text)

			# Fallback - treat as raw string (f-strings already evaluated here)
			if rendered == text:
				rendered = text

		# 2. Always use the special $var formatting we have
		try:
			rendered = _expand_template(rendered)
		except Exception:
			pass

		if not config._g_enabled or config._g_deco_only:
			return rendered

		name = _get_assignment_target_for_call(frame)

		# NOTE: We could also watch all strings automatically passed into the f-string lol
		# NOTE: But this would be too invasive methinks
		# local_vars = frame.f_locals
		#
		# for var_name, value in local_vars.items():
		# 	try:
		# 		if str(value) in rendered:
		# 			_mark_watched(frame, var_name)
		# 	except Exception:
		# 		continue

		filename, lineno = _get_location(frame)

		if name:
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
	Dispatches behaviour based on input type:

	- class     -> wrap class (__init__)
	- function  -> trace execution
	- string    -> formatted message
	- mapping/object -> LoggedObject wrapper
	- other     -> simple value logging
	"""

	if show_wrapper_locals is None:
		show_wrapper_locals = False

	if mode is None:
		mode = config._g_log_mode
	else:
		mode = config._normalize_mode(mode)

	filter_set = set(filter) if filter else None
	deco_path = _resolve_filepath(file=file, filepath=filepath)

	if show_time is None:
		show_time = config._g_show_time

	if show_file is None:
		show_file = config._g_show_file

	if show_lineno is None:
		show_lineno = config._g_show_lineno

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
			obj, show_time=show_time, show_file=show_file, show_lineno=show_lineno
		)

	# Plain objects just return as-is (already handled by @log class)
	if hasattr(obj, "__dict__"):
		return obj

	if isinstance(obj, list):
		frame = _caller_frame()
		name = _get_assignment_target_for_call(frame) or "set"

		_mark_watched(frame, name, threshold=threshold)
		_install_global_trace(frame)

		return _wrap_value(obj, name=name)

	return watch(obj, threshold=threshold, show_time=show_time, show_file=show_file, show_lineno=show_lineno)


class _LogAPI:
	def __init__(self) -> None:
		self._pending_kwargs: dict[str, object] | None = None

	def _set_pending(self, **kwargs: object) -> None:
		self._pending_kwargs = kwargs

	def _consume_pending(self) -> dict[str, object] | None:
		pending = self._pending_kwargs
		self._pending_kwargs = None
		return pending

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
		if obj is _NO_VALUE:
			self._set_pending(
				file=file,
				filepath=filepath,
				level=level,
				filter=filter,
				mode=mode,
				threshold=threshold,
				show_time=show_time,
				show_file=show_file,
				show_lineno=show_lineno,
				show_wrapper_locals=show_wrapper_locals,
				**kwargs,
			)
			return self

		pending = self._consume_pending()
		if pending:
			file = pending.pop("file", file)
			filepath = pending.pop("filepath", filepath)
			level = pending.pop("level", level)
			filter = pending.pop("filter", filter)
			mode = pending.pop("mode", mode)
			threshold = pending.pop("threshold", threshold)
			show_time = pending.pop("show_time", show_time)
			show_file = pending.pop("show_file", show_file)
			show_lineno = pending.pop("show_lineno", show_lineno)
			show_wrapper_locals = pending.pop("show_wrapper_locals", show_wrapper_locals)
			kwargs = {**pending, **kwargs}

		return _dispatch_log(
			obj,
			*args,
			file=file,
			filepath=filepath,
			level=level,
			filter=filter,
			mode=mode,
			threshold=threshold,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
			show_wrapper_locals=show_wrapper_locals,
			**kwargs,
		)

	def __ror__(self, other: object) -> object:
		pending = self._consume_pending()
		if pending:
			return _dispatch_log(other, **pending)
		return _log_pipe_value(other)


def _log_pipe_value(other: object) -> object:
	frame = _caller_frame()

	try:
		name = _infer_name_from_frame(frame)
		filename, lineno = _get_location(frame)

		if name:
			_mark_watched(frame, name)
			_install_global_trace(frame)

			_emit("set", name, other, filename=filename, lineno=lineno)

			_mark_emitted(frame, name)

			_g_last_seen.setdefault(frame.f_code, {})[name] = other
		else:
			_emit("message", "message", other, filename=filename, lineno=lineno)
			_mark_emitted(frame, name)
	finally:
		del frame

	return other

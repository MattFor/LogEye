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
	LoggedObject,
	LoggedList,
	LoggedDict,
	LoggedSet,
	_wrap_value,
	_path,
)
from .introspection.frames import _caller_frame, _get_location
from .watcher import _mark_emitted, _mark_watched, _install_global_trace, _recently_emitted

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

# FIXME: CRITICAL - METHOD CALLS ARE NOT TRACKED FOR CLASSES
# Currently, @log only tracks attribute changes
# Methods like `obj.method()` are NOT intercepted or logged
# We need to wrap or proxy instance methods so calls + returns are traced
# This is a major missing feature and should be implemented asap on features/class-method-logging
def _log_class(
		cls: type,
		*,
		filepath: str | None = None,
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

			_emit(
				"call",
				f"{qualname}.__init__",
				{"args": args, "kwargs": kwargs},
				filename=call_filename,
				lineno=call_lineno,
				filepath=filepath,
				show_time=show_time,
				show_file=show_file,
				show_lineno=show_lineno,
			)

			original_init(self, *args, **kwargs)

		# def __setattr__(self, name: str, value: object) -> None:
		# 	is_private = name.startswith("_")
		#
		# 	object.__setattr__(self, name, value)
		#
		# 	if is_private:
		# 		object.__setattr__(self, name, value)
		# 	else:
		# 		data = object.__getattribute__(self, "_data")
		# 		log_name = object.__getattribute__(self, "_log_name")
		#
		# 		wrapped = _wrap_value(value, name=f"{log_name}.{name}")
		# 		data[name] = wrapped
		#
		# 	frame = _caller_frame()
		# 	try:
		# 		filename, lineno = _get_location(frame)
		#
		# 		prefix = "<priv> " if is_private else ""
		# 		full_name = f"{log_name}.{name}" if not is_private else f"{log_name}.{name}"
		#
		# 		display_value = (
		# 			f"<func {_path(value)}>" if callable(value) else value
		# 		)
		#
		# 		_emit_change(
		# 			full_name,
		# 			"setattr",
		# 			state=value,
		# 			filename=filename,
		# 			lineno=lineno,
		# 			value=f"{prefix}{display_value}",
		# 		)
		# 	finally:
		# 		del frame
		#
		# 	wrapped = _wrap_value(value, name=f"{class_name}.{name}")
		# 	object.__setattr__(self, name, wrapped)
		#
		# 	frame = _caller_frame()
		# 	try:
		# 		filename, lineno = _get_location(frame)
		#
		# 		if callable(wrapped):
		# 			_emit(
		# 				"set",
		# 				f"{class_name}.{name}",
		# 				f"<func {_path(wrapped)}>",
		# 				filename=filename,
		# 				lineno=lineno,
		# 				filepath=filepath,
		# 				show_time=show_time,
		# 				show_file=show_file,
		# 				show_lineno=show_lineno,
		# 			)
		# 		else:
		# 			_emit(
		# 				"set",
		# 				f"{class_name}.{name}",
		# 				wrapped,
		# 				filename=filename,
		# 				lineno=lineno,
		# 				filepath=filepath,
		# 				show_time=show_time,
		# 				show_file=show_file,
		# 				show_lineno=show_lineno,
		# 			)
		# 	finally:
		# 		del frame

		def __setattr__(self, name: str, value: object) -> None:
			is_private = name.startswith("_")
			class_name = type(self).__name__.lower()

			already_exists = hasattr(self, name)

			# Wrap for nested tracking
			wrapped = _wrap_value(value, name=f"{class_name}.{name}")
			object.__setattr__(self, name, wrapped)

			if not config._g_enabled:
				return

			frame = _caller_frame()
			try:
				filename, lineno = _get_location(frame)

				prefix = "<priv> " if is_private else ""

				if callable(value):
					display = f"<func {_path(value)}>"
				else:
					display = wrapped

				kind = "change" if already_exists else "set"

				_emit(
					kind,
					f"{class_name}.{name}",
					f"{prefix}{display}",
					filename=filename,
					lineno=lineno,
					filepath=filepath,
					show_time=show_time,
					show_file=show_file,
					show_lineno=show_lineno,
				)

				_mark_emitted(frame, f"{class_name}.{name}")
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

				_emit(
					"set",
					f"{c_name}.{name}",
					"<deleted>",
					filename=filename,
					lineno=lineno,
				)

				_mark_emitted(frame, f"{c_name}.{name}")
			finally:
				del frame

	LoggedClass.__name__ = cls.__name__
	LoggedClass.__qualname__ = cls.__qualname__
	LoggedClass.__module__ = cls.__module__

	return LoggedClass


# =====================
# WATCH (value logging)
# =====================


def watch(
		value: T,
		name: str | None = None,
		*,
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

	_mark_watched(frame, name)
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

	func_path = getattr(
		target_func, "__qualname__", getattr(func, "__qualname__", "")
	).replace(".<locals>.", ".")
	allowed_codes = {target_code} if target_code is not None else set()

	if show_wrapper_locals:
		allowed_codes |= _collect_code_objects(func)

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

		short_name = _shorten_name(call_name)
		call_signature = _format_call_signature(short_name, args, kwargs)

		if _should_emit("call", call_name):
			_emit(
				"call",
				call_name,
				{"args": args, "kwargs": kwargs},
				filename=call_filename,
				lineno=call_lineno,
				filepath=filepath,
				show_time=show_time,
				show_file=show_file,
				show_lineno=show_lineno,
			)

		last_values = {}

		try:
			def tracer(frame: FrameType, event: str, arg: object):
				code = frame.f_code

				parent = frame.f_back

				if not (
						code in allowed_codes or (parent and parent.f_code in allowed_codes)
				):
					return tracer

				filename = code.co_filename
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

				if event == "call":
					if frame.f_code in allowed_codes or (
							frame.f_back and frame.f_back.f_code in allowed_codes
					):
						nested_name = code.co_name

						# Skip itself so we don't get cases like outer.outer
						if nested_name == target_func.__name__:
							return tracer

						if nested_name.startswith("__"):
							return tracer

						if nested_name in ("currentframe", "abspath", "join", "parse"):
							return tracer

						if _should_emit("call", nested_name):
							_emit(
								"call",
								f"{call_name}.{nested_name}",
								{"args": (), "kwargs": {}},
								filename=filename,
								lineno=lineno,
								filepath=filepath,
								show_time=show_time,
								show_file=show_file,
								show_lineno=show_lineno,
							)

					return tracer

				if frame.f_code in allowed_codes or (
						frame.f_back and frame.f_back.f_code in allowed_codes
				):
					if event == "line":
						current = dict(frame.f_locals)

						for key, value in current.items():
							if mode == "educational" and key in (
									"_"
							):  # , "i", "j", "k"):
								continue

							old = last_values.get(key, object())

							# Skip if already emitted manually
							if (frame.f_code, key) in _recently_emitted:
								_recently_emitted.remove((frame.f_code, key))
								last_values[key] = value  # sync state
								continue

							if not isinstance(
									value, (LoggedObject, LoggedList, LoggedDict, LoggedSet)
							):
								wrapped = _wrap_value(value, name=f"{call_name}.{key}")
								if wrapped is not value:
									frame.f_locals[key] = wrapped
									value = wrapped

							name = f"{call_name}.{key}"
							if old != value:
								if callable(value):
									display = _path(value)
									if _should_emit("set", name):
										_emit(
											"set",
											name,
											f"<func {display}>",
											filename=filename,
											lineno=lineno,
											filepath=filepath,
											show_time=show_time,
											show_file=show_file,
											show_lineno=show_lineno,
										)
								else:
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
								last_values[key] = value
					elif event == "return":
						if _should_emit("return", call_name):
							_emit(
								"return",
								call_name,
								{
									"value": arg,
									"call_signature": call_signature,
								},
								filename=filename,
								lineno=lineno,
								filepath=filepath,
								show_time=show_time,
								show_file=show_file,
								show_lineno=show_lineno,
							)

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

	if obj is _NO_VALUE:

		def decorator(target: T):
			if inspect.isclass(target):
				return _log_class(
					target,
					filepath=deco_path,
					show_time=show_time,
					show_file=show_file,
					show_lineno=show_lineno,
				)
			if callable(target):
				return _log_function(
					target,
					filepath=deco_path,
					level=level,
					filter_set=filter_set,
					mode=mode,
					show_time=show_time,
					show_file=show_file,
					show_lineno=show_lineno,
					show_wrapper_locals=show_wrapper_locals,
				)
			raise TypeError("@log(...) can only decorate a function or class")

		return decorator

	if inspect.isclass(obj):
		return _log_class(
			obj,
			filepath=deco_path,
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

	return watch(obj, show_time=show_time, show_file=show_file, show_lineno=show_lineno)


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
			show_time: bool | None = None,
			show_file: bool | None = None,
			show_lineno: bool | None = None,
			show_wrapper_locals: bool | None = None,
			**kwargs: object,
	) -> object:
		return _dispatch_log(
			obj,
			*args,
			file=file,
			filepath=filepath,
			level=level,
			filter=filter,
			mode=mode,
			show_time=show_time,
			show_file=show_file,
			show_lineno=show_lineno,
			show_wrapper_locals=show_wrapper_locals,
			**kwargs,
		)

	def __ror__(self, other: object) -> object:
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
		else:
			_emit("message", "message", other, filename=filename, lineno=lineno)
			_mark_emitted(frame, name)
	finally:
		del frame

	return other

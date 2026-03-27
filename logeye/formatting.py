from __future__ import annotations

import os

from string import Template
from typing import TYPE_CHECKING
from . import config
from collections.abc import Callable
from .introspection.frames import _caller_frame, _get_location

if TYPE_CHECKING:
	from .core import Kind


def _last_name(name: str) -> str:
	return name.split(".")[-1]


def _is_simple_value(value: object) -> bool:
	return isinstance(value, (str, int, float, bool, type(None)))


def _display_name(name: str) -> str:
	parts = [p for p in name.split(".") if not p.startswith("test_")]
	return ".".join(parts) if parts else name


def _pretty_arg(a):
	if hasattr(a, "__class__") and hasattr(a, "__dict__"):
		return a.__class__.__name__
	return repr(a)


def _path(obj: object) -> str:
	"""
	Return a readable name/path for a callable or object
	"""

	if hasattr(obj, "__qualname__"):
		return obj.__qualname__.replace(".<locals>.", ".")

	return getattr(obj, "__name__", str(obj))


def _format_change_payload(
	name: str,
	payload: dict[str, object],
	prefix: str,
	*,
	include_kind: bool = True,
) -> str | None:
	op = payload.get("op")
	val = payload.get("value")
	state = payload.get("state")

	kind_prefix = "(change) " if include_kind else ""

	if op in ("setattr", "setitem"):
		if _is_simple_value(val):
			# Simple assignment -> more detail would overcomplicate, is also hard on the eyes
			return f"{prefix}{kind_prefix}{name} = {val!r}"

		# Complex assignment -> more detail
		return f"{prefix}{kind_prefix}{name} = {val!r} -> {state}"

	# Skip other operations (kinds)
	return None


def _default_formatter(
	elapsed: float,
	kind: Kind,
	name: str,
	value: object,
	filename: str | None,
	lineno: int | None,
	*,
	show_time: bool = True,
	show_file: bool = True,
	show_lineno: bool = True,
):
	parts = []

	is_edu_mode = config._g_log_mode == "educational"

	if is_edu_mode:
		show_file = False
		show_lineno = False

	stamp = f"{elapsed:0.3f}s"
	time_prefix = f"[{stamp}] " if show_time else ""

	location = ""

	if show_file and filename:
		location += _format_path(filename)

	if show_lineno and lineno is not None:
		if location:
			location += f":{lineno}"
		else:
			location += str(lineno)

	if location:
		parts.append(location)

	location_prefix = " ".join(parts)
	if location_prefix:
		location_prefix += " "

	prefix = f"{time_prefix}{location_prefix}"

	if is_edu_mode:
		if kind in ("set", "change"):
			is_private = isinstance(value, dict) and value.get("type") == "private"

			if isinstance(value, dict) and "op" in value:
				op = value["op"]
				val = value.get("value")
				state = value.get("state")

				short_name = _last_name(name)

				if op == "append":
					return f"{prefix}Added {val} to the end of {short_name}"

				if op == "extend":
					if not val:
						return None

					if len(val) == 1:
						return f"{prefix}Added {val[0]} to {short_name}"

					return f"{prefix}Added {val} to {short_name}"

				if op == "setitem":
					return f"{prefix}set {short_name} = {val} -> {state}"

			if (
				kind == "set"
				and isinstance(value, dict)
				and value.get("type") == "function"
			):
				defaults = value.get("defaults", {})
				short_name = _display_name(name)

				if defaults:
					args = ", ".join(f"{k}={v!r}" for k, v in defaults.items())
					return f"{prefix}Defined {short_name}({args})"

				return f"{prefix}Defined {short_name}()"

			actual = value["value"] if is_private else value
			prefix_priv = "<priv> " if is_private else ""

			if kind == "set":
				return f"{prefix}Defined {prefix_priv}{_display_name(name)} = {actual!r}"

			return f"{prefix}{prefix_priv}{name} = {actual!r}"

		if kind == "call":
			if isinstance(value, dict) and value.get("type") == "class_init":
				cls = value["class_name"].split(".")[-1]
				inst = value["instance_name"]

				args = value.get("args", ())
				kwargs = value.get("kwargs", {})

				parts = []

				if args:
					parts.append(", ".join(repr(a) for a in args))

				if kwargs:
					parts.append(", ".join(f"{k}={v!r}" for k, v in kwargs.items()))

				arg_str = ", ".join(parts)
				return f"{prefix}Created new {cls}({arg_str}) as {inst}"

			if name.endswith("__init__"):
				return None

			func_name = _display_name(name)

			if isinstance(value, dict):
				args = value.get("args", ())
				kwargs = value.get("kwargs", {})

				if args and hasattr(args[0], "_logeye_name"):
					args = args[1:]

				arg_parts = []
				if args:
					arg_parts.append(", ".join(_pretty_arg(a) for a in args))
				if kwargs:
					arg_parts.append(", ".join(f"{k}={v!r}" for k, v in kwargs.items()))

				return f"{prefix}Calling {func_name}({', '.join(arg_parts)})"

			return f"{prefix}Calling {func_name}()"

		if kind == "return":
			if isinstance(value, dict):
				result = value.get("value")

				func_name = _display_name(name)

				return f"{prefix}{func_name}() returned {result!r}"

			return f"{prefix}{value!r}"

	if kind == "message":
		if not config._g_show_message_meta:
			return f"{value}"

		return f"{prefix}{value}"

	if kind == "change" and isinstance(value, dict) and "op" in value:
		formatted = _format_change_payload(name, value, prefix)
		if formatted is not None:
			return formatted

	if isinstance(value, dict) and value.get("type") == "private":
		value = value["value"]

	if kind == "return" and isinstance(value, dict) and "value" in value:
		return f"{prefix}({kind}) {_display_name(name)} -> {value['value']!r}"

	if kind == "call" and isinstance(value, dict):
		args = value.get("args", ())
		kwargs = value.get("kwargs", {})
		target = value.get("target")

		# Remove self/cls
		if args:
			first = args[0]
			if hasattr(first, "_logeye_name") or isinstance(first, type):
				args = args[1:]

		func_name = _display_name(name)

		payload_parts = []
		if args:
			payload_parts.append(f"args={args!r}")
		if kwargs:
			payload_parts.append(f"kwargs={kwargs!r}")

		payload_str = "{" + ", ".join(payload_parts) + "}" if payload_parts else ""

		if target:
			return f"{prefix}({kind}) {target} <- {func_name} {payload_str}".rstrip()
		else:
			return f"{prefix}({kind}) {func_name} {payload_str}".rstrip()

	return f"{prefix}({kind}) {name} = {value!r}"


_formatter = _default_formatter


def _format_path(filename: str | None) -> str:
	if not filename:
		return ""

	if config._g_path_mode == "absolute":
		return filename

	if config._g_path_mode == "project":
		try:
			return os.path.relpath(filename, config._g_project_root)
		except Exception:
			return filename

	if config._g_path_mode == "file":
		return os.path.basename(filename)

	return filename


def set_output_formatter(func: Callable[..., object]) -> None:
	global _formatter
	_formatter = func


def reset_output_formatter() -> None:
	global _formatter
	_formatter = _default_formatter


def _format_message(text: str, *args: object, **kwargs: object) -> str:
	try:
		return text.format(*args, **kwargs)
	except Exception:
		pass

	frame = _caller_frame()
	try:
		if frame is not None:
			namespace = {}
			namespace.update(frame.f_globals)
			namespace.update(frame.f_locals)

			filename, lineno = _get_location(frame)
			namespace["apath"] = filename or ""
			namespace["rpath"] = (
				os.path.relpath(filename, config._g_project_root) if filename else ""
			)
			namespace["fpath"] = os.path.basename(filename) if filename else ""

			try:
				return text.format(**namespace)
			except Exception:
				pass

			try:
				return Template(text).safe_substitute(namespace)
			except Exception:
				pass
	finally:
		del frame

	return text

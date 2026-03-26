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

	# Remove root like "obj"
	if parts and parts[0] not in ("self",):
		parts = parts[1:]

	return ".".join(parts) if parts else name


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

	if config._g_log_mode == "educational":
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

	if config._g_log_mode == "educational":
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
					return f"{prefix}Added {val[0]} to {short_name} -> {state}"

				return f"{prefix}Added {val} to {short_name} -> {state}"

			if op == "setitem":
				return f"{prefix}set {short_name} = {val} -> {state}"

			return f"{prefix}{short_name} changed -> {state}"

		if kind == "set":
			if isinstance(value, dict) and value.get("type") == "function":
				short_name = name if value.get("type") == "function" else _display_name(name)
				defaults = value.get("defaults", {})

				if defaults:
					args = ", ".join(f"{k}={v!r}" for k, v in defaults.items())
					return f"{prefix}Defined {short_name}({args})"

				return f"{prefix}Defined {short_name}()"

			short_name = _display_name(name)
			return f"{prefix}{short_name} = {value!r}"

		if kind == "call":
			func_name = _display_name(name)

			if isinstance(value, dict):
				args = value.get("args", ())
				kwargs = value.get("kwargs", {})

				arg_parts = []

				if args:
					arg_parts.append(", ".join(repr(a) for a in args))

				if kwargs:
					arg_parts.append(", ".join(f"{k}={v!r}" for k, v in kwargs.items()))

				args_str = ", ".join(arg_parts)

				return f"{prefix}Calling {func_name}({args_str})"

			return f"{prefix}Calling {func_name}"

		if kind == "return":
			if isinstance(value, dict):
				call_signature = value.get("call_signature")
				return_value = value.get("value")
				if call_signature:
					raw_name = call_signature.split("(")[0]
					func_name = _display_name(raw_name)
					args_part = call_signature[len(raw_name):]

					return f"{prefix}{func_name}{args_part} returned {return_value!r}"

			return f"{prefix}Returned {value!r}"

	if kind == "message":
		if not config._g_show_message_meta:
			return f"{value}"

		return f"{prefix}{value}"

	if kind == "change" and isinstance(value, dict) and "op" in value:
		formatted = _format_change_payload(name, value, prefix)
		if formatted is not None:
			return formatted

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

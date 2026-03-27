from __future__ import annotations
import os
import time
from typing import TYPE_CHECKING

from . import config
from .formatting import _formatter
from .introspection import _is_user_code

if TYPE_CHECKING:
	from .core import Kind


def _write_line_to_file(filepath: str, line: str) -> None:
	directory = os.path.dirname(filepath)
	if directory:
		os.makedirs(directory, exist_ok=True)

	with open(filepath, "a", encoding="utf-8") as f:
		f.write(line + "\n")


def _emit(
	kind: Kind,
	name: str,
	value: object,
	*,
	filename: str | None = None,
	lineno: int | None = None,
	filepath: str | None = None,
	show_time: bool = True,
	show_file: bool = True,
	show_lineno: bool = True,
) -> None:
	if config._g_start_time is None:
		config._g_start_time = time.perf_counter()

	if not config._g_enabled:
		return

	if filename and not _is_user_code(filename):
		return

	if config._g_log_mode == "educational":
		if kind == "change" and isinstance(value, dict):
			if value.get("op") == "extend" and not value.get("value"):
				return

	if config._g_log_mode == "educational":
		filename = None
		lineno = None

	elapsed = time.perf_counter() - config._g_start_time
	line = _formatter(
		elapsed,
		kind,
		name,
		value,
		filename,
		lineno,
		show_time=show_time,
		show_file=show_file,
		show_lineno=show_lineno,
	)

	# Educational mode is on, ignoring stuff
	if not line:
		return

	if filepath is not None:
		_write_line_to_file(filepath, line)
		return

	if config._g_log_file_enabled and config._g_log_file:
		_write_line_to_file(config._g_log_file, line)
		return

	print(line)

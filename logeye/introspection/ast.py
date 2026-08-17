from __future__ import annotations

import os
import ast
import linecache

from typing import NamedTuple

from .. import config
from types import FrameType
from .frames import _is_library_file

# log() calls per line, for `a, b = log(...), log(...)`; wraps on target count
_call_counter_per_line: dict[tuple[str, int], int] = {}


def _is_user_code(filename: str) -> bool:
	"""True only for user code, not logeye's own frames"""

	if not filename:
		return True

	return not _is_library_file(filename)


def _is_direct_log_call(node: ast.AST) -> bool:
	"""Is this node a direct `log(...)` / `l(...)` call?"""

	return (
		isinstance(node, ast.Call)
		and isinstance(node.func, ast.Name)
		and (node.func.id == "log" or node.func.id == "l")
	)


# ==========================
#  CACHED SOURCE INSPECTION
# ==========================


class _LineInfo(NamedTuple):
	"""What the assignment on a single source line targets"""

	# Target when the value is literally log(...) / l(...) or a `| l` pipe
	log_single: str | None

	# Target for any simple assignment, whatever the right-hand side
	any_single: str | None

	# Tuple-assignment targets, empty when the line is not one
	tuple_names: tuple[str, ...]

	# False when the line could not be read or parsed
	parsed: bool


_NO_INFO = _LineInfo(None, None, (), False)

# (filename, lineno) -> _LineInfo, invalidated on mtime change
_line_info_cache: dict[tuple[str, int], _LineInfo] = {}
_file_stamp_cache: dict[str, float] = {}


def _file_stamp(filename: str) -> float:
	try:
		return os.stat(filename).st_mtime
	except OSError:
		return 0.0


def _invalidate_if_stale(filename: str) -> None:
	"""Drop cached line info when the file changed on disk"""

	stamp = _file_stamp(filename)
	if _file_stamp_cache.get(filename) == stamp:
		return

	_file_stamp_cache[filename] = stamp
	_ = _module_cache.pop(filename, None)

	for key in [k for k in _line_info_cache if k[0] == filename]:
		del _line_info_cache[key]


def _targets_of(node: ast.Assign | ast.AnnAssign) -> tuple[str | None, tuple[str, ...]]:
	"""Split an assignment's targets into (single name, tuple names)"""

	if isinstance(node, ast.AnnAssign):
		target = node.target
		return (target.id if isinstance(target, ast.Name) else None), ()

	if not node.targets:
		return None, ()

	target = node.targets[0]

	if isinstance(target, ast.Name):
		return target.id, ()

	if isinstance(target, ast.Tuple):
		names = tuple(el.id for el in target.elts if isinstance(el, ast.Name))
		return None, names

	return None, ()


def _info_from_statement(stmt: ast.AST) -> _LineInfo | None:
	if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
		return None

	value = stmt.value
	if value is None:
		return None

	single, tuple_names = _targets_of(stmt)

	log_single = None

	# x = log(...)
	if _is_direct_log_call(value):
		log_single = single

	# x = something | l
	elif (
		isinstance(value, ast.BinOp)
		and isinstance(value.op, ast.BitOr)
		and isinstance(value.right, ast.Name)
		and value.right.id == config._g_log_pipe_name
	):
		log_single = single

	# a, b = log(...), log(...) tuple_names carries the mapping
	if isinstance(value, ast.Tuple) and tuple_names:
		return _LineInfo(log_single, single, tuple_names, True)

	return _LineInfo(log_single, single, (), True)


def _analyze_line(filename: str, lineno: int) -> _LineInfo:
	"""What the statement at filename:lineno assigns to"""

	if not filename:
		return _NO_INFO

	_invalidate_if_stale(filename)

	key = (filename, lineno)
	cached = _line_info_cache.get(key)
	if cached is not None:
		return cached

	info = _NO_INFO

	# Fast path: one line
	source = linecache.getline(filename, lineno).strip()
	if source:
		try:
			node = ast.parse(source)
		except SyntaxError:
			node = None

		if node is not None and node.body:
			parsed = _info_from_statement(node.body[0])
			# Parsed fine but not an assignment
			info = parsed if parsed is not None else _LineInfo(None, None, (), True)

	# Slow path: multi-line statement, parse the module once
	if info.any_single is None and not info.tuple_names:
		module = _module_ast(filename)

		if module is not None:
			for node in ast.walk(module):
				if not isinstance(node, (ast.Assign, ast.AnnAssign)):
					continue

				start = node.lineno
				end = getattr(node, "end_lineno", start)

				if not (start <= lineno <= end):
					continue

				parsed = _info_from_statement(node)
				if parsed is not None and (parsed.any_single or parsed.tuple_names):
					info = parsed
					break

	_line_info_cache[key] = info
	return info


# filename -> module AST, invalidated with the line cache
_module_cache: dict[str, ast.Module | None] = {}


def _module_ast(filename: str) -> ast.Module | None:
	if filename in _module_cache:
		return _module_cache[filename]

	tree: ast.Module | None

	try:
		with open(filename, "r", encoding="utf-8") as f:
			tree = ast.parse(f.read())
	except (OSError, SyntaxError, ValueError):
		tree = None

	_module_cache[filename] = tree
	return tree


def _get_call_index_in_line(frame: FrameType, target_count: int) -> int:
	"""
	Which log() call this is on the current line
	`a, b = log("x"), log("y")` -> 0 for a, 1 for b; wraps so loops restart at 0
	"""

	if target_count <= 0:
		return 0

	key = (frame.f_code.co_filename, frame.f_lineno)

	idx = _call_counter_per_line.get(key, 0)
	_call_counter_per_line[key] = (idx + 1) % target_count

	return idx % target_count


def _infer_name_from_frame(
	frame: FrameType | None, default: str = "PLACEHOLDER"
) -> str | None:
	"""Infer the variable name, handling `x = ...` and `a, b = ..., ...`"""

	if frame is None:
		return default

	info = _analyze_line(frame.f_code.co_filename, frame.f_lineno)

	if not info.parsed:
		return default

	if info.tuple_names:
		return info.tuple_names[_get_call_index_in_line(frame, len(info.tuple_names))]

	if info.any_single:
		return info.any_single

	# Not found, probably a `| l` statement, so not the default
	return None


def _get_assignment_target_for_call(frame: FrameType | None) -> str | None:
	"""Which variable a log(...) call is assigned to"""

	if frame is None:
		return None

	info = _analyze_line(frame.f_code.co_filename, frame.f_lineno)

	if info.tuple_names:
		return info.tuple_names[_get_call_index_in_line(frame, len(info.tuple_names))]

	return info.log_single


__all__ = [
	"_is_user_code",
	"_is_direct_log_call",
	"_infer_name_from_frame",
	"_get_call_index_in_line",
	"_get_assignment_target_for_call",
]

from __future__ import annotations

import os
import ast
import time
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

# Seconds between stat() calls on the same file; the watcher asks per line event,
# and stat'ing that often costs more than everything else the tracer does
_STALE_CHECK_INTERVAL = 0.25
_file_checked_at: dict[str, float] = {}


def _file_stamp(filename: str) -> float:
	try:
		return os.stat(filename).st_mtime
	except OSError:
		return 0.0


def _invalidate_if_stale(filename: str) -> None:
	"""Drop cached line info when the file changed on disk"""

	now = time.monotonic()
	if now - _file_checked_at.get(filename, 0.0) < _STALE_CHECK_INTERVAL:
		return

	_file_checked_at[filename] = now

	stamp = _file_stamp(filename)
	if _file_stamp_cache.get(filename) == stamp:
		return

	_file_stamp_cache[filename] = stamp
	_ = _module_cache.pop(filename, None)
	_ = _assignments_cache.pop(filename, None)

	for key in [k for k in _line_info_cache if k[0] == filename]:
		del _line_info_cache[key]


def _flatten_target_names(target: ast.expr) -> tuple[str, ...]:
	"""
	Every binding an assignment target introduces, left to right
	Nested targets flatten into one sequence, so `(a, (b, c))` reads as
	("a", "b", "c") and lines up with the log() calls on the right-hand side
	Anything that is not a plain name (obj.attr, items[0]) keeps a blank slot,
	so the positions of the names around it stay correct
	"""

	if isinstance(target, ast.Name):
		return (target.id,)

	if isinstance(target, ast.Starred):
		return _flatten_target_names(target.value)

	if isinstance(target, (ast.Tuple, ast.List)):
		names: list[str] = []

		for element in target.elts:
			names.extend(_flatten_target_names(element))

		return tuple(names)

	# Assignable, but not to a name we can report
	return ("",)


def _targets_of(node: ast.Assign | ast.AnnAssign) -> tuple[str | None, tuple[str, ...]]:
	"""Split an assignment's targets into (single name, unpacked names)"""

	if isinstance(node, ast.AnnAssign):
		target = node.target
		return (target.id if isinstance(target, ast.Name) else None), ()

	if not node.targets:
		return None, ()

	target = node.targets[0]

	if isinstance(target, ast.Name):
		return target.id, ()

	if isinstance(target, (ast.Tuple, ast.List)):
		return None, _flatten_target_names(target)

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
	if isinstance(value, (ast.Tuple, ast.List)) and tuple_names:
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


# filename -> {lineno: names bound there}, invalidated with the line cache
_assignments_cache: dict[str, dict[int, frozenset[str]]] = {}


def _assignment_targets(node: ast.AST) -> list[ast.expr]:
	"""The targets a statement binds, or none when it binds nothing"""

	if isinstance(node, ast.Assign):
		return list(node.targets)

	if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
		return [node.target] if node.value is not None else []

	if isinstance(node, (ast.For, ast.AsyncFor)):
		return [node.target]

	if isinstance(node, (ast.With, ast.AsyncWith)):
		return [item.optional_vars for item in node.items if item.optional_vars]

	return []


def _assignments_of_file(filename: str) -> dict[int, frozenset[str]]:
	"""Every line that binds a name, mapped to the names it binds"""

	cached = _assignments_cache.get(filename)
	if cached is not None:
		return cached

	table: dict[int, set[str]] = {}
	module = _module_ast(filename)

	if module is not None:
		for node in ast.walk(module):
			for target in _assignment_targets(node):
				names = {name for name in _flatten_target_names(target) if name}
				if not names:
					continue

				# The target's own span, not the statement's; a `for` header
				# binds on its own line, not down the whole loop body
				start = target.lineno
				end = getattr(target, "end_lineno", start) or start

				for line in range(start, end + 1):
					table.setdefault(line, set()).update(names)

	frozen = {line: frozenset(names) for line, names in table.items()}
	_assignments_cache[filename] = frozen

	return frozen


_NO_NAMES: frozenset[str] = frozenset()


def _line_assigns(filename: str, lineno: int | None, name: str) -> bool:
	"""Does the assignment at filename:lineno bind `name`?

	Tells a genuine re-assignment apart from a line that merely read the name,
	so watching can report `x = 1` twice in a row instead of swallowing the second

	The watcher asks this on every line event, so the warm path is dict lookups
	and nothing else; the table is only rebuilt when the file changed on disk
	"""

	if not filename or lineno is None:
		return False

	table = _assignments_cache.get(filename)

	if (
		table is None
		or time.monotonic() - _file_checked_at.get(filename, 0.0) >= _STALE_CHECK_INTERVAL
	):
		_invalidate_if_stale(filename)
		table = _assignments_of_file(filename)

	# Watched names are bare locals; a dotted one never matches a target
	return name in table.get(lineno, _NO_NAMES)


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


def _unpacked_name(frame: FrameType, names: tuple[str, ...]) -> str | None:
	"""The name this log() call fills in an unpacking target, blank slots aside"""

	return names[_get_call_index_in_line(frame, len(names))] or None


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
		return _unpacked_name(frame, info.tuple_names) or default

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
		return _unpacked_name(frame, info.tuple_names) or info.log_single

	return info.log_single


__all__ = [
	"_is_user_code",
	"_line_assigns",
	"_is_direct_log_call",
	"_infer_name_from_frame",
	"_get_call_index_in_line",
	"_get_assignment_target_for_call",
]

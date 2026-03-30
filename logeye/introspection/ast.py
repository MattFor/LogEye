import os
import ast
import linecache

from .. import config
from types import FrameType
from .frames import _caller_frame

# Tracks how many log() calls happened on a single line
# Used to map tuples a, b = log(...), log(...)
_call_counter_per_line: dict[tuple[str, int], int] = {}


def _is_user_code(filename: str) -> bool:
	"""
	Filter out internal library frames

	Returns True only for user code (not inside logeye itself)
	"""

	if not filename:
		return True

	filename = os.path.abspath(filename)
	return "/logeye/" not in filename


def _is_direct_log_call(node: ast.AST) -> bool:
	"""
	Check if an AST node is a direct call to `log(...)` or pipe `l`
	"""

	return (
		isinstance(node, ast.Call)
		and isinstance(node.func, ast.Name)
		and (node.func.id == "log" or node.func.id == "l")
	)


def _is_assigned_call(frame: FrameType | None) -> bool:
	"""
	Detect whether the current line contains an assignment
	where log(...) is used

	Used to differentiate between:
	- x = log(...)
	- log(...)  (by itself)
	"""

	if frame is None:
		return False

	filename = frame.f_code.co_filename
	lineno = frame.f_lineno

	# Read single line, fast but kinda limited
	source = linecache.getline(filename, lineno).strip()

	if not source:
		return False

	try:
		node = ast.parse(source)
	except SyntaxError:
		return False

	for stmt in node.body:
		if isinstance(stmt, ast.Assign) and _is_direct_log_call(stmt.value):
			return True

		if (
			isinstance(stmt, ast.AnnAssign)
			and stmt.value is not None
			and _is_direct_log_call(stmt.value)
		):
			return True

	return False


def _get_call_index_in_line(frame: FrameType):
	"""
	Track which log() call this is on the current line

	Example:
		a, b = log("x"), log("y")

	First call -> index 0 -> maps to 'a'
	Second call ->  index 1 -> maps to 'b'
	"""

	key = (frame.f_code.co_filename, frame.f_lineno)

	idx = _call_counter_per_line.get(key, 0)
	_call_counter_per_line[key] = idx + 1

	return idx


def _infer_name_from_frame(
	frame: FrameType | None, default: str = "PLACEHOLDER"
) -> str | None:
	"""
	Infer variable name from a simple single-line assignment

	Only works for straightforward cases like x = log(...)
	"""

	if frame is None:
		return default

	filename = frame.f_code.co_filename
	lineno = frame.f_lineno
	source = linecache.getline(filename, lineno).strip()

	if not source:
		return default

	try:
		node = ast.parse(source)
	except SyntaxError:
		return default

	if not node.body:
		return default

	stmt = node.body[0]

	if isinstance(stmt, ast.Assign) and stmt.targets:
		target = stmt.targets[0]

		if isinstance(target, ast.Name):
			return target.id

	if isinstance(stmt, ast.AnnAssign):
		target = stmt.target

		if isinstance(target, ast.Name):
			return target.id

	# Name isn't found, should not be returning default!
	# Probably a <| l> statement
	return None


def _infer_callsite_name(default: str = "set") -> str:
	frame = _caller_frame()
	try:
		return _infer_name_from_frame(frame, default)
	finally:
		del frame


def _get_assignment_target_for_call(frame: FrameType | None) -> str | None:
	"""
	Main name inference location

	Attempts to determine which variable a log(...) call is assigned to

	Strategy:
	1. Fast path -> parse current line only
	2. Fallback -> parse entire file AST for multi-line statements
	"""

	if frame is None:
		return None

	filename = frame.f_code.co_filename
	lineno = frame.f_lineno

	# Single line
	source = linecache.getline(filename, lineno).strip()
	if source:
		try:
			node = ast.parse(source)
		except SyntaxError:
			node = None

		if node and node.body:
			stmt = node.body[0]

			if isinstance(stmt, ast.Assign):
				targets = stmt.targets

				# Simple
				if isinstance(stmt.value, ast.Call) and _is_direct_log_call(stmt.value):
					if isinstance(targets[0], ast.Name):
						return targets[0].id

				# Pipe
				if isinstance(stmt.value, ast.BinOp):
					if isinstance(stmt.value.op, ast.BitOr):
						if (
							isinstance(stmt.value.right, ast.Name)
							and stmt.value.right.id == config._g_log_pipe_name
						):
							if isinstance(stmt.targets[0], ast.Name):
								return stmt.targets[0].id

				# Tuple
				if isinstance(stmt.value, ast.Tuple):
					targets_list = (
						stmt.targets[0].elts
						if isinstance(stmt.targets[0], ast.Tuple)
						else []
					)
					call_index = _get_call_index_in_line(frame)

					if call_index is not None and call_index < len(targets_list):
						target = targets_list[call_index]
						if isinstance(target, ast.Name):
							return target.id

	# Multiline AST -> complex statement (multiline)
	try:
		with open(filename, "r") as f:
			full_source = f.read()
	except OSError:
		return None

	try:
		tree = ast.parse(full_source)
	except SyntaxError:
		return None

	for node in ast.walk(tree):
		if isinstance(node, ast.Assign):
			# Check if this assignment spans current line
			if not (node.lineno <= lineno <= getattr(node, "end_lineno", node.lineno)):
				continue

			# Simple assignments
			if isinstance(node.value, ast.Call) and _is_direct_log_call(node.value):
				target = node.targets[0]
				if isinstance(target, ast.Name):
					return target.id

			# Tuples
			if isinstance(node.value, ast.Tuple):
				targets = (
					node.targets[0].elts if isinstance(node.targets[0], ast.Tuple) else []
				)

				call_index = _get_call_index_in_line(frame)

				if call_index is not None and call_index < len(targets):
					target = targets[call_index]
					if isinstance(target, ast.Name):
						return target.id

	return None


def _get_assignment_target_for_pipe(frame: FrameType | None) -> str | None:
	if frame is None:
		return None

	filename = frame.f_code.co_filename
	lineno = frame.f_lineno
	source = linecache.getline(filename, lineno).strip()

	if not source:
		return None

	try:
		node = ast.parse(source)
	except SyntaxError:
		return None

	if not node.body:
		return None

	stmt = node.body[0]

	if isinstance(stmt, ast.Assign):
		if isinstance(stmt.value, ast.BinOp) and isinstance(stmt.value.op, ast.BitOr):
			right = stmt.value.right

			if isinstance(right, ast.Name) and right.id == "l":
				target = stmt.targets[0]
				if isinstance(target, ast.Name):
					return target.id

	return None


__all__ = [
	"_is_user_code",
	"_is_assigned_call",
	"_is_direct_log_call",
	"_infer_callsite_name",
	"_infer_name_from_frame",
	"_get_call_index_in_line",
	"_get_assignment_target_for_call",
	"_get_assignment_target_for_pipe",
]

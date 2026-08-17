from __future__ import annotations

import sys

from numbers import Real
from types import CodeType, FrameType
from collections.abc import Mapping

from typing import (
	TYPE_CHECKING,
	Callable,
	Literal,
	SupportsFloat,
	SupportsIndex,
	TypeAlias,
	TypeGuard,
	TypeVar,
	cast,
)

from logeye.emmiter import _emit

# Events sys.settrace dispatches
TraceEvent: TypeAlias = Literal["call", "line", "return", "exception", "opcode"]

if TYPE_CHECKING:
	from _typeshed import TraceFunction

	from .core import Kind

_NO_VALUE: object = object()

# Cap on tracked code objects, bounding growth under exec / hot reload / closures
_MAX_TRACKED_CODES = 512

# How many any() passes to collapse an elementwise mask (ndarray, DataFrame)
_MAX_MASK_REDUCTIONS = 4

K = TypeVar("K")


def _slot(store: dict[CodeType, K], code: CodeType, factory: Callable[[], K]) -> K:
	"""Per-code-object state, evicting the oldest entries past the cap"""

	existing = store.get(code)
	if existing is not None:
		return existing

	if len(store) >= _MAX_TRACKED_CODES:
		# Insertion-ordered; front is oldest
		for stale in list(store)[: _MAX_TRACKED_CODES // 4]:
			del store[stale]

	fresh = factory()
	store[code] = fresh
	return fresh


_recently_emitted: set[tuple[CodeType, str]] = set()

_g_trace_installed: bool = False

# Whatever was installed before (pdb, coverage.py); chained to and restored
_g_previous_trace: TraceFunction | None = None

_g_watched_names: dict[CodeType, set[str]] = {}
_g_last_seen: dict[CodeType, dict[str, object]] = {}
_g_watch_meta: dict[CodeType, dict[str, dict[str, object]]] = {}

# frame -> last line seen; dropped on return so frames are not retained
_g_last_line: dict[FrameType, int] = {}


def _mark_emitted(frame: FrameType, name: str) -> None:
	if not name:
		return

	if len(_recently_emitted) >= _MAX_TRACKED_CODES * 4:
		_recently_emitted.clear()

	_recently_emitted.add((frame.f_code, name))


def _mark_watched(
	frame: FrameType, name: str, *, threshold: object | None = None
) -> None:
	if not name or name == "_":
		return

	_slot(_g_watched_names, frame.f_code, set).add(name)

	if threshold is not None:
		_slot(_g_watch_meta, frame.f_code, dict)[name] = {
			"threshold": threshold,
		}


def _is_number(value: object) -> TypeGuard[Real]:
	# bool is a Real at runtime; it subclasses int
	return isinstance(value, Real) and not isinstance(value, bool)  # pyright: ignore[reportUnnecessaryIsInstance]


def _to_float(value: object) -> float:
	"""float() on a user value; it already raises on anything it cannot convert"""

	return float(cast("SupportsFloat | SupportsIndex | str | bytes", value))


def _is_single_threshold_spec(value: object) -> bool:
	if isinstance(value, (int, float)) and not isinstance(value, bool):
		return True

	if isinstance(value, tuple):
		# noinspection PyUnnecessaryCast
		parts = cast("tuple[object, ...]", value)
		if len(parts) == 2 and isinstance(parts[0], str):
			return parts[0] in {"absolute", "relative", "abs", "rel"}

	if isinstance(value, Mapping):
		# noinspection PyUnnecessaryCast
		keys = cast("Mapping[object, object]", value)
		return set(keys.keys()) <= {"absolute", "abs", "relative", "rel", "epsilon"}

	return False


def _normalize_threshold_spec(spec: object) -> dict[str, float]:
	if spec is None:
		return {}

	if isinstance(spec, (int, float)) and not isinstance(spec, bool):
		return {"absolute": float(spec)}

	if isinstance(spec, tuple):
		# noinspection PyUnnecessaryCast
		parts = cast("tuple[object, ...]", spec)

		if len(parts) == 2 and isinstance(parts[0], str):
			mode, value = parts[0], parts[1]

			if mode in {"absolute", "abs"}:
				return {"absolute": _to_float(value)}

			if mode in {"relative", "rel"}:
				return {"relative": _to_float(value)}

			raise TypeError(f"Unknown threshold mode: {mode!r}")

	if isinstance(spec, Mapping):
		# noinspection PyUnnecessaryCast
		mapping = cast("Mapping[object, object]", spec)

		out: dict[str, float] = {}
		if "absolute" in mapping:
			out["absolute"] = _to_float(mapping["absolute"])

		if "abs" in mapping:
			out["absolute"] = _to_float(mapping["abs"])

		if "relative" in mapping:
			out["relative"] = _to_float(mapping["relative"])

		if "rel" in mapping:
			out["relative"] = _to_float(mapping["rel"])

		if "epsilon" in mapping:
			out["epsilon"] = _to_float(mapping["epsilon"])

		return out

	raise TypeError(
		"threshold must be a number, a ('absolute'|'relative', value) tuple, or a mapping!"
	)


def _resolve_threshold_for_name(
	name: str,
	threshold: object | None,
) -> dict[str, float] | None:
	if threshold is None:
		return None

	# A global spec applies to every watched variable
	if _is_single_threshold_spec(threshold):
		return _normalize_threshold_spec(threshold)

	if isinstance(threshold, Mapping):
		# noinspection PyUnnecessaryCast
		per_name = cast("Mapping[object, object]", threshold)

		# Per-name mapping {"velocity": ("relative", 0.1), "hp": ("absolute", 1)}
		for candidate in (name, name.split(".")[-1]):
			if candidate in per_name:
				return _normalize_threshold_spec(per_name[candidate])

	return None


def _differs(old: object, new: object) -> bool:
	"""
	Did the value change?
	numpy arrays, pandas frames and friends answer `!=` with an elementwise mask
	that raises on bool(), so collapse it with any() until a real bool falls out.
	"""

	if old is new:
		return False

	try:
		result = old != new
	except Exception:
		return True

	for _ in range(_MAX_MASK_REDUCTIONS):
		try:
			return bool(result)
		except Exception:
			pass

		reducer = getattr(result, "any", None)
		if not callable(reducer):
			break

		try:
			result = reducer()
		except Exception:
			break

	return True


def _passes_threshold(
	old: object, new: object, threshold: dict[str, float] | None
) -> bool:
	if old is _NO_VALUE:
		return True

	if threshold is None:
		return _differs(old, new)

	# Thresholds only for numbers
	if not (_is_number(old) and _is_number(new)):
		return _differs(old, new)

	delta = abs(float(new) - float(old))
	eps = threshold.get("epsilon", 1e-12)

	abs_th = threshold.get("absolute")
	if abs_th is not None and delta < abs_th:
		return False

	rel_th = threshold.get("relative")
	if rel_th is not None:
		base = max(abs(float(old)), eps)
		if delta / base < rel_th:
			return False

	return _differs(old, new)


def _global_tracer(frame: FrameType, event: str, arg: object) -> TraceFunction | None:
	"""Line tracer for names registered through watch() / log()"""

	previous = _g_previous_trace
	if previous is not None:
		try:
			# `event` is str so this also fits frame.f_trace, typed loosely
			# noinspection PyCallingNonCallable
			_ = previous(frame, cast("TraceEvent", event), arg)
		except Exception:
			pass

	watched = _g_watched_names.get(frame.f_code)
	if not watched:
		return None

	if event not in ("line", "return"):
		return _global_tracer

	filename = frame.f_code.co_filename
	current = cast("Mapping[str, object]", frame.f_locals)
	last = _slot(_g_last_seen, frame.f_code, dict)
	meta = _g_watch_meta.get(frame.f_code)

	# Values seen on statement N's line event were produced by N-1
	lineno = _g_last_line.get(frame, frame.f_lineno)

	if event == "line":
		_g_last_line[frame] = frame.f_lineno
	else:
		_ = _g_last_line.pop(frame, None)

	for name in watched:
		if name == "_" or name not in current:
			continue

		key = (frame.f_code, name)
		if key in _recently_emitted:
			_recently_emitted.discard(key)
			last[name] = current[name]  # Sync state
			continue

		value = current[name]
		old = last.get(name, _NO_VALUE)

		kind: Kind
		if old is _NO_VALUE:
			kind = "set"
		elif _differs(old, value):
			kind = "change"
		else:
			continue

		threshold = _resolve_threshold_for_name(
			name, (meta or {}).get(name, {}).get("threshold")
		)

		if not _passes_threshold(old, value, threshold):
			continue

		_emit(kind, name, value, filename=filename, lineno=lineno)
		last[name] = value

	return _global_tracer


def _install_global_trace(frame: FrameType | None = None) -> None:
	global _g_trace_installed, _g_previous_trace

	if not _g_trace_installed:
		existing = sys.gettrace()

		if existing is not _global_tracer:
			_g_previous_trace = existing

		sys.settrace(_global_tracer)
		_g_trace_installed = True
	elif sys.gettrace() is not _global_tracer:
		# Something replaced this, restore without losing the original
		sys.settrace(_global_tracer)

	# Frames already on the stack predate settrace and need f_trace set manually
	while frame is not None:
		if frame.f_code in _g_watched_names:
			frame.f_trace = _global_tracer

			_ = _g_last_line.setdefault(frame, frame.f_lineno)

		frame = frame.f_back


def _uninstall_global_trace() -> None:
	"""Remove the watcher and restore what preceded it, so it does not outlive its use"""

	global _g_trace_installed, _g_previous_trace

	if not _g_trace_installed:
		return

	if sys.gettrace() is _global_tracer:
		sys.settrace(_g_previous_trace)

	_g_trace_installed = False
	_g_previous_trace = None


def _reset_watch_state() -> None:
	"""Forget everything the watcher has accumulated"""

	_g_watched_names.clear()
	_g_last_seen.clear()
	_g_watch_meta.clear()
	_g_last_line.clear()
	_recently_emitted.clear()


__all__ = [
	"TraceEvent",
	"_mark_emitted",
	"_mark_watched",
	"_differs",
	"_passes_threshold",
	"_recently_emitted",
	"_resolve_threshold_for_name",
	"_global_tracer",
	"_install_global_trace",
	"_uninstall_global_trace",
	"_reset_watch_state",
]

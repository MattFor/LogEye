import sys

from numbers import Real
from time import monotonic
from types import FrameType
from collections.abc import Mapping

from logeye.emmiter import _emit

_NO_VALUE = object()

_recently_emitted: set[tuple] = set()

_g_trace_installed = False

_g_watched_names: dict[object, set[str]] = {}
_g_last_seen: dict[object, dict[str, object]] = {}
_g_last_emit_time: dict[object, dict[str, float]] = {}
_g_watch_meta: dict[object, dict[str, dict[str, object]]] = {}


def _mark_emitted(frame: FrameType, name: str) -> None:
	if not name:
		return

	_recently_emitted.add((frame.f_code, name))


def _mark_watched(frame: FrameType, name: str, *, threshold: object | None = None) -> None:
	if not name or name == "_":
		return

	_g_watched_names.setdefault(frame.f_code, set()).add(name)

	if threshold is not None:
		_g_watch_meta.setdefault(frame.f_code, {})[name] = {
			"threshold": threshold,
		}


# Threshold stuff

def _is_number(value: object) -> bool:
	return isinstance(value, Real) and not isinstance(value, bool)


def _is_single_threshold_spec(value: object) -> bool:
	if isinstance(value, (int, float)) and not isinstance(value, bool):
		return True

	if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
		return value[0] in {"absolute", "relative", "abs", "rel"}

	if isinstance(value, Mapping):
		return set(value.keys()) <= {"absolute", "abs", "relative", "rel", "epsilon"}

	return False


def _normalize_threshold_spec(spec: object) -> dict[str, float]:
	if spec is None:
		return {}

	if isinstance(spec, (int, float)) and not isinstance(spec, bool):
		return {"absolute": float(spec)}

	if isinstance(spec, tuple) and len(spec) == 2 and isinstance(spec[0], str):
		mode, value = spec

		if mode in {"absolute", "abs"}:
			return {"absolute": float(value)}

		if mode in {"relative", "rel"}:
			return {"relative": float(value)}

		raise TypeError(f"Unknown threshold mode: {mode!r}")

	if isinstance(spec, Mapping):
		out: dict[str, float] = {}
		if "absolute" in spec:
			out["absolute"] = float(spec["absolute"])

		if "abs" in spec:
			out["absolute"] = float(spec["abs"])

		if "relative" in spec:
			out["relative"] = float(spec["relative"])

		if "rel" in spec:
			out["relative"] = float(spec["rel"])

		if "epsilon" in spec:
			out["epsilon"] = float(spec["epsilon"])

		return out

	raise TypeError("threshold must be a number, a ('absolute'|'relative', value) tuple, or a mapping!")


def _resolve_threshold_for_name(
		name: str,
		threshold: object | None,
) -> dict[str, float] | None:
	if threshold is None:
		return None

	# Global spec applies to every watched variable
	if _is_single_threshold_spec(threshold):
		return _normalize_threshold_spec(threshold)

	if isinstance(threshold, Mapping):
		# Per-name mapping: {"velocity": ("relative", 0.1), "hp": ("absolute", 1)}
		for candidate in (name, name.split(".")[-1]):
			if candidate in threshold:
				return _normalize_threshold_spec(threshold[candidate])

	return None


def _passes_threshold(old: object, new: object, threshold: dict[str, float] | None) -> bool:
	# First observation always emits
	if old is _NO_VALUE:
		return True

	# No threshold means normal change detection
	if threshold is None:
		return old != new

	# Thresholds only make sense for numeric values
	if not (_is_number(old) and _is_number(new)):
		return old != new

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

	return old != new


def _install_global_trace(frame: FrameType | None = None) -> None:
	global _g_trace_installed
	if _g_trace_installed and frame is None:
		return

	def global_tracer(frame: FrameType, event: str, arg: object):
		# Let's see how it interacts with already logged stuff
		# if frame.f_code.co_name != "<module>":
		# 	return global_tracer

		if event not in ("line", "return"):
			return global_tracer

		watched = _g_watched_names.get(frame.f_code)
		if not watched:
			return global_tracer

		filename = frame.f_code.co_filename
		lineno = frame.f_lineno
		current = frame.f_locals
		last = _g_last_seen.setdefault(frame.f_code, {})

		for name in watched:
			if name not in current or name == "_":  # The _ guard is for safety so even if I break something later it won't show up regardless
				continue

			# Skip if manually emitted
			key = (frame.f_code, name)
			if key in _recently_emitted:
				_recently_emitted.remove(key)
				last[name] = current[name]  # Sync state
				continue

			value = current[name]

			old = last.get(name, _NO_VALUE)
			#
			# if old is None and name in last:
			# 	old = last[name]
			# elif name not in last:
			# 	old = _NO_VALUE

			meta = _g_watch_meta.get(frame.f_code, {}).get(name, {})
			threshold = _resolve_threshold_for_name(name, meta.get("threshold"))

			if old is _NO_VALUE:
				kind = "set"
			elif old != value:
				kind = "change"
			else:
				continue

			# TODO: Somewhere in here is a bug that causes repeat calls of log on the same function to display (set)
			# When in reality it should be (change) >:(
			if not _passes_threshold(old, value, threshold):
				continue

			_emit(kind, name, value, filename=filename, lineno=lineno)
			last[name] = value
			_g_last_emit_time.setdefault(frame.f_code, {})[name] = monotonic()

		return global_tracer

	# if not _g_trace_installed:
	# Let's always set it, see what happens
	sys.settrace(global_tracer)
	_g_trace_installed = True

	if frame is not None:
		while frame:
			frame.f_trace = global_tracer
			frame = frame.f_back

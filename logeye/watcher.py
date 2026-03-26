import sys
from types import FrameType

from logeye.emmiter import _emit

_NO_VALUE = object()

_recently_emitted: set[tuple] = set()

_g_watched_names: dict[object, set[str]] = {}
_g_last_seen: dict[object, dict[str, object]] = {}
_g_trace_installed = False


def _mark_emitted(frame: FrameType, name: str) -> None:
	if not name:
		return
	_recently_emitted.add((frame.f_code, name))


def _mark_watched(frame: FrameType, name: str) -> None:
	if not name:
		return

	_g_watched_names.setdefault(frame.f_code, set()).add(name)


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
			if name not in current:
				continue

			# Skip if manually emitted
			key = (frame.f_code, name)
			if key in _recently_emitted:
				_recently_emitted.remove(key)
				last[name] = current[name]  # Sync state
				continue

			value = current[name]
			old = last.get(name, _NO_VALUE)

			if old is _NO_VALUE:
				kind = "set"
			elif old != value:
				kind = "change"
			else:
				continue

			_emit(kind, name, value, filename=filename, lineno=lineno)
			last[name] = value

		return global_tracer

	# if not _g_trace_installed:
	# Let's always set it, see what happens
	sys.settrace(global_tracer)
	_g_trace_installed = True

	if frame is not None:
		while frame:
			frame.f_trace = global_tracer
			frame = frame.f_back

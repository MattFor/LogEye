import os
import sys

from types import FrameType

# Resolved once, recomputing per frame walk dominated _caller_frame
_LIBRARY_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
_LIBRARY_PREFIX = _LIBRARY_ROOT + os.sep

# co_filename -> part of logeye itself? Interned per code object, so stays tiny
_library_file_cache: dict[str, bool] = {}


def _is_library_file(filename: str) -> bool:
	cached = _library_file_cache.get(filename)
	if cached is not None:
		return cached

	if filename:
		resolved = os.path.abspath(filename)
		is_library = resolved == _LIBRARY_ROOT or resolved.startswith(_LIBRARY_PREFIX)
	else:
		is_library = False

	_library_file_cache[filename] = is_library
	return is_library


# Interpreter and third-party roots
_EXTERNAL_ROOTS = tuple(
	os.path.abspath(p) + os.sep
	for p in {
		os.path.dirname(os.__file__),
		sys.prefix,
		sys.base_prefix,
	}
	if p
)

_external_file_cache: dict[str, bool] = {}


def _is_external_code(filename: str) -> bool:
	"""True for the stdlib, site-packages and frozen modules: traceable, but noise"""

	cached = _external_file_cache.get(filename)
	if cached is not None:
		return cached

	if not filename:
		is_external = True
	elif filename.startswith("<"):
		# <string>, <stdin> are user code; <frozen ...> is not
		is_external = filename.startswith("<frozen")
	else:
		resolved = os.path.abspath(filename)
		is_external = (
			"site-packages" in resolved
			or "dist-packages" in resolved
			or resolved.startswith(_EXTERNAL_ROOTS)
		)

	_external_file_cache[filename] = is_external
	return is_external


def _get_location(frame: FrameType | None) -> tuple[str | None, int | None]:
	if frame is None:
		return None, None

	return frame.f_code.co_filename, frame.f_lineno


def _caller_frame() -> FrameType | None:
	"""Walk outwards to the first frame not inside logeye itself"""

	try:
		frame = sys._getframe(1)
	except ValueError:
		return None

	try:
		while frame is not None:
			if not _is_library_file(frame.f_code.co_filename):
				return frame

			frame = frame.f_back

		return None
	finally:
		del frame


__all__ = [
	"_get_location",
	"_caller_frame",
	"_is_library_file",
	"_is_external_code",
]

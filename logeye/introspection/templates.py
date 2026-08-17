import os
from string import Template

from .. import config
from .frames import _caller_frame, _get_location


def _expand_template(text: str) -> str:
	frame = _caller_frame()
	try:
		if frame is None:
			return text

		# Frame namespaces hold arbitrary values; Template stringifies them
		namespace: dict[str, object] = {}
		namespace.update(frame.f_globals)
		namespace.update(frame.f_locals)

		filename, _ = _get_location(frame)

		namespace["apath"] = filename or ""
		namespace["rpath"] = (
			os.path.relpath(filename, config._g_project_root) if filename else ""
		)
		namespace["fpath"] = os.path.basename(filename) if filename else ""

		return Template(text).safe_substitute(namespace)
	finally:
		del frame


__all__ = [
	"_expand_template",
]

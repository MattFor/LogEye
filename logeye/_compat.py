import sys

if sys.version_info >= (3, 12):
	from typing import override
else:
	# Runtime-only fallback for 3.10 / 3.11
	from typing import TypeVar  # pyright: ignore[reportUnreachable]

	_F = TypeVar("_F")

	def override(method: _F, /) -> _F:
		"""Backport of typing.override marks only the method"""

		try:
			method.__override__ = True
		except (AttributeError, TypeError):
			# Not every callable accepts attributes
			pass

		return method


__all__ = ["override"]

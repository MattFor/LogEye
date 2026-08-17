import json
import math
import functools
import warnings

from logeye import log

print("\n--- BUILTINS ---")

length = log(len)
length([1, 2, 3])

ordered = log(sorted)
ordered([3, 1, 2])

print("\n--- BOUND BUILTIN METHODS ---")

upper = log("hello".upper)
upper()

print("\n--- BUILTIN RAISE ---")

index = log([1, 2, 3].index)

try:
	index(99)  # (raise) ValueError and the error propagates
except ValueError:
	print("...ValueError propagated to the caller, as it should")

print("\n--- PARTIAL / CALLABLE OBJECTS ---")

at_least_ten = log(functools.partial(max, 10))
at_least_ten(4)


class Dispatcher:
	def __call__(self, value):
		return value * 2


dispatch = log(Dispatcher())
dispatch(21)

print("\n--- C EXTENSION FUNCTIONS ---")

sqrt = log(math.sqrt)
sqrt(144)

encode = log(json.encoder.encode_basestring_ascii)
encode("hi")

print("\n--- IMMUTABLE C TYPES ---")

with warnings.catch_warnings(record=True) as caught:
	warnings.simplefilter("always")
	logged_int = log(int)  # warns; an immutable C type cannot be patched

for entry in caught:
	print(f"...warned: {entry.message}")
	print(f"...blamed: {entry.filename.split('/')[-1]}:{entry.lineno}")

print(f"log(int) is int -> {logged_int is int}")
print(f"int('7') still works -> {int('7')}")

print("\n--- LEVEL / FILTER APPLY ---")

quiet = log(len, level="state")  # (return) only; no (call)
quiet([1, 2])

silent = log(len, filter=["nothing_matches"])
silent([1, 2])

print("\n--- ARRAY-LIKE LOCALS ---")

try:
	import numpy
except ImportError:
	numpy = None

if numpy is None:
	print("...numpy is not installed, skipping")
else:

	@log
	def scale(n):
		a = numpy.arange(n)
		a = a * 2
		return a.sum()

	scale(4)

	print("\n--- NUMPY C FUNC ---")

	array = log(numpy.array)
	array([1, 2, 3])

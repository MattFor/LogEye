from logeye import log, l
from functools import lru_cache


#
# Here I just post whatever is fun to try or to test new features!
# Can be edited from any branch - used for testing!
#

@log  # (mode="edu")
class Counter:
	def __init__(self):
		self.value = 0
		self._secret = 10

	def inc(self):
		self.value += 1
		return self.value

	def z(self, kind="w"):
		pass


c = l(Counter())

c._secret = 42

c.inc()

w = c.z(kind="wecwa") | l

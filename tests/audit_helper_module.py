from logeye import log


@log
def compute(n):
	doubled = n * 2
	shifted = doubled + 1
	return shifted

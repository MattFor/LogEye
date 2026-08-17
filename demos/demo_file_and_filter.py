from logeye import log, clear_log_file, set_global_log_file, toggle_global_log_file

LOG_FILES = (
	"demo_txt/global.log",
	"demo_txt/func.log",
	"demo_txt/special.log",
	"demo_txt/queue.log",
)

clear_log_file(*LOG_FILES)

print("\n--- Global file logging ---")

set_global_log_file("demo_txt/global.log")
toggle_global_log_file(True)

x = log(10)
y = log(20)
log("sum is {}", x + y)

print("\n--- Back to stdout ---")

toggle_global_log_file(False)
log("this goes to stdout")

print("\n--- Per-function file logging ---")


@log(filepath="demo_txt/func.log")
def add(a, b):
	total = a + b
	return total


add(2, 3)

print("\n--- Mixed file logging ---")

set_global_log_file("demo_txt/global.log")
toggle_global_log_file(True)


@log(filepath="demo_txt/special.log")
def special():
	x = 100
	return x


def normal():
	y = log(50)
	return y


special()  # special.log
normal()  # global.log

print("\n--- Filtering: basic ---")


@log(filter=["x"])
def foo():
	x = 10
	y = 20
	z = 30
	return x + y + z


foo()

print("\n--- Filtering: algorithm ---")


@log(filter=["distances", "queue"])
def dijkstra(graph, start):
	distances = {node: float("inf") for node in graph}
	distances[start] = 0

	queue = [(0, start)]

	while queue:
		dist, node = queue.pop(0)

		for neighbor, weight in graph[node].items():
			new_dist = dist + weight

			if new_dist < distances[neighbor]:
				distances[neighbor] = new_dist
				queue.append((new_dist, neighbor))

		queue.sort()

	return distances


graph = {"A": {"B": 1, "C": 4}, "B": {"C": 2, "D": 5}, "C": {"D": 1}, "D": {}}

dijkstra(graph, "A")

print("\n--- Filtering + file ---")


@log(filter=["queue"], filepath="demo_txt/queue.log")
def process():
	queue = []
	queue.append(1)
	queue.append(2)
	queue.pop(0)


process()

print("\n--- Filtering + level ---")


@log(level="state", filter=["x"])
def compute():
	x = 5
	y = 10
	z = x + y
	return z


compute()

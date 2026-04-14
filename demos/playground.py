from logeye import log, l, watch

#
# Here I just post whatever is fun to try or to test new features!
# Can be edited from any branch - used for testing!
#


x = log(100, threshold=("relative", 0.1))

x += 5
x += 6

y = log(10, threshold=("absolute", 3))

y += 1  # Ignored
y += 1  # Ignored
y += 2

z = log(100, threshold={"absolute": 2, "relative": 0.1})

z += 5  # abs=5 OK | rel=5% -> Ignored
z += 6


@log(threshold={"velocity": ("relative", 0.2)})
def simulate():
	velocity = 10
	velocity += 1  # 10% -> Ignored
	velocity += 1  # Still Ignored
	velocity += 3  # 30% -> Logged


simulate()


@log(
	threshold={
		"velocity": ("relative", 0.2),
		"hp": ("absolute", 5),
	}
)
def update():
	velocity = 10
	hp = 100

	velocity += 1  # Ignored
	hp -= 2  # Ignored

	velocity += 3  # Logged
	hp -= 5  # Logged


update()

velocity = 10 | log(threshold=("relative", 0.1))

velocity += 0.5  # Ignored
velocity += 1.0  # Logged

velocity = watch(10, threshold=("relative", 0.1))

velocity += 0.2  # Ignored
velocity += 1.0  # Logged

arr = log([10, 20, 30], threshold=("absolute", 5))

arr[0] += 2  # Ignored
arr[0] += 5  # Logged


@log(
	threshold={
		"velocity": ("relative", 0.05),
		"position": ("absolute", 1),
	}
)
def game_tick():
	velocity = 10.0
	position = 0.0

	for _ in range(5):
		velocity += 0.2
		position += velocity


game_tick()


@log(threshold={"x": ("absolute", 2)})
def compute():
	x = log(10, threshold=("relative", 0.2))

	x += 1  # Ignored
	x += 3  # Logged

	y = 5 | log(threshold=("absolute", 2))
	y += 1  # Ignored
	y += 2  # Logged


compute()

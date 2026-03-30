![PyPI](https://img.shields.io/pypi/v/logeye?cachebust=1774629933)
![Python](https://img.shields.io/pypi/pyversions/logeye)
![License](https://img.shields.io/github/license/MattFor/LogEye)

# LogEye

**Understand exactly what your code is doing in real time, no debugger needed.**

LogEye is a frictionless runtime logger for Python that shows variable changes, function calls, and data mutations as
they happen.

**Think of it as "print debugging" just better - automated, structured, easy to drop into, and remove from any codebase**

## Installation

```bash
pip install logeye
```

## Quick example
```python
from logeye import log

@log
def add(a, b):
	return a + b

add(2, 3)

@log(mode="edu")
def add_edu(a, b):
	return a + b

add_edu(2, 3)
```

Output:

```commandline
[0.000s] playground.py:7 (call) add args=(2, 3)
[0.000s] playground.py:5 (set) add.a = 2
[0.000s] playground.py:5 (set) add.b = 3
[0.000s] playground.py:5 (return) add args=(2, 3) -> 5
[0.000s] Calling add_edu(2, 3)
[0.000s] Defined add_edu.a = 2
[0.000s] Defined add_edu.b = 3
[0.000s] add_edu(2, 3) returned 5
```

# Table of Contents

- [Who is it for?](#who-is-it-for)
- [What does it do?](#what-does-it-do)
  - [What exactly does it track?](#what-exactly-does-it-track) 
- [Quick start](#quick-start)
- [Educational Mode](#educational-mode)
  - [Before vs After](#before-vs-after)
  - [What changes in educational mode](#what-changes-in-educational-mode)
  - [Example - Educational Factorial](#example---educational-factorial)
- [Logging functions](#logging-functions)
- [Advanced function logging](#advanced-function-logging)
- [Logging objects](#logging-objects)
- [Messages](#messages)
- [Utility functions](#utility-functions)
- [Output format](#output-format)
- [Some Usage Examples](#some-usage-examples)
- [Inspiration](#inspiration)
- [Limitations](#limitations)
- [Contact](#contact)
- [License](#license)

## Who is it for?

LogEye helps you see how your code executes step by step.

Perfect for:

- beginners learning programming
- students studying algorithms
- teachers explaining concepts

No more scattered `print()` calls. No debugger setup. Simply run your code and see everything.

Why keep doing this?
```python
print(x)
print(y)
print(queue)
```
When a single `| l` suffices?
```commandline
Added (1, 'B') to queue -> [(1, 'B')]
Sorted queue -> [(1, 'B'), (4, 'C')]
Popped (1, 'B') from queue
```

## What does it do?

Core features:

* educational mode for algorithm tracing
* log values with automatic variable name inference
* trace function calls, local variables, and returns
* track object and data structure mutations in real time
* format messages using f-string, template, or scope variables

Advanced features:

* filter variables and control verbosity (`level`, `filter`)
* log to files or stdout
* recursively track nested structures
* AST-based name inference (including multi-line assignments)

However, keep in mind that name inference is best-effort and may not be accurate in some more extreme cases.

### What exactly does it track?

Without changing your code, LogEye shows:

- function calls and returns
- local variables inside functions
- object attribute changes
- list / dict / set mutations
- nested structures
- recursion and call depth

## Quick start

```python
from logeye import log

x = log(10)
message = log("Hello from {name}", name="Matt")


@log(level="call")
def add(a, b):
	something = 2 + 2  # Unused
	return a + b


add(2, 2)

name = "Matt"
message2 = log("Hello from $name")

config = log({"debug": True, "port": 8080})
config.port = 9090
config["debug"] = False
```

Example output:

```commandline
[0.000s] playground.py:3 (set) x = 10
[0.024s] playground.py:4 (set) message = 'Hello from Matt'
[0.026s] playground.py:13 (call) add args=(2, 2)
[0.026s] playground.py:10 (return) add args=(2, 2) -> 4
[0.026s] playground.py:16 (set) message2 = 'Hello from Matt'
[0.027s] playground.py:18 (set) config = {'debug': True, 'port': 8080}
[0.027s] playground.py:19 (change) config.port = 9090
[0.027s] playground.py:20 (change) config.debug = False
```

# Educational Mode!

Educational mode is designed to make algorithms read like a story instead of a trace. :)

Instead of raw internal logs, it shows:

* clean function calls
* meaningful variable changes
* human-readable operations
* minimal noise

Enable it with:

```python
from logeye import log, set_mode

# Globally
set_mode("edu")


# Locally
@log(mode="edu")
def my_function():
	...
```

## Before vs After

### Default mode

```text
[0.000s] demo_dijkstra.py:36 (call) dijkstra args=({'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}, 'A')
[0.001s] demo_dijkstra.py:8 (set) dijkstra.graph = {'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}
[0.001s] demo_dijkstra.py:8 (set) dijkstra.start = 'A'
[0.001s] demo_dijkstra.py:8 (set) dijkstra.node = 'A'
...
[0.005s] demo_dijkstra.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (6, 'D'), 'state': []}
[0.005s] demo_dijkstra.py:17 (change) dijkstra.current_dist = 6
[0.005s] demo_dijkstra.py:31 (return) dijkstra args=({'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}, 'A') -> {'A': 0, 'B': 1, 'C': 3, 'D': 4}
```

---

### Educational mode

```text
[0.000s] demo_dijkstra.py:3 DIJKSTRA - SHORTEST PATH
[0.000s] Calling dijkstra({'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}, 'A')
[0.001s] Defined dijkstra.graph = {'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}
[0.001s] Defined dijkstra.start = 'A'
...
[0.004s] Sorted queue -> [(6, 'D')]
[0.005s] Popped (6, 'D') from queue
[0.005s] dijkstra.current_dist = 6
[0.005s] dijkstra({'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}, 'A') returned {'A': 0, 'B': 1, 'C': 3, 'D': 4}
```

## What changes in educational mode

* Function calls become readable:

  ```text
  Calling foo(1, b=2)
  ```

* No raw `args/kwargs` dictionaries

* Internal noise is removed:

    * no `<func ...>`
    * no test/module prefixes
    * no irrelevant internals

* Data structure operations are human-friendly:

  ```text
  Added 5 to arr -> [1, 2, 5]
  ```

## Example - Educational Factorial

```python
from logeye import log, l

l("FACTORIAL")


@log(mode="edu")
def factorial(n):
	if n == 1:
		return 1
	return n * factorial(n - 1)


factorial(5)
```

Output:

```text
[0.000s] FACTORIAL
[0.000s] Calling factorial(5)
[0.000s] Defined factorial.n = 5
[0.001s] Calling factorial#2(4)
[0.001s] Defined factorial#2.n = 4
[0.002s] Calling factorial#3(3)
[0.002s] Defined factorial#3.n = 3
[0.002s] Calling factorial#4(2)
[0.003s] Defined factorial#4.n = 2
[0.003s] Calling factorial#5(1)
[0.003s] Defined factorial#5.n = 1
[0.003s] factorial#5(1) returned 1
[0.003s] factorial#4(2) returned 2
[0.003s] factorial#3(3) returned 6
[0.003s] factorial#2(4) returned 24
[0.003s] factorial(5) returned 120
```

It’s especially useful for:

* learning recursion
* understanding sorting algorithms
* teaching data structures
* quickly verifying logic without a debugger

## Logging functions

Decorate a function or wrap it with `log`:

```python
from logeye import log


@log
def add(a, b):
	total = a + b
	return total


add(2, 3)
```

```commandline
[0.000s] playground.py:10 (call) add args=(2, 3)
[0.000s] playground.py:6 (set) add.a = 2
[0.000s] playground.py:6 (set) add.b = 3
[0.000s] playground.py:7 (set) add.total = 5
[0.000s] playground.py:7 (return) add args=(2, 3) -> 5
```

This will log:

* the function call
* local variable changes inside the function
* the return value

## Advanced function logging

You can customise how functions are logged using `@log(...)`:

### Control verbosity

```python
from logeye import log


@log(level="call")
def foo():
	x = 10
	return x
```

#### Levels:

* "call" - only function calls and returns
* "state" - variable changes only (no call spam)
* "full" - full tracing (default)

```python
from logeye import log


@log(filter=["x"])
def foo():
	x = 10
	y = 20
	return x + y
```

Only selected variables will be logged.

```python
from logeye import log


@log(filepath="logs/my_func.log")
def foo():
	x = 10
	return x
```

Logs for this function will be written to a file instead of stdout.

### Combos

```python
from logeye import log


@log(level="state", filter=["queue"], filepath="queue.log")
def process():
	queue = []
	queue.append(1)
	queue.append(2)
```

## Logging objects

`log()` can wrap mappings and objects with `__dict__` into a `LoggedObject`:

```python
from logeye import log

settings = log({"theme": "dark", "volume": 3})
settings.theme = "light"
settings.volume += 1
```

You can also pass an object:

```python
from logeye import *


@log
class User:
	def __init__(self):
		self.name = "Matt"
		self.active = True


user = l(User())
user.name = "For"
```

```commandline
[0.000s] playground.py:11 (call) user <- User.__init__
[0.000s] playground.py:7 (set) user.name = 'Matt'
[0.000s] playground.py:8 (set) user.active = True
[0.000s] playground.py:12 (change) user.name = 'For'
```

## Messages

Use `log()` with a string to emit a formatted message:

```python
from logeye import log

name = "Matt"
email = "mattfor@relaxy.xyz"
log("Current user: $name\nEmail: $email")

# Also works like this!
log("Current user: {}\nEmail: {}", "Matt", "mattfor@relaxy.xyz")
```

```commandline
[0.001s] demo9.py:5 
Current user: Matt
Email: mattfor@relaxy.xyz
[0.002s] demo9.py:7 
Current user: Matt
Email: mattfor@relaxy.xyz
```

`str.format()` is tried first. If that fails, the logger also tries caller globals / locals and template substitution.

## Utility functions

### `watch(value, name=None)`

Wraps a value for logging without changing its type unless needed.

### `toggle_logs(True/False)`

Disable or enable logging globally.

### `set_path_mode(mode)`

Controls how file paths are shown in output.

Accepted values:

* `absolute`
* `project`
* `file`

### `set_output_formatter(func)`

Replace the default formatter.

Signature:

```python
func(elapsed, kind, name, value, filename, lineno)
```

### `reset_output_formatter()`

Restore the built-in formatter.

## Output format

By default, messages look like this:  
(note, the path by default is relative to the run directory of the file you're launching the module in)

```commandline
[0.123s] path/to/file.py:42 (set) x = 10
```

For plain messages:

```commandline
[0.123s] path/to/file.py:42 some text
```

### File logging

```python
from logeye.config import set_global_log_file, toggle_global_log_file

set_global_log_file("logs/app.log")
toggle_global_log_file(True)
```

All logs will now be written to the specified file.
To disable: `toggle_global_log_file(False)`

# Some Usage Examples

<details> 

<summary><strong>Example 1: Master Demo, a bit of everything</strong></summary>

### Code

```python
from logeye import (
	log,
	l,
	set_path_mode,
	toggle_logs,
	reset_output_formatter,
	set_output_formatter,
)

log("=== BASIC MESSAGES ===", show_time=False, show_file=False, show_lineno=False)

x = 5
log("value is {}", x)
log("value via template: $x")
log("file absolute: $apath")
log("file relative: $rpath")
log("file name: $fpath")

log("\n=== ASSIGNMENTS ===", show_time=False, show_file=False, show_lineno=False)

a = log(10)
b = l(20)
c = 30 | l

# tuple unpacking
d, e = log("hello"), log("world")

log("\n=== EXPRESSIONS ===", show_time=False, show_file=False, show_lineno=False)

f = (10 + 5) | l
g = l(100 + 200)

log("\n=== FUNCTIONS ===", show_time=False, show_file=False, show_lineno=False)


@log
def add(a, b):
	total = a + b
	total = total * 2
	return total


res = add(3, 4)

log("\n=== NESTED FUNCTIONS ===", show_time=False, show_file=False, show_lineno=False)


@log
def outer(x):
	def inner(y):
		z = y + 1
		return z

	return inner(x)


outer(10)

log("\n=== LAMBDAS ===", show_time=False, show_file=False, show_lineno=False)

f = lambda: log("lambda called")
f()

g = lambda v: v * 2
g = l(g)  # wrap lambda
g(5)

log("\n=== OBJECT TRACKING ===", show_time=False, show_file=False, show_lineno=False)

obj = log({"x": 1, "nested": {"y": 2}})

obj.x = 10
obj.nested.y = 20
obj["x"] = 30

log("\n=== CLASS TRACKING ===", show_time=False, show_file=False, show_lineno=False)


@log
class User:
	def __init__(self, name):
		self.name = name
		self.active = True


user = l(User("Matt"))
user.name = "For"
user.active = False

log("\n=== PATH MODES ===", show_time=False, show_file=False, show_lineno=False)

set_path_mode("absolute")
log("absolute path mode")

set_path_mode("project")
log("project path mode")

set_path_mode("file")
log("file path mode")

log("\n=== CUSTOM FORMATTER ===", show_time=False, show_file=False, show_lineno=False)


def simple_formatter(elapsed, kind, name, value, filename, lineno):
	return f"{kind.upper()} -> {name}: {value}"


set_output_formatter(simple_formatter)

x = log(123)
log("formatted message")

reset_output_formatter()

log("\n=== ENABLE / DISABLE ===", show_time=False, show_file=False, show_lineno=False)

log("this should appear")

toggle_logs(False)
log("this should NOT appear")

toggle_logs(True)
log("logging back on")

log("\n=== MIXED USAGE ===", show_time=False, show_file=False, show_lineno=False)

value = (5 | l) * (10 | l)
log("final value is $value")
```

### Output

```commandline
=== BASIC MESSAGES ===
[0.001s] master_demo.py:13 value is 5
[0.002s] master_demo.py:14 value via template: 5
[0.003s] master_demo.py:15 file absolute: /home/mattfor/Programming/Python/LogEye/demos/master_demo.py
[0.004s] master_demo.py:16 file relative: master_demo.py
[0.005s] master_demo.py:17 file name: master_demo.py

=== ASSIGNMENTS ===
[0.006s] master_demo.py:21 (set) a = 10
[0.006s] master_demo.py:22 (set) b = 20
[0.007s] master_demo.py:23 (set) c = 30
[0.007s] master_demo.py:26 (set) d = 'hello'
[0.008s] master_demo.py:26 (set) e = 'world'

=== EXPRESSIONS ===
[0.016s] master_demo.py:30 (set) f = 15
[0.016s] master_demo.py:31 (set) g = 300

=== FUNCTIONS ===
[0.033s] master_demo.py:43 (call) add args=(3, 4)
[0.033s] master_demo.py:38 (set) add.a = 3
[0.033s] master_demo.py:38 (set) add.b = 4
[0.033s] master_demo.py:39 (set) add.total = 7
[0.033s] master_demo.py:40 (change) add.total = 14
[0.033s] master_demo.py:40 (return) add args=(3, 4) -> 14

=== NESTED FUNCTIONS ===
[0.049s] master_demo.py:57 (call) outer args=(10)
[0.050s] master_demo.py:50 (set) outer.x = 10
[0.050s] master_demo.py:50 (call) outer.inner
[0.050s] master_demo.py:50 (set) outer.inner = {'type': 'function', 'path': 'outer.inner', 'defaults': {'y': 10}}
[0.050s] master_demo.py:50 (set) outer.inner.y = 10
[0.050s] master_demo.py:52 (set) outer.inner.z = 11
[0.050s] master_demo.py:52 (return) outer.inner args=(10) -> 11
[0.050s] master_demo.py:54 (return) outer args=(10) -> 11

=== LAMBDAS ===
[0.058s] master_demo.py:62 (change) f = <function <lambda> at 0x7fe3a8fa7d70>
[0.066s] master_demo.py:61 lambda called
[0.066s] master_demo.py:65 (change) g = <function <lambda> at 0x7fe3a8fa7cc0>
[0.066s] master_demo.py:66 (change) g = <function <lambda> at 0x7fe3a8fa7ed0>
[0.074s] master_demo.py:66 (call) <lambda> args=(5)
[0.074s] master_demo.py:64 (set) <lambda>.v = 5
[0.074s] master_demo.py:64 (return) <lambda> args=(5) -> 10

=== OBJECT TRACKING ===
[0.083s] master_demo.py:70 (set) obj = {'x': 1, 'nested': {'y': 2}}
[0.083s] master_demo.py:72 (change) obj.x = 10
[0.083s] master_demo.py:73 (change) obj.nested.y = 20
[0.083s] master_demo.py:74 (change) obj.x = 30

=== CLASS TRACKING ===
[0.092s] master_demo.py:86 (call) user <- User.__init__ args=('Matt')
[0.092s] master_demo.py:82 (set) user.name = 'Matt'
[0.093s] master_demo.py:83 (set) user.active = True
[0.093s] master_demo.py:87 (change) user.name = 'For'
[0.093s] master_demo.py:88 (change) user.active = False

=== PATH MODES ===
[0.109s] /home/mattfor/Programming/Python/LogEye/demos/master_demo.py:93 absolute path mode
[0.118s] master_demo.py:96 project path mode
[0.126s] master_demo.py:99 file path mode

=== CUSTOM FORMATTER ===
[0.134s] master_demo.py:110 (set) x = 123
[0.143s] master_demo.py:111 formatted message

=== ENABLE / DISABLE ===
[0.159s] master_demo.py:117 this should appear
[0.167s] master_demo.py:123 logging back on

=== MIXED USAGE ===
[0.176s] master_demo.py:127 (set) value = 5
[0.176s] master_demo.py:127 (set) value = 10
[0.184s] master_demo.py:128 final value is 50
```

</details>

<details>

<summary><strong>Example 2: Factorial</strong></summary>

### Code

```python
from logeye import log, l

l("FACTORIAL - BY ITERATION")


# Iteration
@log
def factorial(n):
	result = 1
	for i in range(1, n + 1):
		result *= i
	return result


factorial(5)

l("FACTORIAL - BY RECURSION")


# Recursion
@log
def factorial(n):
	if n == 1:
		return 1
	return n * factorial(n - 1)


factorial(5)
```

## Output

```commandline
[0.000s] playground.py:3 FACTORIAL - BY ITERATION
[0.000s] playground.py:15 (call) factorial args=(5)
[0.000s] playground.py:9 (set) factorial.n = 5
[0.000s] playground.py:10 (set) factorial.result = 1
[0.000s] playground.py:11 (set) factorial.i = 1
[0.000s] playground.py:11 (change) factorial.i = 2
[0.000s] playground.py:10 (change) factorial.result = 2
[0.000s] playground.py:11 (change) factorial.i = 3
[0.000s] playground.py:10 (change) factorial.result = 6
[0.000s] playground.py:11 (change) factorial.i = 4
[0.000s] playground.py:10 (change) factorial.result = 24
[0.000s] playground.py:11 (change) factorial.i = 5
[0.000s] playground.py:10 (change) factorial.result = 120
[0.000s] playground.py:12 (return) factorial args=(5) -> 120
[0.001s] playground.py:17 FACTORIAL - BY RECURSION
[0.001s] playground.py:28 (call) factorial args=(5)
[0.001s] playground.py:23 (set) factorial.n = 5
[0.002s] playground.py:25 (call) factorial#2 args=(4)
[0.002s] playground.py:23 (set) factorial#2.n = 4
[0.004s] playground.py:25 (call) factorial#3 args=(3)
[0.004s] playground.py:23 (set) factorial#3.n = 3
[0.005s] playground.py:25 (call) factorial#4 args=(2)
[0.005s] playground.py:23 (set) factorial#4.n = 2
[0.006s] playground.py:25 (call) factorial#5 args=(1)
[0.006s] playground.py:23 (set) factorial#5.n = 1
[0.006s] playground.py:24 (return) factorial#5 args=(1) -> 1
[0.006s] playground.py:25 (return) factorial#4 args=(2) -> 2
[0.006s] playground.py:25 (return) factorial#3 args=(3) -> 6
[0.006s] playground.py:25 (return) factorial#2 args=(4) -> 24
[0.006s] playground.py:25 (return) factorial args=(5) -> 120
```

</details> 

<details> 

<summary><strong>Example 3: Dijkstra</strong></summary>

```python
from logeye import log, l

l("DIJKSTRA - SHORTEST PATH")


@log
def dijkstra(graph, start):
	distances = {node: float("inf") for node in graph}
	distances[start] = 0

	visited = set()
	queue = [(0, start)]

	while queue:
		current_dist, node = queue.pop(0)

		if node in visited:
			continue

		visited.add(node)

		for neighbor, weight in graph[node].items():
			new_dist = current_dist + weight

			if new_dist < distances[neighbor]:
				distances[neighbor] = new_dist
				queue.append((new_dist, neighbor))

		queue.sort()

	return distances


graph = {
	"A": {"B": 1, "C": 4},
	"B": {"C": 2, "D": 5},
	"C": {"D": 1},
	"D": {}
}

dijkstra(graph, "A")
```

## Output

```commandline
[0.000s] playground.py:3 DIJKSTRA - SHORTEST PATH
[0.001s] playground.py:41 (call) dijkstra args=({'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}, 'A')
[0.001s] playground.py:8 (set) dijkstra.graph = {'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}
[0.001s] playground.py:8 (set) dijkstra.start = 'A'
[0.001s] playground.py:8 (set) dijkstra.node = 'A'
[0.001s] playground.py:8 (change) dijkstra.node = 'B'
[0.001s] playground.py:8 (change) dijkstra.node = 'C'
[0.001s] playground.py:8 (change) dijkstra.node = 'D'
[0.001s] playground.py:9 (set) dijkstra.distances = {'A': inf, 'B': inf, 'C': inf, 'D': inf}
[0.001s] playground.py:9 (change) dijkstra.distances.A = 0
[0.002s] playground.py:12 (set) dijkstra.visited = set()
[0.002s] playground.py:14 (set) dijkstra.queue = [(0, 'A')]
[0.002s] playground.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (0, 'A'), 'state': []}
[0.002s] playground.py:17 (change) dijkstra.node = 'A'
[0.002s] playground.py:17 (set) dijkstra.current_dist = 0
[0.002s] playground.py:20 (change) dijkstra.visited = {'op': 'add', 'value': 'A', 'state': {'A'}}
[0.002s] playground.py:23 (set) dijkstra.neighbor = 'B'
[0.002s] playground.py:23 (set) dijkstra.weight = 1
[0.002s] playground.py:25 (set) dijkstra.new_dist = 1
[0.002s] playground.py:26 (change) dijkstra.distances.B = 1
[0.002s] playground.py:27 (change) dijkstra.queue = {'op': 'append', 'value': (1, 'B'), 'state': [(1, 'B')]}
[0.003s] playground.py:23 (change) dijkstra.neighbor = 'C'
[0.003s] playground.py:23 (change) dijkstra.weight = 4
[0.003s] playground.py:25 (change) dijkstra.new_dist = 4
[0.003s] playground.py:26 (change) dijkstra.distances.C = 4
[0.003s] playground.py:27 (change) dijkstra.queue = {'op': 'append', 'value': (4, 'C'), 'state': [(1, 'B'), (4, 'C')]}
[0.003s] playground.py:29 (change) dijkstra.queue = {'op': 'sort', 'args': (), 'kwargs': {}, 'state': [(1, 'B'), (4, 'C')]}
[0.003s] playground.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (1, 'B'), 'state': [(4, 'C')]}
[0.003s] playground.py:17 (change) dijkstra.node = 'B'
[0.003s] playground.py:17 (change) dijkstra.current_dist = 1
[0.003s] playground.py:20 (change) dijkstra.visited = {'op': 'add', 'value': 'B', 'state': {'B', 'A'}}
[0.003s] playground.py:23 (change) dijkstra.weight = 2
[0.003s] playground.py:25 (change) dijkstra.new_dist = 3
[0.003s] playground.py:26 (change) dijkstra.distances.C = 3
[0.004s] playground.py:27 (change) dijkstra.queue = {'op': 'append', 'value': (3, 'C'), 'state': [(4, 'C'), (3, 'C')]}
[0.004s] playground.py:23 (change) dijkstra.neighbor = 'D'
[0.004s] playground.py:23 (change) dijkstra.weight = 5
[0.004s] playground.py:25 (change) dijkstra.new_dist = 6
[0.004s] playground.py:26 (change) dijkstra.distances.D = 6
[0.004s] playground.py:27 (change) dijkstra.queue = {'op': 'append', 'value': (6, 'D'), 'state': [(4, 'C'), (3, 'C'), (6, 'D')]}
[0.004s] playground.py:29 (change) dijkstra.queue = {'op': 'sort', 'args': (), 'kwargs': {}, 'state': [(3, 'C'), (4, 'C'), (6, 'D')]}
[0.004s] playground.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (3, 'C'), 'state': [(4, 'C'), (6, 'D')]}
[0.004s] playground.py:17 (change) dijkstra.node = 'C'
[0.004s] playground.py:17 (change) dijkstra.current_dist = 3
[0.004s] playground.py:20 (change) dijkstra.visited = {'op': 'add', 'value': 'C', 'state': {'B', 'C', 'A'}}
[0.005s] playground.py:23 (change) dijkstra.weight = 1
[0.005s] playground.py:25 (change) dijkstra.new_dist = 4
[0.005s] playground.py:26 (change) dijkstra.distances.D = 4
[0.005s] playground.py:27 (change) dijkstra.queue = {'op': 'append', 'value': (4, 'D'), 'state': [(4, 'C'), (6, 'D'), (4, 'D')]}
[0.005s] playground.py:29 (change) dijkstra.queue = {'op': 'sort', 'args': (), 'kwargs': {}, 'state': [(4, 'C'), (4, 'D'), (6, 'D')]}
[0.005s] playground.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (4, 'C'), 'state': [(4, 'D'), (6, 'D')]}
[0.005s] playground.py:17 (change) dijkstra.current_dist = 4
[0.005s] playground.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (4, 'D'), 'state': [(6, 'D')]}
[0.005s] playground.py:17 (change) dijkstra.node = 'D'
[0.006s] playground.py:20 (change) dijkstra.visited = {'op': 'add', 'value': 'D', 'state': {'B', 'C', 'D', 'A'}}
[0.006s] playground.py:29 (change) dijkstra.queue = {'op': 'sort', 'args': (), 'kwargs': {}, 'state': [(6, 'D')]}
[0.006s] playground.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (6, 'D'), 'state': []}
[0.006s] playground.py:17 (change) dijkstra.current_dist = 6
[0.006s] playground.py:31 (return) dijkstra args=({'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}, 'A') -> {'A': 0, 'B': 1, 'C': 3, 'D': 4}
```

</details>

# Inspiration

Idea came to be during Warsaw IT Days 2026. During the Python lecture "Logging module adventures".  
I thought there definitely was an easier way to do it without repeating yourself constantly, and it turns out there was!

## Limitations

* variable name inference is **best-effort** and may fail in complex or highly dynamic expressions
* some edge cases (e.g. deeply nested calls, chained expressions, unusual syntax) may fall back to a generic name like
  `"set"`
* lambda functions are **not automatically traced** unless explicitly wrapped with `log()`
* function tracing relies on `sys.settrace()` and may introduce overhead in performance-sensitive code
* logging inside heavily recursive or multithreaded code may produce noisy or hard-to-follow output
* AST-based analysis requires access to source files and may not work correctly in environments without source code (
  e.g. compiled/obfuscated code, some REPLs)
* tuple assignment tracking depends on call order and may behave unexpectedly in complex expressions
* object wrapping only supports mappings and objects with `__dict__`
* custom objects with unusual attribute behaviour may not be fully tracked
* logging output is intended for debugging and introspection, not structured logging or production telemetry
* local variables may be wrapped at runtime to enable mutation tracking, which can affect identity checks and edge-case
  behaviour

## Contact

If you have questions, ideas, or run into issues:

- please open an issue!
- or email me mattfor@relaxy.xyz
- or add me on discord @mattfor

## Notable contributors

- @OutSquareCapital Helped with typing and refactoring

## License

MIT License © 2026

See [LICENSE](LICENSE) for details.

Version 1.5.0


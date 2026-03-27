![PyPI](https://img.shields.io/pypi/v/logeye?cachebust=1774629933)
![Python](https://img.shields.io/pypi/pyversions/logeye)
![License](https://img.shields.io/github/license/MattFor/LogEye)

# LogEye

Understand exactly what your code is doing in real time, no debugger needed.  

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
[0.000s] playground.py:7 (call) add = {'args': (2, 3), 'kwargs': {}}
[0.000s] playground.py:5 (set) add.a = 2
[0.000s] playground.py:5 (set) add.b = 3
[0.000s] playground.py:5 (return) add = 5
[0.000s] Calling add_edu(2, 3)
[0.000s] a = 2
[0.000s] b = 3
[0.000s] add_edu(2, 3) returned 5
```

# Table of Contents

- [Who is it for](#who-is-it-for)
- [What does it do](#what-does-it-do)
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

## Who is it for

LogEye helps you see how your code executes step by step.

Perfect for:

- beginners learning programming
- students studying algorithms
- teachers explaining concepts

No more scattered `print()` calls. No debugger setup. Just run your code and see everything.

## What does it do

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

## Quick start

```python
from logeye import log

x = log(10)
message = log("Hello from {name}", name="Matt")


@log(level="call")
def add(a, b):
	something = 2 + 2
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
[0.000s] playground.py:4 (set) message = 'Hello from Matt'
[0.000s] playground.py:13 (call) add = {'args': (2, 2), 'kwargs': {}}
[0.000s] playground.py:10 (return) add = 4
[0.000s] playground.py:16 (set) message2 = 'Hello from Matt'
[0.001s] playground.py:18 (set) config = {'debug': True, 'port': 8080}
[0.001s] playground.py:19 (set) config.port = 9090
[0.001s] playground.py:20 (set) config.debug = False
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
[0.000s] (call) factorial = {'args': (5,), 'kwargs': {}}
[0.000s] (set) factorial.n = 5
[0.000s] (set) factorial.result = 1
[0.000s] (set) factorial.i = 1
[0.000s] (set) factorial.result = 2
...
[0.001s] (return) factorial = 120
```

---

### Educational mode

```text
[0.000s] Calling factorial(5)
[0.000s] n = 5
[0.000s] Calling factorial#2(4)
[0.000s] n = 4
[0.000s] Calling factorial#3(3)
[0.000s] n = 3
[0.000s] Calling factorial#4(2)
[0.000s] n = 2
[0.000s] Calling factorial#5(1)
[0.000s] n = 1
[0.000s] factorial#5(1) returned 1
[0.000s] factorial#4(2) returned 2
[0.000s] factorial#3(3) returned 6
[0.000s] factorial#2(4) returned 24
[0.001s] factorial(5) returned 120
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
[0.000s] n = 5
[0.000s] Calling factorial#2(4)
[0.000s] n = 4
[0.000s] Calling factorial#3(3)
[0.000s] n = 3
[0.000s] Calling factorial#4(2)
[0.000s] n = 2
[0.000s] Calling factorial#5(1)
[0.001s] n = 1
[0.001s] factorial#5(1) returned 1
[0.001s] factorial#4(2) returned 2
[0.001s] factorial#3(3) returned 6
[0.001s] factorial#2(4) returned 24
[0.001s] factorial(5) returned 120
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
[0.001s] demo9.py:17 (call) add = {'args': (2, 3), 'kwargs': {}}
[0.001s] demo9.py:13 (set) add.a = 2
[0.001s] demo9.py:13 (set) add.b = 3
[0.001s] demo9.py:14 (set) add.total = 5
[0.001s] demo9.py:14 (return) add = 5
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
[0.001s] demo8.py:11 (call) User.__init__ = {'args': (<__main__.User object at 0x7fbacb1f0980>,), 'kwargs': {}}
[0.001s] demo8.py:7 (set) user.name = 'Matt'
[0.001s] demo8.py:8 (set) user.active = True
[0.001s] demo8.py:11 (set) user = {}
[0.001s] demo8.py:12 (set) user.name = 'For'
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

<summary><strong>Example 1: Factorial</strong></summary>

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
[0.002s] demo_factorial.py:3 FACTORIAL - BY ITERATION
[0.002s] demo_factorial.py:15 (call) factorial = {'args': (5,), 'kwargs': {}}
[0.002s] demo_factorial.py:9 (set) factorial.n = 5
[0.002s] demo_factorial.py:10 (set) factorial.result = 1
[0.002s] demo_factorial.py:11 (set) factorial.i = 1
[0.002s] demo_factorial.py:11 (set) factorial.i = 2
[0.002s] demo_factorial.py:10 (set) factorial.result = 2
[0.002s] demo_factorial.py:11 (set) factorial.i = 3
[0.002s] demo_factorial.py:10 (set) factorial.result = 6
[0.002s] demo_factorial.py:11 (set) factorial.i = 4
[0.002s] demo_factorial.py:10 (set) factorial.result = 24
[0.002s] demo_factorial.py:11 (set) factorial.i = 5
[0.002s] demo_factorial.py:10 (set) factorial.result = 120
[0.002s] demo_factorial.py:12 (return) factorial = 120
[0.002s] demo_factorial.py:17 FACTORIAL - BY RECURRENCY
[0.002s] demo_factorial.py:28 (call) factorial = {'args': (5,), 'kwargs': {}}
[0.002s] demo_factorial.py:23 (set) factorial.n = 5
[0.002s] demo_factorial.py:25 (call) factorial_2 = {'args': (4,), 'kwargs': {}}
[0.002s] demo_factorial.py:23 (set) factorial_2.n = 4
[0.002s] demo_factorial.py:25 (call) factorial_3 = {'args': (3,), 'kwargs': {}}
[0.002s] demo_factorial.py:23 (set) factorial_3.n = 3
[0.002s] demo_factorial.py:25 (call) factorial_4 = {'args': (2,), 'kwargs': {}}
[0.002s] demo_factorial.py:23 (set) factorial_4.n = 2
[0.002s] demo_factorial.py:25 (call) factorial_5 = {'args': (1,), 'kwargs': {}}
[0.002s] demo_factorial.py:23 (set) factorial_5.n = 1
[0.002s] demo_factorial.py:24 (return) factorial_5 = 1
[0.002s] demo_factorial.py:25 (return) factorial_4 = 2
[0.002s] demo_factorial.py:25 (return) factorial_3 = 6
[0.002s] demo_factorial.py:25 (return) factorial_2 = 24
[0.002s] demo_factorial.py:25 (return) factorial = 120
```

</details> 

<details> 

<summary><strong>Example 2: Dijkstra</strong></summary>

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
[0.000s] demo_dijkstra.py:3 DIJKSTRA - SHORTEST PATH
[0.000s] demo_dijkstra.py:41 (call) dijkstra = {'args': ({'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}, 'A'), 'kwargs': {}}
[0.000s] demo_dijkstra.py:8 (set) dijkstra.graph = {'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}
[0.000s] demo_dijkstra.py:8 (set) dijkstra.start = 'A'
[0.000s] demo_dijkstra.py:8 (set) dijkstra.node = 'A'
[0.000s] demo_dijkstra.py:8 (set) dijkstra.node = 'B'
[0.000s] demo_dijkstra.py:8 (set) dijkstra.node = 'C'
[0.000s] demo_dijkstra.py:8 (set) dijkstra.node = 'D'
[0.000s] demo_dijkstra.py:9 (set) dijkstra.distances = {'A': inf, 'B': inf, 'C': inf, 'D': inf}
[0.000s] demo_dijkstra.py:9 (change) dijkstra.distances.A = {'op': 'setitem', 'value': 0, 'state': {'A': 0, 'B': inf, 'C': inf, 'D': inf}}
[0.000s] demo_dijkstra.py:12 (set) dijkstra.visited = set()
[0.000s] demo_dijkstra.py:14 (set) dijkstra.queue = [(0, 'A')]
[0.001s] demo_dijkstra.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (0, 'A'), 'state': []}
[0.001s] demo_dijkstra.py:17 (set) dijkstra.node = 'A'
[0.001s] demo_dijkstra.py:17 (set) dijkstra.current_dist = 0
[0.001s] demo_dijkstra.py:20 (change) dijkstra.visited = {'op': 'add', 'value': 'A', 'state': {'A'}}
[0.001s] demo_dijkstra.py:23 (set) dijkstra.neighbor = 'B'
[0.001s] demo_dijkstra.py:23 (set) dijkstra.weight = 1
[0.001s] demo_dijkstra.py:25 (set) dijkstra.new_dist = 1
[0.001s] demo_dijkstra.py:26 (change) dijkstra.distances.B = {'op': 'setitem', 'value': 1, 'state': {'A': 0, 'B': 1, 'C': inf, 'D': inf}}
[0.001s] demo_dijkstra.py:27 (change) dijkstra.queue = {'op': 'append', 'value': (1, 'B'), 'state': [(1, 'B')]}
[0.001s] demo_dijkstra.py:23 (set) dijkstra.neighbor = 'C'
[0.001s] demo_dijkstra.py:23 (set) dijkstra.weight = 4
[0.001s] demo_dijkstra.py:25 (set) dijkstra.new_dist = 4
[0.001s] demo_dijkstra.py:26 (change) dijkstra.distances.C = {'op': 'setitem', 'value': 4, 'state': {'A': 0, 'B': 1, 'C': 4, 'D': inf}}
[0.001s] demo_dijkstra.py:27 (change) dijkstra.queue = {'op': 'append', 'value': (4, 'C'), 'state': [(1, 'B'), (4, 'C')]}
[0.001s] demo_dijkstra.py:29 (change) dijkstra.queue = {'op': 'sort', 'args': (), 'kwargs': {}, 'state': [(1, 'B'), (4, 'C')]}
[0.001s] demo_dijkstra.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (1, 'B'), 'state': [(4, 'C')]}
[0.001s] demo_dijkstra.py:17 (set) dijkstra.node = 'B'
[0.001s] demo_dijkstra.py:17 (set) dijkstra.current_dist = 1
[0.001s] demo_dijkstra.py:20 (change) dijkstra.visited = {'op': 'add', 'value': 'B', 'state': {'A', 'B'}}
[0.001s] demo_dijkstra.py:23 (set) dijkstra.weight = 2
[0.001s] demo_dijkstra.py:25 (set) dijkstra.new_dist = 3
[0.002s] demo_dijkstra.py:26 (change) dijkstra.distances.C = {'op': 'setitem', 'value': 3, 'state': {'A': 0, 'B': 1, 'C': 3, 'D': inf}}
[0.002s] demo_dijkstra.py:27 (change) dijkstra.queue = {'op': 'append', 'value': (3, 'C'), 'state': [(4, 'C'), (3, 'C')]}
[0.002s] demo_dijkstra.py:23 (set) dijkstra.neighbor = 'D'
[0.002s] demo_dijkstra.py:23 (set) dijkstra.weight = 5
[0.002s] demo_dijkstra.py:25 (set) dijkstra.new_dist = 6
[0.002s] demo_dijkstra.py:26 (change) dijkstra.distances.D = {'op': 'setitem', 'value': 6, 'state': {'A': 0, 'B': 1, 'C': 3, 'D': 6}}
[0.002s] demo_dijkstra.py:27 (change) dijkstra.queue = {'op': 'append', 'value': (6, 'D'), 'state': [(4, 'C'), (3, 'C'), (6, 'D')]}
[0.002s] demo_dijkstra.py:29 (change) dijkstra.queue = {'op': 'sort', 'args': (), 'kwargs': {}, 'state': [(3, 'C'), (4, 'C'), (6, 'D')]}
[0.002s] demo_dijkstra.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (3, 'C'), 'state': [(4, 'C'), (6, 'D')]}
[0.002s] demo_dijkstra.py:17 (set) dijkstra.node = 'C'
[0.002s] demo_dijkstra.py:17 (set) dijkstra.current_dist = 3
[0.002s] demo_dijkstra.py:20 (change) dijkstra.visited = {'op': 'add', 'value': 'C', 'state': {'C', 'A', 'B'}}
[0.002s] demo_dijkstra.py:23 (set) dijkstra.weight = 1
[0.002s] demo_dijkstra.py:25 (set) dijkstra.new_dist = 4
[0.002s] demo_dijkstra.py:26 (change) dijkstra.distances.D = {'op': 'setitem', 'value': 4, 'state': {'A': 0, 'B': 1, 'C': 3, 'D': 4}}
[0.003s] demo_dijkstra.py:27 (change) dijkstra.queue = {'op': 'append', 'value': (4, 'D'), 'state': [(4, 'C'), (6, 'D'), (4, 'D')]}
[0.003s] demo_dijkstra.py:29 (change) dijkstra.queue = {'op': 'sort', 'args': (), 'kwargs': {}, 'state': [(4, 'C'), (4, 'D'), (6, 'D')]}
[0.003s] demo_dijkstra.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (4, 'C'), 'state': [(4, 'D'), (6, 'D')]}
[0.003s] demo_dijkstra.py:17 (set) dijkstra.current_dist = 4
[0.003s] demo_dijkstra.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (4, 'D'), 'state': [(6, 'D')]}
[0.003s] demo_dijkstra.py:17 (set) dijkstra.node = 'D'
[0.003s] demo_dijkstra.py:20 (change) dijkstra.visited = {'op': 'add', 'value': 'D', 'state': {'C', 'A', 'D', 'B'}}
[0.003s] demo_dijkstra.py:29 (change) dijkstra.queue = {'op': 'sort', 'args': (), 'kwargs': {}, 'state': [(6, 'D')]}
[0.003s] demo_dijkstra.py:15 (change) dijkstra.queue = {'op': 'pop', 'index': 0, 'value': (6, 'D'), 'state': []}
[0.003s] demo_dijkstra.py:17 (set) dijkstra.current_dist = 6
[0.003s] demo_dijkstra.py:31 (return) dijkstra = {'A': 0, 'B': 1, 'C': 3, 'D': 4}
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

## License

MIT License © 2026

See [LICENSE](LICENSE) for details.

Version 1.5.0


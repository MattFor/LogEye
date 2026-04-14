# Changelog

## [1.5.2] - 2026-04-15

### Added

* **Threshold-based change filtering**

    * New `threshold` parameter for `log()` and `watch()` to control when changes are emitted
    * Supports:

        * Absolute thresholds:
          ```python
          x = log(10, threshold=5)
          ```

        * Relative thresholds:
          ```python
          x = log(100, threshold=("relative", 0.1))  # 10%
          ```

        * Combined thresholds:
          ```python
          x = log(100, threshold={"absolute": 5, "relative": 0.1})
          ```

        * Per-variable thresholds in functions:
          ```python
          @log(threshold={"x": ("relative", 0.2)})
          def f():
              x = 10
              x += 1   # Ignored here
              x += 3   # Emitted normally
          ```

    * Prevents noisy logs from small fluctuations
    * Works with:

        * scalar values
        * function-local variables
        * watched variables (`watch`)
        * nested structures (e.g. `arr[0]`)

    * First assignment always emits (`(set)`), a threshold applies only to `(change)`

### Changed

* Function-level tracing now integrates threshold filtering directly (no longer depends on global watcher state)

---

## [1.5.1] - 2026-03-30

### Fixed

* _infer_name_from_frame incorrectly returning "set" as a default option when literally nothing is found,   
  instead it now returns None so that the pipe operator single messages work correctly,  
  also adjusted the default to be PLACEHOLDER and not "set" to avoid confusion
* Fixed incorrect self-referencing of basic types

### Changed

* Updated examples
* Better formatting in educational mode
* Better formatting in code

---

## [1.5.0] - 2026-03-27

### Added

* **Global variable tracking improvements**

    * `var = log(val)` now reliably registers variables for continuous tracking
    * Improved watcher integration with global trace system  
      For example:
      ```python
      x = "xyz" | l
      
      x = 10
      x = {"a": 1, "b": 2}
      x = "xyz"
      ```
      Completely automatically does this!
      ```commandline
      [0.000s] demo1.py:15 (set) x = 'xyz'
      [0.000s] demo1.py:18 (change) x = 10
      [0.000s] demo1.py:19 (change) x = {'a': 1, 'b': 2}
      [0.000s] demo1.py:21 (change) x = 'xyz'
      ```

* **Class instrumentation (`@log` on classes)**

    * Logs `__init__` calls with arguments
    * Tracks attribute assignments on instances
    * Supports mutation detection:

        * `(set)` for first assignment
        * `(change)` for updates
    * Attribute deletion tracking (`<deleted>`)
    * Private attributes are now logged with `<priv>` prefix  
      Automatic garbage noise differentiation between _hidden and _stdlibstuff!

* **Deep nested structure tracking**

    * Enables mutation logging like:

        * `obj.user["name"] = ...`
        * `obj.items.append(...)`

* **log and l unification**

    * Both log and l now refer to the same function
    * `log` is now the preferred function for logging
    * `l` is preferred for pipe operations
  ```python
  x = "xyz" | l # For tracking variables
  log("X is $x") # For manual logging
  ```

* **Full class method logging**

    * Methods inside `@log` classes are now fully traced
    * Includes:

        * method calls (`(call) obj.method`)
        * returns (`(return) obj.method -> value`)
        * internal state mutations during method execution
    * Class instances now behave like fully traceable execution scopes

* **Directional flow indicators**

    * Introduced clearer execution flow markers:

        * `->` for outputs / returns
        * `<-` (internally / structurally) for flow consistency
    * Improves readability of execution traces, especially for nested calls

* **Educational mode improvements**

    * Better alignment with real execution order:

        * `Calling -> state changes -> return`
    * More consistent variable display (`x = value`)
    * Reduced ambiguity between definition vs mutation
    * Cleaner, more predictable output for testing

### Changed

* **Stricter and expanded test suite**

    * Standardised output capturing using `capture(capsys)`
    * Introduced reusable assertion helpers across all test files

* **Educational test expectations tightened**

    * Tests now assert:

        * exact number of lines
        * exact ordering of events
    * Prevents regression via accidental extra logs

* **Formatting consistency overhaul**

    * Unified output across:
        * message logging
        * function tracing
        * object mutations
    * Reduced inconsistencies between different logging paths

### Fixed

* Nested function names appearing incorrectly (e.g. `test_x.outer.inner`)
* Duplicate function definition emissions (`Defined inner()` appearing twice)
* Missing default arguments in nested function definitions
* Incorrect ordering of:
    * `Calling inner()`
    * `Defined outer.inner(...)`
* Lambda logging inconsistencies (missing or duplicated outputs)
* Variable tracking inside nested scopes
* Attribute access issues when wrapping class instances
* Broken method calls on logged class instances (`LoggedObject` conflicts)
* Nested structure mutations not being tracked correctly
* List/dict attributes not emitting mutation events
* Recursion errors in self-referencing structures
* Mixed formatting (`{}` + `$var`) not expanding correctly
* Pipe operator edge cases and name inference issues

### Discovered Limitations

* **C-based decorators (e.g. `functools.lru_cache`)**

    * Inner execution cannot be traced due to lack of Python-level introspection

* **Nested assignment unpacking**

    * Complex patterns like:

      ```python
      (a, (b, c)) = ...
      ```
    * Only partially tracked due to Python runtime limitations (no full AST access)  
      However! I will be getting to this soon!

### Dev

* Significantly expanded test suite for edge cases and complex scenarios
* Improved internal structure for future features (method tracing, advanced introspection)
* Added multiple branches for easier separation:
    * master -> stable
    * dev -> development
    * readme-changelog -> documentation
    * feature -> feature branches
    * tests -> test coverage
    * demos -> demos and examples

### Plans

* **Repeated identical assignments edge case**

    * Intended behavior:

      ```python
      x = "a" | l
      x = "a"
      x = "a"
      ```

      should produce:

      ```
      (set) x = 'a'
      (change) x = 'a'
      (change) x = 'a'
      ```
    * Currently not fully implemented in all paths
* Upcoming feature plans are now just the sub-branches on the features/ branch.
* Standardising and improving demos and documentation

---

## [1.4.0] - 2026-03-24

### Added

* Educational mode now includes clear return output:
    * `(function) returned (value)` style formatting for better readability
* Integrated Ruff for consistent formatting and linting
* Added basedpyright for static type checking
* Introduced initial type annotations across the codebase
* Improved educational mode examples in README and demos

### Changed

* Improved consistency of call and return formatting
* Updated publishing pipeline:
    * automatic Ruff formatting
    * lint + type checks during release
* Internal refactors to support typing and future maintainability

### Fixed

* Various formatting inconsistencies between full and educational modes
* Edge cases in return logging output
* Minor issues in logging behaviour uncovered during type integration

### Developer Experience

* Added Ruff integration for standardised code style
* Added basedpyright integration for type safety
* Improved contribution workflow and code consistency

### Plans

* Multithreading support!

---

## [1.3.2] - 2026-03-24

### Added

* set_mode() for setting the mode globally (f.e to education)
* More tests for the global mode setting

### Improved

* README examples

---

## [1.3.1] - 2026-03-24

### Added

* Comprehensive README overhaul with clearer structure and examples

### Dev

* Improved release pipeline with automated versioning and GitHub releases

---

## [1.3.0] - 2026-03-24

### Added

* **Educational logging mode (`mode="edu"`)**

    * Human-readable, step-by-step output for learning and algorithm tracing
    * Function calls rendered as:

      ```
      Calling foo(1, b=2)
      ```
    * Automatic argument formatting (args + kwargs)
    * Omits empty kwargs

* **Nested function call tracing**

    * Logs calls inside functions (e.g. `outer.inner()`)

* **Context-aware logging**

    * `log()` inside decorated functions now inherits:

        * `mode`
        * `show_time`
        * `show_file`
        * `show_lineno`

### Improved

* **Output clarity in educational mode**

    * Removed internal noise (`<func ...>`, debug artefacts)
    * Simplified function names (no test/module prefixes)
    * More natural mutation messages:

      ```
      Added 5 to arr -> [1, 2, 5]
      ```

### Fixed

* Formatter crash (`UnboundLocalError: prefix`)
* Incorrect call argument display (`{'args': ..., 'kwargs': ...}`)
* Missing nested call events due to tracer scope issues

### Tests

* Added educational mode test coverage:

    * Call formatting
    * Argument rendering
    * Nested function tracing
    * Inherited logging behavior
    * Human-readable mutations
    * Output cleanliness

---

## [1.2.0] - 2026-03-23

### Added

* `@log(level=...)` for verbosity control (`call`, `state`, `full`)
* `@log(filter=[...])` to log only selected variables
* Per-function file logging via `@log(filepath=...)`
* Global file logging support
* Decorator-only logging mode toggle

### Improved

* Overall logging flexibility and usability
* Reduced noise in complex traces

---

## [1.1.5] - 2026-03-23

### Changed

* Updated README documentation

---

## [1.1.4] - 2026-03-23

### Fixed

* Class wrapping issues

---

## [1.1.3] - 2026-03-23

### Fixed

* Wrapped object representation

---

## [1.1.2] - 2026-03-23

### Fixed

* Incorrect wrapping of callables

---

## [1.1.1] - 2026-03-23

### Fixed

* Mutation tracking issues
* Nested path logging bugs
* Test failures

---

## [1.1.0] - 2026-03-23

### Added

* Mutation logging support for tracked objects

### Improved

* Core logging capabilities

---

## [1.0.0] - 2026-03-23

### Added

* Initial release
* Variable logging with name inference
* Function tracing
* Object and mapping tracking
* Message logging system
* Basic test suite
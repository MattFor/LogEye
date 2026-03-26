# Changelog

## [1.5.0] - 2026-03-?

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

* **Mixed formatting support**

    * Combine `{}` formatting with `$var` templates:

      ```python
      log("value: {} and $x", x)
      ```

* **Recursive structure protection**

    * Prevents infinite recursion in self-referencing objects
    * Safe fallback representation for cyclic references

* **Expanded test coverage**

    * Complex object mutation scenarios
    * Class behaviours (methods, inheritance, overrides)
    * Edge cases (inline expressions, unpacking, pipes, formatting)
    * Multi-decorator compatibility tests
    * Nested functions and scope handling
    * Lambda execution patterns
    * Default argument correctness
    * Variable tracking consistency
    * Edge cases (pipes, unpacking, inline expressions)

### Changed

* **Class logging architecture refactor**

    * Removed reliance on internal `_data` for class instances
    * Switched to direct attribute instrumentation
    * Clear separation between:
        * class instrumentation
        * object wrapping system

* **Function tracing architecture overhaul**
    * Reworked `sys.settrace` usage for:
        * nested function detection
        * cleaner call/return matching
    * Improved frame tracking and scope resolution

**Educational mode formatting**

* Simplified output:
    * removed excessive noise
    * improved ordering (call → state → return)
* More predictable and testable output

* **Logging semantics upgraded and fixed**

    * Distinction between:
        * `(set)` -> initial assignment
        * `(change)` -> reassignment
    * More meaningful state transitions in output

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
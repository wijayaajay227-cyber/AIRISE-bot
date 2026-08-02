---
name: Generate Python Tests
description: "Generate pytest-compatible unit tests for a selected Python file or function, using the current repository layout and existing conventions."
---

Generate pytest-compatible unit tests for the selected Python code.

Include:
- test cases for expected behavior and edge cases
- fixtures or helper functions only when useful
- minimal mocking for external dependencies
- concise explanations for each test case

Use the repository structure and existing test style when available.

If the selection is a whole file, generate a new test module under `tests/`.
If the selection is a single function or class, generate focused tests for that symbol.

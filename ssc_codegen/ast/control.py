"""AST nodes for pipeline control flow and execution safety.

This module defines nodes that manage data flow, state loading, error recovery,
and execution termination within field extraction pipelines:

- `Self`: Loads pre-computed intermediate values from the struct constructor's `@init` cache.
- `Fallback`: Encapsulates preceding pipeline operations into a protected error-recovery block,
  returning a default fallback value if an exception, panic, or assertion failure occurs.
- `Return`: Terminal pipeline node that emits the return statement for the final computation.

### Fallback Error-Recovery Across Target Languages

Different target languages use different error-handling paradigms:

- **Python**: Emits a native `try ... except Exception:` block.
- **JavaScript**: Emits a native `try { ... } catch (e) { ... }` block.
- **Go**: Since Go does not have `try/catch` exception syntax, the Go code generator emits
  a generic runtime helper function `stdFallback[T any](fn func() T, fallback T) T`
  (part of `BASE_RUNTIME` in `targets/golang/runtime.py`). This helper wraps the pipeline
  execution in an anonymous closure and uses Go's `defer` and `recover()` mechanisms
  to intercept runtime panics (e.g. nil pointer dereferences, index out of bounds,
  string conversion errors) and safely return the fallback value.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class Self(Node):
    """Loads a pre-computed value from the constructor `@init` cache.

    Must appear as the initial operation in a field pipeline. At AST build time, its return type
    is resolved from the matching `InitField` return type.

    Attributes:
        name: Name of the cached `@init` field to load into the pipeline.

    Examples:
        - KDL: `@container` (or `-init` reference)
        - Python: `v1 = self._container`
        - JavaScript: `const v1 = this._container;`
        - Go: `v1 := p.container`
    """

    name: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )


@dataclass
class Fallback(Node):
    """Wraps preceding pipeline operations in an exception/error recovery block.

    All preceding pipeline operations in the field are moved into `Fallback.body` and emitted
    inside a protective block. If any error, assertion failure, or unhandled exception/panic
    occurs during evaluation of the body, the default `value` is returned.

    ### Target Backend Implementation

    - **Python**: Emits `try: ... except Exception: return <value>`
    - **JavaScript**: Emits `try { ... } catch (e) { return <value>; }`
    - **Go**: Emits a call to the generated generic runtime helper `stdFallback(fn, fallback)`:
      ```go
      // Generated runtime helper function (in sscgen_runtime.go or file header):
      func stdFallback[T any](fn func() T, fallback T) T {
          var result T
          defer func() {
              if r := recover(); r != nil {
                  result = fallback
              }
          }()
          result = fn()
          return result
      }
      ```

    Attributes:
        value: Literal default value returned upon error or panic.

    Examples:
        - KDL: `fallback 0`, `fallback ""`
        - Python:
            ```python
            try:
                v1 = v.select_one(".price")
                v2 = v1.get_text(strip=True)
                return int(v2)
            except Exception:
                return 0
            ```
        - JavaScript:
            ```javascript
            try {
                const v1 = v.querySelector(".price");
                const v2 = v1.textContent.trim();
                return parseInt(v2, 10);
            } catch (e) {
                return 0;
            }
            ```
        - Go:
            ```go
            return stdFallback(func() int {
                v1 := v.Find(".price").First()
                v2 := strings.TrimSpace(v1.Text())
                v3, _ := strconv.Atoi(v2)
                return v3
            }, 0)
            ```
    """

    value: Any = None
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )

    def __post_init__(self) -> None:
        if self.ret_type_info.base != VariableType.AUTO:
            # already set explicitly, skip inference
            return
        if self.value is None:
            self.ret_type_info = TypeInfo(base=VariableType.NULL)
        elif isinstance(self.value, bool):
            # bool before int — bool is subclass of int in Python
            self.ret_type_info = TypeInfo(base=VariableType.BOOL)
        elif isinstance(self.value, int):
            self.ret_type_info = TypeInfo(base=VariableType.INT)
        elif isinstance(self.value, float):
            self.ret_type_info = TypeInfo(base=VariableType.FLOAT)
        elif isinstance(self.value, str):
            self.ret_type_info = TypeInfo(base=VariableType.STRING)
        elif isinstance(self.value, list):
            self.ret_type_info = TypeInfo(
                base=VariableType.STRING, is_array=True
            )


@dataclass
class Return(Node):
    """Terminal pipeline node emitting the return statement for the final computation result.

    Examples:
        - Python: `return v3`
        - JavaScript: `return v3;`
        - Go: `return v3`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )

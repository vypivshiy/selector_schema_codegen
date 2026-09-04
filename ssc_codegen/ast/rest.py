"""AST nodes for REST API client result artifacts and error dispatch tables.

This module defines synthesized declaration nodes for REST endpoint code generation:
- `ResultVariantDef`: Generates typed error variant classes for mapped `@error` response statuses.
- `ResultAliasDef`: Generates polymorphic `Result[T, E]` union type aliases for method return types.
- `MatcherEntry`: Represents a single pattern matcher checking HTTP status and response body conditions.
- `MatcherListDef`: Generates the ordered registry array of error response matchers used for dispatch.

### End-to-End REST Architecture Lifecycle

```
KDL Declaration                  Compiler Core                   AST Nodes                  Generated Client
(rest)struct UsersClient  ───►  rest_artifacts_from_struct  ───► ResultVariantDef  ───►  class UsersClient404Err(Err[...])
  @error 404 schema=...          (synthesizes AST nodes)         ResultAliasDef    ───►  GetUserResult = Union[Ok[...], ...]
  @request ...                                                   MatcherListDef    ───►  _users_matchers = [ErrMatcher(...)]
                                                                 StructRest        ───►  class UsersClient: def get_user(...)
```

1. **Schema Declaration**: The user declares a `(rest)struct` in KDL with `@error` status rules and `@request` endpoints.
2. **Artifact Synthesis**: Before visiting the struct, `core/rest_artifacts.py` synthesizes `ResultVariantDef`,
   `ResultAliasDef`, and `MatcherListDef` nodes and prepends them to `Module.body` (mirroring how `TypeDef`
   nodes are synthesized from parsing structs).
3. **Target Code Generation**:
   - Each error status generates a distinct error class inheriting from base `Err[T]`.
   - Each endpoint generates a typed method returning `Result[Ok[T], Err1 | Err2 | UnknownErr | TransportErr]`.
   - An error matcher table is generated to route HTTP responses based on status code and body predicates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import Node


@dataclass
class ResultVariantDef(Node):
    """Error variant class declaration synthesized for REST endpoints.

    Emitted as a typed error dataclass/class inheriting from base `Err[T]` where `T` is the
    associated error JSON schema model (or void/empty payload).

    Attributes:
        name: Name of the generated error variant class (e.g. `"UsersClient404Err"`).
        status: HTTP status code associated with this error variant (e.g. `404`).
        schema_name: Name of the JSON schema model for error body deserialization (`""` for no schema).
        schema_is_array: Flag indicating whether the error payload is an array schema.

    Examples:
        - Generated Python:
            ```python
            @dataclass
            class UsersClient404Err(Err[NotFoundJson]):
                status: Literal[404] = 404
            ```
        - Generated JavaScript:
            ```javascript
            class UsersClient404Err extends Err {
                constructor(value) { super(value, 404); }
            }
            ```
        - Generated Go:
            ```go
            type UsersClient404Err struct {
                Err[NotFoundJson]
            }
            ```
    """

    name: str = ""  # "UsersClient404Err"
    status: int = 0
    schema_name: str = ""  # raw JsonDef name, "" → no schema
    schema_is_array: bool = False


@dataclass
class ResultAliasDef(Node):
    """Result union type alias declaration synthesized for REST methods.

    Represents the polymorphic return type union for an endpoint method, combining
    successful `Ok[ResponseSchema]`, all matched error variants `ErrVariant`, standard
    `UnknownErr`, and network `TransportErr`.

    Attributes:
        name: Identifier of the generated type alias (e.g. `"GetUserResult"`).
        response_schema: Name of the successful JSON response schema model (`""` for void).
        response_is_array: Flag indicating whether the response payload is an array schema.
        err_variants: List of error variant class names included in the union.

    Examples:
        - Generated Python:
            ```python
            GetUserResult = Union[Ok[UserJson], UsersClient404Err, UnknownErr, TransportErr]
            ```
        - Generated JavaScript (JSDoc):
            ```javascript
            /** @typedef {Ok<UserJson> | UsersClient404Err | UnknownErr | TransportErr} GetUserResult */
            ```
        - Generated Go:
            ```go
            type GetUserResult = Result[UserJson, any]
            ```
    """

    name: str = ""  # "GetUserResult"
    response_schema: str = ""  # raw JsonDef name, "" → void
    response_is_array: bool = False
    err_variants: list[str] = field(default_factory=list)


@dataclass
class MatcherEntry:
    """Single HTTP status and payload condition matcher entry.

    Encapsulates the criteria for matching an HTTP response to a specific error variant factory.

    Attributes:
        status: HTTP status code to match (e.g. `400`, `404`, `500`).
        required_keys: List of top-level keys that must be present in the JSON body.
        conditions: Dictionary of dot-path property match rules (e.g. `{"error.code": "NOT_FOUND"}`).
        factory_name: Error variant class identifier to instantiate upon a successful match.
        error_schema: Name of the associated error payload schema.
    """

    status: int
    required_keys: list[str]  # keys that must exist in the JSON body
    conditions: dict[str, Any]  # path=value checks against the JSON body
    factory_name: str  # ResultVariantDef.name to construct on match
    error_schema: str = ""


@dataclass
class MatcherListDef(Node):
    """Ordered registry of HTTP error response matchers synthesized for a REST client.

    Emitted as a module-level or class-level dispatch list of `ErrMatcher` instances.
    During HTTP response handling, the client iterates over this list to select the appropriate
    typed error variant constructor.

    Attributes:
        struct_name: Identifier of the associated REST client struct.
        entries: Ordered sequence of `MatcherEntry` instances.

    Examples:
        - Generated Python:
            ```python
            _users_client_matchers = [
                ErrMatcher(404, lambda b: True, UsersClient404Err, "NotFoundJson"),
            ]
            ```
        - Generated JavaScript:
            ```javascript
            const _usersClientMatchers = [
                new ErrMatcher(404, (b) => true, UsersClient404Err, "NotFoundJson"),
            ];
            ```
        - Generated Go:
            ```go
            var usersClientMatchers = []ErrMatcher{
                {Status: 404, Match: func(b gjson.Result) bool { return true }, Factory: NewUsersClient404Err},
            }
            ```
    """

    struct_name: str = ""
    entries: list[MatcherEntry] = field(default_factory=list)

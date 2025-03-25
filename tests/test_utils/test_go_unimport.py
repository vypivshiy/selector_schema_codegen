import pytest

from ssc_codegen.str_utils import go_unimport_naive

# Test case 1: Unused import is removed
# Test data constants
VALID_CODE_WITH_UNUSED_IMPORTS = (
    """package main

import (
    "fmt"
    "math/rand"
)

func main() {
    fmt.Println("Hello, world!")
}""",
    """package main

import (
    "fmt"
)

func main() {
    fmt.Println("Hello, world!")
}""",
)

VALID_CODE_WITH_NO_UNUSED_IMPORTS = (
    """package main

import (
    "fmt"
    "math/rand"
)

func main() {
    fmt.Println("Hello, world!")
    rand.Seed(42)
}""",
    """package main

import (
    "fmt"
    "math/rand"
)

func main() {
    fmt.Println("Hello, world!")
    rand.Seed(42)
}""",
)

EMPTY_IMPORTS_BLOCK = (
    """package main

import (
)

func main() {
    fmt.Println("Hello, world!")
}""",
    """package main

import (
)

func main() {
    fmt.Println("Hello, world!")
}""",
)

IMPORTS_WITH_SPECIAL_CHARACTERS = (
    """package main

import (
    "github.com/example/lib"
    "fmt"
)

func main() {
    fmt.Println("Hello, world!")
}""",
    """package main

import (
    "fmt"
)

func main() {
    fmt.Println("Hello, world!")
}""",
)

NESTED_IMPORTS = (
    """package main

import (
    "fmt"
    "math/rand"
    "github.com/example/lib"
)

func main() {
    fmt.Println("Hello, world!")
    rand.Seed(42)
}""",
    """package main

import (
    "fmt"
    "math/rand"
)

func main() {
    fmt.Println("Hello, world!")
    rand.Seed(42)
}""",
)

INVALID_CODE_NO_IMPORTS_BLOCK = """package main

func main() {
    fmt.Println("Hello, world!")
}"""


@pytest.mark.parametrize(
    "input_code, expected_output",
    [
        # Test case 1: Unused import is removed
        VALID_CODE_WITH_UNUSED_IMPORTS,
        # Test case 2: No unused imports, code remains unchanged
        VALID_CODE_WITH_NO_UNUSED_IMPORTS,
        # Test case 3: Empty imports block
        EMPTY_IMPORTS_BLOCK,
        # Test case 4: Imports with special characters
        IMPORTS_WITH_SPECIAL_CHARACTERS,
        # Test case 5: Nested imports (should not be affected)
        NESTED_IMPORTS,
    ],
)
def test_go_unimport_naive(input_code, expected_output) -> None:
    # this function just remove unused import, later gofmt fix code style
    output = go_unimport_naive(input_code).replace("\n", "").replace(" ", "")
    assert output == expected_output.replace("\n", "").replace(" ", "")

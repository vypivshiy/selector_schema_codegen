# mark variable type in expression
from ssc_codegen._compat import IntEnum


class TypeVariableState(IntEnum):
    DOCUMENT = 1
    LIST_DOCUMENT = 2  # html elements
    STRING = 3
    LIST_STRING = 4
    NONE = 5
    DOCSTRING = 6  # ///
    NESTED = 7  # link to another struct

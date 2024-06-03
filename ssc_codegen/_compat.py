import sys

if sys.version_info >= (3, 11):
    from enum import IntEnum
else:
    from enum import Enum

    class IntEnum(int, Enum):
        pass

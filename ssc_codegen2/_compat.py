# TODO: check via python version (sys.version)
try:
    from enum import IntEnum
except ImportError:
    from enum import Enum


    class IntEnum(int, Enum):
        pass

from typing_extensions import Self, deprecated

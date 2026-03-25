"""
Loads the compiled tree-sitter KDL language.
The .dll/.so/.dylib must be built first via scripts/build_kdl.py
"""

import ctypes
import platform
import sys
from pathlib import Path
from tree_sitter import Language, Parser

_LIB_DIR = Path(__file__).parent

_PLATFORM_EXT_ORDER: tuple[str, ...]
if sys.platform == "win32":
    _PLATFORM_EXT_ORDER = ("*.dll", "*.so", "*.dylib")
elif platform.system() == "Darwin":
    _PLATFORM_EXT_ORDER = ("*.dylib", "*.so", "*.dll")
else:
    _PLATFORM_EXT_ORDER = ("*.so", "*.dylib", "*.dll")


def _find_lib() -> Path:
    for ext in _PLATFORM_EXT_ORDER:
        candidates = list(_LIB_DIR.glob(ext))
        if candidates:
            return candidates[0]
    raise FileNotFoundError(
        "KDL tree-sitter library not found. Run: python scripts/build_kdl.py"
    )


def _load_language() -> Language:
    lib_path = _find_lib()
    lib = ctypes.CDLL(str(lib_path))
    lib.tree_sitter_kdl.restype = ctypes.c_void_p
    lib.tree_sitter_kdl.argtypes = []
    ptr_int = lib.tree_sitter_kdl()

    # Convert pointer to PyCapsule to avoid deprecated int overload
    # tree-sitter 0.21+ expects capsule or object, not int
    try:
        import ctypes.pythonapi as pythonapi

        pythonapi.PyCapsule_New.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_void_p,
        ]
        pythonapi.PyCapsule_New.restype = ctypes.py_object
        capsule = pythonapi.PyCapsule_New(ptr_int, None, None)
        return Language(capsule)
    except Exception:
        # Fallback to int (deprecated but works with older tree-sitter)
        return Language(ptr_int)  # type: ignore[arg-type]


KDL_LANGUAGE: Language = _load_language()
KDL_PARSER: Parser = Parser(KDL_LANGUAGE)

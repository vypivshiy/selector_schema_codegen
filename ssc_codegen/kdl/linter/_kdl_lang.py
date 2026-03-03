"""
Loads the compiled tree-sitter KDL language.
The .dll/.so/.dylib must be built first via scripts/build_kdl.py
"""
import ctypes
from pathlib import Path
from tree_sitter import Language, Parser

_LIB_DIR = Path(__file__).parent

def _find_lib() -> Path:
    for ext in ("*.dll", "*.so", "*.dylib"):
        candidates = list(_LIB_DIR.glob(ext))
        if candidates:
            return candidates[0]
    raise FileNotFoundError(
        "KDL tree-sitter library not found. "
        "Run: python scripts/build_kdl.py"
    )

def _load_language() -> Language:
    lib_path = _find_lib()
    lib = ctypes.CDLL(str(lib_path))
    lib.tree_sitter_kdl.restype = ctypes.c_void_p
    lib.tree_sitter_kdl.argtypes = []
    ptr = lib.tree_sitter_kdl()
    return Language(ptr)


KDL_LANGUAGE: Language = _load_language()
KDL_PARSER: Parser = Parser(KDL_LANGUAGE)
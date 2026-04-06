"""Hatch custom build hook: compile tree-sitter-kdl and set platform wheel tag."""

import platform
import struct
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


VENDOR_SRC = Path("vendor/tree-sitter-kdl/src")


def _get_platform_tag() -> str:
    if sys.platform == "win32":
        arch = "amd64" if struct.calcsize("P") == 8 else "win32"
        return f"win_{arch}"
    elif sys.platform == "darwin":
        machine = platform.machine()
        if machine == "arm64":
            return "macosx_11_0_arm64"
        return "macosx_10_9_x86_64"
    else:
        machine = platform.machine()
        return f"manylinux_2_17_{machine}.manylinux2014_{machine}"


def _lib_suffix() -> str:
    if sys.platform == "win32":
        return ".dll"
    elif sys.platform == "darwin":
        return ".dylib"
    return ".so"


def _compile_kdl(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = _lib_suffix()
    out_lib = out_dir / f"kdl{suffix}"

    if out_lib.exists():
        return out_lib

    parser_c = str(VENDOR_SRC / "parser.c")
    scanner_c = str(VENDOR_SRC / "scanner.c")
    include = str(VENDOR_SRC)

    if sys.platform == "win32":
        build_temp = Path("build/temp")
        build_temp.mkdir(parents=True, exist_ok=True)
        cmd = [
            "cl.exe", "/LD", "/O2", "/nologo",
            f"/I{include}",
            parser_c, scanner_c,
            f"/Fe{out_lib}",
            f"/Fo{build_temp}\\",
            "/link", "/DLL", "/NODEFAULTLIB:python",
        ]
    else:
        cmd = [
            "gcc", "-shared", "-fPIC", "-O2",
            f"-I{include}",
            parser_c, scanner_c,
            "-o", str(out_lib),
        ]

    subprocess.run(cmd, check=True)
    return out_lib


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:
        if self.target_name != "wheel":
            return

        out_dir = Path("ssc_codegen/linter")
        lib_path = _compile_kdl(out_dir)

        build_data["tag"] = f"py3-none-{_get_platform_tag()}"
        build_data["force_include"][str(lib_path)] = (
            f"ssc_codegen/linter/{lib_path.name}"
        )

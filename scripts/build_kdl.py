# scripts/build_kdl.py
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
VENDOR = ROOT / "vendor" / "tree-sitter-kdl"
OUT = ROOT / "ssc_codegen" / "kdl" / "linter"
BUILD_TEMP = ROOT / "build" / "temp"


def setup_msvc_env():
    """Найти и активировать MSVC окружение."""
    import shutil
    if shutil.which("cl.exe"):
        return  # уже в PATH

    vcvars_candidates = [
        r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat",
    ]

    vcvars = None
    for path in vcvars_candidates:
        if Path(path).exists():
            vcvars = path
            break

    if not vcvars:
        print("ERROR: Visual Studio not found")
        print("Install 'Desktop development with C++' workload from VS installer")
        sys.exit(1)

    # выполнить vcvars64.bat и получить переменные окружения
    result = subprocess.run(
        f'"{vcvars}" && set',
        capture_output=True, text=True, shell=True
    )
    for line in result.stdout.splitlines():
        if "=" in line:
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip()

    print(f"MSVC environment loaded from: {vcvars}")


def build_windows():
    setup_msvc_env()
    
    BUILD_TEMP.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    parser_c = VENDOR / "src" / "parser.c"
    scanner_c = VENDOR / "src" / "scanner.c"
    out_dll = OUT / "kdl.dll"

    # компилируем через cl.exe напрямую — без PyInit
    result = subprocess.run([
        "cl.exe",
        "/LD",                          # собрать как DLL
        "/O2",
        "/nologo",
        f"/I{VENDOR / 'src'}",
        str(parser_c),
        str(scanner_c),
        f"/Fe{out_dll}",                # output dll
        f"/Fo{BUILD_TEMP}\\",           # temp .obj файлы
        "/link", "/DLL", "/NODEFAULTLIB:python",
    ], capture_output=True, text=True)

    print(result.stdout)
    if result.returncode != 0:
        print("STDERR:", result.stderr)
        sys.exit(1)

    print(f"Built: {out_dll}")


def build_unix():
    BUILD_TEMP.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    parser_c = VENDOR / "src" / "parser.c"
    scanner_c = VENDOR / "src" / "scanner.c"

    import platform
    suffix = ".dylib" if platform.system() == "Darwin" else ".so"
    out_lib = OUT / f"kdl{suffix}"

    result = subprocess.run([
        "gcc",
        "-shared", "-fPIC", "-O2",
        f"-I{VENDOR / 'src'}",
        str(parser_c), str(scanner_c),
        "-o", str(out_lib),
    ], capture_output=True, text=True)

    print(result.stdout)
    if result.returncode != 0:
        print("STDERR:", result.stderr)
        sys.exit(1)

    print(f"Built: {out_lib}")


if __name__ == "__main__":
    if sys.platform == "win32":
        build_windows()
    else:
        build_unix()
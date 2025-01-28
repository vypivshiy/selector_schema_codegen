import re
from enum import Enum
import typer

app = typer.Typer()

DEFAULT_FILE_PATH = "pyproject.toml"
DEFAULT_PY_VER_FILE = "ssc_codegen/__init__.py"
DEFAULT_RE_VER_PATTERN = r'VERSION = [\'"]\d+\.\d+\.\d+[\'"]'
DEFAULT_RE_TOML_PATTERN = r'version = [\'"](\d+\.\d+\.\d+)[\'"]'
class BumpType(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


def update_init_file_version(init_file: str, new_version: str) -> None:
    """
    Update the VERSION variable in the __init__.py file.
    """
    with open(init_file, "r") as f:
        content = f.read()

    # Use regex to find and replace the VERSION variable
    updated_content = re.sub(
        r'VERSION = "\d+\.\d+\.\d+"',
        f'VERSION = "{new_version}"',
        content,
    )

    with open(init_file, "w") as f:
        f.write(updated_content)


@app.command()
def bump_version(
    file_path: str = typer.Option(
        DEFAULT_FILE_PATH, help="Path to the pyproject.toml file"
    ),
    init_file: str = typer.Option(
        DEFAULT_PY_VER_FILE, help="Path to the __init__.py file"
    ),
    part: BumpType = typer.Option("patch", help="Part of the version to bump"),
) -> None:
    """
    Bump the version in the pyproject.toml file and update the VERSION variable in __init__.py.
    """
    try:
        # Bump version in pyproject.toml
        with open(file_path, "r") as f:
            pyproject = f.read()

        version = re.search(DEFAULT_RE_TOML_PATTERN, pyproject)[1]  # type:ignore[index]
        major, minor, patch = map(int, version.split("."))

        if part == "major":
            major += 1
            minor = 0
            patch = 0
        elif part == "minor":
            minor += 1
            patch = 0
        elif part == "patch":
            patch += 1
        else:
            raise ValueError("Invalid part value. Choose 'major', 'minor', or 'patch'.")
        new_version = f"{major}.{minor}.{patch}"
        pyproject = re.sub(DEFAULT_RE_TOML_PATTERN, f'version = "{new_version}"', pyproject)
        with open(file_path, "w") as f:
            f.write(pyproject)
        typer.echo(f"Version bumped to {new_version} in {file_path}")
        # Update VERSION in __init__.py
        update_init_file_version(init_file, new_version)
        typer.echo(f"Updated VERSION to {new_version} in {init_file}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

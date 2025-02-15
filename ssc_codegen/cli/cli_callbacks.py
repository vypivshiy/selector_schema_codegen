from pathlib import Path
from typing import Generator
from typer import BadParameter


def cb_check_ssc_files(
    files: list[Path] | Generator[Path, None, None],
) -> list[Path]:
    tmp_files = []
    for f in files:
        if f.is_dir():
            tmp_files += cb_check_ssc_files(f.iterdir())
        elif not f.exists():
            raise BadParameter(f"'{f.name}' does not exist")
        elif not f.is_file():
            raise BadParameter(f"'{f.name}' is not file")
        # TODO: change extension???
        elif f.suffix == ".py":
            tmp_files.append(f)
    return tmp_files


def cb_folder_out(folder: Path) -> Path:
    if not folder.exists():
        folder.mkdir(exist_ok=True)
    if folder.is_file():
        raise BadParameter(f"'{folder.name}' should be a dir, not file")
    return folder


def cb_file_out(file: Path) -> Path:
    if not file.is_file():
        raise BadParameter(f"'{file.name}' is not a file")
    return file

import logging
import sys


class ColoredFormatter(logging.Formatter):
    COLOR_MAP = {
        "DEBUG": "\033[94m",  # Blue
        "INFO": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[95m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        if color := self.COLOR_MAP.get(record.levelname):
            reset = self.COLOR_MAP["RESET"]
        else:
            color = ""
            reset = ""
        msg = super().format(record)
        return f"{color}{msg}{reset}"


def setup_logger(
    name: str = "ssc_gen",
    level: int = logging.INFO,
    colored: bool = True,
    fmt: str = "[%(levelname)-8s] %(name)s: %(asctime)s - %(message)s",
    datefmt: str = "%Y-%m-%d %H:%M:%S",
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers if the logger is already configured
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        if colored:
            if sys.platform.startswith("win"):
                import colorama

                colorama.init()
            formatter = ColoredFormatter(fmt, datefmt=datefmt)
        else:
            formatter = logging.Formatter(fmt, datefmt=datefmt)  # type: ignore
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

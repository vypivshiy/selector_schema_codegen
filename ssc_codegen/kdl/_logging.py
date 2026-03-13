"""Logging configuration for ssc_codegen.kdl.

Usage
-----
Import the logger in any submodule::

    from ssc_codegen.kdl._logging import logger

To enable DEBUG output from the CLI, pass ``--verbose`` / ``-v`` flag,
or configure it manually::

    import logging
    logging.getLogger("ssc_codegen.kdl").setLevel(logging.DEBUG)
"""

from __future__ import annotations

import logging
import sys

# Windows ANSI backport
try:
    import colorama

    colorama.init(autoreset=False)
    _COLORAMA_AVAILABLE = True
except ImportError:
    _COLORAMA_AVAILABLE = False

# ANSI color codes (used on all platforms; colorama translates them on Windows)
_RESET = "\033[0m"
_BOLD = "\033[1m"
_COLORS: dict[int, str] = {
    logging.DEBUG: "\033[36m",  # cyan
    logging.INFO: "\033[32m",  # green
    logging.WARNING: "\033[33m",  # yellow
    logging.ERROR: "\033[31m",  # red
    logging.CRITICAL: "\033[35m",  # magenta
}


class _ColorFormatter(logging.Formatter):
    """Formatter that wraps the level name in ANSI color codes."""

    _FMT = "[{color}{bold}{level}{reset}] {name}: {message}"

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        color = _COLORS.get(record.levelno, "")
        level = record.levelname
        name = record.name
        # format the message part the normal way (handles exc_info etc.)
        record.message = record.getMessage()
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)

        msg = self._FMT.format(
            color=color,
            bold=_BOLD,
            level=level,
            reset=_RESET,
            name=name,
            message=record.message,
        )
        if record.exc_text:
            msg = f"{msg}\n{record.exc_text}"
        return msg


# Single named logger for the entire ssc_codegen.kdl package.
# All child loggers (parser, main, …) are children of this one,
# so a single ``logging.getLogger("ssc_codegen.kdl").setLevel(DEBUG)``
# enables everything at once.
logger = logging.getLogger("ssc_codegen.kdl")


def setup_debug_logging() -> None:
    """Enable DEBUG-level logging to stderr for the ssc_codegen.kdl logger.

    Called by the CLI when ``--verbose`` is passed.
    Idempotent: calling multiple times is safe.
    """
    pkg_logger = logging.getLogger("ssc_codegen.kdl")
    if pkg_logger.level > logging.DEBUG or pkg_logger.level == logging.NOTSET:
        pkg_logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if already configured
    if not any(
        isinstance(h, logging.StreamHandler) for h in pkg_logger.handlers
    ):
        # Use colors only when stderr is a real TTY or colorama is available
        use_color = _COLORAMA_AVAILABLE or (
            hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
        )
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter: logging.Formatter = (
            _ColorFormatter()
            if use_color
            else logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )
        handler.setFormatter(formatter)
        pkg_logger.addHandler(handler)

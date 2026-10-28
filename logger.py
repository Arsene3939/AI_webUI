"""
Unified logging system for MiniMax-H3 ComfyUI WebUI.
Provides formatted terminal console logging and rotating file output for clear debugging.
"""
import os
import sys
import logging
from typing import Optional

# Ensure UTF-8 output encoding for terminal on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ColouredFormatter(logging.Formatter):
    """Custom formatter with ANSI color coding for terminal display."""
    GREY = "\x1b[38;20m"
    CYAN = "\x1b[36;20m"
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    COLORS = {
        logging.DEBUG: CYAN,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.GREY)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


_LOG_INITIALIZED = False
_LOG_FILE: Optional[str] = None


def init_logging(log_dir: Optional[str] = None, log_level: int = logging.INFO, force_reinit: bool = False):
    """Initializes the root logger with both console and file handlers."""
    global _LOG_INITIALIZED, _LOG_FILE
    if _LOG_INITIALIZED and not force_reinit:
        return

    root_logger = logging.getLogger("MiniMaxWebUI")
    root_logger.setLevel(log_level)
    root_logger.propagate = False

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = ColouredFormatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File Handler
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
            _LOG_FILE = os.path.join(log_dir, "webui.log")
            file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8", mode="a")
            file_handler.setLevel(log_level)
            file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        except Exception:
            pass

    _LOG_INITIALIZED = True


def get_logger(module_name: str) -> logging.Logger:
    """Returns a child logger under the MiniMaxWebUI namespace."""
    if not _LOG_INITIALIZED:
        try:
            from config import OUTPUT_DIR
            init_logging(log_dir=OUTPUT_DIR)
        except Exception:
            init_logging(log_dir=None)
    return logging.getLogger(f"MiniMaxWebUI.{module_name}")

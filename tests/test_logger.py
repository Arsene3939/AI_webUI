"""
Unit tests for unified logging system (logger.py).
"""
import os
import logging
from logger import get_logger, init_logging, ColouredFormatter


class TestLogger:
    def test_get_logger_instance(self):
        """Ensures get_logger returns a valid logging.Logger instance."""
        logger = get_logger("TestModule")
        assert isinstance(logger, logging.Logger)
        assert "MiniMaxWebUI.TestModule" in logger.name

    def test_colored_formatter(self):
        """Tests that ColouredFormatter adds color escape sequences."""
        formatter = ColouredFormatter("[%(levelname)s] %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Hello Info",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        assert "Hello Info" in formatted
        assert "\x1b[" in formatted  # Contains ANSI color sequence

    def test_file_logging(self, tmp_path):
        """Tests that file logging writes to log file."""
        log_dir = str(tmp_path / "logs")
        init_logging(log_dir=log_dir, log_level=logging.DEBUG, force_reinit=True)
        test_logger = get_logger("FileTest")
        test_msg = "Unique_Test_Message_12345"
        test_logger.info(test_msg)

        log_file = os.path.join(log_dir, "webui.log")
        assert os.path.exists(log_file)
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert test_msg in content

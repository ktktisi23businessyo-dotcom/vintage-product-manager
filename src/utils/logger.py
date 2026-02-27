from __future__ import annotations

import logging
from pathlib import Path


LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _build_file_logger(name: str, filename: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(LOG_DIR / filename, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


def get_app_logger() -> logging.Logger:
    return _build_file_logger("vintage.app", "app.log", logging.INFO)


def get_error_logger() -> logging.Logger:
    return _build_file_logger("vintage.error", "error.log", logging.ERROR)


def get_audit_logger() -> logging.Logger:
    return _build_file_logger("vintage.audit", "audit.log", logging.INFO)

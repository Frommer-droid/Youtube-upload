"""Логирование в каталоге данных конкретной установки (ТЗ, раздел 25).

Запрещено писать в лог: access token, refresh token, authorization code,
содержимое client_secret.json.
"""

from __future__ import annotations

import logging
from datetime import datetime

from . import config

LOGGER_NAME = "youtube_uploader"
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(logs_dir=None) -> logging.Logger:
    """Настроить файловое логирование. Идемпотентно."""
    target_dir = logs_dir or config.logs_dir()
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        log_file = target_dir / f"{datetime.now().astimezone().date().isoformat()}.log"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
    except OSError as exc:
        print(f"Не удалось настроить логирование: {exc}", file=__import__("sys").stderr)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)

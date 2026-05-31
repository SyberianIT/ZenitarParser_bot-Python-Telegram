import logging
import os
from logging.handlers import RotatingFileHandler

import config


def setup_logging():
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    level = getattr(logging, config.LOG_LEVEL, logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        os.path.join(config.LOGS_DIR, "zenitar.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Tame noisy third-party loggers
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)

    return root

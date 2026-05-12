"""Единая настройка логирования для app и engine (без повторного basicConfig)."""
import logging
import os
from logging.handlers import RotatingFileHandler

from paths import PROJECT_ROOT

_configured = False


def configure_application_logging():
    """Идемпотентно: root handlers, файл bot.log + stderr."""
    global _configured
    if _configured:
        return
    level_name = (os.getenv("LOG_LEVEL", "INFO") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    log_path = PROJECT_ROOT / "bot.log"
    fh = RotatingFileHandler(str(log_path), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)
    _configured = True

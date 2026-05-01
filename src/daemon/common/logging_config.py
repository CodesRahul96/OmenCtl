"""OMEN Command Center for Linux — Shared logging configuration.

Every microservice calls ``setup_logging(service_name)`` at start-up to
obtain a consistently formatted logger that also plays nicely with
*journald* (systemd captures stdout/stderr automatically).
"""

import logging
import sys


def setup_logging(service_name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure and return a logger for *service_name*.

    Log lines include the service name so that entries from different
    services are easy to tell apart when viewed in ``journalctl``.

    Format::

        2026-05-01 14:00:00,123 [fan] [INFO] Fan mode set to auto
    """
    fmt = f"%(asctime)s [{service_name}] [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        stream=sys.stdout,
    )
    logger = logging.getLogger(f"hp-manager.{service_name}")
    logger.setLevel(level)
    return logger

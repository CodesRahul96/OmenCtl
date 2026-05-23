"""OMEN Command Center for Linux — Sysfs read/write helpers.

Centralised, safe helpers for interacting with the Linux sysfs virtual
filesystem.  Every microservice imports these instead of re-implementing
its own open/read/write wrappers.
"""

import logging
import os

logger = logging.getLogger("hp-manager.sysfs")

# Allowed path prefixes for sysfs/procfs operations
_ALLOWED_PREFIXES = ('/sys/', '/proc/')


def _validate_path(path: str) -> str:
    """Resolve symlinks and verify the path is under an allowed prefix.

    Raises ValueError if the resolved path escapes the allowed prefixes.
    """
    real = os.path.realpath(path)
    if not any(real == prefix.rstrip('/') or real.startswith(prefix)
               for prefix in _ALLOWED_PREFIXES):
        raise ValueError(
            f"Path '{path}' resolves to '{real}', "
            f"outside allowed prefixes {_ALLOWED_PREFIXES}"
        )
    return real


def sysfs_read(path: str, default: int = 0) -> int:
    """Read an integer value from a sysfs file.

    Returns *default* when the file is missing or cannot be parsed.
    """
    try:
        real_path = _validate_path(path)
        with open(real_path) as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return default
    except (ValueError, OSError) as exc:
        logger.debug("sysfs_read %s failed: %s", path, exc)
        return default


def sysfs_read_str(path: str, default: str = "") -> str:
    """Read a string value from a sysfs file."""
    try:
        real_path = _validate_path(path)
        with open(real_path) as f:
            return f.read().strip()
    except (FileNotFoundError, OSError) as exc:
        logger.debug("sysfs_read_str %s failed: %s", path, exc)
        return default


def sysfs_write(path: str, value) -> bool:
    """Write *value* to a sysfs file.  Returns True on success."""
    try:
        real_path = _validate_path(path)
        with open(real_path, "w") as f:
            f.write(str(value))
        return True
    except OSError as exc:
        logger.error("sysfs_write %s=%s error: %s", path, value, exc)
        return False


def sysfs_exists(path: str) -> bool:
    """Check whether a sysfs path exists."""
    try:
        _validate_path(path)
        return os.path.exists(path)
    except ValueError:
        return False


def normalize_profile_name(value: str, default: str = "balanced") -> str:
    """Normalize platform/thermal profile names for comparisons."""
    raw = (value or default).strip().lower()
    return raw.replace("_", "-")


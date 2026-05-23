"""OMEN Command Center for Linux — Per-service state management.

Each microservice owns its own JSON state file under ``/etc/hp-manager/``.
This module provides atomic read/write helpers with file-level locking so
that concurrent services never corrupt each other's data.

State files
-----------
- ``/etc/hp-manager/fan.json``
- ``/etc/hp-manager/rgb.json``
- ``/etc/hp-manager/power.json``
- ``/etc/hp-manager/mux.json``
- ``/etc/hp-manager/platform.json``

Legacy migration
~~~~~~~~~~~~~~~~
On first start a service checks whether the monolithic
``/etc/hp-manager/state.json`` exists and, if so, extracts its own
relevant keys from it.  After all services have migrated, the old file
is no longer needed.
"""

import copy
import json
import logging
import os
import threading
from typing import Any, Dict, Optional

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]  # Windows fallback

logger = logging.getLogger("hp-manager.config")

CONFIG_DIR = "/etc/hp-manager"
LEGACY_STATE_FILE = os.path.join(CONFIG_DIR, "state.json")

# Maps service name → keys that belong to it (used for legacy migration)
_SERVICE_KEYS = {
    "fan": {"fan_mode"},
    "rgb": {"mode", "colors", "speed", "brightness", "direction", "power", "win_lock"},
    "power": {"power_profile"},
    "mux": {"mux_backend"},
    "platform": {"prtsc_fix", "f1_fix"},
}


class ServiceConfig:
    """Thread-safe, per-service state store backed by a JSON file.

    Parameters
    ----------
    service_name : str
        Short name such as ``"fan"`` or ``"rgb"``.
    defaults : dict
        Default values when no state file exists yet.
    """

    def __init__(self, service_name: str, defaults: Dict[str, Any]):
        self._service = service_name
        self._path = os.path.join(CONFIG_DIR, f"{service_name}.json")
        self._lock = threading.RLock()
        self._state: Dict[str, Any] = dict(defaults)
        self._defaults = dict(defaults)
        self._changed = threading.Event()

    # ── public API ────────────────────────────────────────────────────

    @property
    def changed(self) -> threading.Event:
        """Event that is set whenever state changes (useful for animation loops)."""
        return self._changed

    def get(self, key: str, default=None):
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value):
        with self._lock:
            self._state[key] = value

    def update(self, mapping: dict):
        with self._lock:
            self._state.update(mapping)

    def snapshot(self) -> Dict[str, Any]:
        """Return a deep-copy of the current state."""
        with self._lock:
            return copy.deepcopy(self._state)

    def load(self):
        """Load state from disk, falling back to legacy migration if needed."""
        with self._lock:
            if os.path.exists(self._path):
                self._load_file(self._path, full=True)
            elif os.path.exists(LEGACY_STATE_FILE):
                logger.info(
                    "[%s] Migrating from legacy state.json", self._service
                )
                self._load_file(LEGACY_STATE_FILE, full=False)
                # Persist immediately so next boot uses the new file
                self._save_unlocked()

    def save(self):
        """Persist current state to disk atomically."""
        with self._lock:
            self._save_unlocked()
        self._changed.set()

    # ── internal ──────────────────────────────────────────────────────

    def _load_file(self, path: str, full: bool):
        """Read JSON from *path*.

        When *full* is True every key in the file is loaded.  When False
        (legacy migration) only the keys belonging to this service are
        extracted.
        """
        try:
            with open(path) as f:
                if fcntl is not None:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    if fcntl is not None:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            if not isinstance(data, dict):
                return

            if full:
                # Load all keys, merging with defaults
                for k, v in data.items():
                    self._state[k] = v
            else:
                # Legacy: extract only our keys
                my_keys = _SERVICE_KEYS.get(self._service, set())
                for k in my_keys:
                    if k in data:
                        self._state[k] = data[k]
        except Exception as exc:
            logger.error("[%s] State load error: %s", self._service, exc)

    def _save_unlocked(self):
        """Write state to disk using atomic rename with restrictive permissions."""
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            tmp = self._path + ".tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
            with os.fdopen(fd, "w") as f:
                if fcntl is not None:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(self._state, f, indent=2)
                finally:
                    if fcntl is not None:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            os.replace(tmp, self._path)
        except Exception as exc:
            logger.error("[%s] State save error: %s", self._service, exc)

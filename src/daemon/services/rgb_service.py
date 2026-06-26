#!/usr/bin/env python3
"""OMEN Command Center for Linux — RGB Microservice.

Owns RGB LED zone control and all lighting animation modes (static,
breathing, cycle, wave).  Exposes its functionality over D-Bus as
``com.yyl.hpmanager.rgb``.
"""

import colorsys
import json
import math
import os
import re
import sys
import threading
import time
import typing

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.logging_config import setup_logging
from common.config import ServiceConfig
from common.dbus_helpers import run_service, system_sleeping

logger = setup_logging("rgb")

DRIVER_PATH_CUSTOM = "/sys/devices/platform/hp-rgb-lighting"
HEX_COLOR_RE = re.compile(r"^[0-9A-F]{6}$")
VALID_LIGHT_MODES = {"static", "breathing", "cycle", "wave"}
VALID_DIRECTIONS = {"ltr", "rtl"}

# ─── RGB Controller ───────────────────────────────────────────────────────────


class RGBController:
    """Low-level RGB LED zone access via sysfs."""

    def __init__(self):
        self.driver_path = self._find_rgb_path()
        self.available = self.driver_path is not None
        self.rgb_supported = self.available
        self.brightness_supported = self.available and os.path.exists(f"{self.driver_path}/brightness")
        self.last_written = [None] * 8
        self.reversed = True
        self._fds: typing.Dict[int, typing.IO] = {}
        
        # Test if the RGB hardware is actually present and functional.
        # On non-RGB hardware (like Victus 15), the hp-rgb-lighting driver is loaded
        # and creates sysfs nodes, but writing to them is ignored and reading them
        # always returns "000000" (or fails to match the written value).
        if self.rgb_supported:
            try:
                # Write a test pattern to zone0
                with open(f"{self.driver_path}/zone0", "w") as f:
                    f.write("FF0000")
                # Wait briefly for driver/WMI sync
                time.sleep(0.01)
                # Read it back
                with open(f"{self.driver_path}/zone0", "r") as f:
                    val = f.read().strip()
                if val != "FF0000":
                    logger.info("RGB: Write test failed (read back '%s' instead of 'FF0000'). Disabling RGB support.", val)
                    self.rgb_supported = False
            except Exception as e:
                logger.warning("RGB: Write test failed with error: %s. Disabling RGB support.", e)
                self.rgb_supported = False

        if self.available and self.rgb_supported:
            for i in range(8):
                try:
                    self._fds[i] = open(f"{self.driver_path}/zone{i}", "w")
                except Exception:
                    pass

    def _find_rgb_path(self):
        if os.path.exists(DRIVER_PATH_CUSTOM):
            logger.info("RGB: Using custom driver path %s", DRIVER_PATH_CUSTOM)
            return DRIVER_PATH_CUSTOM

        try:
            with open("/proc/modules") as f:
                loaded = f.read()
            if "hp_rgb_lighting" in loaded:
                for candidate in (
                    "/sys/devices/platform/hp-rgb-lighting",
                    "/sys/devices/platform/hp_rgb_lighting",
                ):
                    if os.path.exists(candidate):
                        logger.info("RGB: Found loaded module at %s", candidate)
                        return candidate
        except Exception:
            pass

        logger.info("RGB: No RGB control path found (hp-rgb-lighting not loaded)")
        return None

    def is_available(self):
        return self.available

    def write_zone(self, zone, hex_color):
        if not self.available or not self.rgb_supported or not (0 <= zone <= 7):
            return

        target_zone = zone
        if self.reversed and 0 <= zone <= 3:
            target_zone = 3 - zone

        if self.last_written[target_zone] == hex_color:
            return

        try:
            time.sleep(0.001)
            fd = self._fds.get(target_zone)
            if fd:
                fd.seek(0)
                fd.write(hex_color)
                fd.flush()
            else:
                with open(f"{self.driver_path}/zone{target_zone}", "w") as f:
                    f.write(hex_color)
            self.last_written[target_zone] = hex_color
        except Exception:
            try:
                with open(f"{self.driver_path}/zone{target_zone}", "w") as f:
                    f.write(hex_color)
                self.last_written[target_zone] = hex_color
                self._fds[target_zone] = open(
                    f"{self.driver_path}/zone{target_zone}", "w"
                )
            except Exception:
                pass

    def write_all(self, hex_list):
        if not self.rgb_supported:
            return
        for i, hc in enumerate(hex_list[:8]):
            self.write_zone(i, hc)

    def write_brightness(self, on):
        if not self.available:
            return
        try:
            with open(f"{self.driver_path}/brightness", "w") as f:
                f.write("1" if on else "0")
                f.flush()
        except Exception:
            pass

    def write_win_lock(self, locked):
        if not self.available:
            return
        try:
            with open(f"{self.driver_path}/win_lock", "w") as f:
                f.write("1" if locked else "0")
                f.flush()
        except Exception:
            pass


# ─── Animation Engine ─────────────────────────────────────────────────────────


class AnimationEngine(threading.Thread):
    """Runs in its own thread, reading state from *config* and driving *rgb*."""

    FRAME_TIME = 0.12
    FRAME_TIME_WAVE = 0.15
    FRAME_TIME_SLOW = 0.12
    _COLOR_THRESHOLD = 3

    def __init__(self, rgb_ctrl: RGBController, config: ServiceConfig):
        super().__init__(daemon=True)
        self.rgb = rgb_ctrl
        self.config = config
        self.running = True
        self._last_uniform: tuple = (-1, -1, -1)
        self._last_wave: typing.List[typing.Tuple[int, int, int]] = [(-1, -1, -1)] * 8

    def _uniform_changed(self, new: tuple) -> bool:
        return any(
            abs(n - o) > self._COLOR_THRESHOLD
            for n, o in zip(new, self._last_uniform)
        )

    def _zone_changed(self, new: tuple, old: tuple) -> bool:
        return any(
            abs(n - o) > self._COLOR_THRESHOLD for n, o in zip(new, old)
        )

    def run(self):
        logger.info("Animation engine started")
        while self.running:
            if system_sleeping.is_set():
                time.sleep(0.1)
                continue

            loop_start = time.time()
            snap = self.config.snapshot()
            pwr = bool(snap.get("power", True))
            mode = str(snap.get("mode", "static"))
            bri = float(snap.get("brightness", 100)) / 100.0
            spd = float(snap.get("speed", 50))
            cols = [str(c) for c in snap.get("colors", ["FF0000"] * 8)]
            d = str(snap.get("direction", "ltr"))

            if not pwr:
                self.rgb.write_brightness(False)
                if self.rgb.rgb_supported:
                    self.rgb.write_all(["000000"] * 8)
                self._last_uniform = (-1, -1, -1)
                self._last_wave = [(-1, -1, -1)] * 8
                self.config.changed.clear()
                self.config.changed.wait()
                continue

            self.rgb.write_brightness(True)
            if not self.rgb.rgb_supported:
                self.config.changed.clear()
                self.config.changed.wait()
                continue

            t = time.time()

            if mode == "static":
                targets = [self._hex_to_rgb(c) for c in cols]
                self.rgb.write_all(
                    [
                        f"{int(r * bri):02X}{int(g * bri):02X}{int(b * bri):02X}"
                        for r, g, b in targets
                    ]
                )
                self._last_uniform = (-1, -1, -1)
                self._last_wave = [(-1, -1, -1)] * 8
                self.config.changed.clear()
                self.config.changed.wait()
                continue

            elif mode == "breathing":
                period = 8.0 - (spd * 0.06)
                phase = 0.1 + 0.9 * ((math.sin(2 * math.pi * t / period) + 1) / 2)
                base = self._hex_to_rgb(cols[0])
                new_color = (
                    int(base[0] * phase * bri),
                    int(base[1] * phase * bri),
                    int(base[2] * phase * bri),
                )
                if self._uniform_changed(new_color):
                    self._last_uniform = new_color
                    hx = f"{new_color[0]:02X}{new_color[1]:02X}{new_color[2]:02X}"
                    self.rgb.write_all([hx] * 8)
                self._last_wave = [(-1, -1, -1)] * 8
                sleep_time = max(
                    self.FRAME_TIME_SLOW - (time.time() - loop_start), 0.001
                )
                if self.config.changed.wait(timeout=sleep_time):
                    self.config.changed.clear()
                continue

            elif mode == "cycle":
                hue = (t * (spd * 0.003)) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, bri)
                new_color = (int(r * 255), int(g * 255), int(b * 255))
                if self._uniform_changed(new_color):
                    self._last_uniform = new_color
                    hx = f"{new_color[0]:02X}{new_color[1]:02X}{new_color[2]:02X}"
                    self.rgb.write_all([hx] * 8)
                self._last_wave = [(-1, -1, -1)] * 8
                sleep_time = max(
                    self.FRAME_TIME_SLOW - (time.time() - loop_start), 0.001
                )
                if self.config.changed.wait(timeout=sleep_time):
                    self.config.changed.clear()
                continue

            elif mode == "wave":
                base_cols = [self._hex_to_rgb(c) for c in cols[:4]]
                if not base_cols:
                    base_cols = [(255, 0, 0)]
                while len(base_cols) < 4:
                    base_cols.append(base_cols[-1])

                step_period = max(0.06, 0.42 - (spd * 0.0036))
                shift_pos = t / step_period
                shift_int = int(shift_pos)
                shift_frac = shift_pos - shift_int

                for i in range(8):
                    zone = i if d == "ltr" else (7 - i)
                    idx = (zone + shift_int) % 4
                    nxt = (idx + 1) % 4

                    c0 = base_cols[idx]
                    c1 = base_cols[nxt]

                    r = int((c0[0] + (c1[0] - c0[0]) * shift_frac) * bri)
                    g = int((c0[1] + (c1[1] - c0[1]) * shift_frac) * bri)
                    b = int((c0[2] + (c1[2] - c0[2]) * shift_frac) * bri)
                    new_color = (r, g, b)

                    if self._zone_changed(new_color, self._last_wave[i]):
                        self._last_wave[i] = new_color
                        self.rgb.write_zone(
                            i,
                            f"{new_color[0]:02X}{new_color[1]:02X}{new_color[2]:02X}",
                        )
                self._last_uniform = (-1, -1, -1)
                sleep_time = max(
                    self.FRAME_TIME_WAVE - (time.time() - loop_start), 0.001
                )
                if self.config.changed.wait(timeout=sleep_time):
                    self.config.changed.clear()
                continue

            sleep_time = max(self.FRAME_TIME - (time.time() - loop_start), 0.001)
            if self.config.changed.wait(timeout=sleep_time):
                self.config.changed.clear()

    @staticmethod
    def _hex_to_rgb(h):
        h = str(h).lstrip("#")
        if not h or len(h) < 6:
            logger.warning("Invalid hex color: '%s', falling back to red", h)
            return (255, 0, 0)
        try:
            return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError as e:
            logger.error("Hex conversion error for '%s': %s", h, e)
            return (255, 0, 0)


# ─── D-Bus Service ────────────────────────────────────────────────────────────


class RGBService:
    """
    <node>
      <interface name="com.yyl.hpmanager.rgb">
        <method name="SetColor"><arg type="i" name="z" direction="in"/><arg type="s" name="h" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetMode"><arg type="s" name="m" direction="in"/><arg type="i" name="s" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetGlobal"><arg type="b" name="p" direction="in"/><arg type="i" name="b" direction="in"/><arg type="s" name="d" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="GetState"><arg type="s" name="j" direction="out"/></method>
        <method name="SetWinLock"><arg type="b" name="locked" direction="in"/><arg type="s" name="result" direction="out"/></method>
        <method name="Ping"><arg type="s" name="resp" direction="out"/></method>
      </interface>
    </node>
    """

    def __init__(self):
        self._rgb = RGBController()
        self._config = ServiceConfig(
            "rgb",
            {
                "mode": "static",
                "colors": ["FF0000"] * 8,
                "speed": 50,
                "brightness": 100,
                "direction": "ltr",
                "power": True,
                "win_lock": False,
            },
        )
        self._config.load()

        # Validate loaded colors
        colors = self._config.get("colors", [])
        if isinstance(colors, list):
            cleaned = []
            for c in colors[:8]:
                cs = str(c).lstrip("#").upper()
                if HEX_COLOR_RE.match(cs):
                    cleaned.append(cs)
            if cleaned:
                c0 = cleaned[0]
                self._config.set("colors", (cleaned + [c0] * 8)[:8])

        # Validate mode
        if self._config.get("mode") not in VALID_LIGHT_MODES:
            self._config.set("mode", "static")

        # Restore win lock
        if self._rgb.is_available():
            self._rgb.write_win_lock(self._config.get("win_lock", False))

        # Start animation engine
        self._engine = None
        if self._rgb.is_available():
            self._engine = AnimationEngine(self._rgb, self._config)
            self._engine.start()
            logger.info("RGB engine started")

    # ── D-Bus methods ─────────────────────────────────────────────────

    def SetColor(self, z, h):
        c = str(h).lstrip("#").upper()
        if not HEX_COLOR_RE.match(c):
            return "FAIL"

        self._config.set("mode", "static")
        self._config.set("power", True)
        if z == 8:
            self._config.set("colors", [c] * 8)
        elif 0 <= z < 8:
            colors = self._config.get("colors", ["FF0000"] * 8)
            colors[z] = c
            self._config.set("colors", colors)
        else:
            return "FAIL"
        self._config.save()
        return "OK"

    def SetMode(self, m, s):
        if m not in VALID_LIGHT_MODES:
            return "FAIL"
        self._config.set("mode", m)
        self._config.set("speed", max(1, min(int(s), 100)))
        self._config.set("power", True)
        self._config.save()
        return "OK"

    def SetGlobal(self, p, b, d):
        if d not in VALID_DIRECTIONS:
            return "FAIL"
        self._config.set("power", bool(p))
        self._config.set("brightness", max(0, min(int(b), 100)))
        self._config.set("direction", d)
        self._config.save()
        return "OK"

    def GetState(self):
        data = self._config.snapshot()
        data["rgb_available"] = self._rgb.is_available()
        data["rgb_supported"] = getattr(self._rgb, "rgb_supported", True)
        data["brightness_supported"] = getattr(self._rgb, "brightness_supported", True)
        return json.dumps(data)

    def SetWinLock(self, locked):
        logger.info("SetWinLock: %s", "LOCKED" if locked else "UNLOCKED")
        self._config.set("win_lock", bool(locked))
        self._rgb.write_win_lock(bool(locked))
        self._config.save()
        return "OK"

    def Ping(self):
        return "OK"


# ─── Entry point ──────────────────────────────────────────────────────────────


def main():
    service = RGBService()
    run_service("com.yyl.hpmanager.rgb", service, service_name="rgb")


if __name__ == "__main__":
    main()

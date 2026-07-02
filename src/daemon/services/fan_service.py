#!/usr/bin/env python3
"""OMEN Command Center for Linux — Fan Microservice.

Owns fan speed monitoring, fan mode control (auto/max/custom), and per-fan
RPM target setting.  Exposes its functionality over D-Bus as
``com.yyl.hpmanager.fan``.
"""

import glob
import os
import sys
import threading
import time

# Ensure the parent package is importable when run as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.logging_config import setup_logging
from common.config import ServiceConfig
from common.sysfs import (
    normalize_profile_name,
    sysfs_exists,
    sysfs_read,
    sysfs_read_str,
    sysfs_write,
)
from common.dbus_helpers import run_service, system_sleeping
from common.ec_controller import LinuxEcController

logger = setup_logging("fan")

PWM_MAX = 255
PWM_FALLBACK_MIN = 50
THERMAL_PROFILE_BALANCED = 0
THERMAL_PROFILE_MAX = 1

# ─── Fan Controller ───────────────────────────────────────────────────────────


class FanController:
    """Low-level fan hardware access via hwmon sysfs."""

    def __init__(self):
        self.ec = LinuxEcController()
        self.hwmon_path = self._find_hwmon()
        self.fan_count = 0
        self.found_fans = []
        self.max_speeds = {}
        self.mode = "auto"
        self._fallback_paths = {}
        self._last_targets = {}
        if self.hwmon_path:
            self._detect_fans()
            self._read_max_speeds()
            self._read_current_mode()
        if not self.found_fans and self.ec.has_ec_access:
            logger.info("No hwmon fans detected, but EC access is available. Populating legacy EC fans.")
            self.found_fans = [1, 2]
            self.fan_count = 2
            self.max_speeds = {1: 6000, 2: 6000}

    # ── discovery ─────────────────────────────────────────────────────

    def _find_hwmon(self):
        for path in glob.glob("/sys/class/hwmon/hwmon*/name"):
            try:
                with open(path) as f:
                    name = f.read().strip()
                    if name in ("hp", "hp-omen"):
                        hwmon = os.path.dirname(path)
                        logger.info("Found HP/OMEN hwmon at %s (driver=%s)", hwmon, name)
                        return hwmon
            except Exception:
                pass

        for platform_name in ("hp-wmi", "hp_wmi", "hp-omen"):
            platform_hwmon = f"/sys/devices/platform/{platform_name}/hwmon"
            if os.path.exists(platform_hwmon):
                try:
                    entries = sorted(os.listdir(platform_hwmon))
                    if entries:
                        path = os.path.join(platform_hwmon, entries[0])
                        logger.info("Found HP hwmon via platform device at %s", path)
                        return path
                except Exception:
                    pass

        logger.warning("No HP hwmon device found")
        return None

    def _detect_fans(self):
        if not self.hwmon_path:
            return
        for f in os.listdir(self.hwmon_path):
            if f.startswith("fan") and f.endswith("_input"):
                try:
                    fan_num = int(f[3:-6])
                    self.found_fans.append(fan_num)
                    self._fallback_paths[fan_num] = self._find_fallback_path(fan_num)
                except ValueError:
                    continue
        self.found_fans.sort()
        self.fan_count = len(self.found_fans)

    def _find_fallback_path(self, fan_num):
        for path in glob.glob("/sys/class/hwmon/hwmon*/fan*_input"):
            try:
                basename = os.path.basename(path)
                hwmon_dir = os.path.dirname(path)
                if hwmon_dir == self.hwmon_path:
                    continue
                idx = basename.replace("fan", "").replace("_input", "")
                if idx == str(fan_num):
                    return path
            except Exception:
                continue
        return None

    def _read_max_speeds(self):
        if not self.hwmon_path:
            return
        for i in self.found_fans:
            max_path = os.path.join(self.hwmon_path, f"fan{i}_max")
            self.max_speeds[i] = sysfs_read(max_path, 6000)

    def _read_current_mode(self):
        if not self.hwmon_path:
            return
        pwm_path = os.path.join(self.hwmon_path, "pwm1_enable")
        val = sysfs_read(pwm_path, 2)
        if val == 0:
            self.mode = "max"
            return
        if val == 1:
            self.mode = "custom"
            return
        # pwm1_enable == 2 means auto; don't use platform_profile fallback
        # because "performance" power profile ≠ "max" fan mode.
        self.mode = "auto"

    def supports_custom_mode(self):
        if self.hwmon_path:
            if sysfs_exists(os.path.join(self.hwmon_path, "fan1_target")) or sysfs_exists(os.path.join(self.hwmon_path, "pwm1")):
                return True
        if self.ec.has_ec_access and not self.ec.is_unsafe_ec_model:
            return True
        return False

    # ── read ──────────────────────────────────────────────────────────

    def _hwmon_read(self, filename):
        if not self.hwmon_path:
            return 0
        return sysfs_read(os.path.join(self.hwmon_path, filename))

    def get_fan_count(self):
        return self.fan_count

    def get_max_speed(self, fan_num):
        val = self.max_speeds.get(fan_num, 6000)
        if val <= 0:
            val = 6000
        return val

    def get_current_speed(self, fan_num):
        speed = self._hwmon_read(f"fan{fan_num}_input")
        if speed == 0:
            speed = self._try_fan_speed_fallback(fan_num)
        return speed

    def _try_fan_speed_fallback(self, fan_num):
        path = self._fallback_paths.get(fan_num)
        if path:
            val = sysfs_read(path)
            if val > 0:
                return val
        return 0

    def get_target_speed(self, fan_num):
        target_path = os.path.join(self.hwmon_path, f"fan{fan_num}_target") if self.hwmon_path else None
        if target_path and sysfs_exists(target_path):
            return sysfs_read(target_path)

        if self._has_pwm_fallback():
            pwm = self._hwmon_read("pwm1")
            return int(self.get_max_speed(fan_num) * pwm / PWM_MAX)

        return 0

    # ── write ─────────────────────────────────────────────────────────

    def set_mode(self, mode):
        val = {"auto": 2, "max": 0, "custom": 1}.get(mode)
        if val is None:
            return False

        ok = False
        if self.hwmon_path:
            # Always attempt the pwm1_enable write instead of relying on
            # cached/fallback mode detection which can be inaccurate.
            ok = sysfs_write(os.path.join(self.hwmon_path, "pwm1_enable"), val)

        if not ok and mode == "custom" and self._has_pwm_fallback():
            logger.info("pwm1_enable write failed for custom, falling back to direct pwm1 write availability")
            ok = True

        if not ok and mode == "max":
            logger.info("pwm1_enable write failed for max, trying platform profile fallback")
            for profile_path, profile_value in (
                ("/sys/devices/platform/hp-wmi/thermal_profile", "1"),
                ("/sys/devices/platform/hp-omen/thermal_profile", "1"),
                ("/sys/firmware/acpi/platform_profile", "performance"),
                ("/sys/devices/platform/hp-wmi/platform_profile", "performance"),
            ):
                if not sysfs_exists(profile_path):
                    continue
                logger.debug("Trying fallback: %s = %s", profile_path, profile_value)
                if sysfs_write(profile_path, profile_value):
                    ok = True
                    logger.info("Max fan mode set via fallback: %s", profile_path)
                    break
            if not ok and self._has_pwm_fallback():
                logger.info("Using direct pwm1 write (255) for max mode fallback")
                if sysfs_write(os.path.join(self.hwmon_path, "pwm1"), 255):
                    ok = True

        if not ok and mode == "auto":
            logger.info("pwm1_enable write failed for auto, trying platform profile fallback")
            for profile_path, profile_value in (
                ("/sys/devices/platform/hp-wmi/thermal_profile", "0"),
                ("/sys/devices/platform/hp-omen/thermal_profile", "0"),
                ("/sys/firmware/acpi/platform_profile", "balanced"),
                ("/sys/devices/platform/hp-wmi/platform_profile", "balanced"),
            ):
                if not sysfs_exists(profile_path):
                    continue
                logger.debug("Trying fallback: %s = %s", profile_path, profile_value)
                if sysfs_write(profile_path, profile_value):
                    ok = True
                    logger.info("Auto fan mode set via fallback: %s", profile_path)
                    break
            if not ok and self._has_pwm_fallback():
                logger.info("Using direct pwm1 write (0) for auto mode fallback")
                if sysfs_write(os.path.join(self.hwmon_path, "pwm1"), 0):
                    ok = True

        if not ok and self.ec.has_ec_access and not self.ec.is_unsafe_ec_model:
            logger.info("Using direct EC write for mode %s fallback", mode)
            if self.ec.set_perf_mode(mode):
                ok = True

        if ok:
            self.mode = mode
            self._last_targets.clear()
            logger.info("Fan mode set to %s", mode)
        else:
            logger.warning("Failed to set fan mode to %s (all paths failed)", mode)
        return ok

    def set_fan_target(self, fan_num, rpm):
        if fan_num not in self.found_fans:
            logger.debug("set_fan_target: invalid fan_num=%s", fan_num)
            return False
        rpm = max(0, min(rpm, self.get_max_speed(fan_num)))

        # Mode recovery: ensure pwm1_enable is 1 before writing target RPM
        if self.hwmon_path:
            pwm_path = os.path.join(self.hwmon_path, "pwm1_enable")
            if sysfs_exists(pwm_path) and sysfs_read(pwm_path, 2) != 1:
                sysfs_write(pwm_path, 1)
                self.mode = "custom"

        # Avoid WMI flooding if target RPM hasn't changed meaningfully (>100 RPM)
        last_rpm = self._last_targets.get(fan_num, -1)
        if last_rpm >= 0 and abs(rpm - last_rpm) < 100:
            return True

        path = os.path.join(self.hwmon_path, f"fan{fan_num}_target") if self.hwmon_path else None
        if path and sysfs_exists(path):
            ok = sysfs_write(path, rpm)
        elif self._has_pwm_fallback():
            ok = self._set_pwm_fallback_target(fan_num, rpm)
        elif self.ec.has_ec_access and not self.ec.is_unsafe_ec_model:
            max_rpm = self.get_max_speed(fan_num)
            pct = int(round(rpm * 100.0 / max_rpm))
            logger.info("Using direct EC write for fan %d target (%d%%)", fan_num, pct)
            ok = self.ec.set_fan_speed_pct(fan_num, pct)
        else:
            logger.debug(
                "No fan%d_target, pwm1 fallback, or EC access available",
                fan_num,
            )
            return False

        if ok:
            self._last_targets[fan_num] = rpm
            logger.info("Fan %d target set to %d RPM", fan_num, rpm)
        else:
            logger.debug("Fan %d target set to %d RPM failed", fan_num, rpm)
        return ok

    def _has_pwm_fallback(self):
        if not self.hwmon_path:
            return False
        return sysfs_exists(os.path.join(self.hwmon_path, "pwm1"))

    def _set_pwm_fallback_target(self, fan_num, rpm):
        max_speed = self.get_max_speed(fan_num)
        if max_speed <= 0:
            max_speed = 6000

        pwm = int(round(rpm * PWM_MAX / max_speed))
        pwm = max(0, min(pwm, PWM_MAX))
        if pwm > 0:
            pwm = max(pwm, PWM_FALLBACK_MIN)

        enable_path = os.path.join(self.hwmon_path, "pwm1_enable")
        if sysfs_exists(enable_path) and self.mode != "custom":
            if sysfs_read(enable_path, 2) != 1:
                sysfs_write(enable_path, 1)
                self.mode = "custom"

        return sysfs_write(os.path.join(self.hwmon_path, "pwm1"), pwm)

    def is_available(self):
        return (self.hwmon_path is not None and self.fan_count > 0) or self.ec.has_ec_access

    def get_mode(self):
        if self.hwmon_path:
            self._read_current_mode()
        return self.mode


# ─── D-Bus Service ────────────────────────────────────────────────────────────

import json
import subprocess


def send_desktop_notification(title, message):
    """Send desktop notification to active user sessions."""
    try:
        # Find active user sessions by inspecting active X11/Wayland processes
        for p in glob.glob("/proc/*/environ"):
            try:
                with open(p, "rb") as f:
                    content = f.read()
                if b"DISPLAY=" in content or b"WAYLAND_DISPLAY=" in content:
                    env = {}
                    for item in content.split(b"\0"):
                        if b"=" in item:
                            k, v = item.split(b"=", 1)
                            env[k.decode("utf-8", "ignore")] = v.decode("utf-8", "ignore")
                    user = env.get("USER") or env.get("LOGNAME")
                    display = env.get("DISPLAY") or ":0"
                    dbus_addr = env.get("DBUS_SESSION_BUS_ADDRESS")
                    xdg_runtime = env.get("XDG_RUNTIME_DIR")
                    if user and (dbus_addr or xdg_runtime):
                        cmd = ["sudo", "-u", user, "env", f"DISPLAY={display}"]
                        if dbus_addr:
                            cmd.append(f"DBUS_SESSION_BUS_ADDRESS={dbus_addr}")
                        if xdg_runtime:
                            cmd.append(f"XDG_RUNTIME_DIR={xdg_runtime}")
                        cmd.extend(["notify-send", "-u", "critical", "-a", "OmenCtl", title, message])
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
                        break
            except Exception:
                pass
    except Exception as e:
        logger.debug("Failed to send desktop notification: %s", e)


class FanService:
    """
    <node>
      <interface name="com.yyl.hpmanager.fan">
        <method name="SetFanMode"><arg type="s" name="mode" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetFanTarget"><arg type="i" name="fan" direction="in"/><arg type="i" name="rpm" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="GetFanInfo"><arg type="s" name="j" direction="out"/></method>
        <method name="SaveCustomCurve"><arg type="s" name="curve_json" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="Ping"><arg type="s" name="resp" direction="out"/></method>
      </interface>
    </node>
    """

    def __init__(self):
        self._fan = FanController()
        self._config = ServiceConfig("fan", {"fan_mode": "auto", "custom_curve": "[]"})
        self._config.load()

        self._cache_lock = threading.Lock()
        self._fan_cache = {}
        self._thermal_protection_active = False
        self._thermal_protection_entered_at = 0.0
        self._pre_protection_mode = None

        # Restore saved fan mode
        self._restore_fan_mode()

        # Background monitoring thread
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _restore_fan_mode(self):
        if not self._fan.is_available():
            return
        saved = self._config.get("fan_mode", "auto")

        if saved in ("auto", "max", "custom"):
            if self._fan.get_mode() != saved:
                ok = self._fan.set_mode(saved)
                logger.info("Restored fan mode '%s' (success=%s)", saved, ok)
            else:
                logger.info("Fan mode already '%s', skipping write", saved)

    # Known CPU/GPU hwmon driver names for targeted temperature reading
    _CPU_GPU_DRIVERS = frozenset({
        "coretemp", "k10temp", "zenpower", "cpu_thermal",  # CPU
        "amdgpu", "nvidia", "nouveau", "radeon",            # GPU
        "hp", "hp-omen",                                    # HP WMI (reports CPU/GPU)
    })

    def _get_max_temp(self):
        """Read the highest CPU/GPU temperature.

        Prefer sensors from known CPU/GPU drivers to avoid phantom readings
        from NVMe, VRM, ACPI, or other unrelated hwmon devices.
        Falls back to all sensors only if no known driver is found.
        """
        cpu_gpu_max = 0.0
        all_max = 0.0
        found_known_driver = False

        try:
            for hwmon_dir in glob.glob("/sys/class/hwmon/hwmon*/"):
                # Identify the driver name for this hwmon device
                name_path = os.path.join(hwmon_dir, "name")
                driver_name = ""
                try:
                    with open(name_path) as f:
                        driver_name = f.read().strip().lower()
                except Exception:
                    pass

                is_known = driver_name in self._CPU_GPU_DRIVERS
                if is_known:
                    found_known_driver = True

                for temp_path in glob.glob(os.path.join(hwmon_dir, "temp*_input")):
                    try:
                        with open(temp_path) as f:
                            t = int(f.read().strip()) / 1000.0
                            if 0 < t < 120:
                                if is_known and t > cpu_gpu_max:
                                    cpu_gpu_max = t
                                if t > all_max:
                                    all_max = t
                    except Exception:
                        pass
        except Exception:
            pass

        # Prefer CPU/GPU-specific reading; fall back to all sensors
        if found_known_driver and cpu_gpu_max > 0:
            return cpu_gpu_max

        if all_max > 0:
            return all_max

        # Last resort: thermal zones
        try:
            for path in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
                try:
                    with open(path) as f:
                        t = int(f.read().strip()) / 1000.0
                        if 0 < t < 120 and t > all_max:
                            all_max = t
                except Exception:
                    pass
        except Exception:
            pass

        return all_max or 45.0

    def _curve_fan_pct(self, points, temp):
        if not points:
            return 0
        if temp <= points[0][0]:
            return points[0][1]
        if temp >= points[-1][0]:
            return points[-1][1]
        for idx in range(len(points) - 1):
            t0, f0 = points[idx]
            t1, f1 = points[idx + 1]
            if t0 <= temp <= t1:
                ratio = (temp - t0) / (t1 - t0) if t1 != t0 else 0
                return f0 + (f1 - f0) * ratio
        return points[-1][1]

    def _monitor_loop(self):
        while True:
            if system_sleeping.is_set():
                time.sleep(0.5)
                continue

            temp = self._get_max_temp()

            # Thermal Protection Mode
            if temp > 95.0 and not self._thermal_protection_active:
                logger.warning("Temperature exceeded 95°C (%d°C). Activating Thermal Protection Mode (Max Fan).", temp)
                self._thermal_protection_active = True
                self._thermal_protection_entered_at = time.monotonic()
                self._pre_protection_mode = self._config.get("fan_mode", self._fan.get_mode())
                self._fan.set_mode("max")
                send_desktop_notification(
                    "OmenCtl Koruma Modu",
                    "Yüksek sıcaklıklardan cihazınızı korumak için max fan modu aktif edildi."
                )
            elif self._thermal_protection_active:
                elapsed = time.monotonic() - self._thermal_protection_entered_at
                # Exit conditions:
                # 1. Temperature dropped below 85°C (10°C hysteresis from 95°C entry), OR
                # 2. Protection active >5 minutes AND temp below 90°C (timeout safety net)
                should_exit = temp <= 85.0 or (elapsed > 300.0 and temp <= 90.0)

                if should_exit:
                    if elapsed > 300.0:
                        logger.info("Thermal Protection timeout after %.0fs (temp=%d°C). Deactivating.", elapsed, temp)
                    else:
                        logger.info("Temperature dropped to %d°C. Deactivating Thermal Protection Mode.", temp)
                    self._thermal_protection_active = False
                    self._thermal_protection_entered_at = 0.0
                    restore = self._pre_protection_mode or "auto"
                    self._fan.set_mode(restore)
                    send_desktop_notification(
                        "OmenCtl Koruma Modu",
                        f"Sıcaklık normale döndü ({int(temp)}°C). Fanlar eski moduna ({restore}) geri getirildi."
                    )
                else:
                    # Keep ensuring max mode while protection is active
                    if self._fan.get_mode() != "max":
                        self._fan.set_mode("max")

            mode = self._fan.get_mode()
            custom_curve_str = self._config.get("custom_curve", "[]")

            if mode == "custom" and not self._thermal_protection_active:
                try:
                    curve = json.loads(custom_curve_str)
                    if not curve or len(curve) == 0:
                        # Fallback default safe curve if empty
                        curve = [[40, 30], [60, 50], [80, 80], [90, 100]]
                    if curve and len(curve) > 0:
                        pct = self._curve_fan_pct(curve, temp)
                        for i in self._fan.found_fans:
                            max_rpm = self._fan.get_max_speed(i)
                            target = int(max_rpm * pct / 100.0)
                            self._fan.set_fan_target(i, target)
                except Exception as e:
                    logger.debug("Failed to apply custom curve in monitor loop: %s", e)

            fans_data = {
                str(i): {
                    "current": self._fan.get_current_speed(i),
                    "max": self._fan.get_max_speed(i),
                    "target": self._fan.get_target_speed(i),
                }
                for i in self._fan.found_fans
            }
            snapshot = {
                "available": self._fan.is_available(),
                "fan_count": self._fan.get_fan_count(),
                "mode": mode,
                "supports_custom": self._fan.supports_custom_mode(),
                "custom_curve": custom_curve_str,
                "fans": fans_data,
                "thermal_protection": self._thermal_protection_active,
            }

            with self._cache_lock:
                self._fan_cache = snapshot

            time.sleep(2.0)

    # ── D-Bus methods ─────────────────────────────────────────────────

    def SetFanMode(self, mode):
        logger.info("SetFanMode: %s", mode)
        if self._thermal_protection_active:
            logger.info("Thermal protection is active. Recording target mode '%s' for post-protection restoration.", mode)
            self._pre_protection_mode = mode
            self._config.set("fan_mode", mode)
            self._config.save()
            return "OK"
        if self._fan.get_mode() == mode and self._config.get("fan_mode") == mode:
            return "OK"
        ok = self._fan.set_mode(mode)
        if ok:
            self._config.set("fan_mode", mode)
            self._config.save()
        return "OK" if ok else "FAIL"

    def SetFanTarget(self, fan, rpm):
        logger.info("SetFanTarget: fan=%d, rpm=%d", fan, rpm)
        return "OK" if self._fan.set_fan_target(fan, rpm) else "FAIL"

    def GetFanInfo(self):
        with self._cache_lock:
            return json.dumps(self._fan_cache)

    def SaveCustomCurve(self, curve_json):
        logger.info("SaveCustomCurve: %s", curve_json)
        try:
            data = json.loads(curve_json)
            if not isinstance(data, list):
                return "FAIL"
        except Exception:
            return "FAIL"
        if self._config.get("custom_curve") == curve_json:
            return "OK"
        self._config.set("custom_curve", curve_json)
        self._config.save()
        return "OK"

    def Ping(self):
        return "OK"


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    service = FanService()
    if service._fan.is_available():
        logger.info("Fan control active: %d fans", service._fan.get_fan_count())
    run_service("com.yyl.hpmanager.fan", service, service_name="fan")


if __name__ == "__main__":
    main()

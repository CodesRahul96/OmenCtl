#!/usr/bin/env python3
"""OMEN Command Center for Linux — Power Profile Microservice.

Owns power-profile management (PPD / Tuned / OMEN Direct) and NVIDIA
GPU power-limit synchronisation.  Exposes its functionality over D-Bus
as ``com.yyl.hpmanager.power``.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.logging_config import setup_logging
from common.config import ServiceConfig
from common.app_launchers import get_running_launcher_ids
from common.dbus_helpers import run_service
from common.sysfs import (
    normalize_profile_name,
    sysfs_exists,
    sysfs_read,
    sysfs_read_str,
    sysfs_write,
)

from pydbus import SystemBus

logger = setup_logging("power")
THERMAL_PROFILE_BALANCED = 0


# ─── Power Profile Controller ────────────────────────────────────────────────


class PowerProfileController:
    PPD_BUS = "net.hadess.PowerProfiles"
    PPD_PATH = "/net/hadess/PowerProfiles"
    TUNED_BUS = "com.redhat.tuned"
    TUNED_PATH = "/Tuned"

    def __init__(self):
        self.mode = "ppd"
        self.available = False
        self.bus = SystemBus()
        self.proxy = None

        try:
            self.proxy = self.bus.get(self.TUNED_BUS, self.TUNED_PATH)
            self.proxy.active_profile()
            self.mode = "tuned"
            self.available = True
            logger.info("PowerProfileController: Using Tuned backend")
        except Exception:
            try:
                self.proxy = self.bus.get(self.PPD_BUS, self.PPD_PATH)
                self.mode = "ppd"
                self.available = True
                logger.info("PowerProfileController: Using Power-Profiles-Daemon backend")
            except Exception:
                if sysfs_exists("/sys/devices/platform/hp-wmi/thermal_profile") or \
                   sysfs_exists("/sys/devices/platform/hp-omen/thermal_profile"):
                    self.mode = "omen_direct"
                    self.available = True
                    logger.info("PowerProfileController: Using OMEN Direct sysfs backend")
                else:
                    self.proxy = None
                    self.available = False
                    logger.warning("PowerProfileController: No power profile backend found")

    def get_profiles(self):
        if not self.available:
            return []
        if self.mode == "ppd":
            try:
                return [p["Profile"] for p in self.proxy.Profiles]
            except Exception:
                return ["power-saver", "balanced", "performance"]
        return ["power-saver", "balanced", "performance"]

    def get_active(self):
        if not self.available:
            return "balanced"
        try:
            # First, check direct WMI/ACPI platform profile as it is the absolute source of truth!
            wmi_active = self._get_omen_direct_active()
            if wmi_active is not None:
                return wmi_active

            # Fallback to ppd / tuned
            if self.mode == "ppd":
                return self.proxy.ActiveProfile
            if self.mode == "tuned":
                tp = self.proxy.active_profile()
                if "powersave" in tp:
                    return "power-saver"
                if "performance" in tp:
                    return "performance"
                return "balanced"
            return "balanced"
        except Exception:
            return "balanced"

    def _get_omen_direct_active(self):
        found = False
        for path in (
            "/sys/firmware/acpi/platform_profile",
            "/sys/devices/platform/hp-wmi/platform_profile",
        ):
            if not sysfs_exists(path):
                continue
            found = True
            normalized = normalize_profile_name(sysfs_read_str(path, "balanced"))
            if "performance" in normalized:
                return "performance"
            if normalized in ("low-power", "quiet", "cool", "power-saver"):
                return "power-saver"
            return "balanced"

        for path in (
            "/sys/devices/platform/hp-wmi/thermal_profile",
            "/sys/devices/platform/hp-omen/thermal_profile",
        ):
            if not sysfs_exists(path):
                continue
            found = True
            val = sysfs_read(path, THERMAL_PROFILE_BALANCED)
            if val == 1:
                return "performance"
            return "balanced"

        return None if not found else "balanced"

    def _sync_omen_profile(self, profile):
        target_candidates = {
            "performance": ("performance",),
            "balanced": ("balanced",),
            "power-saver": ("low-power", "quiet", "cool", "power-saver", "balanced"),
        }.get(profile, ("balanced",))

        for path in (
            "/sys/firmware/acpi/platform_profile",
            "/sys/devices/platform/hp-wmi/platform_profile",
        ):
            if not sysfs_exists(path):
                continue
            choices_raw = sysfs_read_str(f"{path}_choices", "")
            choices = {
                normalize_profile_name(token.strip("[]"))
                for token in choices_raw.split()
                if token.strip("[]")
            }
            if choices:
                candidates = [candidate for candidate in target_candidates if candidate in choices]
                if not candidates and "balanced" in choices:
                    candidates = ["balanced"]
            else:
                candidates = list(target_candidates)

            for target in candidates:
                if sysfs_write(path, target):
                    return True

        thermal_val = {"power-saver": "0", "balanced": "0", "performance": "1"}.get(
            profile, "0"
        )
        for path in (
            "/sys/devices/platform/hp-wmi/thermal_profile",
            "/sys/devices/platform/hp-omen/thermal_profile",
        ):
            if not sysfs_exists(path):
                continue
            if sysfs_write(path, thermal_val):
                return True
        return False

    def set_profile(self, profile):
        if not self.available:
            return False
        try:
            if self.mode == "ppd":
                if shutil.which("powerprofilesctl"):
                    try:
                        res = subprocess.run(["powerprofilesctl", "set", profile], capture_output=True, text=True, timeout=2.0)
                        if res.returncode == 0:
                            logger.info("Successfully set ppd profile via powerprofilesctl: %s", profile)
                        else:
                            logger.warning("powerprofilesctl set returned non-zero: %s (stderr: %s), falling back to direct dbus", res.returncode, res.stderr)
                            self.proxy.ActiveProfile = profile
                    except Exception as e:
                        logger.warning("Failed to run powerprofilesctl set: %s, falling back to direct dbus", e)
                        self.proxy.ActiveProfile = profile
                else:
                    self.proxy.ActiveProfile = profile
            elif self.mode == "tuned":
                mapping = {
                    "power-saver": "powersave",
                    "balanced": "balanced",
                    "performance": "throughput-performance",
                }
                self.proxy.switch_profile(mapping.get(profile, "balanced"))
            elif self.mode == "omen_direct":
                if not self._sync_omen_profile(profile):
                    return False
                threading.Thread(
                    target=self._sync_runtime_power, args=(profile,), daemon=True
                ).start()
                return True

            threading.Thread(
                target=self._sync_hardware_power, args=(profile,), daemon=True
            ).start()
            return True
        except Exception as e:
            logger.error("Power profile set error (%s): %s", self.mode, e)
            return False

    def _sync_nvidia_power(self, profile):
        try:
            if not shutil.which("nvidia-smi"):
                return

            if profile == "performance":
                out = subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=power.max_limit",
                        "--format=csv,noheader,nounits",
                    ],
                    timeout=2.0,
                ).decode().strip()
                if out:
                    limit = int(float(out))
                    subprocess.run(
                        ["nvidia-smi", "-pl", str(limit)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2.0,
                    )
                    logger.info("NVIDIA GPU locked to MAX Performance: %dW", limit)
            else:
                out = subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=power.default_limit",
                        "--format=csv,noheader,nounits",
                    ],
                    timeout=2.0,
                ).decode().strip()
                if out:
                    limit = int(float(out))
                    subprocess.run(
                        ["nvidia-smi", "-pl", str(limit)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2.0,
                    )
                    logger.info("NVIDIA GPU restored to DEFAULT Base: %dW", limit)
        except Exception as e:
            logger.warning("Failed to sync NVIDIA power curve: %s", e)

    def _sync_runtime_power(self, profile):
        self._sync_nvidia_power(profile)
        self._sync_kernel_gpu_power(profile)

    def _sync_hardware_power(self, profile):
        """Orchestrate platform profile sync and GPU power limits."""
        self._sync_omen_profile(profile)
        self._sync_runtime_power(profile)

    def _sync_kernel_gpu_power(self, profile):
        """Trigger TGP and PPAB via the patched hp-wmi driver."""
        base = "/sys/devices/platform/hp-wmi"
        if not sysfs_exists(base):
            base = "/sys/devices/platform/hp-omen"
        
        tgp_path = f"{base}/gpu_tgp"
        ppab_path = f"{base}/gpu_ppab"

        if not sysfs_exists(tgp_path):
            return

        try:
            if profile == "performance":
                sysfs_write(tgp_path, "1")
                sysfs_write(ppab_path, "1")
                logger.info("Kernel GPU Power: TGP=Enabled, PPAB=Enabled")
            elif profile == "balanced":
                sysfs_write(tgp_path, "0")
                sysfs_write(ppab_path, "1")
                logger.info("Kernel GPU Power: TGP=Disabled, PPAB=Enabled")
            else: # power-saver / quiet / eco
                sysfs_write(tgp_path, "0")
                sysfs_write(ppab_path, "0")
                logger.info("Kernel GPU Power: TGP=Disabled, PPAB=Disabled")
        except Exception as e:
            logger.warning("Failed to sync Kernel GPU power: %s", e)


# ─── D-Bus Service ────────────────────────────────────────────────────────────


class PowerService:
    """
    <node>
      <interface name="com.yyl.hpmanager.power">
        <method name="SetPowerProfile"><arg type="s" name="profile" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="GetPowerProfile"><arg type="s" name="j" direction="out"/></method>
        <method name="SetAppProfilesEnabled"><arg type="b" name="enabled" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetAppProfiles"><arg type="s" name="json_str" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="Ping"><arg type="s" name="resp" direction="out"/></method>
      </interface>
    </node>
    """

    def __init__(self):
        self._ctrl = PowerProfileController()
        self._config = ServiceConfig("power", {
            "power_profile": "balanced",
            "app_profiles_enabled": False,
            "app_profiles": {}
        })
        self._config.load()

        # Restore saved profile
        if self._ctrl.available:
            saved = self._config.get("power_profile", "balanced")
            if saved in self._ctrl.get_profiles():
                if self._ctrl.get_active() != saved:
                    ok = self._ctrl.set_profile(saved)
                    logger.info("Restored power profile '%s' (success=%s)", saved, ok)
                else:
                    logger.info("Power profile already '%s', skipping", saved)

        self._matched_app = None
        self._original_fan_mode = None
        self._original_rgb_state = None
        self._proc_cache = {}
        # Start background app profiles monitor
        self._monitor_thread = threading.Thread(target=self._app_monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _get_running_process_names(self):
        names = set()
        new_cache = {}
        try:
            for pid_dir in os.listdir("/proc"):
                if not pid_dir.isdigit():
                    continue
                pid = int(pid_dir)
                try:
                    mtime = os.path.getmtime(f"/proc/{pid_dir}")
                except Exception:
                    continue

                cached_val = self._proc_cache.get(pid)
                if cached_val and cached_val["mtime"] == mtime:
                    names.update(cached_val["names"])
                    new_cache[pid] = cached_val
                    continue

                # Cache miss: read process info
                pid_names = set()
                try:
                    # Read comm (command name)
                    with open(f"/proc/{pid_dir}/comm", "r", errors="ignore") as f:
                        comm = f.read().strip().lower()
                        if comm:
                            pid_names.add(comm)
                    # Read cmdline (args/path)
                    with open(f"/proc/{pid_dir}/cmdline", "r", errors="ignore") as f:
                        cmd = f.read().replace("\x00", " ").strip().lower()
                        if cmd:
                            for token in cmd.split():
                                base = os.path.basename(token)
                                if base:
                                    pid_names.add(base)
                    # Read environ to check for launcher App IDs
                    pid_names.update(get_running_launcher_ids(pid_dir))
                except Exception:
                    pass

                new_cache[pid] = {"mtime": mtime, "names": pid_names}
                names.update(pid_names)
            
            self._proc_cache = new_cache
        except Exception as e:
            logger.warning("Failed to scan /proc: %s", e)
        return names

    def _app_monitor_loop(self):
        # Allow system services to settle
        time.sleep(5)
        while True:
            try:
                enabled = self._config.get("app_profiles_enabled", False)
                app_profiles = self._config.get("app_profiles", {})
                user_profile = self._config.get("power_profile", "balanced")

                matched_app = None
                matched_profile = None
                matched_fan_mode = "default"
                matched_rgb_mode = "default"

                if enabled and app_profiles:
                    running = self._get_running_process_names()
                    for app_name, val in app_profiles.items():
                        profile = val.get("profile", "balanced") if isinstance(val, dict) else val
                        fan_mode = val.get("fan_mode", "default") if isinstance(val, dict) else "default"
                        rgb_mode = val.get("rgb", "default") if isinstance(val, dict) else "default"
                        app_lower = app_name.lower()
                        if app_lower in running:
                            matched_app = app_name
                            matched_profile = profile
                            matched_fan_mode = fan_mode
                            matched_rgb_mode = rgb_mode
                            break
                        
                        # Check substring match
                        for r in running:
                            if app_lower in r:
                                matched_app = app_name
                                matched_profile = profile
                                matched_fan_mode = fan_mode
                                matched_rgb_mode = rgb_mode
                                break
                        if matched_app:
                            break

                self._matched_app = matched_app
                if matched_app:
                    current_applied = self._ctrl.get_active()
                    if current_applied != matched_profile:
                        logger.info(
                            "App Profiles: Detected target app '%s' running, switching profile to '%s' (user default: '%s')",
                            matched_app, matched_profile, user_profile
                        )
                        self._ctrl.set_profile(matched_profile)
                    
                    if matched_fan_mode and matched_fan_mode != "default":
                        current_fan = self._get_system_fan_mode()
                        if current_fan != matched_fan_mode:
                            if self._original_fan_mode is None:
                                self._original_fan_mode = current_fan
                            logger.info("App Profiles: Switching fan mode to '%s' (was '%s')", matched_fan_mode, current_fan)
                            self._set_system_fan_mode(matched_fan_mode)

                    if matched_rgb_mode and matched_rgb_mode != "default":
                        if self._original_rgb_state is None:
                            current_rgb = self._get_system_rgb_state()
                            if current_rgb:
                                self._original_rgb_state = current_rgb
                            logger.info("App Profiles: Switching RGB state to '%s'", matched_rgb_mode)
                            self._set_system_rgb_state(matched_rgb_mode)
                else:
                    current_applied = self._ctrl.get_active()
                    if current_applied != user_profile:
                        logger.info(
                            "App Profiles: Restoring user profile '%s' (was '%s')",
                            user_profile, current_applied
                        )
                        self._ctrl.set_profile(user_profile)
                    
                    if self._original_fan_mode is not None:
                        logger.info("App Profiles: Restoring fan mode to '%s'", self._original_fan_mode)
                        self._set_system_fan_mode(self._original_fan_mode)
                        self._original_fan_mode = None

                    if self._original_rgb_state is not None:
                        logger.info("App Profiles: Restoring RGB state")
                        self._set_system_rgb_state(self._original_rgb_state)
                        self._original_rgb_state = None

            except Exception as e:
                logger.warning("Error in app monitor loop: %s", e)

            time.sleep(4)

    def _get_system_fan_mode(self):
        try:
            bus = SystemBus()
            fan_svc = bus.get("com.yyl.hpmanager.fan")
            info_json = fan_svc.GetFanInfo()
            info = json.loads(info_json)
            return info.get("mode", "auto")
        except Exception as e:
            logger.warning("Failed to query fan mode via D-Bus: %s", e)
            return "auto"

    def _set_system_fan_mode(self, mode):
        try:
            bus = SystemBus()
            fan_svc = bus.get("com.yyl.hpmanager.fan")
            fan_svc.SetFanMode(mode)
        except Exception as e:
            logger.error("Failed to set fan mode via D-Bus: %s", e)

    def _get_system_rgb_state(self):
        try:
            bus = SystemBus()
            rgb_svc = bus.get("com.yyl.hpmanager.rgb")
            state_json = rgb_svc.GetState()
            return json.loads(state_json)
        except Exception as e:
            logger.warning("Failed to query RGB state via D-Bus: %s", e)
            return None

    def _set_system_rgb_state(self, state):
        try:
            bus = SystemBus()
            rgb_svc = bus.get("com.yyl.hpmanager.rgb")
            if isinstance(state, dict):
                # Restore colors
                colors = state.get("colors", [])
                for z, c in enumerate(colors[:8]):
                    rgb_svc.SetColor(z, c)
                # Restore mode and speed
                rgb_svc.SetMode(state.get("mode", "static"), state.get("speed", 50))
                # Restore global settings
                rgb_svc.SetGlobal(state.get("power", True), state.get("brightness", 100), state.get("direction", "ltr"))
            elif isinstance(state, str):
                # Apply preset overrides
                if state == "static_red":
                    rgb_svc.SetColor(8, "FF0000")
                elif state == "static_green":
                    rgb_svc.SetColor(8, "00FF00")
                elif state == "static_blue":
                    rgb_svc.SetColor(8, "0000FF")
                elif state == "static_white":
                    rgb_svc.SetColor(8, "FFFFFF")
                elif state == "breathing":
                    rgb_svc.SetMode("breathing", 50)
                elif state == "cycle":
                    rgb_svc.SetMode("cycle", 50)
                elif state == "wave":
                    rgb_svc.SetMode("wave", 50)
        except Exception as e:
            logger.error("Failed to set RGB state via D-Bus: %s", e)

    def SetPowerProfile(self, profile):
        if profile not in self._ctrl.get_profiles():
            return "FAIL"
        ok = self._ctrl.set_profile(profile)
        if ok:
            self._config.set("power_profile", profile)
            self._config.save()
        return "OK" if ok else "FAIL"

    def SetAppProfilesEnabled(self, enabled):
        self._config.set("app_profiles_enabled", bool(enabled))
        self._config.save()
        logger.info("App Profiles Enabled: %s", enabled)
        return "OK"

    def SetAppProfiles(self, json_str):
        try:
            mapping = json.loads(json_str)
            if not isinstance(mapping, dict):
                return "FAIL"

            # Always have a valid set to check against — fall back to known names
            # if the power backend is unavailable (e.g. hp-wmi not installed).
            _raw_profiles = self._ctrl.get_profiles()
            valid_profiles = set(_raw_profiles) if _raw_profiles else {"power-saver", "balanced", "performance"}
            valid_fan   = {"default", "auto", "max"}
            valid_theme = {"default", "dark", "light"}
            valid_rgb   = {"default", "static_red", "static_green", "static_blue",
                           "static_white", "breathing", "cycle", "wave"}

            cleaned = {}
            for app, val in mapping.items():
                profile_name = val.get("profile") if isinstance(val, dict) else val
                if profile_name not in valid_profiles:
                    logger.warning("SetAppProfiles: skipping '%s' — unknown profile '%s'", app, profile_name)
                    continue
                if isinstance(val, dict):
                    if val.get("fan_mode", "default") not in valid_fan or \
                       val.get("theme", "default") not in valid_theme or \
                       val.get("rgb", "default") not in valid_rgb:
                        logger.warning("SetAppProfiles: skipping '%s' — invalid field value", app)
                        continue
                cleaned[app] = val

            self._config.set("app_profiles", cleaned)
            self._config.save()
            logger.info("App Profiles Updated: %s", cleaned)
            return "OK"
        except Exception as e:
            logger.error("Failed to parse app profiles: %s", e)
            return "FAIL"

    def GetPowerProfile(self):
        return json.dumps(
            {
                "available": self._ctrl.available,
                "active": self._ctrl.get_active(),
                "profiles": self._ctrl.get_profiles(),
                "app_profiles_enabled": self._config.get("app_profiles_enabled", False),
                "app_profiles": self._config.get("app_profiles", {}),
                "active_app": getattr(self, "_matched_app", None),
            }
        )

    def Ping(self):
        return "OK"


# ─── Entry point ──────────────────────────────────────────────────────────────


def main():
    service = PowerService()
    if service._ctrl.available:
        logger.info("Power profiles: %s", service._ctrl.get_profiles())
    run_service("com.yyl.hpmanager.power", service, service_name="power")


if __name__ == "__main__":
    main()

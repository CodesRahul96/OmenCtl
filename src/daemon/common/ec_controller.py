#!/usr/bin/env python3
"""OMEN Command Center for Linux — Embedded Controller (EC) Driver.

Accesses Linux EC via /sys/kernel/debug/ec/ec0/io using the ec_sys module.
Includes strict safety guards to prevent EC panic on 2025+ OMEN Max models
and fallback handling for legacy models like OMEN 15-ek0xxx (Board 878C).
"""

import os
import subprocess
import threading
import logging

from common.capabilities import detect_capabilities, get_board_id, get_product_name

logger = logging.getLogger("ec_controller")

# EC Register Addresses (Valid ONLY for pre-2025 legacy models like OMEN 15 2020)
REG_FAN1_SPEED_SET = 0x34  # Fan 1 speed set in units of 100 RPM
REG_FAN2_SPEED_SET = 0x35  # Fan 2 speed set in units of 100 RPM
REG_FAN1_SPEED_PCT = 0x2E  # Fan 1 speed 0-100%
REG_FAN2_SPEED_PCT = 0x2F  # Fan 2 speed 0-100%
REG_FAN_BOOST      = 0xEC  # Fan boost: 0x00=OFF, 0x0C=ON
REG_FAN_STATE      = 0xF4  # Fan state: 0x00=Enable, 0x02=Disable
REG_CPU_TEMP       = 0x57  # CPU temperature
REG_GPU_TEMP       = 0xB7  # GPU temperature
REG_PERF_MODE      = 0x95  # Performance mode (0x30=Default, 0x31=Perf, 0x50=Cool)
REG_THERMAL_POWER  = 0xBA  # Thermal power limit (0-5)

EC_PATH = "/sys/kernel/debug/ec/ec0/io"

class LinuxEcController:
    def __init__(self):
        self._lock = threading.Lock()
        self.capabilities = detect_capabilities()
        self.board_id = get_board_id()
        self.product_name = get_product_name()
        
        # Check if direct EC access is safe on this board
        self.is_unsafe_ec_model = not self.capabilities.supports_fan_control_ec
        self.has_ec_access = False
        
        if not self.is_unsafe_ec_model:
            self._ensure_ec_sys()
            self.has_ec_access = os.path.exists(EC_PATH)
        else:
            logger.info("Board ID %s (%s) flagged as Unsafe for legacy EC writes. Direct EC access disabled.", self.board_id, self.product_name)

    def _ensure_ec_sys(self):
        """Ensure ec_sys module is loaded with write_support=1."""
        if not os.path.exists(EC_PATH):
            try:
                logger.info("Trying to load ec_sys kernel module with write_support=1...")
                subprocess.run(["modprobe", "ec_sys", "write_support=1"], capture_output=True, timeout=5)
            except Exception as e:
                logger.debug("modprobe ec_sys failed: %s", e)

    def read_byte(self, reg: int) -> int:
        """Read a single byte from the EC register."""
        if not self.has_ec_access or self.is_unsafe_ec_model:
            return 0
        with self._lock:
            try:
                with open(EC_PATH, "rb") as f:
                    f.seek(reg)
                    data = f.read(1)
                    if data:
                        return data[0]
            except Exception as e:
                logger.debug("EC read_byte failed at 0x%02X: %s", reg, e)
                if isinstance(e, PermissionError):
                    logger.info("Kernel lockdown detected (PermissionError). Disabling EC access.")
                    self.has_ec_access = False
        return 0

    def write_byte(self, reg: int, val: int) -> bool:
        """Write a single byte to the EC register."""
        if not self.has_ec_access or self.is_unsafe_ec_model:
            return False
        with self._lock:
            try:
                with open(EC_PATH, "r+b") as f:
                    f.seek(reg)
                    f.write(bytes([val]))
                    f.flush()
                logger.debug("EC write_byte success at 0x%02X = 0x%02X", reg, val)
                return True
            except Exception as e:
                logger.debug("EC write_byte failed at 0x%02X: %s", reg, e)
                if isinstance(e, PermissionError):
                    logger.info("Kernel lockdown detected (PermissionError). Disabling EC access.")
                    self.has_ec_access = False
        return False

    def get_cpu_temp(self) -> float:
        val = self.read_byte(REG_CPU_TEMP)
        return float(val) if val > 0 else 0.0

    def get_gpu_temp(self) -> float:
        val = self.read_byte(REG_GPU_TEMP)
        return float(val) if val > 0 else 0.0

    def set_fan_speed_pct(self, fan_idx: int, pct: int) -> bool:
        """Set fan speed percentage (0-100) directly via EC for legacy models."""
        if self.is_unsafe_ec_model or not self.has_ec_access:
            return False
        pct = max(0, min(100, pct))
        reg = REG_FAN1_SPEED_PCT if fan_idx == 1 else REG_FAN2_SPEED_PCT
        return self.write_byte(reg, pct)

    def set_fan_boost(self, enable: bool) -> bool:
        """Enable or disable fan boost via EC."""
        if self.is_unsafe_ec_model or not self.has_ec_access:
            return False
        val = 0x0C if enable else 0x00
        return self.write_byte(REG_FAN_BOOST, val)

    def set_perf_mode(self, mode: str) -> bool:
        """Set performance mode directly via EC."""
        if self.is_unsafe_ec_model or not self.has_ec_access:
            return False
        mode_map = {
            "default": 0x30,
            "auto": 0x30,
            "balanced": 0x30,
            "performance": 0x31,
            "max": 0x31,
            "cool": 0x50,
            "eco": 0x50,
        }
        val = mode_map.get(mode.lower(), 0x30)
        return self.write_byte(REG_PERF_MODE, val)

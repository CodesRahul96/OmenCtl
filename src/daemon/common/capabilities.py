#!/usr/bin/env python3
"""OMEN Command Center for Linux — Model Capability Database.

Derived from OmenCore Hardware capabilities database. Maps HP OMEN and Victus
Board IDs and product names to their specific hardware support profiles, WMI versions,
fan zones, EC safety requirements, and MUX capabilities.
"""

import os
import glob
import logging

logger = logging.getLogger("capabilities")

class ModelCapabilities:
    def __init__(self, product_id, model_name, **kwargs):
        self.product_id = product_id.upper()
        self.model_name = model_name
        self.model_year = kwargs.get("model_year", 2023)
        self.family = kwargs.get("family", "OMEN")
        
        # Fan Control Capabilities
        self.supports_fan_control_wmi = kwargs.get("supports_fan_control_wmi", True)
        self.supports_fan_control_ec = kwargs.get("supports_fan_control_ec", True)
        self.supports_fan_curves = kwargs.get("supports_fan_curves", True)
        self.supports_independent_fan_curves = kwargs.get("supports_independent_fan_curves", True)
        self.supports_rpm_readback = kwargs.get("supports_rpm_readback", True)
        self.fan_zone_count = kwargs.get("fan_zone_count", 2)
        self.max_fan_speed_percent = kwargs.get("max_fan_speed_percent", 100)
        self.min_fan_speed_percent = kwargs.get("min_fan_speed_percent", 0)
        
        # Performance Mode Capabilities
        self.supports_performance_modes = kwargs.get("supports_performance_modes", True)
        self.performance_modes = kwargs.get("performance_modes", ["Default", "Performance", "Cool"])
        self.allow_decoupled_wmi_thermal_policy_fallback = kwargs.get("allow_decoupled_wmi_thermal_policy_fallback", False)
        
        # GPU Capabilities
        self.has_mux_switch = kwargs.get("has_mux_switch", False)
        self.supports_gpu_power_boost = kwargs.get("supports_gpu_power_boost", True)
        self.supports_advanced_optimus = kwargs.get("supports_advanced_optimus", False)
        
        # Lighting Capabilities
        self.has_keyboard_backlight = kwargs.get("has_keyboard_backlight", True)
        self.has_four_zone_rgb = kwargs.get("has_four_zone_rgb", True)
        self.has_per_key_rgb = kwargs.get("has_per_key_rgb", False)
        self.has_light_bar = kwargs.get("has_light_bar", False)
        
        # Power / Undervolt Capabilities
        self.supports_undervolt = kwargs.get("supports_undervolt", True)
        self.supports_tcc_offset = kwargs.get("supports_tcc_offset", True)
        self.supports_power_limits = kwargs.get("supports_power_limits", True)
        self.supports_battery_care = kwargs.get("supports_battery_care", True)

        self.notes = kwargs.get("notes", "")

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "model_name": self.model_name,
            "model_year": self.model_year,
            "family": self.family,
            "supports_fan_control_wmi": self.supports_fan_control_wmi,
            "supports_fan_control_ec": self.supports_fan_control_ec,
            "supports_fan_curves": self.supports_fan_curves,
            "fan_zone_count": self.fan_zone_count,
            "has_mux_switch": self.has_mux_switch,
            "supports_gpu_power_boost": self.supports_gpu_power_boost,
            "supports_battery_care": self.supports_battery_care,
            "supports_undervolt": self.supports_undervolt,
            "supports_tcc_offset": self.supports_tcc_offset,
            "supports_power_limits": self.supports_power_limits,
            "notes": self.notes,
        }


# Global database of known OMEN / Victus boards
KNOWN_MODELS = {
    # OMEN 15 Series (2020-2021)
    "8A14": ModelCapabilities("8A14", "OMEN 15 (2020) Intel", model_year=2020, family="OMEN", has_mux_switch=False, supports_fan_control_ec=True),
    "878C": ModelCapabilities("878C", "OMEN Laptop 15-ek0xxx", model_year=2020, family="OMEN", has_mux_switch=False, supports_fan_control_ec=True, notes="Direct EC fan control highly recommended when hp-wmi fails"),
    "878A": ModelCapabilities("878A", "OMEN 15 (2020) AMD", model_year=2020, family="OMEN", has_mux_switch=False, supports_fan_control_ec=True),
    
    # OMEN 16 Series
    "8BAB": ModelCapabilities("8BAB", "OMEN by HP Gaming Laptop 16-wf0xxx", model_year=2023, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True, supports_fan_control_ec=False, notes="Uses hp-wmi / hwmon routes; direct legacy EC writes are unsafe"),
    "8BAD": ModelCapabilities("8BAD", "OMEN 16 (2023) Intel", model_year=2023, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8CD1": ModelCapabilities("8CD1", "OMEN 16 (2023) AMD", model_year=2023, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8C58": ModelCapabilities("8C58", "OMEN 16 Transcend", model_year=2024, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8D24": ModelCapabilities("8D24", "OMEN 16 (2024)", model_year=2024, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8D26": ModelCapabilities("8D26", "OMEN 16 (2024) AMD", model_year=2024, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8E35": ModelCapabilities("8E35", "OMEN MAX 16t-ah000", model_year=2025, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8E41": ModelCapabilities("8E41", "OMEN MAX 16-ah0xxx", model_year=2025, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8C78": ModelCapabilities("8C78", "OMEN by HP Gaming Laptop 16-wf1xxx", model_year=2024, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),

    # OMEN 17 Series
    "8BB1": ModelCapabilities("8BB1", "OMEN 17 / Victus 15", model_year=2023, family="OMEN/Victus", has_mux_switch=True, supports_fan_control_ec=False),

    # Victus Series
    "88EC": ModelCapabilities("88EC", "Victus by HP 16-e0xxx", model_year=2021, family="Victus", has_mux_switch=False, supports_fan_control_ec=True),
    "8A25": ModelCapabilities("8A25", "Victus by HP 15-fb0xxx", model_year=2022, family="Victus", has_mux_switch=False, supports_fan_control_ec=True),
    "8A97": ModelCapabilities("8A97", "Victus by HP 16-d1xxx", model_year=2022, family="Victus", has_mux_switch=False, supports_fan_control_ec=True),
    "8B19": ModelCapabilities("8B19", "Victus by HP 16-r0xxx", model_year=2023, family="Victus", has_mux_switch=True, supports_fan_control_ec=False),
    "8B1A": ModelCapabilities("8B1A", "Victus by HP 16-s0xxx", model_year=2023, family="Victus", has_mux_switch=True, supports_fan_control_ec=False),
    "8C9C": ModelCapabilities("8C9C", "Victus by HP Gaming Laptop 16-s1xxx", model_year=2024, family="Victus", has_mux_switch=True, supports_fan_control_ec=False),
}

DEFAULT_CAPS = ModelCapabilities("DEFAULT", "Unknown HP System", model_year=2023, family="HP", has_mux_switch=False, supports_fan_control_ec=False, notes="Default capability profile")

def get_board_id():
    """Detect HP Board ID from DMI table."""
    for dmi in ("/sys/class/dmi/id/board_name", "/sys/devices/virtual/dmi/id/board_name"):
        if os.path.exists(dmi):
            try:
                with open(dmi) as f:
                    val = f.read().strip()
                    # Some boards have leading 0x or letters, take the core 4 hex chars if possible
                    val = val.replace("0x", "").upper()
                    return val
            except Exception:
                pass
    return "UNKNOWN"

def get_product_name():
    """Detect HP Product Name from DMI table."""
    for dmi in ("/sys/class/dmi/id/product_name", "/sys/devices/virtual/dmi/id/product_name"):
        if os.path.exists(dmi):
            try:
                with open(dmi) as f:
                    return f.read().strip()
            except Exception:
                pass
    return "HP Laptop"

def detect_capabilities():
    """Discover capabilities based on current board ID and product name."""
    board_id = get_board_id()
    if board_id in KNOWN_MODELS:
        logger.info("Matched board ID %s in capabilities database", board_id)
        return KNOWN_MODELS[board_id]

    # Try matching product name as fallback
    prod = get_product_name().lower()
    for cap in KNOWN_MODELS.values():
        if cap.model_name.lower() in prod:
            logger.info("Matched product name %s in capabilities database", cap.model_name)
            return cap

    logger.warning("Board ID %s not found in database, using default capabilities", board_id)
    return DEFAULT_CAPS

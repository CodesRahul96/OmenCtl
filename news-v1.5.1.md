# 🔧 OmenCtl v1.5.1 — Fan Control Hotfix

### *Fixing Maximum fan mode regression on Omen boards*

This patch release addresses two user-reported issues related to fan control on specific HP Omen/Victus hardware:

---

## 🐛 1. Fix: "Maximum" Fan Mode Broken on Omen Boards (Board 878A and similar)

**Affected boards:** All boards in `omen_thermal_profile_boards[]` where the kernel driver does **not** expose `fan*_target` sysfs files (e.g., Board 878A — HP OMEN Laptop 15-ek0xxx).

**Root cause (3 separate bugs):**

### Bug A — GUI sent unnecessary `SetFanTarget` after `SetFanMode("max")`
The GUI's "Max" button (fan control level 2) previously mapped to `("max", 100)`, meaning it would:
1. Call `SetFanMode("max")` — which correctly wrote `pwm1_enable=0` or used the platform profile fallback
2. **Then** loop through all fans and call `SetFanTarget(fan, max_rpm)` — which on boards **with** `fan_target` support would write to the kernel driver, automatically switching the driver mode from `PWM_MODE_MAX` back to `PWM_MODE_MANUAL`, **undoing the MAX mode!**

On boards **without** `fan_target` support, step 2 simply failed silently, so the MAX mode persisted. But on boards where the custom hp-wmi driver exposes `fan_target`, this was a direct regression.

**Fix:** Changed Max button mapping from `("max", 100)` → `("max", None)`. Now clicking Max **only** calls `SetFanMode("max")` and lets the BIOS/EC handle the actual fan speed ramping. No individual fan target writes are sent.

### Bug B — `_read_mode_fallback()` conflated "performance" power profile with "max" fan mode
When `pwm1_enable` returned `2` (AUTO), the daemon's `_read_current_mode()` would call `_read_mode_fallback()`, which checked the platform profile path. If the power profile was set to `"performance"`, it incorrectly returned `"max"` as the current fan mode.

This caused `set_mode("max")` to hit the early-return check (`if self.get_mode() == mode: return True`) and **skip the actual pwm1_enable write entirely**, since it believed the fan was already in max mode.

**Fix:** Removed `_read_mode_fallback()` entirely. When `pwm1_enable == 2`, the mode is definitively `"auto"`. The "performance" power profile is a separate concept from the "max" fan mode.

### Bug C — `set_mode()` early-return skipped writes based on stale cache
The `set_mode()` method called `self.get_mode()` to check if the requested mode was already active. Since `get_mode()` called `_read_current_mode()` which relied on the buggy fallback, it could return incorrect results, causing legitimate mode change requests to be silently ignored.

**Fix:** Removed the early-return optimization. The daemon now always attempts the `pwm1_enable` write, ensuring the hardware state is always synchronized with the requested mode.

### Bonus — Added "auto" mode platform profile fallback
Previously, only the "max" mode had a fallback chain (writing to `thermal_profile` or `platform_profile` when `pwm1_enable` write failed). Now, the "auto" mode also has a fallback that writes `balanced` to the platform profile paths, ensuring fans return to EC control even on boards where direct PWM control is unsupported.

---

## 🔍 2. Diagnosis: ACPI Errors on Board 8BAB (OMEN 16-wf0xxx)

**Board:** 8BAB — OMEN by HP Gaming Laptop 16-wf0xxx

The kernel logs show ACPI errors:
```
ACPI Error: Aborting method \_SB.WMID.WQBC due to previous error (AE_AML_OPERAND_VALUE)
ACPI Error: Aborting method \_SB.WMID.WQBE due to previous error (AE_AML_OPERAND_VALUE)
ACPI Error: Aborting method \_SB.WMID.WHCM due to previous error (AE_AML_OPERAND_VALUE)
ACPI Error: Aborting method \_SB.WMID.WMAA due to previous error (AE_AML_OPERAND_VALUE)
```

**Diagnosis:** These are **BIOS firmware bugs** — the ACPI tables contain a broken `GETB` helper method (`CreateField` with zero length) that causes certain WMI methods to abort. This is the **same issue** documented for board 8BAC in the kernel driver.

**Impact:** These errors are **cosmetic** and do not affect fan control. The fan speed queries (WMI 0x2D/0x2E) and thermal profile commands (WMI 0x1A) use separate WMI paths that are not affected by the broken GETB helper. The user's debug info confirms this — fan speeds are being read correctly (5000/5300 RPM) and all services are active.

**No code changes needed** for this issue. The errors are a BIOS-level bug that HP would need to address in a BIOS update.

---

## 🔌 3. Decoupling Power and Fan Modes (UX & Reliability Fix)

**Change:** Power profile changes (quiet, balanced, performance) no longer automatically modify or override the user's active fan mode. 

**Why this was done:** Previously, selecting "performance" power profile would automatically force the fan mode to custom/performance, and choosing "balanced" or "saver" would override the fan mode to "auto". This prevented users from running balanced power mode with custom fan speeds, or quiet power mode with high fan speeds.

**How it works now:** The fan mode is completely decoupled from the power profile. Changing the power profile will adjust CPU/GPU power limits (and toggles like cTGP/PPAB) at the hardware level but will **not** touch your fan controller. Your fan mode will stay exactly on what you set (Auto, Custom, or Max) until you change it.

---

## ⚡ 4. Aggressive Performance Fan Curve & Telemetry Governing

### Redesigned Performance Curve
The previous performance curve was too conservative:
`self.performance_points = [(35, 0), (50, 35), (80, 70), (85, 90), (90, 100)]`
At 80°C (which is typical under modern CPU workloads), the fans only spun at **70%**, causing temperatures to rapidly spike to very high levels before reaching full speed.

We redesigned the performance curve to ramp up much more aggressively to keep temperatures low under heavy loads:
- **New Performance Points**: `[(35, 0), (50, 45), (65, 70), (75, 90), (82, 100)]`
- At 50°C, the fans start cooling earlier at **45%** speed.
- At 65°C, fans run at **70%**.
- At 75°C, fans run at **90%**.
- At 82°C and above, fans run at **100%** to keep temperatures safe.

### Dual-Telemetry Temperature Governing
Previously, the active fan curve was solely driven by the CPU temperature. If you were playing a GPU-bound game, the CPU could remain relatively idle (e.g. 55°C) while the GPU was running extremely hot (e.g. 80°C). Since the curve only looked at CPU temperature, the fans would stay very quiet, causing the GPU to overheat.

We have updated the telemetry history to collect `max(cpu_temp, gpu_temp)`. Now, the fan curves (both custom and performance) will react to the **hottest component in the system**, ensuring absolute safety and optimal cooling regardless of whether the load is CPU-intensive or GPU-intensive.

## 📦 5. D-Bus Policy Permissions & Service Startup Reliability (setup.sh)

**Changes & Improvements:**
1. **D-Bus Config Hot-Reload**: We added an automatic `systemctl reload dbus` call right after copying the service policy configurations. This ensures that new D-Bus permissions are immediately active during installation or update, avoiding AccessDenied/policy errors without requiring a system reboot.
2. **Secure Permissions & Ownership**: The installer now explicitly applies secure `644` file permissions and `root:root` ownership to all D-Bus configurations and systemd service files.
3. **Correct Boot Ordering (`systemd-logind.service`)**: To address race conditions during startup, we updated all five systemd microservice configuration templates (`data/hpm-*.service`) to boot `After` and `Require` `systemd-logind.service`.
4. **Startup Jitter Delay (`ExecStartPre=/bin/sleep 2`)**: Added a 2-second sleep delay before service launch to guarantee that the `hwmon` driver directory in `/sys` has fully initialized, avoiding early startup telemetry crashes.
5. **Real-time Installation Verification**: Added a post-installation service status validation loop in `setup.sh` that checks if each microservice starts successfully using `systemctl is-active`. If a service fails to initialize, it immediately warns the user and provides the exact `journalctl` command to troubleshoot.

---

## ⚡ 6. Technical Note: NVIDIA Laptop GPU Power Limits (115W vs 140W)

**Explanation:**
Some users noted that their laptop GPU (e.g. RTX 5070 Ti / 4070 Laptop) has a specified maximum power cap of **140W**, but `nvidia-smi` or OmenCtl shows it at **115W** (fluctuating up to 140W for the first few minutes and then settling at 115W when idle).

This is **fully expected and correct hardware behavior** under Linux:
1. **Base TGP (115W)**: The physical base power budget of the GPU is 115W.
2. **Dynamic Boost (cTGP/PPAB, +25W = 140W)**: The additional 25W is dynamically allocated using NVIDIA Dynamic Boost 2.0.
3. **Behavior**: Under Linux, the `nvidia-powerd` system daemon monitors active CPU and GPU loads.
   - When **idle or under light load**, `nvidia-powerd` (or the driver itself) automatically locks the power limit to the base **115W** to conserve energy and keep temperatures low.
   - When a **heavy 3D workload/game** is launched, the dynamic boost rails (PPAB/cTGP) are immediately engaged, boosting the power cap dynamically up to the maximum **140W**.
   - If a manual query is sent via terminal when the system is idle, it will register 115W, but under full load, it will scale perfectly up to 140W.

---

## 📊 Summary of Changes

| File | Change |
| :--- | :--- |
| `src/daemon/services/fan_service.py` | Removed buggy `_read_mode_fallback()` that conflated "performance" profile with "max" fan mode |
| `src/daemon/services/fan_service.py` | Removed `set_mode()` early-return optimization that skipped writes based on stale/incorrect mode detection |
| `src/daemon/services/fan_service.py` | Added platform profile fallback for "auto" mode (writes `balanced` to thermal/platform profile when `pwm1_enable=2` write fails) |
| `src/daemon/services/fan_service.py` | Improved logging: added debug/info messages for fallback paths, failure warnings, and fan target operations |
| `src/gui/pages/fan_page.py` | Fixed Max button: changed from `("max", 100)` to `("max", None)` — Max mode now only calls `SetFanMode("max")` without sending `SetFanTarget` writes |
| `src/gui/pages/fan_page.py` | Decoupled fan and power modes: removed fan mode sync logic from power profile toggles |
| `src/gui/pages/fan_page.py` | Simplified `_power_mode_confirmed` to only check power profiles and ignore fan profiles |
| `src/gui/pages/fan_page.py` | Optimized `performance_points` to ramp up much faster, ensuring better thermal management under load |
| `src/gui/pages/fan_page.py` | Changed fan curve temperature driver in `_refresh` to use `max(cpu_temp, gpu_temp)` instead of only CPU temperature |
| `data/hpm-*.service` | Updated all five services to require `systemd-logind.service` and added `ExecStartPre=/bin/sleep 2` for startup reliability |
| `setup.sh` | Integrated secure `chmod 644` permissions, D-Bus dynamic reloading, post-install validation checks, and automatic status reporting |

---

*Thank you to the issue reporters for their detailed technical analysis — it made diagnosing these bugs significantly easier! 🙏*



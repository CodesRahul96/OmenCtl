# OmenCtl v1.5.3 Update Log

A comprehensive roadmap and set of fixes were implemented for the upcoming v1.5.3 release to address the issues reported:

## 1. Autostart & Background Tray Icon 🚀
*   **Added `--hidden` CLI flag**: Implemented in `src/omen-cli.py` and `src/gui/main_window.py`. When launched with `--hidden`, the GTK window is initialized but not presented to the user, allowing it to act purely as a background process.
*   **System Tray Icon (`pystray`)**: Integrated a system tray icon that runs in its own background thread. The tray icon allows users to show the GUI or completely Quit the app.
*   **Autostart Toggle**: Added a new "Autostart on login" toggle in the Settings page (`src/gui/pages/settings_page.py`). This creates `~/.config/autostart/omenctl-bg.desktop` executing `omenctl --hidden` when the user logs in.

## 2. Fan Control Plan Persistence 💾
*   **D-Bus Service Support**: Updated `src/daemon/services/fan_service.py` with a new `SaveCustomCurve` D-Bus method. This allows the background daemon to natively store the customized JSON fan curve array to `/etc/hp-manager/fan.json` using `ServiceConfig`.
*   **UI Integration**: Modified `src/gui/pages/fan_page.py` to check for and load `custom_curve` from the `fan_info` dictionary upon application startup. When the user clicks Apply on their fan curve, it now synchronously sends the array to the daemon for safe keeping instead of being wiped out upon restart.

## 3. "Fan control unavailable" Stability & D-Bus Quota Flooding 🛡️
*   **D-Bus Flooding Fix**: Found the root cause of the system D-Bus quota being maxed out. In `fan_page.py`, the `_apply_fan_curve` debounced background task was unconditionally calling `_set_daemon_fan_mode("custom")` over D-Bus every 1 second (1000ms timer loop). When the hardware hwmon paths became inaccessible ("unavailable" state), the daemon's mode setter would block or retry platform profile fallbacks continuously, choking the bus.
*   **Safety Checks**: Added early-exit checks. `_apply_fan_curve` now verifies `fan_info.get("available")` and compares `fan_info.get("mode") != "custom"` before ever attempting to fire the `SetFanMode` command, entirely preventing the D-Bus flood.

## 4. Victus 15 8A3D Compatibility 💻
*   **Board ID Map**: Added DMI board match `8A3D` into `victus_s_thermal_profile_boards` in `driver/hp-wmi.c`. This officially restores Fan/Thermal profile hwmon visibility to the Victus 15-fb0xxx hardware.

## 5. Keyboard RGB DKMS Build Fix 🛠️
*   **Compile Error Patch**: The `modpost` dependency error (`"hp_wmi_mutex" undefined!`) was tracked down to a DKMS caching issue. `driver/setup.sh` was running `dkms remove` *before* the new source code files (which had removed the mutex dependency) were copied into `/usr/src/`.
*   **Logic Re-ordered**: Re-arranged `driver/setup.sh` to purge old `.ko` files and overwrite the `/usr/src/hp-rgb-lighting-1.0` files *first*, before triggering `dkms remove` and `dkms add`. This ensures `make` compiles the correct, independent source.

Please deploy these changes and run `sudo ./driver/setup.sh install` and `sudo ./setup.sh install` on your Linux machine to test the fixes.

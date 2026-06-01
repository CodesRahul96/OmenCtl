# Changelog

## v1.5.2
- **Kernel Compatibility**: Upstreamed Linux 7.1 kernel `hp-wmi` patches (Added support for new board IDs like 8C58, 8902, 8A44, 8BC2, 8C77, 8D41 and updated fan struct mappings).
- **RGB Driver Fixes (`hp-rgb-lighting`)**:
  - Fixed a critical WMI Mutex race condition by integrating and sharing the global `hp_wmi_mutex` from the main `hp-wmi` driver.
  - Added support for space-separated decimal RGB input (e.g. "255 0 0") in the sysfs node `zone_store` function.
  - Added detailed kernel error logging (`pr_warn`) for WMI `GET` and `SET` query failures.
- **UI & UX Enhancements**: 
  - Fixed an issue where the "Lighting" and "Dark/Light Theme" toggle icons were invisible on some light desktop themes (e.g. Pop!_OS) by migrating to widely supported standard GTK symbolic icons (`lightbulb-symbolic` and `weather-clear-night-symbolic`).
- **Cleanup**: 
  - Removed outdated news files.

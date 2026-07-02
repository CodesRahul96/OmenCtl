#!/usr/bin/env python3
"""OMEN Command Center for Linux — Standalone Tray Icon Process.

Runs in a separate process to prevent GTK3 (AppIndicator) and GTK4 mainloop conflicts.
"""

import os
import sys
import subprocess
import time
try:
    from PIL import Image
    import pystray
except ImportError as e:
    print(f"Required dependency missing ({e}). Tray icon unavailable.")
    sys.exit(0)

def on_open(icon, item):
    subprocess.Popen(["omenctl"])

def on_quit(icon, item):
    icon.stop()
    subprocess.Popen(["omenctl", "--quit"])

def main():
    icon_path = "/usr/share/icons/hicolor/48x48/apps/omenctl.png"
    if not os.path.exists(icon_path):
        icon_path = "/usr/share/hp-manager/images/omenctl.png"
    
    if os.path.exists(icon_path):
        image = Image.open(icon_path)
    else:
        image = Image.new('RGB', (64, 64), color=(15, 15, 15))

    menu = pystray.Menu(
        pystray.MenuItem("Open OmenCtl", on_open, default=True),
        pystray.MenuItem("Quit", on_quit)
    )

    icon = pystray.Icon("omenctl", image, "OmenCtl", menu)
    
    # Robust retry loop for early login autostart when tray DBus isn't ready yet
    for attempt in range(12):
        try:
            icon.run()
            break
        except Exception as e:
            print(f"pystray run failed (attempt {attempt+1}): {e}. Retrying in 3 seconds...")
            time.sleep(3)

if __name__ == "__main__":
    main()

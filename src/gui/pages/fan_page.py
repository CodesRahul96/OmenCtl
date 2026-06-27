#!/usr/bin/env python3
"""
OMEN Gaming Hub Style Consolidated Master Dashboard Redesign
Extremely high-fidelity Cairo drawings that strictly replicate the official 
OMEN Gaming Hub interface, featuring mechanical brackets, speedometer radial ticks,
rounded segmented button tabs, thin flat sliders, and organic connected widgets.
Customizable spacing, enlarged gauges, real-time sensor panel, and Feral GameMode diagnostics.
Features ovalized cards and cTGP, PPAB, and GameMode toggle switches.
"""
import os, json, subprocess, shutil, glob, threading, time, concurrent.futures, math
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, GObject
from widgets.smooth_scroll import SmoothScrolledWindow
from widgets.fan_curve import FanCurveWidget
import cairo

DEFAULT_MODE_SYNC_DELAY_MS = 1500
CUSTOM_MODE_SYNC_DELAY_MS = 3000
_DBUS_TIMEOUT = 5
_dbus_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="dbus")

def T(k):
    from i18n import T as _T
    return _T(k)

def _dbus_call(fn, *args, timeout=_DBUS_TIMEOUT):
    """Run a D-Bus proxy call with a timeout to avoid indefinite blocking."""
    fut = _dbus_pool.submit(fn, *args)
    try:
        return fut.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        print(f"⚠ D-Bus call timed out after {timeout}s: {fn}")
        return None
    except Exception as e:
        print(f"⚠ D-Bus call failed: {e}")
        return None

def hsv_to_rgb(h, s, v):
    """Convert HSV to RGB for the color wheel."""
    c = v * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = v - c
    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (r + m, g + m, b + m)

# ═════════════════════════════════════════════════════════════════════════════
#  HIGH-FIDELITY CAIRO INSTRUMENT PANELS
# ═════════════════════════════════════════════════════════════════════════════

class OmenHighTechGauge(Gtk.DrawingArea):
    """Circular gauge replicating the OMEN speedometer design, scaled up."""

    def __init__(self, label="CPU", is_left=True, active_color=(0.66, 0.33, 0.97)):
        super().__init__()
        self.label = label
        self.is_left = is_left  # True for Left Gauge (CPU), False for Right (GPU)
        self.active_color = active_color
        
        self.usage = 0.0
        self.temp = 0.0
        self.speed = "0.00GHz"
        self.rpm = 0
        self.rotation = 0.0
        self.is_dark = True
        
        self.set_size_request(260, 260)
        self.set_draw_func(self._draw)

    def set_dark(self, is_dark):
        self.is_dark = is_dark
        self.queue_draw()

    def set_val(self, usage, temp, speed, rpm):
        self.usage = float(usage)
        self.temp = float(temp)
        self.speed = str(speed)
        self.rpm = int(rpm)
        self.queue_draw()

    def tick_rotation(self):
        if self.rpm > 0:
            speed = 0.03 + (self.rpm / 6000.0) * 0.15
            self.rotation += speed
            if self.rotation >= 2 * math.pi:
                self.rotation -= 2 * math.pi
            self.queue_draw()

    def _draw(self, _, cr, w, h):
        cx, cy = w / 2, h / 2 - 12
        r_main = 94
        r_tick_out = 85
        r_tick_in = 75
        
        # ── 1. Outer Temperature Arc & Ticks (Thicker and Offset) ──
        cr.set_line_width(5.5) # Even thicker temperature curves as requested
        
        if self.is_left:
            # CPU Temp Arc: Top-Left from 125° to 215°
            start_angle = 125 * math.pi / 180
            end_angle = 215 * math.pi / 180
            temp_pct = max(0.0, min(100.0, self.temp)) / 100.0
            fill_angle = start_angle + temp_pct * (end_angle - start_angle)
            
            # Base track
            if self.is_dark:
                cr.set_source_rgba(255, 255, 255, 0.05)
            else:
                cr.set_source_rgba(0, 0, 0, 0.06)
            cr.arc(cx, cy, r_main + 16, start_angle, end_angle)
            cr.stroke()
            
            # Dynamic color coding based on temp threshold
            if self.temp >= 80.0:
                arc_color = (0.94, 0.23, 0.23) # Red / Hot
            elif self.temp >= 68.0:
                arc_color = (0.96, 0.62, 0.15) # Amber / Warm
            else:
                arc_color = self.active_color

            # Fill track
            cr.set_source_rgba(*arc_color, 0.85)
            cr.arc(cx, cy, r_main + 16, start_angle, fill_angle)
            cr.stroke()
            
            # Label temperature e.g. "51°C" bold, italic, and exactly ON TOP of the curve
            cr.select_font_face("Sans", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(18)
            cr.set_source_rgba(*arc_color, 0.95)
            cr.move_to(cx - 100, cy - 76) # Slightly larger label for clearer visibility
            cr.show_text(f"{int(self.temp)}°C")
        else:
            # GPU Temp Arc: Top-Right from 325° to 415°
            start_angle = 325 * math.pi / 180
            end_angle = 415 * math.pi / 180
            temp_pct = max(0.0, min(100.0, self.temp)) / 100.0
            fill_angle = start_angle + temp_pct * (end_angle - start_angle)
            
            # Base track
            if self.is_dark:
                cr.set_source_rgba(255, 255, 255, 0.05)
            else:
                cr.set_source_rgba(0, 0, 0, 0.06)
            cr.arc(cx, cy, r_main + 16, start_angle, end_angle)
            cr.stroke()
            
            # Dynamic color coding based on temp threshold
            if self.temp >= 80.0:
                arc_color = (0.94, 0.23, 0.23) # Red / Hot
            elif self.temp >= 68.0:
                arc_color = (0.96, 0.62, 0.15) # Amber / Warm
            else:
                arc_color = self.active_color

            # Fill track
            cr.set_source_rgba(*arc_color, 0.85)
            cr.arc(cx, cy, r_main + 16, start_angle, fill_angle)
            cr.stroke()
            
            # Label temperature e.g. "0°C" bold, italic, and exactly ON TOP of the curve
            cr.select_font_face("Sans", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(18)
            cr.set_source_rgba(*arc_color, 0.95)
            cr.move_to(cx + 62, cy - 76) # Slightly larger label for clearer visibility
            cr.show_text(f"{int(self.temp)}°C")

        # ── 2. Speedometer Radial Ticks (Thicker) ──
        num_ticks = 72
        angle_step = 2 * math.pi / num_ticks
        
        for i in range(num_ticks):
            angle = -math.pi / 2 + i * angle_step
            is_active = (i / num_ticks) <= (self.usage / 100.0)
            
            cr.save()
            if is_active:
                cr.set_source_rgba(self.active_color[0], self.active_color[1], self.active_color[2], 0.9)
                cr.set_line_width(4.5) # Even thicker active ticks as requested
            else:
                if self.is_dark:
                    cr.set_source_rgba(255, 255, 255, 0.06)
                else:
                    cr.set_source_rgba(0, 0, 0, 0.08)
                cr.set_line_width(2.4) # Even thicker inactive ticks as requested
                
            x_in = cx + r_tick_in * math.cos(angle)
            y_in = cy + r_tick_in * math.sin(angle)
            x_out = cx + r_tick_out * math.cos(angle)
            y_out = cy + r_tick_out * math.sin(angle)
            
            cr.move_to(x_in, y_in)
            cr.line_to(x_out, y_out)
            cr.stroke()
            cr.restore()

        # Outer thick frame boundary line (Thicker)
        cr.set_line_width(3.0) # Even thicker boundary line as requested
        if self.is_dark:
            cr.set_source_rgba(255, 255, 255, 0.04)
        else:
            cr.set_source_rgba(0, 0, 0, 0.05)
        cr.arc(cx, cy, r_main, 0, 2 * math.pi)
        cr.stroke()

        # ── 3. Central Details ──
        # Label (CPU / GPU) - Italic and Bold using Sans and a forced shear slant matrix
        cr.save()
        cr.select_font_face("Sans", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(14)
        cr.set_source_rgba(self.active_color[0], self.active_color[1], self.active_color[2], 0.85)
        
        # Mathematically shear/slant font matrix to guarantee beautiful italic slant on all systems
        font_matrix = cr.get_font_matrix()
        font_matrix.xy = -0.25 * font_matrix.xx
        cr.set_font_matrix(font_matrix)
        
        te = cr.text_extents(self.label)
        cr.move_to(cx - te.width / 2, cy - r_tick_in * 0.35)
        cr.show_text(self.label)
        cr.restore()
        
        # Usage Value
        val_txt = f"{int(self.usage)}%"
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(32)
        if self.is_dark:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
        else:
            cr.set_source_rgba(0.09, 0.11, 0.16, 0.95)
        te = cr.text_extents(val_txt)
        cr.move_to(cx - te.width / 2, cy + te.height / 2 - 3)
        cr.show_text(val_txt)
        
        # Clock Speed
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        if self.is_dark:
            cr.set_source_rgba(0.55, 0.60, 0.68, 0.7)
        else:
            cr.set_source_rgba(0.27, 0.33, 0.41, 0.8)
        te = cr.text_extents(self.speed)
        cr.move_to(cx - te.width / 2, cy + r_tick_in * 0.52)
        cr.show_text(self.speed)

        # ── 4. Fan Speed RPM text centered under dial (whiter, larger, italic, and bold) ──
        cr.select_font_face("Inter", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        if self.is_dark:
            cr.set_source_rgba(0.9, 0.94, 1.0, 0.95)
        else:
            cr.set_source_rgba(0.1, 0.11, 0.15, 0.95)
        rpm_txt = f"{self.rpm} RPM"
        te = cr.text_extents(rpm_txt)
        cr.move_to(cx - te.width / 2, cy + r_main + 26)
        cr.show_text(rpm_txt)


class OmenSpecsBridge(Gtk.DrawingArea):
    """Compact bridging bar for RAM, Disk, and Battery metrics."""

    def __init__(self, size_w=160, size_h=52, color=(0.24, 0.60, 1.0)):
        super().__init__()
        self.set_size_request(size_w, size_h)
        self.pct = 0.0
        self.text = ""
        self.color = color
        self.is_dark = True
        self.set_draw_func(self._draw)

    def set_dark(self, is_dark):
        self.is_dark = is_dark
        self.queue_draw()

    def set_val(self, pct, text):
        self.pct = float(pct)
        self.text = str(text)
        self.queue_draw()

    def _draw(self, _, cr, w, h):
        cx, cy = w / 2, h / 2
        bar_w = w * 0.90
        bar_h = 6
        bar_x = cx - bar_w / 2
        
        # ── 1. Thin Translucent Bridge line ──
        cr.set_line_width(1.0)
        if self.is_dark:
            cr.set_source_rgba(255, 255, 255, 0.03)
        else:
            cr.set_source_rgba(0, 0, 0, 0.04)
        cr.move_to(0, cy)
        cr.line_to(w, cy)
        cr.stroke()
        
        # ── 2. Background Capsule Tube ──
        if self.is_dark:
            cr.set_source_rgba(22, 25, 30, 0.95)
        else:
            cr.set_source_rgba(0, 0, 0, 0.06)
        cr.set_line_width(bar_h)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(bar_x, cy)
        cr.line_to(bar_x + bar_w, cy)
        cr.stroke()
        
        # Outer border
        if self.is_dark:
            cr.set_source_rgba(255, 255, 255, 0.08)
        else:
            cr.set_source_rgba(0, 0, 0, 0.04)
        cr.set_line_width(bar_h + 1.2)
        cr.move_to(bar_x, cy)
        cr.line_to(bar_x + bar_w, cy)
        cr.stroke()

        # ── 3. Glowing Fill ──
        fill_w = bar_w * (max(0.0, min(100.0, self.pct)) / 100.0)
        if fill_w > 0:
            cr.set_source_rgba(self.color[0], self.color[1], self.color[2], 0.95)
            cr.set_line_width(bar_h)
            cr.move_to(bar_x, cy)
            cr.line_to(bar_x + fill_w, cy)
            cr.stroke()
            
            # Subtle radial shadow/glow
            cr.set_source_rgba(self.color[0], self.color[1], self.color[2], 0.22)
            cr.set_line_width(bar_h + 3)
            cr.move_to(bar_x, cy)
            cr.line_to(bar_x + fill_w, cy)
            cr.stroke()
            
        # ── 4. Small Pointer Indicator Triangle on top ──
        px = bar_x + fill_w
        py = cy - bar_h / 2 - 3
        if self.is_dark:
            cr.set_source_rgb(1.0, 1.0, 1.0)
        else:
            cr.set_source_rgb(self.color[0], self.color[1], self.color[2])
        cr.move_to(px, py)
        cr.line_to(px - 3, py - 4)
        cr.line_to(px + 3, py - 4)
        cr.close_path()
        cr.fill()
        
        # ── 5. Details Text under the bar ──
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        if self.is_dark:
            cr.set_source_rgba(0.82, 0.86, 0.92, 0.8)
        else:
            cr.set_source_rgba(0.2, 0.25, 0.33, 0.85)
        te = cr.text_extents(self.text)
        cr.move_to(cx - te.width / 2, cy + bar_h + 14)
        cr.show_text(self.text)

# ═════════════════════════════════════════════════════════════════════════════
#  SYSTEM MONITOR DATA WORKER
# ═════════════════════════════════════════════════════════════════════════════

class SystemMonitor(threading.Thread):
    def __init__(self, services_provider):
        super().__init__(daemon=True)
        self.services_provider = services_provider
        self.running = True
        self._active_event = threading.Event()
        self._active_event.set()
        self.lock = threading.Lock()
        self.data = {
            "cpu_temp": 0.0,
            "gpu_temp": 0.0,
            "cpu_pct": 0.0,
            "gpu_pct": 0.0,
            "cpu_freq": "0.00GHz",
            "gpu_freq": "0.00GHz",
            "ram_pct": 0.0,
            "ram_text": "RAM 0% 0.0GB",
            "disk_pct": 0.0,
            "disk_text": "DISK 0% 0.0GB",
            "bat_pct": 0.0,
            "bat_text": "BAT 0%",
            "fan_info": {},
            "power_profile": {},
            "rgb_state": {},
            "power_conflict": None,
            "gamemode": "Inactive",
            "all_sensors": [],
            "gpu_tgp_state": False,
            "gpu_ppab_state": False,
        }
        self._conflict_cache = None
        self._conflict_counter = 0
        self._nvidia_smi = shutil.which("nvidia-smi") or ""

    def set_active(self, active):
        if active:
            self._active_event.set()
        else:
            self._active_event.clear()

    def run(self):
        while self.running:
            if not self._active_event.is_set():
                time.sleep(4.0)
                continue

            c, g = 0.0, 0.0
            fi, pp, si, rg = {}, {}, {}, {}
            services = self.services_provider()

            # D-Bus reads
            if services:
                platform_svc = services.get("platform")
                fan_svc = services.get("fan")
                power_svc = services.get("power")
                rgb_svc = services.get("rgb")

                if platform_svc:
                    try:
                        raw = _dbus_call(platform_svc.GetSystemInfo)
                        if raw is not None:
                            si = json.loads(raw)
                            c = si.get("cpu_temp", 0.0)
                            g = si.get("gpu_temp", 0.0)
                    except Exception: pass

                if fan_svc:
                    try:
                        raw = _dbus_call(fan_svc.GetFanInfo)
                        if raw is not None:
                            fi = json.loads(raw)
                    except Exception: pass

                if power_svc:
                    try:
                        raw = _dbus_call(power_svc.GetPowerProfile)
                        if raw is not None:
                            pp = json.loads(raw)
                    except Exception: pass

                if rgb_svc:
                    try:
                        raw = _dbus_call(rgb_svc.GetState)
                        if raw is not None:
                            rg = json.loads(raw)
                    except Exception: pass

            # CPU / GPU Utilization and speeds
            cpu_pct = 0.0
            try:
                with open("/proc/stat") as f:
                    cpu = f.readline().strip().split()
                vals = [int(x) for x in cpu[1:9]]
                idle_all = vals[3] + vals[4]
                total = sum(vals)
                cpu_pct = max(0.0, min(100.0, (1.0 - (idle_all / total)) * 100.0))
            except Exception: pass

            cpu_freq = "3.20GHz"
            try:
                with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") as f:
                    val = int(f.read().strip())
                    cpu_freq = f"{val / 1000000:.2f}GHz"
            except Exception:
                try:
                    with open("/proc/cpuinfo") as f:
                        for line in f:
                            if line.startswith("cpu MHz"):
                                cpu_freq = f"{float(line.split(':')[1].strip()) / 1000:.2f}GHz"
                                break
                except Exception: pass

            gpu_pct = 0.0
            gpu_freq = "0.00GHz"
            if self._nvidia_smi:
                try:
                    out_pct = subprocess.check_output(
                        [self._nvidia_smi, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                        stderr=subprocess.DEVNULL, timeout=1.5
                    ).decode().strip()
                    if out_pct:
                        gpu_pct = float(out_pct.splitlines()[0])

                    out_freq = subprocess.check_output(
                        [self._nvidia_smi, "--query-gpu=clocks.gr", "--format=csv,noheader,nounits"],
                        stderr=subprocess.DEVNULL, timeout=1.5
                    ).decode().strip()
                    if out_freq:
                        gpu_freq = f"{float(out_freq.splitlines()[0]) / 1000:.2f}GHz"
                except Exception: pass

            # RAM percentage and text
            ram_pct = 0.0
            ram_text = "RAM 0% 0.0GB"
            try:
                mem = {}
                with open("/proc/meminfo") as f:
                    for line in f:
                        k, v = line.split(":", 1)
                        mem[k.strip()] = int(v.split()[0])
                mt = mem.get("MemTotal", 1)
                ma = mem.get("MemAvailable", mt)
                used = mt - ma
                ram_pct = (used / mt) * 100
                used_gb = used / (1024 * 1024)
                total_gb = mt / (1024 * 1024)
                ram_text = f"RAM {int(ram_pct)}% {used_gb:.1f}GB / {total_gb:.0f}GB"
            except Exception: pass

            # Disk percentage and text
            disk_pct = 0.0
            disk_text = "DISK 0% 0.0GB"
            try:
                total, used, free = shutil.disk_usage("/")
                if total > 0:
                    disk_pct = (used / total) * 100
                used_gb = used / (1024 ** 3)
                total_gb = total / (1024 ** 3)
                disk_text = f"DISK {int(disk_pct)}% {used_gb:.1f}GB / {total_gb:.0f}GB"
            except Exception: pass

            # Battery percentage and text
            bat_pct = 0.0
            bat_text = "BAT N/A"
            try:
                lang_is_tr = T("fan") == "Performans" or "tr" in os.getenv("LANG", "").lower()
                bat_paths = glob.glob("/sys/class/power_supply/BAT*")
                if bat_paths:
                    bp = bat_paths[0]
                    cap_p = f"{bp}/capacity"
                    status_p = f"{bp}/status"
                    
                    pct = 100
                    if os.path.exists(cap_p):
                        with open(cap_p) as f:
                            pct = int(f.read().strip())
                    
                    status = "Unknown"
                    if os.path.exists(status_p):
                        with open(status_p) as f:
                            status = f.read().strip()
                    
                    bat_pct = float(pct)
                    
                    status_tr = {
                        "Charging": "Şarj Oluyor" if lang_is_tr else "Charging",
                        "Discharging": "Deşarj Oluyor" if lang_is_tr else "Discharging",
                        "Full": "Dolu" if lang_is_tr else "Full",
                        "Not charging": "Şarj Olmuyor" if lang_is_tr else "Not Charging",
                    }
                    stat_lbl = status_tr.get(status, status)
                    bat_text = f"BAT {int(pct)}% ({stat_lbl})"
                else:
                    bat_pct = 100.0
                    bat_text = "BAT 100% (AC)"
            except Exception: pass

            # Feral GameMode Query
            gamemode = "Inactive"
            if shutil.which("gamemoded"):
                try:
                    res = subprocess.run(["gamemoded", "-s"], capture_output=True, text=True, timeout=1.0)
                    out = res.stdout.lower()
                    if "active" in out:
                        gamemode = "Active"
                except Exception: pass

            # Query all real-time sensor diagnostics
            sensors = self._get_all_sensors()

            # Query physical hp-wmi cTGP & PPAB states
            gpu_tgp_state = False
            gpu_ppab_state = False
            try:
                for base in ("/sys/devices/platform/hp-wmi", "/sys/devices/platform/hp-omen"):
                    tgp_p = f"{base}/gpu_tgp"
                    ppab_p = f"{base}/gpu_ppab"
                    if os.path.exists(tgp_p):
                        with open(tgp_p) as f:
                            gpu_tgp_state = f.read().strip() == "1"
                    if os.path.exists(ppab_p):
                        with open(ppab_p) as f:
                            gpu_ppab_state = f.read().strip() == "1"
            except Exception: pass

            # Fallbacks for temperatures
            if not c:
                try:
                    for path in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
                        with open(path) as f:
                            c = int(f.read().strip()) / 1000
                            break
                except Exception: c = 42.0
            if not g: g = 0.0

            # Conflict checking
            self._conflict_counter += 1
            if self._conflict_counter >= 8:
                self._conflict_counter = 0
                self._conflict_cache = None
                for tool in ("tlp", "auto-cpufreq"):
                    try:
                        res = subprocess.run(["systemctl", "is-active", f"{tool}.service"],
                                             capture_output=True, text=True, timeout=1.5)
                        if res.stdout.strip() == "active":
                            self._conflict_cache = tool
                            break
                    except Exception: pass

            with self.lock:
                self.data["cpu_temp"] = c
                self.data["gpu_temp"] = g
                self.data["cpu_pct"] = cpu_pct
                self.data["gpu_pct"] = gpu_pct
                self.data["cpu_freq"] = cpu_freq
                self.data["gpu_freq"] = gpu_freq
                self.data["ram_pct"] = ram_pct
                self.data["ram_text"] = ram_text
                self.data["disk_pct"] = disk_pct
                self.data["disk_text"] = disk_text
                self.data["bat_pct"] = bat_pct
                self.data["bat_text"] = bat_text
                self.data["fan_info"] = fi
                self.data["power_profile"] = pp
                self.data["rgb_state"] = rg
                self.data["power_conflict"] = self._conflict_cache
                self.data["gamemode"] = gamemode
                self.data["all_sensors"] = sensors
                self.data["gpu_tgp_state"] = gpu_tgp_state
                self.data["gpu_ppab_state"] = gpu_ppab_state

            time.sleep(2.0)

    def _get_all_sensors(self):
        sensors = []
        try:
            for d in sorted(os.listdir("/sys/class/hwmon")):
                path = os.path.join("/sys/class/hwmon", d)
                name = "unknown"
                try:
                    with open(os.path.join(path, "name")) as f:
                        name = f.read().strip()
                except Exception: continue

                for tf in sorted(glob.glob(os.path.join(path, "temp*_input"))):
                    try:
                        with open(tf) as f:
                            temp = int(f.read().strip()) / 1000
                        label_file = tf.replace("_input", "_label")
                        try:
                            with open(label_file) as f:
                                label = f.read().strip()
                        except Exception:
                            label = os.path.basename(tf).replace("_input", "")
                        
                        if label.lower() == "package id 0":
                            label = "CPU Package"
                        elif label.lower().startswith("core "):
                            try:
                                core_num = int(label.split()[1])
                                label = f"Core {core_num + 1}"
                            except ValueError: pass
                        elif label.lower() == "tctl":
                            label = "CPU (tctl)"
                        elif label.lower() == "tdie":
                            label = "CPU (tdie)"
                            
                        sensors.append({"driver": name, "label": label, "temp": temp})
                    except Exception: pass
        except Exception: pass
        return sensors

    def get_data(self):
        with self.lock:
            return self.data.copy()

    def stop(self):
        self.running = False
        self._active_event.set()

# ═════════════════════════════════════════════════════════════════════════════
#  PERFORMANCE & FAN PAGE MAIN COMPONENT
# ═════════════════════════════════════════════════════════════════════════════

class FanPage(Gtk.Box):
    def __init__(self, service=None, on_profile_change=None):
        super().__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        
        self.service = service  # fan service D-Bus proxy
        self._platform_svc = None
        self._power_svc = None
        self._rgb_svc = None
        self.on_profile_change = on_profile_change
        
        self.active_mode = "balanced"  # quiet, balanced, performance, custom
        self.temp_unit = "C"
        self.temp_history = []
        self.last_applied_rpm = {}
        self._block_sync = False
        self._pending_power_mode = None
        self._pending_power_started = 0.0
        self._sensor_labels = {}
        self.is_dark = True
        self.fan_control_level = 1
        self.fan_control_mode = "performance"
        self.fan_curve_editor_open = False

        self._css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )
        self._update_theme_css(self.is_dark)

        # Monitor Thread
        self.monitor = SystemMonitor(lambda: {
            "fan": self.service,
            "platform": self._platform_svc,
            "power": self._power_svc,
            "rgb": self._rgb_svc,
        })
        self.monitor.start()

        self._build_ui()
        self._timer = None
        self._anim_timer = None
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)

    def _update_theme_css(self, is_dark):
        if is_dark:
            capsule_bg = "rgba(14, 12, 20, 0.85)"
            capsule_border = "rgba(168, 85, 247, 0.16)"
            btn_color = "#8890a0"
            btn_hover_color = "#ffffff"
            btn_hover_bg = "rgba(255, 255, 255, 0.02)"
            btn_checked_bg = "linear-gradient(135deg, rgba(168, 85, 247, 0.35), rgba(236, 72, 153, 0.2))"
            btn_checked_border = "rgba(168, 85, 247, 0.45)"
            btn_checked_shadow = "inset 0 0 8px rgba(168, 85, 247, 0.2), 0 0 12px rgba(168, 85, 247, 0.3)"
            card_bg = "rgba(18, 16, 24, 0.72)"
            card_border = "rgba(168, 85, 247, 0.08)"
            card_shadow = "none"
            card_title_color = "#a0aec0"
            sep_color = "rgba(255, 255, 255, 0.06)"
            slider_bg = "#4a5568"
            bad_active_bg = "rgba(236, 72, 153, 0.12)"
            bad_active_border = "rgba(236, 72, 153, 0.3)"
            bad_inactive_bg = "rgba(255, 255, 255, 0.03)"
            bad_inactive_border = "rgba(255, 255, 255, 0.08)"
            act_btn_bg = "rgba(255, 255, 255, 0.04)"
            act_btn_border = "rgba(255, 255, 255, 0.1)"
            act_btn_color = "#ffffff"
            act_btn_hover_bg = "rgba(255, 255, 255, 0.08)"
            sensor_row_border = "rgba(255, 255, 255, 0.02)"
            chip_bg = "rgba(255, 255, 255, 0.03)"
            chip_border = "rgba(255, 255, 255, 0.07)"
            chip_title_color = "#8890a0"
        else:
            capsule_bg = "rgba(255, 255, 255, 0.85)"
            capsule_border = "rgba(168, 85, 247, 0.25)"
            btn_color = "#475569"
            btn_hover_color = "#000000"
            btn_hover_bg = "rgba(0, 0, 0, 0.03)"
            btn_checked_bg = "linear-gradient(135deg, rgba(168, 85, 247, 0.75), rgba(236, 72, 153, 0.6))"
            btn_checked_border = "rgba(168, 85, 247, 0.85)"
            btn_checked_shadow = "inset 0 0 8px rgba(168, 85, 247, 0.2), 0 0 12px rgba(168, 85, 247, 0.4)"
            card_bg = "rgba(255, 255, 255, 0.85)"
            card_border = "rgba(0, 0, 0, 0.06)"
            card_shadow = "0 4px 16px rgba(0, 0, 0, 0.05)"
            card_title_color = "#334155"
            sep_color = "rgba(0, 0, 0, 0.08)"
            slider_bg = "#cbd5e1"
            bad_active_bg = "rgba(236, 72, 153, 0.18)"
            bad_active_border = "rgba(236, 72, 153, 0.4)"
            bad_inactive_bg = "rgba(0, 0, 0, 0.03)"
            bad_inactive_border = "rgba(0, 0, 0, 0.08)"
            act_btn_bg = "rgba(0, 0, 0, 0.04)"
            act_btn_border = "rgba(0, 0, 0, 0.1)"
            act_btn_color = "#0f172a"
            act_btn_hover_bg = "rgba(0, 0, 0, 0.08)"
            sensor_row_border = "rgba(0, 0, 0, 0.04)"
            chip_bg = "rgba(0, 0, 0, 0.025)"
            chip_border = "rgba(0, 0, 0, 0.07)"
            chip_title_color = "#64748b"

        css_data = f"""
        .mode-selector-capsule {{
            background-color: {capsule_bg};
            border: 1px solid {capsule_border};
            border-radius: 24px;
            padding: 2px;
            margin: 18px 0;
        }}
        .mode-selector-btn {{
            background: transparent;
            color: {btn_color};
            border: none;
            border-radius: 20px;
            font-weight: 600;
            font-size: 13px;
            font-family: "Inter", "Geist", sans-serif;
            padding: 8px 26px;
            transition: all 180ms ease;
            box-shadow: none;
            border-bottom: none;
        }}
        .mode-selector-btn:hover {{
            color: {btn_hover_color};
            background-color: {btn_hover_bg};
        }}
        .mode-selector-btn:checked {{
            color: #ffffff;
            background: {btn_checked_bg};
            box-shadow: {btn_checked_shadow};
            border: 1px solid {btn_checked_border};
        }}
        .fan-control-btn.active {{
            color: #ffffff;
            background: {btn_checked_bg};
            box-shadow: {btn_checked_shadow};
            border: 1px solid {btn_checked_border};
        }}
        .omen-dashboard-card {{
            background-color: {card_bg};
            border: 1px solid {card_border};
            border-radius: 24px; /* Highly ovalized card layout */
            padding: 22px;
            box-shadow: {card_shadow};
        }}
        .omen-dashboard-card separator {{
            background-color: {sep_color};
        }}
        .omen-dashboard-card-title {{
            font-size: 10px;
            font-weight: 800;
            color: {card_title_color};
            letter-spacing: 1.2px;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        .gaming-switch {{
            background-color: rgba(125, 211, 252, 0.18);
        }}
        .gaming-switch slider {{
            background-color: rgba(186, 230, 253, 0.95);
            border-radius: 99px;
            transition: background-color 180ms ease, box-shadow 180ms ease;
        }}
        .gaming-switch:checked {{
            background-color: rgba(125, 211, 252, 0.42);
        }}
        .gaming-switch:checked slider {{
            background-color: #7dd3fc;
            box-shadow: 0 0 8px rgba(125, 211, 252, 0.75);
        }}
        .fan-control-strip {{
            margin: 6px 0 18px 0;
        }}
        .fan-control-btn {{
            min-width: 0;
        }}
        .sensor-temp-val {{
            font-size: 17px;
            font-weight: 800;
        }}
        .warning-label {{
            color: #ef5b4a;
            font-size: 11px;
            font-weight: bold;
        }}
        .gamemode-badge-active {{
            color: #ec4899;
            font-weight: 800;
            background-color: {bad_active_bg};
            border: 1px solid {bad_active_border};
            border-radius: 4px;
            padding: 2px 10px;
            font-size: 11px;
        }}
        .gamemode-badge-inactive {{
            color: #718096;
            font-weight: 600;
            background-color: {bad_inactive_bg};
            border: 1px solid {bad_inactive_border};
            border-radius: 4px;
            padding: 2px 10px;
            font-size: 11px;
        }}
        .gaming-action-btn {{
            background-color: {act_btn_bg};
            border: 1px solid {act_btn_border};
            color: {act_btn_color};
            font-weight: bold;
            font-size: 12px;
            border-radius: 4px;
            padding: 8px 18px;
            transition: all 180ms ease;
        }}
        .gaming-action-btn:hover {{
            background-color: {act_btn_hover_bg};
            border-color: rgba(168, 85, 247, 0.5);
            box-shadow: 0 0 10px rgba(168, 85, 247, 0.25);
        }}
        .sensor-chip {{
            background-color: {chip_bg};
            border: 1px solid {chip_border};
            border-radius: 12px;
            padding: 8px 12px;
            transition: all 150ms ease;
        }}
        .sensor-chip-title {{
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            color: {chip_title_color};
        }}
        .sensor-chip-val {{
            font-size: 16px;
            font-weight: 800;
        }}
        .alert-banner {{
            background-color: rgba(239, 91, 74, 0.12);
            border: 1px solid rgba(239, 91, 74, 0.3);
            border-radius: 12px;
            padding: 8px 16px;
        }}
        """
        self._css_provider.load_from_data(css_data.encode())

    def _start_timers(self):
        if self._timer is None:
            self._timer = GLib.timeout_add(1500, self._refresh)
        if self._anim_timer is None:
            self._anim_timer = GLib.timeout_add(40, self._anim_tick)

    def _stop_timers(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        if self._anim_timer:
            GLib.source_remove(self._anim_timer)
            self._anim_timer = None

    def _on_map(self, *_args):
        self.monitor.set_active(True)
        self._start_timers()
        self._refresh()

    def _on_unmap(self, *_args):
        self.monitor.set_active(False)
        self._stop_timers()

    def _anim_tick(self):
        if not self.get_mapped():
            return True
        self.fan1_gauge.tick_rotation()
        self.fan2_gauge.tick_rotation()
        return True

    def set_service(self, service):
        self.service = service

    def set_platform_service(self, service):
        self._platform_svc = service

    def set_power_service(self, service):
        self._power_svc = service

    def set_rgb_service(self, service):
        self._rgb_svc = service

    def set_temp_unit(self, unit):
        self.temp_unit = unit

    def set_dark(self, is_dark):
        self.is_dark = is_dark
        if hasattr(self, "fan1_gauge") and self.fan1_gauge is not None:
            self.fan1_gauge.set_dark(is_dark)
        if hasattr(self, "fan2_gauge") and self.fan2_gauge is not None:
            self.fan2_gauge.set_dark(is_dark)
        if hasattr(self, "ram_bridge") and self.ram_bridge is not None:
            self.ram_bridge.set_dark(is_dark)
        if hasattr(self, "disk_bridge") and self.disk_bridge is not None:
            self.disk_bridge.set_dark(is_dark)
        if hasattr(self, "bat_bridge") and self.bat_bridge is not None:
            self.bat_bridge.set_dark(is_dark)
        self._update_theme_css(is_dark)

    def _rebuild_mode_selector(self, profiles):
        # Prevent rebuilding if the profiles list hasn't actually changed
        current_profiles = list(self.selector_buttons.keys())
        if sorted(profiles) == sorted(current_profiles):
            return

        # Clear existing buttons
        while True:
            child = self.selector_capsule.get_first_child()
            if child is None:
                break
            self.selector_capsule.remove(child)

        self.selector_group = None
        self.selector_buttons = {}

        # Fallback to defaults if profiles list is empty
        if not profiles:
            profiles = ["power-saver", "balanced", "performance"]

        mode_mapping = {
            "power-saver": T("saver"),
            "quiet": T("saver"),
            "low-power": T("saver"),
            "eco": T("saver"),
            "balanced": T("balanced"),
            "performance": T("performance"),
            "throughput-performance": T("performance"),
        }

        for mid in profiles:
            label = mode_mapping.get(mid, mid.replace("-", " ").title())
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("mode-selector-btn")
            if self.selector_group:
                btn.set_group(self.selector_group)
            else:
                self.selector_group = btn

            btn.connect("toggled", lambda w, m=mid: self._on_mode_toggled(w, m))
            self.selector_capsule.append(btn)
            self.selector_buttons[mid] = btn

        # Highlight current active mode
        if self.active_mode in self.selector_buttons:
            self._sync_mode_buttons(self.active_mode)

    @staticmethod
    def _human_storage(value_bytes):
        try:
            val = float(value_bytes)
        except Exception:
            return "N/A"
        if val <= 0:
            return "N/A"
        gib = val / (1024 ** 3)
        if gib >= 1024:
            return f"{gib / 1024:.1f} TB"
        return f"{gib:.0f} GB"

    @staticmethod
    def _trim_hw_text(text, max_len=30):
        txt = " ".join(str(text or "").split())
        if len(txt) <= max_len:
            return txt
        return txt[:max_len - 1].rstrip() + "..."

    def _get_hardware_info(self):
        info = {
            "cpu": "N/A",
            "disk": "N/A",
            "gpu": "N/A",
            "ram": "N/A",
        }

        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        info["cpu"] = self._trim_hw_text(line.split(":", 1)[1].strip(), 34)
                        break
        except Exception:
            pass

        try:
            total, _used, _free = shutil.disk_usage("/")
            info["disk"] = self._human_storage(total)
        except Exception:
            pass

        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        gib = kb / (1024 * 1024)
                        info["ram"] = f"{gib:.1f} GB"
                        break
        except Exception:
            pass

        try:
            n_smi = shutil.which("nvidia-smi")
            if n_smi:
                out = subprocess.check_output(
                    [n_smi, "--query-gpu=name", "--format=csv,noheader"],
                    stderr=subprocess.DEVNULL,
                    timeout=1.5,
                ).decode().strip().splitlines()
                if out and out[0].strip():
                    info["gpu"] = self._trim_hw_text(out[0].strip(), 30)
            if info["gpu"] == "N/A":
                out = subprocess.check_output(["lspci"], stderr=subprocess.DEVNULL, timeout=1.5).decode("utf-8", "ignore")
                for line in out.splitlines():
                    low = line.lower()
                    if "vga compatible controller" in low or "3d controller" in low:
                        info["gpu"] = self._trim_hw_text(line.split(":", 2)[-1].strip(), 30)
                        break
        except Exception:
            pass

        return info

    def _get_device_model_name(self):
        invalid = {
            "",
            "to be filled by o.e.m.",
            "not applicable",
            "default string",
            "system product name",
            "unknown",
            "hp laptop",
        }
        try:
            for dmi_file in (
                "/sys/class/dmi/id/product_name",
                "/sys/class/dmi/id/product_family",
                "/sys/class/dmi/id/board_name",
            ):
                if os.path.exists(dmi_file):
                    with open(dmi_file, "r") as f:
                        name = " ".join(f.read().strip().split())
                    if name.lower() not in invalid:
                        return name
        except Exception:
            pass
        return "HP Gaming System"

    def _build_ui(self):
        scroll = SmoothScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_bottom(20)
        self._content_box = content

        # ─── 1. DYNAMIC CENTERED SPEEDOMETER GAUGES & COMPACT RAM BRIDGE ───
        gauges_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=32, halign=Gtk.Align.CENTER)
        gauges_row.set_homogeneous(False)
        gauges_row.set_margin_top(14)
        gauges_row.set_margin_bottom(14)
        self._gauges_row = gauges_row

        # CPU Left Gauge (260x260, large!)
        self.fan1_gauge = OmenHighTechGauge(label="CPU", is_left=True, active_color=(0.66, 0.33, 0.97))
        gauges_row.append(self.fan1_gauge)

        # Center bridges column (RAM, Disk, Battery)
        middle_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        middle_column.set_valign(Gtk.Align.CENTER)

        self.ram_bridge = OmenSpecsBridge(color=(0.24, 0.60, 1.0))
        middle_column.append(self.ram_bridge)

        self.disk_bridge = OmenSpecsBridge(color=(0.66, 0.33, 0.97))
        middle_column.append(self.disk_bridge)

        self.bat_bridge = OmenSpecsBridge(color=(0.06, 0.72, 0.44))
        middle_column.append(self.bat_bridge)

        gauges_row.append(middle_column)

        # GPU Right Gauge
        self.fan2_gauge = OmenHighTechGauge(label="GPU", is_left=False, active_color=(0.93, 0.28, 0.60))
        gauges_row.append(self.fan2_gauge)

        content.append(gauges_row)

        self.fan_warning = Gtk.Label(label=T("fan_disabled"), css_classes=["warning-label"])
        self.fan_warning.set_halign(Gtk.Align.CENTER)
        self.fan_warning.set_visible(False)
        content.append(self.fan_warning)

        # ─── 2. SLEEK SEGMENTED MODE SELECTOR TABS ───
        self.selector_capsule = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, halign=Gtk.Align.CENTER)
        self.selector_capsule.add_css_class("mode-selector-capsule")
        self.selector_group = None
        self.selector_buttons = {}

        modes = [
            ("power-saver", T("saver")),
            ("balanced", T("balanced")),
            ("performance", T("performance"))
        ]

        for idx, (mid, label) in enumerate(modes):
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("mode-selector-btn")
            if self.selector_group:
                btn.set_group(self.selector_group)
            else:
                self.selector_group = btn

            btn.connect("toggled", lambda w, m=mid: self._on_mode_toggled(w, m))
            self.selector_capsule.append(btn)
            self.selector_buttons[mid] = btn

        content.append(self.selector_capsule)

        self.fan_control_strip = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.fan_control_strip.add_css_class("fan-control-strip")

        fan_control_head = Gtk.Label(label="FAN CONTROL", xalign=0)
        fan_control_head.add_css_class("omen-dashboard-card-title")
        self.fan_control_strip.append(fan_control_head)

        self.fan_control_capsule = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, halign=Gtk.Align.CENTER)
        self.fan_control_capsule.add_css_class("mode-selector-capsule")
        self.fan_control_group = None
        self.fan_control_buttons = {}
        self.fan_control_custom_btn = None

        fan_levels = [
            (0, "Auto"),
            (1, "Performance"),
            (2, "Max"),
        ]

        for level, label in fan_levels:
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("mode-selector-btn")
            btn.add_css_class("fan-control-btn")
            if self.fan_control_group:
                btn.set_group(self.fan_control_group)
            else:
                self.fan_control_group = btn
            btn.connect("toggled", lambda w, l=level: self._on_fan_control_toggled(w, l))
            self.fan_control_capsule.append(btn)
            self.fan_control_buttons[level] = btn

        self.fan_control_custom_btn = Gtk.Button(label="Custom")
        self.fan_control_custom_btn.add_css_class("mode-selector-btn")
        self.fan_control_custom_btn.add_css_class("fan-control-btn")
        self.fan_control_custom_btn.connect("clicked", self._on_custom_fan_control_clicked)
        self.fan_control_capsule.append(self.fan_control_custom_btn)

        self.fan_control_strip.append(self.fan_control_capsule)
        content.append(self.fan_control_strip)

        # ─── 3. FAN CURVE CARD (Shown in custom mode) ───
        self.curve_card = Gtk.Revealer()
        self.curve_card.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.curve_card.set_transition_duration(260)
        self.curve_card.set_reveal_child(False)

        curve_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        curve_panel.add_css_class("omen-dashboard-card")

        curve_header = Gtk.Box(spacing=10)
        curve_header.append(Gtk.Image.new_from_icon_name("document-edit-symbolic"))
        curve_header.append(Gtk.Label(label=T("fan_curve"), css_classes=["section-title"]))
        curve_panel.append(curve_header)

        curve_desc = Gtk.Label(label=T("curve_desc"), css_classes=["dim-label"], xalign=0, wrap=True)
        curve_panel.append(curve_desc)

        self.fan_curve = FanCurveWidget()
        self.fan_curve.on_curve_changed = self._on_curve_changed
        curve_panel.append(self.fan_curve)

        apply_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        apply_row.set_halign(Gtk.Align.END)
        self.curve_apply_btn = Gtk.Button(label="Apply")
        self.curve_apply_btn.add_css_class("suggested-action")
        self.curve_apply_btn.connect("clicked", self._on_custom_curve_apply)
        apply_row.append(self.curve_apply_btn)
        curve_panel.append(apply_row)

        self.curve_card.set_child(curve_panel)
        content.append(self.curve_card)

        # TLP / Auto-cpufreq Conflict label
        self._pp_conflict_lbl = Gtk.Label(label="", use_markup=True, xalign=0.5)
        self._pp_conflict_lbl.add_css_class("warning-label")
        self._pp_conflict_lbl.set_visible(False)
        content.append(self._pp_conflict_lbl)

        # App Profile lock banner
        self._app_profile_banner = Gtk.Label(label="", use_markup=True, xalign=0.5)
        self._app_profile_banner.add_css_class("warning-label")
        self._app_profile_banner.set_visible(False)
        content.append(self._app_profile_banner)

        # ─── 3. OVAL DASHBOARD GRIDS ───
        self.dashboard_grid = Gtk.Grid(column_spacing=18, row_spacing=18)
        self.dashboard_grid.set_column_homogeneous(True)
        self.dashboard_grid.set_hexpand(True)
        content.append(self.dashboard_grid)

        # LEFT CARD: Real-time Sensor Panel
        self.sensor_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.sensor_card.add_css_class("omen-dashboard-card")
        
        lbl_s = Gtk.Label(label=T("system_status"), xalign=0, css_classes=["omen-dashboard-card-title"])
        self.sensor_card.append(lbl_s)
        self.sensor_card.append(Gtk.Separator())

        # Scrollable sensor list (2-column chip grid)
        sensor_scroll = Gtk.ScrolledWindow(height_request=150, vexpand=True)
        sensor_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.sensor_list_box = Gtk.Grid(column_spacing=10, row_spacing=10, hexpand=True)
        self.sensor_list_box.set_column_homogeneous(True)
        sensor_scroll.set_child(self.sensor_list_box)
        self.sensor_card.append(sensor_scroll)
        
        self.dashboard_grid.attach(self.sensor_card, 0, 0, 1, 1)

        # RIGHT CARD: Gaming Optimization & Diagnostics
        self.gaming_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.gaming_card.add_css_class("omen-dashboard-card")
        
        lbl_g = Gtk.Label(label="GAMING OPTIMIZATION", xalign=0, css_classes=["omen-dashboard-card-title"])
        self.gaming_card.append(lbl_g)
        self.gaming_card.append(Gtk.Separator())

        # 1. Windows Key Lock (Oyun Tuş Kilidi) Toggle Row
        win_lock_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        win_lock_row.set_valign(Gtk.Align.CENTER)
        win_lock_row.append(Gtk.Image.new_from_icon_name("changes-prevent-symbolic"))
        win_lock_row.append(Gtk.Label(label=T("win_lock"), xalign=0, css_classes=["dim-label"]))
        win_lock_row.append(Gtk.Label(hexpand=True))
        
        self.win_lock_switch = Gtk.Switch()
        self.win_lock_switch.add_css_class("gaming-switch")
        self.win_lock_switch.connect("state-set", self._on_win_lock_toggled)
        win_lock_row.append(self.win_lock_switch)
        self.gaming_card.append(win_lock_row)

        self.gaming_card.append(Gtk.Separator())

        # 2. cTGP Toggle Row
        ctgp_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ctgp_row.set_valign(Gtk.Align.CENTER)
        ctgp_row.append(Gtk.Image.new_from_icon_name("video-display-symbolic"))
        ctgp_row.append(Gtk.Label(label="cTGP Boost Mode", xalign=0, css_classes=["dim-label"]))
        ctgp_row.append(Gtk.Label(hexpand=True))
        self.ctgp_status_label = Gtk.Label(label=T("inactive"))
        self.ctgp_status_label.add_css_class("gamemode-badge-inactive")
        self.ctgp_status_label.set_margin_end(6)
        ctgp_row.append(self.ctgp_status_label)
        self.gaming_card.append(ctgp_row)

        self.gaming_card.append(Gtk.Separator())

        # 3. PPAB Toggle Row
        ppab_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ppab_row.set_valign(Gtk.Align.CENTER)
        ppab_row.append(Gtk.Image.new_from_icon_name("cpu-symbolic"))
        ppab_row.append(Gtk.Label(label="PPAB Dynamic Boost", xalign=0, css_classes=["dim-label"]))
        ppab_row.append(Gtk.Label(hexpand=True))
        self.ppab_status_label = Gtk.Label(label=T("inactive"))
        self.ppab_status_label.add_css_class("gamemode-badge-inactive")
        self.ppab_status_label.set_margin_end(6)
        ppab_row.append(self.ppab_status_label)
        self.gaming_card.append(ppab_row)

        self.gaming_card.append(Gtk.Separator())

        # 4. Feral GameMode Status Row (no toggle switch, only badge)
        gm_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        gm_row.set_valign(Gtk.Align.CENTER)
        gm_row.append(Gtk.Image.new_from_icon_name("applications-games-symbolic"))
        gm_row.append(Gtk.Label(label="Feral GameMode Status", xalign=0, css_classes=["dim-label"]))
        gm_row.append(Gtk.Label(hexpand=True))
        
        # GameMode status text badge/label
        self.gamemode_status_label = Gtk.Label(label=T("inactive"))
        self.gamemode_status_label.add_css_class("gamemode-badge-inactive")
        self.gamemode_status_label.set_margin_end(6)
        gm_row.append(self.gamemode_status_label)
        
        self.gaming_card.append(gm_row)

        self.dashboard_grid.attach(self.gaming_card, 1, 0, 1, 1)

        # ─── 5. SYSTEM SPECIFICATIONS CARD ───
        self.sys_info_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.sys_info_card.add_css_class("omen-dashboard-card")
        self.sys_info_card.set_margin_top(8)

        sys_header = Gtk.Box(spacing=10)
        sys_header.set_valign(Gtk.Align.CENTER)
        sys_header.append(Gtk.Image.new_from_icon_name("computer-symbolic"))
        
        # Determine language (TR fallback)
        lang_is_tr = T("fan") == "Performans" or "tr" in os.getenv("LANG", "").lower()
        sys_title_lbl = Gtk.Label(label="SİSTEM BİLGİSİ" if lang_is_tr else "SYSTEM INFORMATION", xalign=0)
        sys_title_lbl.add_css_class("section-title")
        sys_header.append(sys_title_lbl)
        
        self.sys_info_card.append(sys_header)
        self.sys_info_card.append(Gtk.Separator())

        # Motherboard model name row
        model_name = self._get_device_model_name()
        model_row = Gtk.Box(spacing=10, margin_top=4, margin_bottom=4)
        model_row.set_valign(Gtk.Align.CENTER)
        
        model_icon = Gtk.Image.new_from_icon_name("computer-symbolic")
        model_icon.set_pixel_size(24)
        model_icon.add_css_class("nav-icon")
        model_row.append(model_icon)

        model_label = Gtk.Label(label=model_name, xalign=0)
        model_label.add_css_class("stat-big")
        model_row.append(model_label)
        self.sys_info_card.append(model_row)
        self.sys_info_card.append(Gtk.Separator())

        # 4 specs item grid/box
        spec_box = Gtk.Box(spacing=12, homogeneous=True, margin_top=8, margin_bottom=8)
        self.sys_info_card.append(spec_box)

        hw = self._get_hardware_info()
        labels = {
            "cpu": "CPU",
            "disk": "Depolama" if lang_is_tr else "Storage",
            "gpu": "GPU",
            "ram": "Bellek" if lang_is_tr else "Memory",
        }
        icons = {
            "cpu": "cpu-symbolic",
            "disk": "drive-harddisk-symbolic",
            "gpu": "video-display-symbolic",
            "ram": "memory-symbolic",
        }

        for key in ("cpu", "gpu", "ram", "disk"):
            item = Gtk.Box(spacing=10)
            item.add_css_class("home-spec-item")
            item.set_valign(Gtk.Align.CENTER)

            ico = Gtk.Image.new_from_icon_name(icons[key])
            ico.set_pixel_size(18)
            ico.add_css_class("nav-icon")
            item.append(ico)

            txt_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            ttl = Gtk.Label(label=labels[key], xalign=0)
            ttl.add_css_class("home-spec-title")
            txt_col.append(ttl)
            
            val = Gtk.Label(label=hw.get(key, "N/A"), xalign=0)
            val.add_css_class("home-spec-value")
            txt_col.append(val)
            item.append(txt_col)

            spec_box.append(item)

        content.append(self.sys_info_card)

        scroll.set_child(content)
        self.append(scroll)
        
        self.default_points = [(48, 0), (58, 35), (70, 60), (78, 72), (85, 100)]
        self.performance_points = [(35, 0), (50, 45), (65, 70), (75, 90), (82, 100)]
        self.custom_points = list(self.default_points)

        # Set default active state
        self._sync_fan_control_buttons(self.fan_control_level)
        self._set_custom_button_active(False)
        self._sync_mode_buttons("balanced")
        self.set_ui_scale("normal")

    def set_ui_scale(self, bucket, _width=0, _height=0):
        content = getattr(self, "_content_box", None)
        if content is not None:
            if bucket == "compact":
                content.set_margin_start(14)
                content.set_margin_end(14)
                content.set_spacing(12)
            elif bucket == "spacious":
                content.set_margin_start(34)
                content.set_margin_end(34)
                content.set_spacing(20)
            else:
                content.set_margin_start(24)
                content.set_margin_end(24)
                content.set_spacing(16)

        row = getattr(self, "_gauges_row", None)
        if row is not None:
            row.set_spacing(20 if bucket == "compact" else 48 if bucket == "spacious" else 36)

    def _sync_mode_buttons(self, mode):
        """Match UI toggle buttons with requested mode silently."""
        if mode in self.selector_buttons:
            btn = self.selector_buttons[mode]
            if not btn.get_active():
                prev = self._block_sync
                self._block_sync = True
                btn.set_active(True)
                self._block_sync = prev

    def _expected_power_state(self, mode):
        mapping = {
            "quiet": ("power-saver", "auto"),
            "balanced": ("balanced", "auto"),
            "performance": ("performance", "auto"),
            "custom": ("performance", "custom"),
        }
        return mapping.get(mode, ("balanced", "auto"))

    def _power_mode_confirmed(self, power_profile, fan_info, mode):
        expected_profile, _ = self._expected_power_state(mode)
        active_profile = power_profile.get("active", "")
        return active_profile == expected_profile

    def _set_pending_power_mode(self, mode):
        self._pending_power_mode = mode
        self._pending_power_started = time.monotonic()

    def _clear_pending_power_mode(self):
        self._pending_power_mode = None
        self._pending_power_started = 0.0
        return False

    def _sync_fan_control_buttons(self, level):
        if hasattr(self, "fan_control_buttons") and self.fan_control_buttons:
            prev = self._block_sync
            self._block_sync = True
            level = int(level)
            for idx, btn in self.fan_control_buttons.items():
                target_active = idx == level and level in self.fan_control_buttons
                if btn.get_active() != target_active:
                    btn.set_active(target_active)
            self._block_sync = prev

    def _set_custom_button_active(self, active):
        if hasattr(self, "fan_control_custom_btn") and self.fan_control_custom_btn is not None:
            if active:
                self.fan_control_custom_btn.add_css_class("active")
            else:
                self.fan_control_custom_btn.remove_css_class("active")

    def _open_custom_curve_editor(self):
        self._pre_override_fan_mode = None
        self._pre_override_fan_level = None
        self.fan_control_mode = "custom"
        self.fan_control_level = 3
        self._sync_fan_control_buttons(self.fan_control_level)
        self.fan_curve_editor_open = True
        self._set_custom_button_active(True)
        if hasattr(self, "curve_card") and self.curve_card is not None:
            self.curve_card.set_reveal_child(True)
        if hasattr(self, "fan_curve") and self.fan_curve is not None:
            self.fan_curve.set_interactive(True)
            self.fan_curve.set_points(self.custom_points)

    def _close_custom_curve_editor(self):
        self.fan_curve_editor_open = False
        if hasattr(self, "curve_card") and self.curve_card is not None:
            self.curve_card.set_reveal_child(False)
        if hasattr(self, "fan_curve") and self.fan_curve is not None:
            self.fan_curve.set_interactive(False)

    def _on_custom_fan_control_clicked(self, _btn):
        self._open_custom_curve_editor()

    def _on_custom_curve_apply(self, _btn):
        if hasattr(self, "fan_curve") and self.fan_curve is not None:
            self.custom_points = self.fan_curve.get_points()
            if self.service:
                try:
                    import json
                    _dbus_call(self.service.SaveCustomCurve, json.dumps(self.custom_points))
                except Exception as e:
                    print(f"Failed to save custom curve: {e}")
        self._set_daemon_fan_mode("custom")
        self._apply_fan_curve()
        self._close_custom_curve_editor()

    def _set_daemon_fan_mode(self, mode):
        if self.service:
            try:
                _dbus_call(self.service.SetFanMode, mode)
            except Exception:
                pass

    def _curve_fan_pct_for_temp(self, points, temp, rpm_floor=None, fan_max=None):
        if not points:
            return 0

        if rpm_floor is not None and fan_max:
            normalized_points = []
            for idx, (point_temp, point_value) in enumerate(points):
                if idx == 1 and point_temp == 50:
                    normalized_points.append((point_temp, (rpm_floor * 100.0) / fan_max))
                else:
                    normalized_points.append((point_temp, point_value))
            points = normalized_points

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

    def _apply_fan_control_level(self, level):
        self._pre_override_fan_mode = None
        self._pre_override_fan_level = None
        level = max(0, min(2, int(level)))
        self.fan_control_level = level

        fan_modes = {
            0: ("auto", None),
            1: ("custom", None),
            2: ("max", None),   # Max mode is handled entirely by driver/BIOS
        }
        fan_mode, fan_pct = fan_modes.get(level, ("auto", None))
        self.fan_control_mode = {0: "auto", 1: "performance", 2: "max"}.get(level, "auto")
        self._sync_fan_control_buttons(level)
        self._set_custom_button_active(False)
        self.fan_curve_editor_open = False
        if hasattr(self, "curve_card") and self.curve_card is not None:
            self.curve_card.set_reveal_child(False)
        if hasattr(self, "fan_curve") and self.fan_curve is not None:
            self.fan_curve.set_interactive(False)

        def _bg():
            try:
                if self.service:
                    if fan_mode is not None:
                        _dbus_call(self.service.SetFanMode, fan_mode)
                    if fan_pct is not None:
                        data = self.monitor.get_data()
                        fan_info = data.get("fan_info", {})
                        fans = fan_info.get("fans", {})
                        for fn, fd in fans.items():
                            max_rpm = fd.get("max", 5800) or 5800
                            target_rpm = int(max_rpm * fan_pct / 100)
                            _dbus_call(self.service.SetFanTarget, int(str(fn)), target_rpm)
                    elif level == 1:
                        self._set_daemon_fan_mode("custom")
                        self._apply_fan_curve(points=self.performance_points)
            except Exception as e:
                print(f"Fan control preset error: {e}")

        threading.Thread(target=_bg, daemon=True).start()

    def _on_fan_control_toggled(self, btn, level):
        if not btn.get_active() or self._block_sync:
            return
        self._apply_fan_control_level(level)

    def _on_mode_toggled(self, btn, mode):
        if not btn.get_active() or self._block_sync:
            return
        
        self.active_mode = mode
        self._set_pending_power_mode(mode)
        
        # Mapping UI modes to Daemon actions
        daemon_profile = "balanced"
        daemon_fan = None
        
        if mode in ("quiet", "power-saver", "eco", "low-power"):
            daemon_profile = "power-saver"
        elif mode == "balanced":
            daemon_profile = "balanced"
        elif mode in ("performance", "throughput-performance"):
            daemon_profile = "performance"
        elif mode == "custom":
            daemon_profile = "performance"
            daemon_fan = "custom"

        self.last_applied_rpm = {}

        # Defer calling D-Bus proxy services in a worker thread
        self._block_sync = True
        GLib.timeout_add(1200, self._unblock_sync)

        def _bg():
            # Automatically turn on cTGP and PPAB boost paths at hardware level if in performance/custom
            if daemon_profile == "performance":
                try:
                    for base in ("/sys/devices/platform/hp-wmi", "/sys/devices/platform/hp-omen"):
                        tgp_p = f"{base}/gpu_tgp"
                        ppab_p = f"{base}/gpu_ppab"
                        if os.path.exists(tgp_p):
                            with open(tgp_p, "w") as f:
                                f.write("1")
                        if os.path.exists(ppab_p):
                            with open(ppab_p, "w") as f:
                                f.write("1")
                except: pass

            # Update power profiles
            if self._power_svc:
                try:
                    result = _dbus_call(self._power_svc.SetPowerProfile, daemon_profile)
                    if result != "OK":
                        GLib.idle_add(self._clear_pending_power_mode)
                except:
                    GLib.idle_add(self._clear_pending_power_mode)

            # Keep fan daemon decoupled from power profile changes as requested.
            # Changing the power profile no longer automatically overrides or alters the user's selected fan mode.
            pass
                    
            if callable(self.on_profile_change):
                try: GLib.idle_add(self.on_profile_change, daemon_profile)
                except: pass

        threading.Thread(target=_bg, daemon=True).start()

    def _unblock_sync(self):
        self._block_sync = False
        return False

    def _on_win_lock_toggled(self, switch, state):
        """Toggle Windows Key Lock by writing to the hp-wmi/hp-rgb-lighting hardware register."""
        def _bg():
            # 1. Direct hardware sysfs write
            try:
                for base in ("/sys/devices/platform/hp-rgb-lighting", "/sys/devices/platform/hp_rgb_lighting"):
                    lock_p = f"{base}/win_lock"
                    if os.path.exists(lock_p):
                        with open(lock_p, "w") as f:
                            f.write("1" if state else "0")
                            break
            except Exception as e:
                print(f"⚠ Direct sysfs WinLock write failed: {e}")

            # 2. Sync via D-Bus daemon if available
            if self._rgb_svc:
                try:
                    _dbus_call(self._rgb_svc.SetWinLock, bool(state))
                except Exception as ex:
                    print(f"⚠ D-Bus WinLock call failed: {ex}")
        threading.Thread(target=_bg, daemon=True).start()
        return True





    def _on_clean_ram_clicked(self, _btn):
        if self._platform_svc:
            def _bg():
                try:
                    _dbus_call(self._platform_svc.CleanMemory)
                except: pass
            threading.Thread(target=_bg, daemon=True).start()

    def _on_curve_changed(self, points):
        if self.fan_control_mode == "custom":
            self.custom_points = points
            if self.fan_curve_editor_open:
                if getattr(self, "_curve_timer", None):
                    GLib.source_remove(self._curve_timer)
                self._curve_timer = GLib.timeout_add(200, self._apply_fan_curve_debounced)

    def _apply_fan_curve_debounced(self):
        self._apply_fan_curve()
        self._curve_timer = None
        return False

    def _apply_fan_curve(self, points=None):
        if self.fan_control_mode not in ("custom", "performance"):
            return
        if not self.temp_history:
            return

        # Initialize last_applied_temp if not present
        if not hasattr(self, "last_applied_temp"):
            self.last_applied_temp = 0.0

        avg_temp = sum(self.temp_history) / len(self.temp_history)

        # Apply Hysteresis:
        # If temperature is cooling down, don't reduce fan speed unless it cools by at least 4.0°C.
        # This prevents annoying pulsing / rapid fluctuation sounds of the fans.
        if avg_temp < self.last_applied_temp:
            if self.last_applied_temp - avg_temp < 4.0:
                effective_temp = self.last_applied_temp
            else:
                effective_temp = avg_temp
                self.last_applied_temp = avg_temp
        else:
            effective_temp = avg_temp
            self.last_applied_temp = avg_temp

        active_points = points or (self.performance_points if self.fan_control_mode == "performance" else self.custom_points)
        rpm_floor = 2000 if self.fan_control_mode == "performance" else None
        fan_max = None

        if self.service:
            try:
                data = self.monitor.get_data()
                info = data.get("fan_info", {})
                
                # Check availability first to avoid flooding
                if not info.get("available", False):
                    return
                    
                # Only set mode if it's not already custom
                if info.get("mode", "") != "custom":
                    self._set_daemon_fan_mode("custom")
                    
                fans = info.get("fans", {})

                for fn, fd in fans.items():
                    max_rpm = fd.get("max", 5800)
                    if max_rpm <= 0:
                        max_rpm = 5800

                    fan_max = max_rpm
                    fan_pct = self._curve_fan_pct_for_temp(active_points, effective_temp, rpm_floor=rpm_floor, fan_max=fan_max)

                    target_rpm = int(max_rpm * fan_pct / 100)
                    last = self.last_applied_rpm.get(str(fn), -1)
                    # Increased deadband threshold to 400 RPM to filter small jitter commands
                    if last >= 0 and abs(target_rpm - last) < 400:
                        continue

                    self.last_applied_rpm[str(fn)] = target_rpm
                    
                    def _apply_async(fidx, rpm):
                        try: self.service.SetFanTarget(fidx, rpm)
                        except: pass
                    threading.Thread(target=_apply_async, args=(int(str(fn)), target_rpm), daemon=True).start()
            except Exception as e:
                print(f"Fan curve set error: {e}")

    def _refresh(self):
        if not self.get_mapped():
            return True

        data = self.monitor.get_data()
        cpu_t = data.get("cpu_temp", 0.0)
        gpu_t = data.get("gpu_temp", 0.0)
        cpu_pct = data.get("cpu_pct", 0.0)
        gpu_pct = data.get("gpu_pct", 0.0)
        cpu_freq = data.get("cpu_freq", "0.00GHz")
        gpu_freq = data.get("gpu_freq", "0.00GHz")
        ram_pct = data.get("ram_pct", 0.0)
        ram_text = data.get("ram_text", "RAM 0% 0.0GB")
        fan_info = data.get("fan_info", {})
        power_profile = data.get("power_profile", {})
        rgb_state = data.get("rgb_state", {})
        gamemode = data.get("gamemode", "Inactive")
        sensors = data.get("all_sensors", [])
        gpu_tgp_state = data.get("gpu_tgp_state", False)
        gpu_ppab_state = data.get("gpu_ppab_state", False)

        if not getattr(self, "_custom_curve_loaded", False):
            saved_curve_json = fan_info.get("custom_curve", "[]")
            try:
                import json
                saved_curve = json.loads(saved_curve_json)
                if saved_curve and len(saved_curve) > 0:
                    self.custom_points = [(p[0], p[1]) for p in saved_curve]
                    if hasattr(self, "fan_curve") and self.fan_curve is not None:
                        self.fan_curve.set_points(self.custom_points)
                self._custom_curve_loaded = True
            except Exception:
                pass

        # Sync temp history and slider marker using max of CPU and GPU temp to ensure proper cooling response for both
        max_t = max(cpu_t, gpu_t)
        self.temp_history.append(max_t)
        # Increased moving average history size to 15 to smooth out short CPU spikes
        if len(self.temp_history) > 15:
            self.temp_history.pop(0)
        self.fan_curve.set_current_temp(max_t)

        # Sync Gauges & RAM Bridge
        fans = fan_info.get("fans", {})
        fan_keys = sorted(fans.keys(), key=lambda x: int(x))
        
        f1_rpm = fans[fan_keys[0]].get("current", 0) if len(fan_keys) > 0 else 0
        f2_rpm = fans[fan_keys[1]].get("current", 0) if len(fan_keys) > 1 else 0
        
        disk_pct = data.get("disk_pct", 0.0)
        disk_text = data.get("disk_text", "")
        bat_pct = data.get("bat_pct", 0.0)
        bat_text = data.get("bat_text", "")

        self.fan1_gauge.set_val(cpu_pct, cpu_t, cpu_freq, f1_rpm)
        self.fan2_gauge.set_val(gpu_pct, gpu_t, gpu_freq, f2_rpm)
        self.ram_bridge.set_val(ram_pct, ram_text)
        self.disk_bridge.set_val(disk_pct, disk_text)
        self.bat_bridge.set_val(bat_pct, bat_text)

        # Sync fan control mode and level with daemon if it was overridden by app profile/daemon
        daemon_mode = fan_info.get("mode", "auto")
        if daemon_mode == "auto" and self.fan_control_mode != "auto":
            if not getattr(self, "_pre_override_fan_mode", None):
                self._pre_override_fan_mode = self.fan_control_mode
                self._pre_override_fan_level = self.fan_control_level
            self.fan_control_mode = "auto"
            self.fan_control_level = 0
            self.last_applied_rpm = {}
            if hasattr(self, "curve_card") and self.curve_card is not None:
                self.curve_card.set_reveal_child(False)
        elif daemon_mode == "max" and self.fan_control_mode != "max":
            if not getattr(self, "_pre_override_fan_mode", None):
                self._pre_override_fan_mode = self.fan_control_mode
                self._pre_override_fan_level = self.fan_control_level
            self.fan_control_mode = "max"
            self.fan_control_level = 2
            self.last_applied_rpm = {}
            if hasattr(self, "curve_card") and self.curve_card is not None:
                self.curve_card.set_reveal_child(False)
        elif daemon_mode == "custom" and self.fan_control_mode not in ("custom", "performance"):
            if getattr(self, "_pre_override_fan_mode", None) in ("custom", "performance"):
                self.fan_control_mode = self._pre_override_fan_mode
                self.fan_control_level = self._pre_override_fan_level
            else:
                self.fan_control_mode = "custom"
                self.fan_control_level = 3
            self._pre_override_fan_mode = None
            self._pre_override_fan_level = None
            self.last_applied_rpm = {}

        # Apply fan curve if manual custom fan mode is enabled
        if self.fan_control_mode in ("custom", "performance"):
            self._apply_fan_curve()

        # Rebuild mode selector dynamically matching available WMI/ACPI profiles
        profiles = power_profile.get("profiles", [])
        if profiles:
            self._rebuild_mode_selector(profiles)

        # Sync Segmented Bar with active Profile, but keep a recent selection sticky
        if not self._block_sync:
            pending_mode = self._pending_power_mode
            pending_valid = False
            if pending_mode is not None:
                if self._power_mode_confirmed(power_profile, fan_info, pending_mode):
                    self._clear_pending_power_mode()
                else:
                    elapsed = time.monotonic() - self._pending_power_started
                    if elapsed < 6.0:
                        pending_valid = True
                    else:
                        self._clear_pending_power_mode()

            if pending_valid:
                ui_mode = pending_mode
            else:
                active_p = power_profile.get("active", "")
                
                if active_p in self.selector_buttons:
                    ui_mode = active_p
                else:
                    # Dynamic fallbacks
                    if active_p == "power-saver":
                        ui_mode = "quiet" if "quiet" in self.selector_buttons else "low-power" if "low-power" in self.selector_buttons else "power-saver"
                    elif active_p == "performance":
                        ui_mode = "performance"
                    else:
                        ui_mode = "balanced"

            self._sync_mode_buttons(ui_mode)
            self.active_mode = ui_mode

        if self.fan_control_mode == "custom":
            self._set_custom_button_active(True)
            if self.fan_curve_editor_open and hasattr(self, "curve_card") and self.curve_card is not None:
                self.curve_card.set_reveal_child(True)
            elif hasattr(self, "curve_card") and self.curve_card is not None:
                self.curve_card.set_reveal_child(False)
        else:
            self._set_custom_button_active(False)
            self._sync_fan_control_buttons(self.fan_control_level)

        # Sync Win Lock Switch
        if not self._block_sync and rgb_state:
            locked = rgb_state.get("win_lock", False)
            if self.win_lock_switch.get_active() != locked:
                self.win_lock_switch.set_active(locked)

        # Sync GameMode badge
        is_gm_active = gamemode == "Active"
        if is_gm_active:
            self.gamemode_status_label.set_label(T("active"))
            self.gamemode_status_label.set_css_classes(["gamemode-badge-active"])
        else:
            self.gamemode_status_label.set_label(T("inactive"))
            self.gamemode_status_label.set_css_classes(["gamemode-badge-inactive"])

        # Sync cTGP & PPAB hardware state switches
        # Fallback to profile states if sysfs not writable/present
        if not self._block_sync:
            active_p = power_profile.get("active", "")
            if active_p == "performance":
                tgp_target = True
                ppab_target = True
            elif active_p == "balanced":
                tgp_target = False
                ppab_target = True
            else:
                tgp_target = False
                ppab_target = False

            current_tgp = gpu_tgp_state if gpu_tgp_state else tgp_target
            current_ppab = gpu_ppab_state if gpu_ppab_state else ppab_target

            if current_tgp:
                self.ctgp_status_label.set_label(T("active"))
                self.ctgp_status_label.set_css_classes(["gamemode-badge-active"])
            else:
                self.ctgp_status_label.set_label(T("inactive"))
                self.ctgp_status_label.set_css_classes(["gamemode-badge-inactive"])

            if current_ppab:
                self.ppab_status_label.set_label(T("active"))
                self.ppab_status_label.set_css_classes(["gamemode-badge-active"])
            else:
                self.ppab_status_label.set_label(T("inactive"))
                self.ppab_status_label.set_css_classes(["gamemode-badge-inactive"])

        # Sync Sensors List (Left Card)
        self._update_sensor_list(sensors)

        # TLP / Auto-cpufreq conflicts
        conflict = data.get("power_conflict")
        active_app = power_profile.get("active_app")
        app_profiles_enabled = power_profile.get("app_profiles_enabled", False)
        app_profile_active = bool(active_app and app_profiles_enabled)

        if app_profile_active:
            # App profile is overriding — lock profile selector and show banner
            self.selector_capsule.set_sensitive(False)
            if hasattr(self, "fan_control_capsule") and self.fan_control_capsule is not None:
                self.fan_control_capsule.set_sensitive(False)
            if hasattr(self, "fan_curve") and self.fan_curve is not None:
                self.fan_curve.set_interactive(False)
            app_display = str(active_app)
            banner_text = T("managed_by_app_profile").format(app=app_display)
            self._app_profile_banner.set_label(
                f"<span color='#57c494'>{banner_text}</span>")
            self._app_profile_banner.set_visible(True)
        else:
            self._app_profile_banner.set_visible(False)
            # Only unlock if no TLP conflict either
            if not conflict:
                self.selector_capsule.set_sensitive(True)
                if hasattr(self, "fan_control_capsule") and self.fan_control_capsule is not None:
                    self.fan_control_capsule.set_sensitive(True)
                if hasattr(self, "fan_curve") and self.fan_curve is not None and getattr(self, "fan_curve_editor_open", False):
                    self.fan_curve.set_interactive(True)

        if conflict:
            self.selector_capsule.set_sensitive(conflict != "tlp")
            self._pp_conflict_lbl.set_label(
                f"<span color='#ef5b4a'>{T('power_managed_by').format(tool=conflict.upper())}</span>")
            self._pp_conflict_lbl.set_visible(True)
        else:
            if not app_profile_active:
                self.selector_capsule.set_sensitive(True)
                if hasattr(self, "fan_control_capsule") and self.fan_control_capsule is not None:
                    self.fan_control_capsule.set_sensitive(True)
                if hasattr(self, "fan_curve") and self.fan_curve is not None and getattr(self, "fan_curve_editor_open", False):
                    self.fan_curve.set_interactive(True)
            self._pp_conflict_lbl.set_visible(False)

        # Fan service warning
        available = fan_info.get("available", False)
        self.fan_warning.set_visible(not available)

        return True

    def _update_sensor_list(self, sensors):
        """Populate the left bottom card with a beautifully formatted chip grid of real-time temperatures."""
        if len(sensors) != len(self._sensor_labels):
            while child := self.sensor_list_box.get_first_child():
                self.sensor_list_box.remove(child)
            self._sensor_labels.clear()

        for idx, s in enumerate(sensors):
            key = f"{s['driver']}_{s['label']}"
            val_str = f"{int(s['temp'])}°C"

            # Temperature color coding
            is_dark = getattr(self, "is_dark", True)
            if is_dark:
                color = "#a0aec0"
                if s["temp"] >= 78.0:
                    color = "#ef5b4a"
                elif s["temp"] >= 62.0:
                    color = "#f6ad55"
                elif s["temp"] > 0:
                    color = "#00f0ff"
            else:
                color = "#475569"
                if s["temp"] >= 78.0:
                    color = "#d93025"
                elif s["temp"] >= 62.0:
                    color = "#b06000"
                elif s["temp"] > 0:
                    color = "#0066cc"

            if key in self._sensor_labels:
                _lbl_name, lbl_temp = self._sensor_labels[key]
                lbl_temp.set_markup(f"<span color='{color}'><b>{val_str}</b></span>")
            else:
                chip = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True)
                chip.add_css_class("sensor-chip")

                lbl_name = Gtk.Label(label=s["label"], xalign=0, css_classes=["sensor-chip-title"])
                chip.append(lbl_name)

                lbl_temp = Gtk.Label(xalign=0, css_classes=["sensor-chip-val"])
                lbl_temp.set_markup(f"<span color='{color}'><b>{val_str}</b></span>")
                chip.append(lbl_temp)

                col = idx % 2
                row = idx // 2
                self.sensor_list_box.attach(chip, col, row, 1, 1)
                self._sensor_labels[key] = (lbl_name, lbl_temp)

        if not sensors:
            if not self.sensor_list_box.get_first_child():
                lbl_empty = Gtk.Label(label=T("no_sensor"), css_classes=["dim-label"])
                lbl_empty.set_opacity(0.6)
                self.sensor_list_box.attach(lbl_empty, 0, 0, 2, 1)

    def cleanup(self):
        self._stop_timers()
        self.monitor.stop()

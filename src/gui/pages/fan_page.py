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

    def __init__(self, label="CPU", is_left=True, active_color=(0.24, 0.60, 1.0)):
        super().__init__()
        self.label = label
        self.is_left = is_left  # True for Left Gauge (CPU), False for Right (GPU)
        self.active_color = active_color
        
        self.usage = 0.0
        self.temp = 0.0
        self.speed = "0.00GHz"
        self.rpm = 0
        self.rotation = 0.0
        
        self.set_size_request(260, 260)
        self.set_draw_func(self._draw)

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
            cr.set_source_rgba(255, 255, 255, 0.05)
            cr.arc(cx, cy, r_main + 16, start_angle, end_angle)
            cr.stroke()
            
            # Fill track
            cr.set_source_rgba(*self.active_color, 0.85)
            cr.arc(cx, cy, r_main + 16, start_angle, fill_angle)
            cr.stroke()
            
            # Label temperature e.g. "51°C" bold, italic, and exactly ON TOP of the curve
            cr.select_font_face("Sans", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(13)
            cr.set_source_rgba(0.9, 0.94, 1.0, 0.95)
            cr.move_to(cx - 98, cy - 78) # Perfectly positioned on top of the CPU temperature bar
            cr.show_text(f"{int(self.temp)}°C")
        else:
            # GPU Temp Arc: Top-Right from 325° to 415°
            start_angle = 325 * math.pi / 180
            end_angle = 415 * math.pi / 180
            temp_pct = max(0.0, min(100.0, self.temp)) / 100.0
            fill_angle = start_angle + temp_pct * (end_angle - start_angle)
            
            # Base track
            cr.set_source_rgba(255, 255, 255, 0.05)
            cr.arc(cx, cy, r_main + 16, start_angle, end_angle)
            cr.stroke()
            
            # Fill track
            cr.set_source_rgba(*self.active_color, 0.85)
            cr.arc(cx, cy, r_main + 16, start_angle, fill_angle)
            cr.stroke()
            
            # Label temperature e.g. "0°C" bold, italic, and exactly ON TOP of the curve
            cr.select_font_face("Sans", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(13)
            cr.set_source_rgba(0.9, 0.94, 1.0, 0.95)
            cr.move_to(cx + 64, cy - 78) # Perfectly positioned on top of the GPU temperature bar
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
                cr.set_source_rgba(255, 255, 255, 0.06)
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
        cr.set_source_rgba(255, 255, 255, 0.04)
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
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
        te = cr.text_extents(val_txt)
        cr.move_to(cx - te.width / 2, cy + te.height / 2 - 3)
        cr.show_text(val_txt)
        
        # Clock Speed
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        cr.set_source_rgba(0.55, 0.60, 0.68, 0.7)
        te = cr.text_extents(self.speed)
        cr.move_to(cx - te.width / 2, cy + r_tick_in * 0.52)
        cr.show_text(self.speed)

        # ── 4. Fan Speed RPM text centered under dial (whiter, larger, italic, and bold) ──
        cr.select_font_face("Inter", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        cr.set_source_rgba(0.9, 0.94, 1.0, 0.95)
        rpm_txt = f"{self.rpm} RPM"
        te = cr.text_extents(rpm_txt)
        cr.move_to(cx - te.width / 2, cy + r_main + 26)
        cr.show_text(rpm_txt)


class OmenRAMBridge(Gtk.DrawingArea):
    """Extremely high-fidelity bridging bar, shortened and shifted up."""

    def __init__(self, size_w=160, size_h=120):
        super().__init__()
        self.set_size_request(size_w, size_h)
        self.pct = 0.0
        self.text = "RAM 0% 0.0GB"
        self.set_draw_func(self._draw)

    def set_val(self, pct, text):
        self.pct = float(pct)
        self.text = str(text)
        self.queue_draw()

    def _draw(self, _, cr, w, h):
        cx, cy = w / 2, h / 2 - 32 # Shifted significantly higher
        bar_w = w * 0.90
        bar_h = 6
        bar_x = cx - bar_w / 2
        
        # ── 1. Thin Translucent Bridge line ──
        cr.set_line_width(1.0)
        cr.set_source_rgba(255, 255, 255, 0.03)
        cr.move_to(0, cy)
        cr.line_to(w, cy)
        cr.stroke()
        
        # ── 2. Mechanical Clamp/Bracket Icons at both ends ──
        cr.set_line_width(1.5)
        cr.set_source_rgba(255, 255, 255, 0.18)
        
        # Left Bracket
        lx = bar_x - 3
        cr.move_to(lx, cy - 8)
        cr.line_to(lx, cy + 8)
        cr.stroke()
        cr.move_to(lx, cy - 8)
        cr.line_to(lx + 4, cy - 8)
        cr.stroke()
        cr.move_to(lx, cy + 8)
        cr.line_to(lx + 4, cy + 8)
        cr.stroke()
        
        # Right Bracket
        rx = bar_x + bar_w + 3
        cr.move_to(rx, cy - 8)
        cr.line_to(rx, cy + 8)
        cr.stroke()
        cr.move_to(rx, cy - 8)
        cr.line_to(rx - 4, cy - 8)
        cr.stroke()
        cr.move_to(rx, cy + 8)
        cr.line_to(rx - 4, cy + 8)
        cr.stroke()

        # ── 3. Background Capsule Tube ──
        cr.set_source_rgba(22, 25, 30, 0.95)
        cr.set_line_width(bar_h)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(bar_x, cy)
        cr.line_to(bar_x + bar_w, cy)
        cr.stroke()
        
        # Outer border
        cr.set_source_rgba(255, 255, 255, 0.08)
        cr.set_line_width(bar_h + 1.2)
        cr.move_to(bar_x, cy)
        cr.line_to(bar_x + bar_w, cy)
        cr.stroke()

        # ── 4. Glowing Blue Fill ──
        fill_w = bar_w * (max(0.0, min(100.0, self.pct)) / 100.0)
        if fill_w > 0:
            cr.set_source_rgba(0.24, 0.60, 1.0, 0.95)
            cr.set_line_width(bar_h)
            cr.move_to(bar_x, cy)
            cr.line_to(bar_x + fill_w, cy)
            cr.stroke()
            
            # Subtle radial shadow/glow
            cr.set_source_rgba(0.24, 0.60, 1.0, 0.22)
            cr.set_line_width(bar_h + 3)
            cr.move_to(bar_x, cy)
            cr.line_to(bar_x + fill_w, cy)
            cr.stroke()
            
        # ── 5. Small Pointer Indicator Triangle on top ──
        px = bar_x + fill_w
        py = cy - bar_h / 2 - 4
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.move_to(px, py)
        cr.line_to(px - 4, py - 5)
        cr.line_to(px + 4, py - 5)
        cr.close_path()
        cr.fill()
        
        # ── 6. Dynamic RAM details ──
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        cr.set_source_rgba(0.82, 0.86, 0.92, 0.8)
        te = cr.text_extents(self.text)
        cr.move_to(cx - te.width / 2, cy + bar_h * 2 + 24)
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
        self._sensor_labels = {}

        self._inject_premium_hub_css()

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

    def _inject_premium_hub_css(self):
        """Register custom CSS styles to strictly replicate OMEN Command Center."""
        css_data = """
        .mode-selector-capsule {
            background-color: #15171e;
            border: 1px solid #232732;
            border-radius: 24px;
            padding: 2px;
            margin: 18px 0;
        }
        .mode-selector-btn {
            background: transparent;
            color: #8890a0;
            border: none;
            border-radius: 20px;
            font-weight: 600;
            font-size: 13px;
            font-family: "Inter", "Geist", sans-serif;
            padding: 8px 26px;
            transition: all 180ms ease;
            box-shadow: none;
            border-bottom: none;
        }
        .mode-selector-btn:hover {
            color: #ffffff;
            background-color: rgba(255, 255, 255, 0.02);
        }
        .mode-selector-btn:checked {
            color: #ffffff;
            background: linear-gradient(180deg, #1b202a, #11141b);
            box-shadow: inset 0 0 8px rgba(0, 240, 255, 0.12), 0 0 10px rgba(0, 240, 255, 0.15);
            border: 1px solid rgba(0, 240, 255, 0.25);
        }
        .omen-dashboard-card {
            background-color: #101115;
            border: 1px solid #1a1d24;
            border-radius: 24px; /* Highly ovalized card layout */
            padding: 22px;
            box-shadow: none;
        }
        .omen-dashboard-card-title {
            font-size: 10px;
            font-weight: 800;
            color: #a0aec0;
            letter-spacing: 1.2px;
            text-transform: uppercase;
            margin-bottom: 6px;
        }
        .gaming-switch slider {
            background-color: #4a5568;
            border-radius: 99px;
        }
        .gaming-switch:checked slider {
            background-color: #00f0ff;
            box-shadow: 0 0 8px rgba(0, 240, 255, 0.8);
        }
        .warning-label {
            color: #ef5b4a;
            font-size: 11px;
            font-weight: bold;
        }
        .gamemode-badge-active {
            color: #00f0ff;
            font-weight: 800;
            background-color: rgba(0, 240, 255, 0.10);
            border: 1px solid rgba(0, 240, 255, 0.3);
            border-radius: 4px;
            padding: 2px 10px;
            font-size: 11px;
        }
        .gamemode-badge-inactive {
            color: #718096;
            font-weight: 600;
            background-color: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 4px;
            padding: 2px 10px;
            font-size: 11px;
        }
        .gaming-action-btn {
            background-color: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #ffffff;
            font-weight: bold;
            font-size: 12px;
            border-radius: 4px;
            padding: 8px 18px;
            transition: all 180ms ease;
        }
        .gaming-action-btn:hover {
            background-color: rgba(255, 255, 255, 0.08);
            border-color: rgba(0, 240, 255, 0.4);
            box-shadow: 0 0 10px rgba(0, 240, 255, 0.15);
        }
        .sensor-row {
            padding: 4px 6px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css_data.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

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
        pass

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
        self.fan1_gauge = OmenHighTechGauge(label="CPU", is_left=True, active_color=(0.24, 0.60, 1.0))
        gauges_row.append(self.fan1_gauge)

        # Compact RAM Bridge in middle (160 width, sits high in the middle)
        self.ram_bridge = OmenRAMBridge(size_w=160, size_h=120)
        self.ram_bridge.set_valign(Gtk.Align.CENTER)
        gauges_row.append(self.ram_bridge)

        # GPU Right Gauge
        self.fan2_gauge = OmenHighTechGauge(label="GPU", is_left=False, active_color=(0.22, 0.88, 0.44))
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
            ("quiet", T("saver")),
            ("balanced", T("balanced")),
            ("performance", T("performance")),
            ("custom", T("custom"))
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

        # TLP / Auto-cpufreq Conflict label
        self._pp_conflict_lbl = Gtk.Label(label="", use_markup=True, xalign=0.5)
        self._pp_conflict_lbl.add_css_class("warning-label")
        self._pp_conflict_lbl.set_visible(False)
        content.append(self._pp_conflict_lbl)

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

        # Scrollable sensor list
        sensor_scroll = Gtk.ScrolledWindow(height_request=150, vexpand=True)
        sensor_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.sensor_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
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
        self.ctgp_switch = Gtk.Switch()
        self.ctgp_switch.add_css_class("gaming-switch")
        self.ctgp_switch.connect("state-set", self._on_ctgp_toggled)
        ctgp_row.append(self.ctgp_switch)
        self.gaming_card.append(ctgp_row)

        self.gaming_card.append(Gtk.Separator())

        # 3. PPAB Toggle Row
        ppab_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ppab_row.set_valign(Gtk.Align.CENTER)
        ppab_row.append(Gtk.Image.new_from_icon_name("processor-symbolic"))
        ppab_row.append(Gtk.Label(label="PPAB Dynamic Boost", xalign=0, css_classes=["dim-label"]))
        ppab_row.append(Gtk.Label(hexpand=True))
        self.ppab_switch = Gtk.Switch()
        self.ppab_switch.add_css_class("gaming-switch")
        self.ppab_switch.connect("state-set", self._on_ppab_toggled)
        ppab_row.append(self.ppab_switch)
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

        # ─── 4. FAN CURVE CARD (Shown in custom mode) ───
        self.curve_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.curve_card.add_css_class("omen-dashboard-card")
        self.curve_card.set_visible(False)

        curve_header = Gtk.Box(spacing=10)
        curve_header.append(Gtk.Image.new_from_icon_name("document-edit-symbolic"))
        curve_header.append(Gtk.Label(label=T("fan_curve"), css_classes=["section-title"]))
        self.curve_card.append(curve_header)

        curve_desc = Gtk.Label(label=T("curve_desc"), css_classes=["dim-label"], xalign=0, wrap=True)
        self.curve_card.append(curve_desc)

        self.fan_curve = FanCurveWidget()
        self.fan_curve.on_curve_changed = self._on_curve_changed
        self.curve_card.append(self.fan_curve)

        content.append(self.curve_card)

        scroll.set_child(content)
        self.append(scroll)
        
        self.default_points = [(48, 0), (58, 35), (70, 60), (78, 72), (85, 100)]
        self.custom_points = list(self.default_points)

        # Set default active state
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

    def _on_mode_toggled(self, btn, mode):
        if not btn.get_active() or self._block_sync:
            return
        
        self.active_mode = mode
        
        # Mapping UI modes to Daemon actions
        daemon_profile = "balanced"
        daemon_fan = "auto"
        
        if mode == "quiet":
            daemon_profile = "power-saver"
            daemon_fan = "auto"
        elif mode == "balanced":
            daemon_profile = "balanced"
            daemon_fan = "auto"
        elif mode == "performance":
            daemon_profile = "performance"
            daemon_fan = "auto"
        elif mode == "custom":
            daemon_profile = "performance"
            daemon_fan = "custom"

        # Toggles manual fan curve layout
        self.curve_card.set_visible(mode == "custom")
        self.fan_curve.set_interactive(mode == "custom")
        if mode == "custom":
            self.fan_curve.set_points(self.custom_points)
        self.last_applied_rpm = {}

        if mode in ("performance", "custom"):
            # Automatically turn on cTGP and PPAB switches instantly in UI
            self.ctgp_switch.set_active(True)
            self.ppab_switch.set_active(True)

        # Defer calling D-Bus proxy services in a worker thread
        self._block_sync = True
        GLib.timeout_add(1200, self._unblock_sync)

        def _bg():
            # Automatically turn on cTGP and PPAB boost paths at hardware level if in performance/custom
            if mode in ("performance", "custom"):
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
                try: _dbus_call(self._power_svc.SetPowerProfile, daemon_profile)
                except: pass
            # Update fan modes
            if self.service:
                try: _dbus_call(self.service.SetFanMode, daemon_fan)
                except: pass
                if mode == "custom":
                    self._apply_fan_curve()
                    
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

    def _on_ctgp_toggled(self, switch, state):
        """Force write configurable TGP override if supported."""
        def _bg():
            try:
                for base in ("/sys/devices/platform/hp-wmi", "/sys/devices/platform/hp-omen"):
                    tgp_p = f"{base}/gpu_tgp"
                    if os.path.exists(tgp_p):
                        with open(tgp_p, "w") as f:
                            f.write("1" if state else "0")
                            break
            except: pass
        threading.Thread(target=_bg, daemon=True).start()
        return True

    def _on_ppab_toggled(self, switch, state):
        """Force write PPAB power dynamic boost override if supported."""
        def _bg():
            try:
                for base in ("/sys/devices/platform/hp-wmi", "/sys/devices/platform/hp-omen"):
                    ppab_p = f"{base}/gpu_ppab"
                    if os.path.exists(ppab_p):
                        with open(ppab_p, "w") as f:
                            f.write("1" if state else "0")
                            break
            except: pass
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
        if self.active_mode == "custom":
            self.custom_points = points
            if getattr(self, "_curve_timer", None):
                GLib.source_remove(self._curve_timer)
            self._curve_timer = GLib.timeout_add(200, self._apply_fan_curve_debounced)

    def _apply_fan_curve_debounced(self):
        self._apply_fan_curve()
        self._curve_timer = None
        return False

    def _apply_fan_curve(self):
        if self.active_mode != "custom":
            return
        if not self.temp_history:
            return

        avg_temp = sum(self.temp_history) / len(self.temp_history)
        fan_pct = self.fan_curve.get_fan_pct_for_temp(avg_temp)

        if self.service:
            try:
                data = self.monitor.get_data()
                info = data.get("fan_info", {})
                fans = info.get("fans", {})

                for fn, fd in fans.items():
                    max_rpm = fd.get("max", 5800)
                    if max_rpm <= 0:
                        max_rpm = 5800

                    target_rpm = int(max_rpm * fan_pct / 100)
                    last = self.last_applied_rpm.get(str(fn), -1)
                    if last >= 0 and abs(target_rpm - last) < 250:
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

        # Sync temp history and slider marker
        self.temp_history.append(cpu_t)
        if len(self.temp_history) > 5:
            self.temp_history.pop(0)
        self.fan_curve.set_current_temp(cpu_t)

        # Sync Gauges & RAM Bridge
        fans = fan_info.get("fans", {})
        fan_keys = sorted(fans.keys(), key=lambda x: int(x))
        
        f1_rpm = fans[fan_keys[0]].get("current", 0) if len(fan_keys) > 0 else 0
        f2_rpm = fans[fan_keys[1]].get("current", 0) if len(fan_keys) > 1 else 0
        
        self.fan1_gauge.set_val(cpu_pct, cpu_t, cpu_freq, f1_rpm)
        self.fan2_gauge.set_val(gpu_pct, gpu_t, gpu_freq, f2_rpm)
        self.ram_bridge.set_val(ram_pct, ram_text)

        # Apply fan curve if manual
        if self.active_mode == "custom":
            self._apply_fan_curve()

        # Sync Segmented Bar with active Profile
        if not self._block_sync:
            active_p = power_profile.get("active", "")
            daemon_m = fan_info.get("mode", "auto")
            
            ui_mode = "balanced"
            if daemon_m == "custom":
                ui_mode = "custom"
            elif active_p == "power-saver":
                ui_mode = "quiet"
            elif active_p == "performance":
                ui_mode = "performance"
            else:
                ui_mode = "balanced"
                
            self._sync_mode_buttons(ui_mode)
            self.active_mode = ui_mode
            self.curve_card.set_visible(ui_mode == "custom")

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

            if self.ctgp_switch.get_active() != current_tgp:
                self.ctgp_switch.set_active(current_tgp)
            if self.ppab_switch.get_active() != current_ppab:
                self.ppab_switch.set_active(current_ppab)

        # Sync Sensors List (Left Card)
        self._update_sensor_list(sensors)

        # TLP / Auto-cpufreq conflicts
        conflict = data.get("power_conflict")
        if conflict:
            self.selector_capsule.set_sensitive(conflict != "tlp")
            self._pp_conflict_lbl.set_label(
                f"<span color='#ef5b4a'>{T('power_managed_by').format(tool=conflict.upper())}</span>")
            self._pp_conflict_lbl.set_visible(True)
        else:
            self.selector_capsule.set_sensitive(True)
            self._pp_conflict_lbl.set_visible(False)

        # Fan service warning
        available = fan_info.get("available", False)
        self.fan_warning.set_visible(not available)

        return True

    def _update_sensor_list(self, sensors):
        """Populate the left bottom card with a beautifully formatted list of real-time temperatures."""
        if len(sensors) != len(self._sensor_labels):
            while child := self.sensor_list_box.get_first_child():
                self.sensor_list_box.remove(child)
            self._sensor_labels.clear()

        for s in sensors:
            key = f"{s['driver']}_{s['label']}"
            val_str = f"{int(s['temp'])}°C"

            # Temperature color coding
            color = "#a0aec0"
            if s["temp"] >= 78.0:
                color = "#ef5b4a"
            elif s["temp"] >= 62.0:
                color = "#f6ad55"
            elif s["temp"] > 0:
                color = "#00f0ff"

            if key in self._sensor_labels:
                _lbl_name, lbl_temp = self._sensor_labels[key]
                lbl_temp.set_markup(f"<span color='{color}'><b>{val_str}</b></span>")
            else:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                row.add_css_class("sensor-row")
                
                bullet = Gtk.Label(label="• ")
                bullet.set_opacity(0.4)
                row.append(bullet)

                lbl_name = Gtk.Label(label=s["label"], xalign=0, css_classes=["dim-label"])
                lbl_name.set_hexpand(True)
                row.append(lbl_name)

                lbl_temp = Gtk.Label(xalign=1)
                lbl_temp.set_markup(f"<span color='{color}'><b>{val_str}</b></span>")
                row.append(lbl_temp)

                self._sensor_list_box_row = row
                self.sensor_list_box.append(row)
                self._sensor_labels[key] = (lbl_name, lbl_temp)

        if not sensors:
            if not self.sensor_list_box.get_first_child():
                lbl_empty = Gtk.Label(label=T("no_sensor"), css_classes=["dim-label"])
                lbl_empty.set_opacity(0.6)
                self.sensor_list_box.append(lbl_empty)

    def cleanup(self):
        self._stop_timers()
        self.monitor.stop()

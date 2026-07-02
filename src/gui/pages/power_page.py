#!/usr/bin/env python3
"""Power Tuning & Undervolt Page — advanced CPU/GPU power management."""
import os, json
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

def T(k):
    from i18n import T as _T
    return _T(k)

class PowerPage(Gtk.Box):
    def __init__(self, service=None):
        super().__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        self.service = service
        
        self.logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "images", "omenlogo.png")
        if not os.path.exists(self.logo_path):
            self.logo_path = "/usr/share/hp-manager/images/omenlogo.png"
            
        self._build_ui()

    def set_service(self, service):
        self.service = service
        self._sync_state()

    def _build_ui(self):
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        root.set_margin_top(24)
        root.set_margin_start(32)
        root.set_margin_end(32)
        root.set_margin_bottom(24)
        scroll.set_child(root)
        self.append(scroll)
        self._root_box = root

        # Header with Logo
        header = Gtk.Box(spacing=15, valign=Gtk.Align.CENTER)
        self._header_box = header
        if os.path.exists(self.logo_path):
            from gi.repository import Gdk
            texture = Gdk.Texture.new_from_filename(self.logo_path)
            img = Gtk.Image.new_from_paintable(texture)
            img.set_pixel_size(48)
            header.append(img)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label=T("power_tuning"), xalign=0, css_classes=["title-1"])
        title_box.append(title)
        desc = Gtk.Label(label=T("power_tuning_desc"), xalign=0, css_classes=["dim-label"])
        title_box.append(desc)
        header.append(title_box)
        root.append(header)

        root.append(Gtk.Separator())

        # ── UNDERVOLT CARD ──
        uv_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        uv_card.add_css_class("card")
        self._uv_card = uv_card
        
        uv_header = Gtk.Box(spacing=10)
        uv_header.append(Gtk.Image.new_from_icon_name("system-run-symbolic"))
        uv_header.append(Gtk.Label(label=T("undervolt_label"), xalign=0, css_classes=["heading"]))
        uv_card.append(uv_header)

        uv_box = Gtk.Box(spacing=15)
        uv_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        uv_info.append(Gtk.Label(label=T("undervolt_label"), xalign=0, css_classes=["title-4"]))
        uv_info.append(Gtk.Label(label=T("undervolt_desc"), xalign=0, css_classes=["dim-label"], wrap=True))
        uv_box.append(uv_info)
        
        self.uv_spin = Gtk.SpinButton.new_with_range(-200, 0, 5)
        self.uv_spin.set_valign(Gtk.Align.CENTER)
        uv_box.append(self.uv_spin)
        uv_box.append(Gtk.Label(label="mV", valign=Gtk.Align.CENTER))
        uv_card.append(uv_box)
        
        root.append(uv_card)

        # ── TCC OFFSET CARD ──
        tcc_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        tcc_card.add_css_class("card")
        self._tcc_card = tcc_card
        
        tcc_header = Gtk.Box(spacing=10)
        tcc_header.append(Gtk.Image.new_from_icon_name("weather-clear-symbolic"))
        tcc_header.append(Gtk.Label(label=T("tcc_label"), xalign=0, css_classes=["heading"]))
        tcc_card.append(tcc_header)

        tcc_box = Gtk.Box(spacing=15)
        tcc_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        tcc_info.append(Gtk.Label(label=T("tcc_label"), xalign=0, css_classes=["title-4"]))
        tcc_info.append(Gtk.Label(label=T("tcc_desc"), xalign=0, css_classes=["dim-label"], wrap=True))
        tcc_box.append(tcc_info)
        
        self.tcc_spin = Gtk.SpinButton.new_with_range(0, 60, 1)
        self.tcc_spin.set_valign(Gtk.Align.CENTER)
        tcc_box.append(self.tcc_spin)
        tcc_card.append(tcc_box)
        
        root.append(tcc_card)

        # ── POWER LIMITS CARD ──
        pl_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        pl_card.add_css_class("card")
        self._pl_card = pl_card
        
        pl_header = Gtk.Box(spacing=10)
        pl_header.append(Gtk.Image.new_from_icon_name("battery-good-symbolic"))
        pl_header.append(Gtk.Label(label=T("power_limits_label"), xalign=0, css_classes=["heading"]))
        pl_card.append(pl_header)

        pl_sw_box = Gtk.Box(spacing=15)
        pl_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        pl_info.append(Gtk.Label(label=T("power_limits_label"), xalign=0, css_classes=["title-4"]))
        pl_info.append(Gtk.Label(label=T("power_limits_desc"), xalign=0, css_classes=["dim-label"], wrap=True))
        pl_sw_box.append(pl_info)
        self.pl_sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        pl_sw_box.append(self.pl_sw)
        pl_card.append(pl_sw_box)

        pl_card.append(Gtk.Separator())

        pl1_box = Gtk.Box(spacing=15)
        pl1_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        pl1_info.append(Gtk.Label(label=T("pl1_w"), xalign=0, css_classes=["title-4"]))
        pl1_box.append(pl1_info)
        self.pl1_spin = Gtk.SpinButton.new_with_range(15, 150, 5)
        self.pl1_spin.set_valign(Gtk.Align.CENTER)
        pl1_box.append(self.pl1_spin)
        pl1_box.append(Gtk.Label(label="W", valign=Gtk.Align.CENTER))
        pl_card.append(pl1_box)

        pl2_box = Gtk.Box(spacing=15)
        pl2_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        pl2_info.append(Gtk.Label(label=T("pl2_w"), xalign=0, css_classes=["title-4"]))
        pl2_box.append(pl2_info)
        self.pl2_spin = Gtk.SpinButton.new_with_range(15, 200, 5)
        self.pl2_spin.set_valign(Gtk.Align.CENTER)
        pl2_box.append(self.pl2_spin)
        pl2_box.append(Gtk.Label(label="W", valign=Gtk.Align.CENTER))
        pl_card.append(pl2_box)

        root.append(pl_card)

        # Footer Action
        footer = Gtk.Box(spacing=12, halign=Gtk.Align.END)
        self._footer_box = footer
        self.apply_btn = Gtk.Button(label=T("apply_power"))
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.connect("clicked", self._on_apply)
        footer.append(self.apply_btn)
        root.append(footer)

        self._sync_state()
        self.set_ui_scale("normal")

    def set_ui_scale(self, bucket, _width=0, _height=0):
        root = getattr(self, "_root_box", None)
        if root is not None:
            if bucket == "compact":
                root.set_spacing(16)
                root.set_margin_top(12)
                root.set_margin_start(14)
                root.set_margin_end(14)
                root.set_margin_bottom(12)
            elif bucket == "spacious":
                root.set_spacing(28)
                root.set_margin_top(30)
                root.set_margin_start(40)
                root.set_margin_end(40)
                root.set_margin_bottom(28)
            else:
                root.set_spacing(24)
                root.set_margin_top(24)
                root.set_margin_start(32)
                root.set_margin_end(32)
                root.set_margin_bottom(24)

        if hasattr(self, "_header_box") and self._header_box is not None:
            self._header_box.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)

        if hasattr(self, "_uv_card") and self._uv_card is not None:
            self._uv_card.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)

        if hasattr(self, "_tcc_card") and self._tcc_card is not None:
            self._tcc_card.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)

        if hasattr(self, "_pl_card") and self._pl_card is not None:
            self._pl_card.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)

        if hasattr(self, "apply_btn") and self.apply_btn is not None:
            self.apply_btn.set_size_request(150 if bucket == "compact" else 210 if bucket == "spacious" else 180, 38 if bucket == "compact" else 46 if bucket == "spacious" else 42)

    def _sync_state(self):
        if not self.service: return
        try:
            raw = self.service.GetPowerProfile()
            st = json.loads(raw)
            self.uv_spin.set_value(st.get("undervolt_mv", 0))
            self.tcc_spin.set_value(st.get("tcc_offset", 0))
            self.pl_sw.set_active(st.get("pl_enabled", False))
            self.pl1_spin.set_value(st.get("pl1_w", 45))
            self.pl2_spin.set_value(st.get("pl2_w", 80))
        except Exception: pass

    def _on_apply(self, btn):
        if not self.service: return
        uv = int(self.uv_spin.get_value())
        tcc = int(self.tcc_spin.get_value())
        pl_en = self.pl_sw.get_active()
        pl1 = int(self.pl1_spin.get_value())
        pl2 = int(self.pl2_spin.get_value())
        
        try:
            self.service.SetUndervolt(uv)
            self.service.SetTccOffset(tcc)
            self.service.SetPowerLimits(pl_en, pl1, pl2)
            
            toast = Gtk.MessageDialog(
                transient_for=self.get_root(),
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=T("power_applied")
            )
            toast.connect("response", lambda r, id: r.destroy())
            toast.present()
        except Exception as e:
            print(f"Apply power tuning failed: {e}")

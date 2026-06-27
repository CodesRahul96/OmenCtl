#!/usr/bin/env python3
"""
Centralized i18n module for OMEN Command Center for Linux.
This module is imported by all pages — never run as __main__,
so there's only one copy of active_lang in memory.
"""

import os as _os


def _detect_system_lang():
    """Detect the system language from environment variables."""
    for var in ("LC_MESSAGES", "LC_ALL", "LANG", "LANGUAGE"):
        val = _os.environ.get(var, "")
        if val:
            code = val.split(".")[0].split("_")[0].lower()
            if code.startswith("tr"):
                return "tr"
            if code.startswith("hi"):
                return "hi"
            if code.startswith("en"):
                return "en"
            # If it's a known code but not tr/hi/en, default to English
            if code:
                return "en"
    return "en"


active_lang = _detect_system_lang()

TRANSLATIONS = {
    "tr": {
        # Nav
        "fan": "Performans",
        "lighting": "Aydınlatma", "mux": "MUX", "settings": "Ayarlar",
        "keyboard": "Kısayollar",
        # Fan page
        "fan_control": "Fan Kontrolü", "system_status": "SİSTEM DURUMU",
        "power_profile": "GÜÇ PROFİLİ", "fan_mode": "FAN MODU",
        "fan_curve": "FAN EĞRİSİ", "all_sensors": "Tüm Sensörler",
        "fan_disabled": "Fan kontrolü devre dışı",
        "checking": "Kontrol ediliyor...", "no_ppd": "PPD yok",
        "active_profile": "Aktif profil", "mode": "Mod",
        "active": "Aktif", "inactive": "Pasif",
        "saver": "Tasarruf", "balanced": "Dengeli", "performance": "Performans",
        "auto": "Otomatik", "max": "Maksimum", "custom": "Özel", "standard": "Standart",
        "curve_desc": "Noktaları sürükleyerek fan eğrisini özelleştirin. X: Sıcaklık (°C), Y: Fan Hızı (%)",
        "no_sensor": "Sensör verisi bulunamadı",
        # Lighting page
        "keyboard_lighting": "Klavye Aydınlatma", "keyboard_light": "KLAVYE IŞIĞI",
        "zone": "Bölge", "all_zones": "Tümü",
        "effect": "EFEKT", "direction": "YÖN", "speed": "HIZ", "brightness": "PARLAKLIK",
        "static_eff": "Sabit", "breathing": "Nefes Alma", "wave": "Dalga", "cycle": "Renk Döngüsü",
        "ltr": "Sol → Sağ", "rtl": "Sağ → Sol",
        "win_lock": "Süper Tuş Kilidi",
        "rgb_not_supported": "RGB Aydınlatma Desteklenmiyor",
        "rgb_not_supported_desc": "Bu cihaz RGB klavye aydınlatmasını desteklememektedir. Tek renkli klavye aydınlatması donanım tarafından kontrol edilir (örn. Fn + Boşluk veya F4 kısayolu).",
        "backlight_active": "Klavye Işığı Açık",
        "backlight_off": "Klavye Işığı Kapalı",
        "backlight_note": "Not: Eğer yazılımsal anahtar çalışmazsa, lütfen fiziksel [Fn + F4] tuş kombinasyonunu kullanın.",
        "theme_default": "Tema Değişmesin",
        "theme_dark": "Koyu Tema",
        "theme_light": "Açık Tema",
        # Keyboard page
        "keyboard_shortcuts": "Kısayollar", "special_keys": "ÖZEL TUŞLAR",
        "omen_key": "Omen Tuşu", "victus_key": "Omen Tuşu",
        "calc_key": "Hesap Makinesi", "prt_sc_fix": "Print Screen (PrtSc) Düzelt",
        "prt_sc_desc": "PrtSc tuşunun ekran alıntısı aracı yerine gerçek 'Print Screen' olarak çalışmasını sağlar (Büyük kolaylık!).",
        "f1_fix": "F1 (Sunum) Tuşunu Düzelt",
        "f1_desc": "F1 tuşunun Super+P (Sunum modu) yerine standart F1 olarak çalışmasını sağlar.",
        "apply_shortcuts": "Değişiklikleri Uygula",
        "shortcuts_desc": "Laptopunuzdaki bazı tuşların davranışlarını buradan kalıcı olarak değiştirebilirsiniz.",
        "hwdb_applied": "Klavye düzeltmeleri başarıyla uygulandı.",
        # MUX page
        "mux_switch": "MUX Anahtarlayıcı", "gpu_info": "GPU BİLGİSİ",
        "gpu_card": "Ekran Kartı", "driver_ver": "Sürücü Sürümü",
        "gpu_mode": "GPU MODU", "hybrid": "Hibrit", "discrete": "Harici GPU",
        "integrated": "Dahili GPU",
        "hybrid_desc": "NVIDIA Optimus (Hibrit)", "discrete_desc": "NVIDIA GeForce RTX",
        "integrated_desc": "Intel Iris Xe / AMD Radeon Graphics",
        "gpu_checking": "GPU modu kontrol ediliyor...",
        "restart_warn": "GPU modunu değiştirmek için sistem yeniden başlatılmalıdır.",
        "mux_not_found": "MUX aracı bulunamadı",
        "mux_install_hint": "envycontrol, supergfxctl veya prime-select yüklü olmalıdır.",
        "restart": "Yeniden Başlat",
        "restart_confirm": "GPU modunu '{mode}' olarak değiştirmek için sistem yeniden başlatılacak. Devam edilsin mi?",
        "mode_set": "Mod '{mode}' olarak ayarlandı. Yeniden başlatılıyor...",
        "mux_backend_label": "MUX Aracı (Backend)", "mux_auto": "Otomatik Algıla",
        # Settings page
        "appearance": "GÖRÜNÜM", "theme": "Tema", "lang_label": "Dil / Language",
        "dark": "Koyu", "light": "Açık", "system": "Sistem Uyarlanır",
        "updates": "GÜNCELLEMELER", "current_ver": "Mevcut sürüm",
        # Dashboard
        "dashboard": "Gösterge Paneli", "quick_status": "Hızlı Durum",
        "hardware_profile": "Donanım Profili", "resources": "Kaynak Kullanımı",
        "quick_actions": "Hızlı Aksiyonlar", "clean_memory": "Belleği Temizle",
        "max_fan": "Turbo Fan", "eco_mode": "Eko Modu",
        "go_performance": "Performans sekmesine git",
        "fan_metric": "Fan",
        "disk": "Disk", "ram": "RAM",
        "cpu_load_30s": "CPU Yükü (Son 30 sn)",
        "power_profile_label": "Güç Profili", "fan_mode_label": "Fan Modu",
        "gpu_mux_label": "GPU / MUX",
        "battery": "Batarya", "ac_power": "Güç Kablosu",
        "health": "Sağlık",
        "power_saver_lbl": "Enerji Tasarrufu",
        "balanced_lbl": "Dengeli", "performance_lbl": "Performans",
        "check_update": "Güncelleme Kontrol Et", "download": "İndir",
        "sys_info": "SİSTEM BİLGİSİ",
        "computer": "Bilgisayar", "kernel": "Çekirdek",
        "os_name": "İşletim Sistemi", "arch": "Mimari",
        "driver_status": "SÜRÜCÜ DURUMU",
        "loaded": "✓ Yüklü", "not_loaded": "✗ Yüklü Değil",
        "developer": "Geliştirici",
        "home_subtitle": "Modül seçerek devam edin",
        "debug_info_title": "Tanılama ve Hata Ayıklama",
        "show_debug_info": "Hata Ayıklama Bilgilerini Göster",
        "copy_debug_log": "Tanı Bilgilerini Kopyala",
        "copied_to_clipboard": "Panoya kopyalandı",
        "debug_console_title": "Sistem Tanı Konsolu",
        "debug_collecting": "Sistem bilgileri toplanıyor...\nWMI bağlantısı kuruluyor...\nDMI tabloları okunuyor...\nKernel logları analiz ediliyor...\n\nLütfen bekleyin...",
        "disclaimer": "Bu aracın <b>Hewlett Packard</b> ile resmi bir bağlantısı bulunmamaktadır.",
        "update_checking": "Kontrol ediliyor...",
        "new_ver_available": "Yeni sürüm mevcut",
        "up_to_date": "Güncel", "conn_failed": "Bağlantı sağlanamadı",
        "error": "Hata",
        "install_update": "Güncellemeyi Kur",
        "downloading_update": "İndiriliyor...",
        "installing_update": "Kuruluyor...",
        "update_success": "Güncelleme başarıyla kuruldu! Uygulamayı yeniden başlatın.",
        "update_failed": "Güncelleme başarısız",
        "restart_app": "Uygulamayı Yeniden Başlat",

        # Temperature unit
        "temp_unit": "Sıcaklık Birimi", "celsius": "Celsius (°C)", "fahrenheit": "Fahrenheit (°F)",
        # Custom App Profiles
        "app_profiles": "Uygulama Profilleri",
        "app_profiles_desc": "Belirli uygulamalar çalışırken güç profilini otomatik olarak değiştirin.",
        "no_profiles": "Yapılandırılmış uygulama profili yok.",
        "app_name": "Uygulama İşlem Adı",
        "add": "Ekle", "delete": "Sil",
        "placeholder_app": "örn. android-studio",
        "category": "Kategori",
        "game": "Oyun", "program": "Program", "other": "Diğer",
        "fan_default": "Varsayılan Fan", "fan_auto": "Otomatik Fan", "fan_max": "Maks Fan",
        "theme_label": "Tema", "theme_default": "Tema Değişmesin", "theme_dark": "Koyu Tema", "theme_light": "Açık Tema",
        # Fan curve widget
        "temp_axis": "Sıcaklık (°C)", "fan_speed_axis": "Fan Hızı (%)",
        # Sensor categories
        "other_sensors": "Diğer",
        # Profile tooltips
        "saver_tooltip": "Maksimum pil ömrü için enerji tasarrufu sağlar. (Düşük Güç Limitleri)",
        "balanced_tooltip": "Güç ve tasarruf arasında denge kurar. (Optimize Güç Limitleri)",
        "performance_tooltip": "Tüm limitleri kaldırır ve en yüksek performansı almanızı sağlar.",
        "power_managed_by": "Güç modu {tool} tarafından yönetilmektedir.",
        "managed_by_app_profile": "🎮 Profil Yönetiminde: {app} — Performans değiştirilemez.",
        "rgb_default": "Aydınlatma Değişmesin",
        "rgb_static_red": "Kırmızı Aydınlatma",
        "rgb_static_green": "Yeşil Aydınlatma",
        "rgb_static_blue": "Mavi Aydınlatma",
        "rgb_static_white": "Beyaz Aydınlatma",
        "rgb_breathing": "Nefes Alma Efekti",
        "rgb_cycle": "Renk Döngüsü Efekti",
        "rgb_wave": "Renk Dalgası Efekti",
    },
    "en": {
        # Nav
        "fan": "Performance",
        "lighting": "Lighting", "mux": "MUX", "settings": "Settings",
        "keyboard": "Shortcuts",
        # Fan page
        "fan_control": "Fan Control", "system_status": "SYSTEM STATUS",
        "power_profile": "POWER PROFILE", "fan_mode": "FAN MODE",
        "fan_curve": "FAN CURVE", "all_sensors": "All Sensors",
        "fan_disabled": "Fan control unavailable",
        "checking": "Checking...", "no_ppd": "No PPD",
        "active_profile": "Active profile", "mode": "Mode",
        "active": "Active", "inactive": "Inactive",
        "saver": "Power Saver", "balanced": "Balanced", "performance": "Performance",
        "auto": "Automatic", "max": "Maximum", "custom": "Custom", "standard": "Standard",
        "curve_desc": "Drag points to customize fan curve. X: Temperature (°C), Y: Fan Speed (%)",
        "no_sensor": "No sensor data found",
        # Lighting page
        "keyboard_lighting": "Keyboard Lighting", "keyboard_light": "KEYBOARD LIGHT",
        "zone": "Zone", "all_zones": "All",
        "effect": "EFFECT", "direction": "DIRECTION", "speed": "SPEED", "brightness": "BRIGHTNESS",
        "static_eff": "Static", "breathing": "Breathing", "wave": "Wave", "cycle": "Cycle",
        "ltr": "Left → Right", "rtl": "Right → Left",
        "win_lock": "Super Key Lock",
        "rgb_not_supported": "RGB Lighting Not Supported",
        "rgb_not_supported_desc": "This device does not support RGB keyboard backlighting. Single-color backlighting is managed by the hardware directly (e.g. via Fn + Space or F4 shortcut).",
        "backlight_active": "Keyboard Backlight Active",
        "backlight_off": "Keyboard Backlight Off",
        "backlight_note": "Note: If the software switch has no effect, please use the physical [Fn + F4] key combination.",
        "theme_default": "No Change",
        "theme_dark": "Force Dark",
        "theme_light": "Force Light",
        # Keyboard page
        "keyboard_shortcuts": "Shortcuts", "special_keys": "SPECIAL KEYS",
        "omen_key": "Omen Key", "victus_key": "Omen Key",
        "calc_key": "Calculator Key", "prt_sc_fix": "Fix Print Screen (PrtSc)",
        "prt_sc_desc": "Makes PrtSc key work as real Print Screen instead of triggering Screenshot Tool.",
        "f1_fix": "Fix F1 (Presentation) Key",
        "f1_desc": "Makes F1 key work as standard F1 instead of Super+P (Presentation mode).",
        "apply_shortcuts": "Apply Changes",
        "shortcuts_desc": "You can permanently change the behavior of certain keys on your laptop here.",
        "hwdb_applied": "Keyboard fixes have been applied successfully.",
        # MUX page
        "mux_switch": "MUX Switch", "gpu_info": "GPU INFO",
        "gpu_card": "Graphics Card", "driver_ver": "Driver Version",
        "gpu_mode": "GPU MODE", "hybrid": "Hybrid", "discrete": "Discrete GPU",
        "integrated": "Integrated GPU",
        "hybrid_desc": "NVIDIA Optimus (Hybrid)", "discrete_desc": "NVIDIA GeForce RTX",
        "integrated_desc": "Intel Iris Xe / AMD Radeon Graphics",
        "gpu_checking": "Checking GPU mode...",
        "restart_warn": "System restart required to change GPU mode.",
        "mux_not_found": "MUX tool not found",
        "mux_install_hint": "envycontrol, supergfxctl or prime-select must be installed.",
        "restart": "Restart",
        "restart_confirm": "System will restart to change GPU mode to '{mode}'. Continue?",
        "mode_set": "Mode set to '{mode}'. Restarting...",
        "mux_backend_label": "MUX Backend Tool", "mux_auto": "Auto Detect",
        # Settings page
        "appearance": "APPEARANCE", "theme": "Theme", "lang_label": "Language",
        "dark": "Dark", "light": "Light", "system": "System Default",
        "updates": "UPDATES", "current_ver": "Current version",
        # Dashboard
        "dashboard": "Dashboard", "quick_status": "Quick Status",
        "hardware_profile": "Hardware Profile", "resources": "Resources",
        "quick_actions": "Quick Actions", "clean_memory": "Clean Memory",
        "max_fan": "MAX Fan", "eco_mode": "Eco Mode",
        "go_performance": "Go to Performance",
        "fan_metric": "Fan",
        "disk": "Disk", "ram": "RAM",
        "cpu_load_30s": "CPU Load (Last 30s)",
        "power_profile_label": "Power Profile", "fan_mode_label": "Fan Mode",
        "gpu_mux_label": "GPU / MUX",
        "battery": "Battery", "ac_power": "Power Cable",
        "health": "Health",
        "power_saver_lbl": "Power Saver",
        "balanced_lbl": "Balanced", "performance_lbl": "Performance",
        "check_update": "Check for Updates", "download": "Download",
        "sys_info": "SYSTEM INFO",
        "computer": "Computer", "kernel": "Kernel",
        "os_name": "Operating System", "arch": "Architecture",
        "driver_status": "DRIVER STATUS",
        "loaded": "✓ Loaded", "not_loaded": "✗ Not Loaded",
        "developer": "Developer",
        "home_subtitle": "Choose a module to continue",
        "debug_info_title": "Diagnostic and Debug",
        "show_debug_info": "Show Debug Info",
        "copy_debug_log": "Copy Debug Info",
        "copied_to_clipboard": "Copied to clipboard",
        "debug_console_title": "System Diagnostic Console",
        "debug_collecting": "Gathering system information...\nConnecting to WMI...\nReading DMI tables...\nAnalyzing kernel logs...\n\nPlease wait...",
        "disclaimer": "This tool has no official affiliation with <b>Hewlett Packard</b>.",
        "update_checking": "Checking...",
        "new_ver_available": "New version available",
        "up_to_date": "Up to date", "conn_failed": "Connection failed",
        "error": "Error",
        "install_update": "Install Update",
        "downloading_update": "Downloading...",
        "installing_update": "Installing...",
        "update_success": "Update installed successfully! Please restart the application.",
        "update_failed": "Update failed",
        "restart_app": "Restart Application",

        # Temperature unit
        "temp_unit": "Temperature Unit", "celsius": "Celsius (°C)", "fahrenheit": "Fahrenheit (°F)",
        # Custom App Profiles
        "app_profiles": "App Profiles",
        "app_profiles_desc": "Automatically switch power profiles when specific applications are running.",
        "no_profiles": "No app profiles configured.",
        "app_name": "App Process Name",
        "add": "Add", "delete": "Delete",
        "placeholder_app": "e.g. android-studio",
        "category": "Category",
        "game": "Game", "program": "Program", "other": "Other",
        "fan_default": "Default Fan", "fan_auto": "Auto Fan", "fan_max": "Max Fan",
        "theme_label": "Theme", "theme_default": "No Change", "theme_dark": "Force Dark", "theme_light": "Force Light",
        # Fan curve widget
        "temp_axis": "Temperature (°C)", "fan_speed_axis": "Fan Speed (%)",
        # Sensor categories
        "other_sensors": "Other",
        # Profile tooltips
        "saver_tooltip": "Maximum battery life with reduced power limits.",
        "balanced_tooltip": "Balance between power and efficiency.",
        "performance_tooltip": "Remove all power limits for maximum performance.",
        "power_managed_by": "Power mode is managed by {tool}.",
        "managed_by_app_profile": "🎮 App Profile Active: {app} — Performance settings locked.",
        "rgb_default": "No RGB Change",
        "rgb_static_red": "Static Red",
        "rgb_static_green": "Static Green",
        "rgb_static_blue": "Static Blue",
        "rgb_static_white": "Static White",
        "rgb_breathing": "Breathing Mode",
        "rgb_cycle": "Color Cycle Mode",
        "rgb_wave": "Wave Mode",
    },
    "hi": {
        # Nav
        "fan": "प्रदर्शन",
        "lighting": "लाइटिंग", "mux": "मक्स", "settings": "सेटिंग्स",
        "keyboard": "शॉर्टकट",
        # Fan page
        "fan_control": "फैन कंट्रोल", "system_status": "सिस्टम की स्थिति",
        "power_profile": "पावर प्रोफाइल", "fan_mode": "फैन मोड",
        "fan_curve": "फैन कर्व", "all_sensors": "सभी सेंसर",
        "fan_disabled": "फैन कंट्रोल उपलब्ध नहीं है",
        "checking": "जाँच की जा रही है...", "no_ppd": "कोई PPD नहीं",
        "active_profile": "सक्रिय प्रोफाइल", "mode": "मोड",
        "active": "सक्रिय", "inactive": "निष्क्रिय",
        "saver": "पावर सेवर", "balanced": "संतुलित", "performance": "प्रदर्शन",
        "auto": "स्वचालित", "max": "अधिकतम", "custom": "कस्टम", "standard": "मानक",
        "curve_desc": "फैन वक्र को अनुकूलित करने के लिए बिंदुओं को खींचें। X: तापमान (°C), Y: फैन गति (%)",
        "no_sensor": "कोई सेंसर डेटा नहीं मिला",
        # Lighting page
        "keyboard_lighting": "कीबोर्ड लाइटिंग", "keyboard_light": "कीबोर्ड लाइट",
        "zone": "ज़ोन", "all_zones": "सभी",
        "effect": "प्रभाव", "direction": "दिशा", "speed": "गति", "brightness": "चमक",
        "static_eff": "स्थिर", "breathing": "साँस लेना", "wave": "लहर", "cycle": "चक्र",
        "ltr": "बाएं → दाएं", "rtl": "दाएं → बाएं",
        "win_lock": "सुपर की लॉक",
        "rgb_not_supported": "RGB लाइटिंग समर्थित नहीं है",
        "rgb_not_supported_desc": "यह डिवाइस RGB कीबोर्ड बैकलाइट का समर्थन नहीं करता है। सिंगल-कलर बैकलाइट को सीधे हार्डवेयर द्वारा नियंत्रित किया जाता है (जैसे Fn + स्पेस या F4 शॉर्टकट के माध्यम से)।",
        "backlight_active": "कीबोर्ड बैकलाइट सक्रिय",
        "backlight_off": "कीबोर्ड बैकलाइट बंद",
        "backlight_note": "नोट: यदि सॉफ़्टवेयर स्विच का कोई प्रभाव नहीं पड़ता है, तो कृपया भौतिक [Fn + F4] कुंजी संयोजन का उपयोग करें।",
        "theme_default": "कोई बदलाव नहीं",
        "theme_dark": "डार्क थीम",
        "theme_light": "लाइट थीम",
        # Keyboard page
        "keyboard_shortcuts": "शॉर्टकट", "special_keys": "विशेष कुंजियाँ",
        "omen_key": "ओमेन की", "victus_key": "ओमेन की",
        "calc_key": "कैलकुलेटर की", "prt_sc_fix": "प्रिंट स्क्रीन (PrtSc) ठीक करें",
        "prt_sc_desc": "स्क्रीनशॉट टूल को ट्रिगर करने के बजाय PrtSc कुंजी को वास्तविक प्रिंट स्क्रीन के रूप में काम कराता है।",
        "f1_fix": "F1 (प्रेजेंटेशन) की ठीक करें",
        "f1_desc": "F1 कुंजी को Super+P (प्रेजेंटेशन मोड) के बजाय मानक F1 के रूप में काम कराता है।",
        "apply_shortcuts": "बदलाव लागू करें",
        "shortcuts_desc": "आप यहाँ अपने लैपटॉप पर कुछ कुंजियों के व्यवहार को स्थायी रूप से बदल सकते हैं।",
        "hwdb_applied": "कीबोर्ड सुधार सफलतापूर्वक लागू किए गए हैं।",
        # MUX page
        "mux_switch": "मक्स स्विच", "gpu_info": "GPU जानकारी",
        "gpu_card": "ग्राफिक्स कार्ड", "driver_ver": "ड्राइवर संस्करण",
        "gpu_mode": "GPU मोड", "hybrid": "हाइब्रिड", "discrete": "डिक्रीट GPU",
        "integrated": "एकीकृत GPU",
        "hybrid_desc": "NVIDIA ऑप्टिमस (हाइब्रिड)", "discrete_desc": "NVIDIA GeForce RTX",
        "integrated_desc": "Intel Iris Xe / AMD Radeon Graphics",
        "gpu_checking": "GPU मोड की जाँच की जा रही है...",
        "restart_warn": "GPU मोड बदलने के लिए सिस्टम को रीस्टार्ट करना आवश्यक है।",
        "mux_not_found": "मक्स टूल नहीं मिला",
        "mux_install_hint": "envycontrol, supergfxctl या prime-select स्थापित होना चाहिए।",
        "restart": "रीस्टार्ट करें",
        "restart_confirm": "GPU मोड को '{mode}' में बदलने के लिए सिस्टम रीस्टार्ट होगा। जारी रखें?",
        "mode_set": "मोड '{mode}' पर सेट किया गया। रीस्टार्ट हो रहा है...",
        "mux_backend_label": "मक्स बैकएंड टूल", "mux_auto": "ऑटो डिटेक्ट",
        # Settings page
        "appearance": "सजावट", "theme": "थीम", "lang_label": "भाषा / Language",
        "dark": "डार्क", "light": "लाइट", "system": "सिस्टम अनुकूलित",
        "updates": "अपडेट", "current_ver": "वर्तमान संस्करण",
        # Dashboard
        "dashboard": "डैशबोर्ड", "quick_status": "त्वरित स्थिति",
        "hardware_profile": "हार्डवेयर प्रोफ़ाइल", "resources": "संसाधन",
        "quick_actions": "त्वरित कार्रवाई", "clean_memory": "मेमोरी साफ़ करें",
        "max_fan": "टर्बो फैन", "eco_mode": "इको मोड",
        "go_performance": "प्रदर्शन पर जाएं",
        "fan_metric": "फैन",
        "disk": "डिस्क", "ram": "रैम",
        "cpu_load_30s": "CPU लोड (अंतिम 30 सेकंड)",
        "power_profile_label": "पावर प्रोफाइल", "fan_mode_label": "फैन मोड",
        "gpu_mux_label": "GPU / मक्स",
        "battery": "बैटरी", "ac_power": "पावर केबल",
        "health": "स्वास्थ्य",
        "power_saver_lbl": "पावर सेवर",
        "balanced_lbl": "संतुलित", "performance_lbl": "प्रदर्शन",
        "check_update": "अपडेट के लिए जाँच करें", "download": "डाउनलोड करें",
        "sys_info": "सिस्टम जानकारी",
        "computer": "कंप्यूटर", "kernel": "कर्नेल",
        "os_name": "ऑपरेटिंग सिस्टम", "arch": "आर्किटेक्चर",
        "driver_status": "ड्राइवर स्थिति",
        "loaded": "✓ लोड किया गया", "not_loaded": "✗ लोड नहीं किया गया",
        "developer": "डेवलपर",
        "home_subtitle": "जारी रखने के लिए एक मोड्यूल चुनें",
        "debug_info_title": "निदान और डिबग",
        "show_debug_info": "डिबग जानकारी दिखाएं",
        "copy_debug_log": "डिबग जानकारी कॉपी करें",
        "copied_to_clipboard": "क्लिपबोर्ड पर कॉपी किया गया",
        "debug_console_title": "सिस्टम निदान कंसोल",
        "debug_collecting": "सिस्टम जानकारी एकत्रित की जा रही है...\nWMI से कनेक्ट किया जा रहा है...\nDMI टेबल पढ़े जा रहे हैं...\nकर्नेल लॉग का विश्लेषण किया जा रहा है...\n\nकृपया प्रतीक्षा करें...",
        "disclaimer": "इस टूल का <b>Hewlett Packard</b> से कोई आधिकारिक संबंध नहीं है।",
        "update_checking": "जाँच की जा रही है...",
        "new_ver_available": "नया संस्करण उपलब्ध है",
        "up_to_date": "अद्यतित (Up to date)", "conn_failed": "कनेक्शन विफल रहा",
        "error": "त्रुटि",
        "install_update": "अपडेट स्थापित करें",
        "downloading_update": "डाउनलोड किया जा रहा है...",
        "installing_update": "स्थापित किया जा रहा है...",
        "update_success": "अपडेट सफलतापूर्वक स्थापित हो गया! कृपया एप्लिकेशन रीस्टार्ट करें।",
        "update_failed": "अपडेट विफल रहा",
        "restart_app": "एप्लिकेशन रीस्टार्ट करें",

        # Temperature unit
        "temp_unit": "तापमान इकाई", "celsius": "सेल्सियस (°C)", "fahrenheit": "फ़ारेनहाइट (°F)",
        # Custom App Profiles
        "app_profiles": "एप्लिकेशन प्रोफाइल",
        "app_profiles_desc": "विशिष्ट एप्लिकेशन चलने पर स्वचालित रूप से पावर प्रोफाइल बदलें।",
        "no_profiles": "कोई एप्लिकेशन प्रोफाइल कॉन्फ़िगर नहीं किया गया है।",
        "app_name": "एप्लिकेशन प्रोसेस नाम",
        "add": "जोड़ें", "delete": "हटाएं",
        "placeholder_app": "उदा. android-studio",
        "category": "श्रेणी",
        "game": "खेल", "program": "कार्यक्रम", "other": "अन्य",
        "fan_default": "डिफ़ॉल्ट फैन", "fan_auto": "ऑटो फैन", "fan_max": "अधिकतम फैन",
        "theme_label": "थीम", "theme_default": "कोई बदलाव नहीं", "theme_dark": "डार्क थीम", "theme_light": "लाइट थीम",
        # Fan curve widget
        "temp_axis": "तापमान (°C)", "fan_speed_axis": "फैन गति (%)",
        # Sensor categories
        "other_sensors": "अन्य",
        # Profile tooltips
        "saver_tooltip": "कम पावर लिमिट के साथ अधिकतम बैटरी लाइफ।",
        "balanced_tooltip": "पावर और दक्षता के बीच संतुलन।",
        "performance_tooltip": "अधिकतम प्रदर्शन के लिए सभी पावर लिमिट हटा दें।",
        "power_managed_by": "Power mode is managed by {tool}.",
        "managed_by_app_profile": "🎮 App Profile Active: {app} — Performance settings locked.",
        "rgb_default": "कोई बदलाव नहीं",
        "rgb_static_red": "लाल लाइट",
        "rgb_static_green": "हरी लाइट",
        "rgb_static_blue": "नीली लाइट",
        "rgb_static_white": "सफेद लाइट",
        "rgb_breathing": "साँस लेने का मोड",
        "rgb_cycle": "कलर चक्र मोड",
        "rgb_wave": "वेव मोड",
    },
}


def T(key):
    """Get translation for key using current active_lang."""
    return TRANSLATIONS.get(active_lang, TRANSLATIONS["en"]).get(key, key)


def set_lang(lang):
    """Set the active language globally."""
    global active_lang
    normalized = str(lang or "").strip().lower()
    if not normalized:
        # No explicit language — keep current (auto-detected) setting
        return
    if normalized.startswith("tr") or "türk" in normalized or "turk" in normalized:
        active_lang = "tr"
        return
    if normalized.startswith("hi") or "hindi" in normalized:
        active_lang = "hi"
        return
    if normalized.startswith("en") or "english" in normalized:
        active_lang = "en"
        return
    active_lang = normalized if normalized in TRANSLATIONS else _detect_system_lang()


def get_lang():
    """Get the current active language."""
    return active_lang

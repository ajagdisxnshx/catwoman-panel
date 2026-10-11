import os
import json

# مسیر فایل تنظیمات داینامیک
SETTINGS_FILE = "/app/data/settings.json"

# تنظیمات پیش‌فرض
DEFAULT_SETTINGS = {
    "admin_username": "admin",
    "admin_password": "admin",
    "telegram_bot_token": "",
    "telegram_admin_id": "",
    "telegram_bot_enabled": False
}

def load_settings():
    """بارگذاری تنظیمات از فایل"""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=2)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            for k, v in DEFAULT_SETTINGS.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """ذخیره تنظیمات"""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

# تنظیمات اولیه - خوانده میشن از فایل
_settings = load_settings()
ADMIN_USERNAME = _settings["admin_username"]
ADMIN_PASSWORD = _settings["admin_password"]

# کلید رمزنگاری سشن
SECRET_KEY = "catwoman-super-secret-key-2024-navy-neon"

# تنظیمات Xray
XRAY_CONFIG_PATH = "/usr/local/etc/xray/config.json"
XRAY_BINARY_PATH = "/usr/local/bin/xray"

# پورت داخلی
PANEL_PORT = 8000
XRAY_PORT = 10000

# نام پنل
PANEL_NAME = "CatWoman"

def get_admin_credentials():
    """دریافت نام کاربری و رمز فعلی از فایل"""
    s = load_settings()
    return s["admin_username"], s["admin_password"]

def update_admin_credentials(new_username, new_password):
    """بروزرسانی نام کاربری و رمز"""
    s = load_settings()
    s["admin_username"] = new_username
    s["admin_password"] = new_password
    save_settings(s)

def get_telegram_settings():
    """دریافت تنظیمات تلگرام"""
    s = load_settings()
    return {
        "token": s.get("telegram_bot_token", ""),
        "admin_id": s.get("telegram_admin_id", ""),
        "enabled": s.get("telegram_bot_enabled", False)
    }

def update_telegram_settings(token, admin_id, enabled):
    """بروزرسانی تنظیمات تلگرام"""
    s = load_settings()
    s["telegram_bot_token"] = token
    s["telegram_admin_id"] = admin_id
    s["telegram_bot_enabled"] = enabled
    save_settings(s)

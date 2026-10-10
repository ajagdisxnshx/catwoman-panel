import os

# تنظیمات ادمین
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "catwoman123")

# کلید رمزنگاری سشن
SECRET_KEY = os.getenv("SECRET_KEY", "catwoman-super-secret-key-2024")

# تنظیمات Xray
XRAY_CONFIG_PATH = "/usr/local/etc/xray/config.json"
XRAY_BINARY_PATH = "/usr/local/bin/xray"

# پورت داخلی
PANEL_PORT = 8000
XRAY_PORT = 10000

# نام پنل
PANEL_NAME = "CatWoman Panel 🐾"
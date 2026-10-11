import json
import os
import subprocess
import time
from config import XRAY_CONFIG_PATH, XRAY_BINARY_PATH, XRAY_PORT
from database import get_all_users

def generate_xray_config():
    """تولید فایل کانفیگ استاندارد Xray بر اساس کاربران فعال دیتابیس"""
    try:
        users = get_all_users()
    except Exception:
        users = []

    # فیلتر کاربران فعال
    clients = []
    for u in users:
        if u.get("status") == "active":
            clients.append({
                "id": u["uuid"],
                "flow": u.get("flow", ""),
                "email": u.get("username", "")
            })

    # اگر کاربر فعالی نبود یک کلاینت پیش‌فرض موقت قرار می‌گیرد تا هسته کرش نکند
    if not clients:
        clients.append({
            "id": "00000000-0000-0000-0000-000000000000",
            "email": "default_inactive"
        })

    config = {
        "log": {
            "loglevel": "warning"
        },
        "inbounds": [
            {
                "port": XRAY_PORT,
                "listen": "127.0.0.1",
                "protocol": "vless",
                "settings": {
                    "clients": clients,
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "ws",
                    "wsSettings": {
                        "path": "/catwoman-ws"
                    }
                }
            }
        ],
        "outbounds": [
            {
                "protocol": "freedom",
                "tag": "direct"
            },
            {
                "protocol": "blackhole",
                "tag": "block"
            }
        ]
    }

    # اطمینان از وجود پوشه کانفیگ
    os.makedirs(os.path.dirname(XRAY_CONFIG_PATH), exist_ok=True)
    
    with open(XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def is_xray_running():
    """بررسی وضعیت اجرای پروسه Xray"""
    try:
        res = subprocess.run(["pgrep", "-f", XRAY_BINARY_PATH], capture_output=True, text=True)
        return res.returncode == 0
    except Exception:
        return False


def restart_xray():
    """ری‌استارت هسته Xray بدون قطع پنل"""
    try:
        # بستن پروسه‌های قبلی در صورت وجود
        subprocess.run(["pkill", "-9", "-f", XRAY_BINARY_PATH], capture_output=True)
        time.sleep(0.5)

        # اجرای مجدد با کانفیگ جدید
        subprocess.Popen(
            [XRAY_BINARY_PATH, "run", "-config", XRAY_CONFIG_PATH],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        print(f"خطا در اجرای Xray: {e}")
        return False


def generate_vless_link(user, host):
    """ساخت لینک سابسکریپشن و اتصال VLESS WebSocket"""
    uuid = user.get("uuid")
    username = user.get("username", "user")
    return (
        f"vless://{uuid}@{host}:443"
        f"?encryption=none"
        f"&security=tls"
        f"&sni={host}"
        f"&type=ws"
        f"&host={host}"
        f"&path=%2Fcatwoman-ws"
        f"#{username}"
    )

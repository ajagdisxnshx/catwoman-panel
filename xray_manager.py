import json
import os
import subprocess
import time
from config import XRAY_CONFIG_PATH, XRAY_BINARY_PATH, XRAY_PORT
from database import get_all_users, update_traffic

def generate_xray_config():
    """تولید فایل کانفیگ استاندارد Xray به همراه سیستم مانیتورینگ ترافیک"""
    try:
        users = get_all_users()
    except Exception as e:
        print(f"خطا در خواندن کاربران: {e}")
        users = []

    # فیلتر کاربران فعال
    clients = []
    for u in users:
        u_dict = dict(u)
        if u_dict.get("status") == "active":
            clients.append({
                "id": u_dict.get("uuid"),
                "flow": u_dict.get("flow", ""),
                "email": u_dict.get("username", "")  # آمار در اکس‌ری بر اساس ایمیل فیلتر میشه
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
        "api": {
            "tag": "api",
            "services": [
                "StatsService"
            ]
        },
        "stats": {},
        "policy": {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True
                }
            },
            "system": {
                "statsInboundUplink": True,
                "statsInboundDownlink": True
            }
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
            },
            {
                "listen": "127.0.0.1",
                "port": 10085,
                "protocol": "dokodemo-door",
                "settings": {
                    "address": "127.0.0.1"
                },
                "tag": "api"
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
        ],
        "routing": {
            "rules": [
                {
                    "type": "field",
                    "inboundTag": [
                        "api"
                    ],
                    "outboundTag": "api"
                }
            ]
        }
    }

    # اضافه کردن اوت‌باند api مخصوص هسته
    config["outbounds"].append({
        "protocol": "api",
        "tag": "api"
    })

    # اطمینان از وجود پوشه کانفیگ
    os.makedirs(os.path.dirname(XRAY_CONFIG_PATH), exist_ok=True)
    
    with open(XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def collect_traffic_stats():
    """خوانش حجم مصرفی کلاینت‌ها از API داخلی اکس‌ری و به‌روزرسانی دیتابیس"""
    try:
        # فراخوانی API اکس‌ری برای گرفتن آمار مصرف و صفر کردن کنتور اکس‌ری (-reset)
        res = subprocess.run(
            [XRAY_BINARY_PATH, "api", "statsquery", "--server=127.0.0.1:10085", "-reset"],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode != 0:
            return  # هسته یا وب‌سرویس هنوز فعال نیستند

        data = json.loads(res.stdout)
        stats = data.get("stat", [])
        
        user_traffic = {}
        for s in stats:
            name = s.get("name", "")
            value = int(s.get("value", 0))
            if value <= 0:
                continue
            
            # فرمت آمار اکس‌ری: user>>>نام‌کاربری>>>traffic>>>downlink یا uplink
            if name.startswith("user>>>"):
                parts = name.split(">>>")
                if len(parts) >= 4:
                    username = parts[1]
                    user_traffic[username] = user_traffic.get(username, 0) + value

        if user_traffic:
            users = get_all_users()
            user_map = {u["username"]: u["id"] for u in users}
            
            for username, bytes_used in user_traffic.items():
                user_id = user_map.get(username)
                if user_id:
                    update_traffic(user_id, bytes_used)
                    
    except Exception as e:
        print(f"خطا در دریافت آمار ترافیک: {e}")


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
        subprocess.run(["pkill", "-9", "-f", XRAY_BINARY_PATH], capture_output=True)
        time.sleep(0.5)

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
    u_dict = dict(user)
    uuid = u_dict.get("uuid")
    username = u_dict.get("username", "user")
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

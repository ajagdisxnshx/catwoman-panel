import json
import os
import subprocess
import time
from config import XRAY_CONFIG_PATH, XRAY_BINARY_PATH, XRAY_PORT
from database import get_all_users, update_traffic

XRAY_API_PORT = 10085

def generate_xray_config():
    """تولید فایل کانفیگ Xray"""
    try:
        users = get_all_users()
    except Exception as e:
        print(f"خطا در خواندن کاربران: {e}")
        users = []

    clients = []
    for u in users:
        u_dict = dict(u)
        if u_dict.get("status") == "active":
            client_data = {
                "id": u_dict.get("uuid"),
                "email": u_dict.get("username", "")
            }
            if u_dict.get("flow"):
                client_data["flow"] = u_dict.get("flow")
            clients.append(client_data)

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
            "services": ["StatsService"]
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
                "tag": "vless-in",
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
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls"]
                }
            },
            {
                "tag": "api-in",
                "listen": "127.0.0.1",
                "port": XRAY_API_PORT,
                "protocol": "dokodemo-door",
                "settings": {
                    "address": "127.0.0.1"
                }
            }
        ],
        "outbounds": [
            {
                "tag": "direct",
                "protocol": "freedom",
                "settings": {}
            },
            {
                "tag": "block",
                "protocol": "blackhole",
                "settings": {}
            }
        ],
        "routing": {
            "rules": [
                {
                    "type": "field",
                    "inboundTag": ["api-in"],
                    "outboundTag": "api"
                }
            ]
        }
    }

    os.makedirs(os.path.dirname(XRAY_CONFIG_PATH), exist_ok=True)
    
    with open(XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def collect_traffic_stats():
    """خوانش ترافیک + ثبت کاربران آنلاین"""
    try:
        res = subprocess.run(
            [XRAY_BINARY_PATH, "api", "statsquery", 
             f"--server=127.0.0.1:{XRAY_API_PORT}", "-reset"],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode != 0:
            return

        data = json.loads(res.stdout)
        stats = data.get("stat", [])
        
        user_traffic = {}
        for s in stats:
            name = s.get("name", "")
            value = int(s.get("value", 0))
            if value <= 0:
                continue
            
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
    try:
        res = subprocess.run(["pgrep", "-f", XRAY_BINARY_PATH], 
                             capture_output=True, text=True)
        return res.returncode == 0
    except Exception:
        return False


def restart_xray():
    try:
        subprocess.run(["pkill", "-9", "-f", XRAY_BINARY_PATH], capture_output=True)
        time.sleep(0.5)

        subprocess.Popen(
            [XRAY_BINARY_PATH, "run", "-config", XRAY_CONFIG_PATH],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)
        return True
    except Exception as e:
        print(f"خطا در اجرای Xray: {e}")
        return False


def generate_vless_link(user, host):
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


def get_server_info():
    """دریافت اطلاعات سرور"""
    try:
        import psutil
        
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        boot_time = psutil.boot_time()
        uptime_seconds = int(time.time() - boot_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        uptime_str = f"{days}d {hours}h {minutes}m"
        
        return {
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "ram_used": mem.used,
            "ram_total": mem.total,
            "disk_percent": disk.percent,
            "disk_used": disk.used,
            "disk_total": disk.total,
            "uptime": uptime_str
        }
    except Exception as e:
        print(f"خطا در دریافت اطلاعات سرور: {e}")
        return {
            "cpu_percent": 0, "ram_percent": 0, "ram_used": 0, "ram_total": 0,
            "disk_percent": 0, "disk_used": 0, "disk_total": 0, "uptime": "N/A"
        }

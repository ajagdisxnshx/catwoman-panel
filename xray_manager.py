import json
import subprocess
import os
from config import XRAY_CONFIG_PATH, XRAY_BINARY_PATH, XRAY_PORT
from database import get_all_users

def generate_xray_config():
    """ساخت کانفیگ Xray بر اساس کاربران فعال"""
    users = get_all_users()
    
    clients = []
    for user in users:
        if user["status"] == "active":
            client = {
                "id": user["uuid"],
                "email": user["username"],
                "flow": user["flow"] if user["flow"] else ""
            }
            clients.append(client)
    
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
                    "clients": clients if clients else [{"id": "00000000-0000-0000-0000-000000000000", "email": "default"}],
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
                "tag": "blocked"
            }
        ]
    }
    
    os.makedirs(os.path.dirname(XRAY_CONFIG_PATH), exist_ok=True)
    with open(XRAY_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

def restart_xray():
    """ری‌استارت هسته Xray"""
    try:
        subprocess.run(["pkill", "-f", "xray"], capture_output=True)
    except:
        pass
    
    generate_xray_config()
    subprocess.Popen(
        [XRAY_BINARY_PATH, "run", "-c", XRAY_CONFIG_PATH],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def is_xray_running():
    """بررسی روشن بودن Xray"""
    try:
        result = subprocess.run(["pgrep", "-f", "xray"], capture_output=True)
        return result.returncode == 0
    except:
        return False

def generate_vless_link(user, host):
    """ساخت لینک VLESS برای کاربر"""
    return (
        f"vless://{user['uuid']}@{host}:443"
        f"?encryption=none&security=tls&type=ws"
        f"&path=%2Fcatwoman-ws"
        f"#{user['username']}"
    )
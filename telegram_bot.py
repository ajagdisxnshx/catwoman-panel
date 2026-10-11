import requests
import threading
import time
from config import get_telegram_settings
from database import get_all_users, get_stats, get_online_count

def format_bytes(bytes_val):
    if bytes_val == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while bytes_val >= 1024 and i < len(units) - 1:
        bytes_val /= 1024
        i += 1
    return f"{bytes_val:.2f} {units[i]}"

def send_message(token, chat_id, text, reply_markup=None):
    """ارسال پیام تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"خطا در ارسال پیام تلگرام: {e}")
        return None

def test_bot_connection(token, admin_id):
    """تست اتصال ربات"""
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("ok"):
            bot_name = data["result"]["username"]
            send_message(token, admin_id, 
                f"✅ <b>اتصال ربات موفقیت‌آمیز بود!</b>\n\n"
                f"🤖 نام ربات: @{bot_name}\n"
                f"🎉 پنل CatWoman به ربات متصل شد")
            return True, bot_name
        return False, "Token نامعتبر است"
    except Exception as e:
        return False, str(e)

def get_main_keyboard():
    """کیبورد اصلی ربات"""
    return {
        "keyboard": [
            [{"text": "📊 وضعیت سرور"}, {"text": "👥 لیست کاربران"}],
            [{"text": "🟢 کاربران آنلاین"}, {"text": "📈 آمار پنل"}]
        ],
        "resize_keyboard": True
    }

def handle_update(update, token, admin_id):
    """پردازش پیام‌های ربات"""
    try:
        if "message" not in update:
            return
        msg = update["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "")
        
        # فقط ادمین
        if chat_id != str(admin_id):
            send_message(token, chat_id, "⛔ شما ادمین نیستید!")
            return
        
        if text == "/start":
            send_message(token, chat_id, 
                "🐱 <b>به ربات پنل CatWoman خوش آمدید</b>\n\n"
                "از دکمه‌های زیر استفاده کنید:",
                reply_markup=get_main_keyboard())
        
        elif text == "📊 وضعیت سرور":
            try:
                from xray_manager import get_server_info, is_xray_running
                info = get_server_info()
                status = "🟢 فعال" if is_xray_running() else "🔴 خاموش"
                send_message(token, chat_id,
                    f"<b>📊 وضعیت سرور</b>\n\n"
                    f"🔧 هسته Xray: {status}\n"
                    f"⚡ CPU: {info['cpu_percent']}%\n"
                    f"💾 RAM: {info['ram_percent']}% ({format_bytes(info['ram_used'])}/{format_bytes(info['ram_total'])})\n"
                    f"💿 Disk: {info['disk_percent']}%\n"
                    f"⏱ Uptime: {info['uptime']}")
            except Exception as e:
                send_message(token, chat_id, f"خطا: {e}")
        
        elif text == "👥 لیست کاربران":
            users = get_all_users()
            if not users:
                send_message(token, chat_id, "هیچ کاربری ساخته نشده!")
                return
            msg_text = "<b>👥 لیست کاربران:</b>\n\n"
            for u in users[:20]:
                status_emoji = "🟢" if u["status"] == "active" else "🔴"
                msg_text += f"{status_emoji} <code>{u['username']}</code> | {format_bytes(u['data_used'])}\n"
            if len(users) > 20:
                msg_text += f"\n... و {len(users)-20} کاربر دیگر"
            send_message(token, chat_id, msg_text)
        
        elif text == "🟢 کاربران آنلاین":
            from database import get_online_users
            online = get_online_users(60)
            if not online:
                send_message(token, chat_id, "هیچ کاربر آنلاینی وجود ندارد!")
                return
            msg_text = f"<b>🟢 کاربران آنلاین ({len(online)}):</b>\n\n"
            for u in online:
                msg_text += f"• <code>{u['username']}</code> | {format_bytes(u['data_used'])}\n"
            send_message(token, chat_id, msg_text)
        
        elif text == "📈 آمار پنل":
            stats = get_stats()
            send_message(token, chat_id,
                f"<b>📈 آمار پنل CatWoman</b>\n\n"
                f"👥 کل کاربران: {stats['total_users']}\n"
                f"🟢 فعال: {stats['active_users']}\n"
                f"🔴 غیرفعال: {stats['disabled_users']}\n"
                f"🌐 آنلاین اکنون: {stats['online_users']}\n"
                f"📊 ترافیک کل: {format_bytes(stats['total_traffic'])}")
        
        else:
            send_message(token, chat_id, 
                "🤖 دستور نامعتبر!\nاز دکمه‌های زیر استفاده کنید.",
                reply_markup=get_main_keyboard())
    
    except Exception as e:
        print(f"خطا در پردازش پیام تلگرام: {e}")


class TelegramBotRunner:
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_update_id = 0
    
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.running = False
    
    def _run(self):
        while self.running:
            try:
                settings = get_telegram_settings()
                if not settings["enabled"] or not settings["token"]:
                    time.sleep(5)
                    continue
                
                token = settings["token"]
                admin_id = settings["admin_id"]
                
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                params = {"offset": self.last_update_id + 1, "timeout": 25}
                r = requests.get(url, params=params, timeout=30)
                data = r.json()
                
                if data.get("ok"):
                    for update in data.get("result", []):
                        self.last_update_id = update["update_id"]
                        handle_update(update, token, admin_id)
            
            except Exception as e:
                print(f"خطا در حلقه ربات تلگرام: {e}")
                time.sleep(5)

bot_runner = TelegramBotRunner()

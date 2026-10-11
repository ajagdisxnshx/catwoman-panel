import sqlite3
import uuid
import time
import os

DB_PATH = "/app/data/catwoman.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs("/app/data", exist_ok=True)
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                data_limit REAL DEFAULT 0,
                data_used REAL DEFAULT 0,
                expiry_date INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                uuid TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                sub_token TEXT UNIQUE NOT NULL,
                protocol TEXT DEFAULT 'vless',
                flow TEXT DEFAULT '',
                ip_limit INTEGER DEFAULT 0,
                note TEXT DEFAULT '',
                telegram_id TEXT DEFAULT '',
                emoji TEXT DEFAULT '😺',
                last_online INTEGER DEFAULT 0,
                last_traffic_check REAL DEFAULT 0
            )
        """)
        # اضافه کردن ستون‌های جدید اگه وجود ندارن
        try:
            conn.execute("ALTER TABLE users ADD COLUMN last_online INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN last_traffic_check REAL DEFAULT 0")
        except Exception:
            pass
        
        # جدول آمار ترافیک روزانه
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traffic_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                total_traffic REAL DEFAULT 0,
                UNIQUE(date)
            )
        """)
        conn.commit()

def get_all_users():
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()

def get_user_by_id(user_id):
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

def get_user_by_username(username):
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

def get_user_by_sub_token(token):
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE sub_token = ?", (token,)).fetchone()

def create_user(username, description, data_limit, expiry_days, protocol, 
                flow, ip_limit, note, telegram_id, emoji):
    user_id = str(uuid.uuid4())[:8]
    user_uuid = str(uuid.uuid4())
    sub_token = str(uuid.uuid4())[:16]
    created_at = int(time.time())
    expiry_date = int(time.time()) + (expiry_days * 86400) if expiry_days > 0 else 0
    data_limit_bytes = data_limit * 1073741824
    
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO users (id, username, description, data_limit, data_used,
                expiry_date, status, uuid, created_at, sub_token, protocol,
                flow, ip_limit, note, telegram_id, emoji, last_online, last_traffic_check)
            VALUES (?, ?, ?, ?, 0, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
        """, (user_id, username, description, data_limit_bytes, expiry_date,
              user_uuid, created_at, sub_token, protocol, flow, ip_limit,
              note, telegram_id, emoji))
        conn.commit()
    return user_id

def update_user(user_id, username, description, data_limit, expiry_days,
                protocol, flow, ip_limit, note, telegram_id, emoji, status):
    expiry_date = int(time.time()) + (expiry_days * 86400) if expiry_days > 0 else 0
    data_limit_bytes = data_limit * 1073741824
    
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE users SET username=?, description=?, data_limit=?,
                expiry_date=?, protocol=?, flow=?, ip_limit=?, note=?,
                telegram_id=?, emoji=?, status=?
            WHERE id = ?
        """, (username, description, data_limit_bytes, expiry_date,
              protocol, flow, ip_limit, note, telegram_id, emoji, status, user_id))
        conn.commit()

def delete_user(user_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

def reset_traffic(user_id):
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET data_used = 0 WHERE id = ?", (user_id,))
        conn.commit()

def toggle_user_status(user_id):
    user = get_user_by_id(user_id)
    new_status = "disabled" if user["status"] == "active" else "active"
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
    return new_status

def update_traffic(user_id, bytes_used):
    """بروزرسانی ترافیک + ثبت آنلاین بودن"""
    now = int(time.time())
    with get_db_connection() as conn:
        conn.execute("""UPDATE users SET 
                        data_used = data_used + ?, 
                        last_online = ?,
                        last_traffic_check = last_traffic_check + ?
                        WHERE id = ?""", 
                     (bytes_used, now, bytes_used, user_id))
        conn.commit()

def get_online_users(threshold_seconds=60):
    """دریافت کاربران آنلاین (کسانی که در X ثانیه اخیر ترافیک داشتن)"""
    threshold = int(time.time()) - threshold_seconds
    with get_db_connection() as conn:
        return conn.execute("""
            SELECT * FROM users 
            WHERE last_online > ? AND status = 'active'
            ORDER BY last_online DESC
        """, (threshold,)).fetchall()

def get_online_count(threshold_seconds=60):
    """تعداد کاربران آنلاین"""
    threshold = int(time.time()) - threshold_seconds
    with get_db_connection() as conn:
        return conn.execute("""
            SELECT COUNT(*) FROM users 
            WHERE last_online > ? AND status = 'active'
        """, (threshold,)).fetchone()[0]

def get_stats():
    with get_db_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM users WHERE status='active'").fetchone()[0]
        disabled = conn.execute("SELECT COUNT(*) FROM users WHERE status='disabled'").fetchone()[0]
        total_traffic = conn.execute("SELECT COALESCE(SUM(data_used),0) FROM users").fetchone()[0]
        online = get_online_count(60)
        return {
            "total_users": total,
            "active_users": active,
            "disabled_users": disabled,
            "total_traffic": total_traffic,
            "online_users": online
        }

def check_users_limits():
    now = int(time.time())
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE users SET status = 'data_exhausted' 
            WHERE data_limit > 0 AND data_used >= data_limit AND status = 'active'
        """)
        conn.execute("""
            UPDATE users SET status = 'expired' 
            WHERE expiry_date > 0 AND expiry_date <= ? AND status = 'active'
        """, (now,))
        conn.commit()

def record_daily_traffic(total_bytes):
    """ثبت ترافیک روزانه"""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO traffic_history (date, total_traffic) VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET total_traffic = ?
        """, (today, total_bytes, total_bytes))
        conn.commit()

def get_traffic_history(days=7):
    """دریافت تاریخچه ترافیک N روز اخیر"""
    with get_db_connection() as conn:
        return conn.execute("""
            SELECT date, total_traffic FROM traffic_history 
            ORDER BY date DESC LIMIT ?
        """, (days,)).fetchall()

def get_top_users(limit=5):
    """پرمصرف‌ترین کاربران"""
    with get_db_connection() as conn:
        return conn.execute("""
            SELECT * FROM users ORDER BY data_used DESC LIMIT ?
        """, (limit,)).fetchall()

from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import time
import asyncio
import base64
import shutil
import os
from contextlib import asynccontextmanager
from datetime import datetime

from config import (SECRET_KEY, PANEL_PORT, PANEL_NAME,
                    get_admin_credentials, update_admin_credentials,
                    get_telegram_settings, update_telegram_settings)
from database import (init_db, get_all_users, get_user_by_id, get_user_by_sub_token,
                      create_user, update_user, delete_user, reset_traffic,
                      toggle_user_status, get_stats, check_users_limits,
                      get_online_users, get_online_count, get_top_users,
                      get_traffic_history, record_daily_traffic, DB_PATH)
from xray_manager import (generate_xray_config, restart_xray, is_xray_running,
                          generate_vless_link, collect_traffic_stats, get_server_info)
from telegram_bot import bot_runner, test_bot_connection

async def periodic_check():
    while True:
        try:
            collect_traffic_stats()
            check_users_limits()
            generate_xray_config()
            
            # ثبت ترافیک روزانه
            stats = get_stats()
            record_daily_traffic(stats["total_traffic"])
        except Exception as e:
            print(f"خطا در بررسی چرخه‌ای: {e}")
        await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    generate_xray_config()
    restart_xray()
    
    # شروع ربات تلگرام
    tg_settings = get_telegram_settings()
    if tg_settings["enabled"] and tg_settings["token"]:
        bot_runner.start()
    
    task = asyncio.create_task(periodic_check())
    yield
    task.cancel()
    bot_runner.stop()

app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def is_logged_in(request: Request):
    return request.session.get("logged_in", False)

def format_bytes(bytes_val):
    if bytes_val == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while bytes_val >= 1024 and i < len(units) - 1:
        bytes_val /= 1024
        i += 1
    return f"{bytes_val:.2f} {units[i]}"

def days_remaining(expiry):
    if expiry == 0:
        return "∞"
    diff = expiry - int(time.time())
    if diff <= 0:
        return "0"
    return f"{int(diff / 86400)}"

def time_ago(timestamp):
    if timestamp == 0:
        return "هرگز"
    diff = int(time.time()) - timestamp
    if diff < 60:
        return f"{diff} ثانیه پیش"
    if diff < 3600:
        return f"{diff // 60} دقیقه پیش"
    if diff < 86400:
        return f"{diff // 3600} ساعت پیش"
    return f"{diff // 86400} روز پیش"

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    return RedirectResponse("/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request, "panel_name": PANEL_NAME, "error": None
    })

@app.post("/login")
async def login_action(request: Request, username: str = Form(...), password: str = Form(...)):
    admin_user, admin_pass = get_admin_credentials()
    if username == admin_user and password == admin_pass:
        request.session["logged_in"] = True
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {
        "request": request, "panel_name": PANEL_NAME,
        "error": "نام کاربری یا رمز عبور اشتباه است"
    })

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    stats = get_stats()
    xray_status = is_xray_running()
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "panel_name": PANEL_NAME,
        "stats": stats, "xray_status": xray_status,
        "format_bytes": format_bytes, "active_page": "dashboard"
    })

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    users = get_all_users()
    online_users = get_online_users(60)
    return templates.TemplateResponse("users.html", {
        "request": request, "panel_name": PANEL_NAME, "users": users,
        "online_users": online_users, "online_count": len(online_users),
        "format_bytes": format_bytes, "days_remaining": days_remaining,
        "time_ago": time_ago, "active_page": "users"
    })

@app.get("/api/online-count")
async def api_online_count(request: Request):
    if not is_logged_in(request):
        return {"count": 0}
    return {"count": get_online_count(60)}

@app.get("/users/add", response_class=HTMLResponse)
async def add_user_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse("add_user.html", {
        "request": request, "panel_name": PANEL_NAME, "active_page": "add"
    })

@app.post("/users/add")
async def add_user_action(
    request: Request,
    username: str = Form(...),
    description: str = Form(""),
    data_limit: float = Form(0),
    expiry_days: int = Form(0),
    protocol: str = Form("vless"),
    flow: str = Form(""),
    ip_limit: int = Form(0),
    note: str = Form("")
):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    try:
        create_user(username, description, data_limit, expiry_days,
                    protocol, flow, ip_limit, note, "", "")
        generate_xray_config()
        restart_xray()
    except Exception as e:
        return HTMLResponse(f"خطا: {e}", status_code=400)
    return RedirectResponse("/users", status_code=303)

@app.get("/users/edit/{user_id}", response_class=HTMLResponse)
async def edit_user_page(request: Request, user_id: str):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    user = get_user_by_id(user_id)
    if not user:
        return RedirectResponse("/users")
    remaining_days = 0
    if user["expiry_date"] > 0:
        remaining_days = max(0, int((user["expiry_date"] - time.time()) / 86400))
    data_limit_gb = user["data_limit"] / 1073741824 if user["data_limit"] else 0
    return templates.TemplateResponse("edit_user.html", {
        "request": request, "panel_name": PANEL_NAME,
        "user": user, "remaining_days": remaining_days,
        "data_limit_gb": data_limit_gb, "active_page": "users"
    })

@app.post("/users/edit/{user_id}")
async def edit_user_action(
    request: Request, user_id: str,
    username: str = Form(...),
    description: str = Form(""),
    data_limit: float = Form(0),
    expiry_days: int = Form(0),
    protocol: str = Form("vless"),
    flow: str = Form(""),
    ip_limit: int = Form(0),
    note: str = Form(""),
    status: str = Form("active")
):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    update_user(user_id, username, description, data_limit, expiry_days,
                protocol, flow, ip_limit, note, "", "", status)
    generate_xray_config()
    restart_xray()
    return RedirectResponse("/users", status_code=303)

@app.get("/users/delete/{user_id}")
async def delete_user_action(request: Request, user_id: str):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    delete_user(user_id)
    generate_xray_config()
    restart_xray()
    return RedirectResponse("/users", status_code=303)

@app.get("/users/reset/{user_id}")
async def reset_user_action(request: Request, user_id: str):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    reset_traffic(user_id)
    return RedirectResponse("/users", status_code=303)

@app.get("/users/toggle/{user_id}")
async def toggle_user(request: Request, user_id: str):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    toggle_user_status(user_id)
    generate_xray_config()
    restart_xray()
    return RedirectResponse("/users", status_code=303)

# ======== SETTINGS ========
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    admin_user, _ = get_admin_credentials()
    server_info = get_server_info()
    return templates.TemplateResponse("settings.html", {
        "request": request, "panel_name": PANEL_NAME,
        "admin_username": admin_user, "server_info": server_info,
        "format_bytes": format_bytes, "active_page": "settings",
        "success": request.session.pop("settings_success", None),
        "error": request.session.pop("settings_error", None)
    })

@app.post("/settings/change-credentials")
async def change_credentials(
    request: Request,
    current_password: str = Form(...),
    new_username: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    
    _, current = get_admin_credentials()
    if current_password != current:
        request.session["settings_error"] = "رمز فعلی اشتباه است!"
        return RedirectResponse("/settings", status_code=303)
    
    if new_password != confirm_password:
        request.session["settings_error"] = "رمز جدید و تکرار آن یکسان نیست!"
        return RedirectResponse("/settings", status_code=303)
    
    if len(new_password) < 4:
        request.session["settings_error"] = "رمز باید حداقل ۴ کاراکتر باشد!"
        return RedirectResponse("/settings", status_code=303)
    
    update_admin_credentials(new_username, new_password)
    request.session["settings_success"] = "اطلاعات ادمین با موفقیت تغییر کرد!"
    return RedirectResponse("/settings", status_code=303)

@app.get("/settings/restart-xray")
async def restart_xray_action(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    restart_xray()
    request.session["settings_success"] = "هسته Xray با موفقیت ری‌استارت شد!"
    return RedirectResponse("/settings", status_code=303)

@app.get("/settings/backup")
async def backup_db(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    if not os.path.exists(DB_PATH):
        return PlainTextResponse("دیتابیس یافت نشد", status_code=404)
    filename = f"catwoman_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return FileResponse(DB_PATH, filename=filename, media_type="application/octet-stream")

@app.post("/settings/restore")
async def restore_db(request: Request, backup_file: UploadFile = File(...)):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    try:
        content = await backup_file.read()
        with open(DB_PATH, "wb") as f:
            f.write(content)
        generate_xray_config()
        restart_xray()
        request.session["settings_success"] = "دیتابیس با موفقیت بازیابی شد!"
    except Exception as e:
        request.session["settings_error"] = f"خطا در بازیابی: {e}"
    return RedirectResponse("/settings", status_code=303)

# ======== TELEGRAM BOT ========
@app.get("/telegram", response_class=HTMLResponse)
async def telegram_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    settings = get_telegram_settings()
    return templates.TemplateResponse("telegram.html", {
        "request": request, "panel_name": PANEL_NAME,
        "settings": settings, "active_page": "telegram",
        "success": request.session.pop("tg_success", None),
        "error": request.session.pop("tg_error", None)
    })

@app.post("/telegram/save")
async def save_telegram(
    request: Request,
    token: str = Form(""),
    admin_id: str = Form(""),
    enabled: str = Form("off")
):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    is_enabled = enabled == "on"
    update_telegram_settings(token.strip(), admin_id.strip(), is_enabled)
    
    if is_enabled and token:
        bot_runner.start()
    else:
        bot_runner.stop()
    
    request.session["tg_success"] = "تنظیمات ربات ذخیره شد!"
    return RedirectResponse("/telegram", status_code=303)

@app.post("/telegram/test")
async def test_telegram(
    request: Request,
    token: str = Form(...),
    admin_id: str = Form(...)
):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    success, result = test_bot_connection(token.strip(), admin_id.strip())
    if success:
        request.session["tg_success"] = f"اتصال موفق! نام ربات: @{result}"
    else:
        request.session["tg_error"] = f"خطا در اتصال: {result}"
    return RedirectResponse("/telegram", status_code=303)

# ======== TRAFFIC MONITOR ========
@app.get("/traffic", response_class=HTMLResponse)
async def traffic_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    
    history_7 = get_traffic_history(7)
    history_30 = get_traffic_history(30)
    top_users = get_top_users(5)
    stats = get_stats()
    
    # محاسبه مصرف امروز
    today_traffic = 0
    if history_7:
        today_traffic = history_7[0]["total_traffic"] if len(history_7) > 0 else 0
    
    # تبدیل برای نمودار
    chart_labels = [h["date"] for h in reversed(history_7)]
    chart_data = [round(h["total_traffic"] / 1073741824, 2) for h in reversed(history_7)]
    
    return templates.TemplateResponse("traffic.html", {
        "request": request, "panel_name": PANEL_NAME,
        "stats": stats, "today_traffic": today_traffic,
        "top_users": top_users, "chart_labels": chart_labels,
        "chart_data": chart_data, "format_bytes": format_bytes,
        "active_page": "traffic"
    })

# ======== SUBSCRIPTION ========
@app.get("/sub/{token}")
async def subscription(request: Request, token: str):
    user = get_user_by_sub_token(token)
    if not user:
        return PlainTextResponse("Not Found", status_code=404)
    
    host = request.url.hostname
    
    if user["status"] in ["disabled", "data_exhausted", "expired"]:
        reason = {
            "disabled": "سرویس شما به صورت موقت توسط ادمین غیرفعال شده است",
            "data_exhausted": "حجم اینترنت شما به پایان رسیده است",
            "expired": "تاریخ انقضای سرویس شما به پایان رسیده است"
        }.get(user["status"], "سرویس غیرفعال")
        
        return templates.TemplateResponse("sub.html", {
            "request": request, "user": user, "config_link": "",
            "host": host, "format_bytes": format_bytes,
            "days_remaining": days_remaining, "is_active": False, "reason": reason,
            "data_used_gb": user["data_used"] / 1073741824,
            "data_limit_gb": user["data_limit"] / 1073741824 if user["data_limit"] else 0,
            "usage_percent": min(100, (user["data_used"] / user["data_limit"] * 100) if user["data_limit"] else 0)
        })
    
    config_link = generate_vless_link(user, host)
    return templates.TemplateResponse("sub.html", {
        "request": request, "user": user, "config_link": config_link,
        "host": host, "format_bytes": format_bytes,
        "days_remaining": days_remaining, "is_active": True, "reason": "",
        "data_used_gb": user["data_used"] / 1073741824,
        "data_limit_gb": user["data_limit"] / 1073741824 if user["data_limit"] else 0,
        "usage_percent": min(100, (user["data_used"] / user["data_limit"] * 100) if user["data_limit"] else 0)
    })

@app.get("/sub/{token}/raw")
async def subscription_raw(request: Request, token: str):
    user = get_user_by_sub_token(token)
    if not user or user["status"] != "active":
        return PlainTextResponse("", status_code=200)
    
    host = request.url.hostname
    config_link = generate_vless_link(user, host)
    encoded = base64.b64encode(config_link.encode()).decode()
    
    return Response(content=encoded, media_type="text/plain", headers={
        "Profile-Title": f"CatWoman - {user['username']}",
        "Subscription-Userinfo": f"upload=0; download={int(user['data_used'])}; total={int(user['data_limit'])}; expire={user['expiry_date']}"
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PANEL_PORT)

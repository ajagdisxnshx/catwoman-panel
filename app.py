from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import time
import asyncio
import base64
from contextlib import asynccontextmanager

from config import (ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY, 
                    PANEL_PORT, PANEL_NAME)
from database import (init_db, get_all_users, get_user_by_id, get_user_by_sub_token,
                      create_user, update_user, delete_user, reset_traffic,
                      toggle_user_status, get_stats, check_users_limits)
from xray_manager import (generate_xray_config, restart_xray, is_xray_running,
                          generate_vless_link)

async def periodic_check():
    while True:
        try:
            check_users_limits()
            generate_xray_config()
        except Exception as e:
            print(f"خطا در بررسی: {e}")
        await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    generate_xray_config()
    restart_xray()
    task = asyncio.create_task(periodic_check())
    yield
    task.cancel()

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
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
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
    return templates.TemplateResponse("users.html", {
        "request": request, "panel_name": PANEL_NAME, "users": users,
        "format_bytes": format_bytes, "days_remaining": days_remaining,
        "active_page": "users"
    })

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
    note: str = Form(""),
    telegram_id: str = Form("")
):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    try:
        create_user(username, description, data_limit, expiry_days,
                    protocol, flow, ip_limit, note, telegram_id, "")
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
    telegram_id: str = Form(""),
    status: str = Form("active")
):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    update_user(user_id, username, description, data_limit, expiry_days,
                protocol, flow, ip_limit, note, telegram_id, "", status)
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

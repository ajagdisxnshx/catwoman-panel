#!/bin/bash

# ساخت پوشه‌های لازم
mkdir -p /app/data /usr/local/etc/xray

# اجرای پنل پایتون در پس‌زمینه
cd /app && python app.py &

# صبر کوتاه برای آماده شدن پنل
sleep 3

# اجرای Caddy در فورگراند
caddy run --config /app/Caddyfile --adapter caddyfile
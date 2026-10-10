FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# نصب پیش‌نیازها و Caddy
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# دانلود Caddy
RUN curl -sSL "https://caddyserver.com/api/download?os=linux&arch=amd64" -o /usr/bin/caddy && \
    chmod +x /usr/bin/caddy

# دانلود Xray Core
RUN mkdir -p /tmp/xray && \
    curl -sSL "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip" -o /tmp/xray/xray.zip && \
    unzip /tmp/xray/xray.zip -d /tmp/xray && \
    mv /tmp/xray/xray /usr/local/bin/xray && \
    chmod +x /usr/local/bin/xray && \
    mkdir -p /usr/local/etc/xray && \
    rm -rf /tmp/xray

# کپی فایل‌ها
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data && chmod +x /app/entrypoint.sh

EXPOSE 8080

CMD ["/app/entrypoint.sh"]
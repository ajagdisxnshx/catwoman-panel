def generate_vless_link(user, host):
    """ساخت لینک VLESS کاملاً استاندارد و سازگار با ریلوی و کلودفلر"""
    return (
        f"vless://{user['uuid']}@{host}:443"
        f"?encryption=none"
        f"&security=tls"
        f"&sni={host}"
        f"&type=ws"
        f"&host={host}"
        f"&path=%2Fcatwoman-ws"
        f"#{user['username']}"
    )
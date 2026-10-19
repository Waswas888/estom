import json
import os
import time
import requests
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

PORTAL_URL = "http://tv.redmax.tv/stalker_portal/server/load.php"
STREAM_BASE_HOST = "http://stream.redmax.tv/"
MAC_BASE = "00:1A:79:00:02:FE"
BASE_PROXY_URL = "https://estom.vercel.app"  # Ваш домен на Vercel

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ И ФИЛЬТРАЦИИ ---
SECRET_KEY = "000"
TELEGRAM_GROUP_URL = "https://t.me/+2lWVU6CKQsVkMWRi"
STUB_VIDEO_URL = "https://raw.githubusercontent.com/Waswas777/video2/refs/heads/main/playlist.m3u8"

BANNED_IPS = {
    "5.253.66.62", "23.106.253.18", "23.106.249.56", "31.3.156.64", 
    "38.180.180.126", "46.150.71.146", "91.214.82.125", "109.86.19.135", 
    "217.12.223.190", "188.233.60.20", "2a02:6ea0:3100:2000:490a:2928:d5eb:e685"
}

ALLOWED_COUNTRIES = {"UA", "RU", "UZ", "BY", "GE", "MD", "AM", "AZ", "KZ"}

app = FastAPI()

status_data = {
    "last_update": "Hali yangilanmagan",
    "total_channels": 0,
    "status": "Kuting...",
}

# --- ЕДИНАЯ ФУНКЦИЯ ПРОВЕРКИ И БЛОКИРОВКИ ---
def is_request_blocked(request: Request) -> bool:
    # 1. Проверка секретного ключа из параметров URL (?key=000)
    user_key = request.query_params.get("key", "")
    if user_key != SECRET_KEY:
        return True

    # 2. Получаем IP клиента
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0].strip()
    
    # 3. Получаем User-Agent
    ua = request.headers.get("user-agent", "").lower()
    
    # 4. Получаем страну (заголовок от Cloudflare/Vercel)
    country = request.headers.get("cf-ipcountry", "").upper()

    # Проверка на поисковых ботов и сканеры
    is_search_bot = any(bot in ua for bot in ["google", "bot", "crawler", "spider", "yandex"])

    # Проверка черного списка IP и подсетей
    is_banned_ip = (
        client_ip in BANNED_IPS or
        client_ip.startswith("2a09:bac5:") or
        client_ip.startswith("2a02:3032:")
    )

    # Проверка по стране
    is_disallowed_country = bool(country and country not in ALLOWED_COUNTRIES)

    return is_search_bot or is_banned_ip or is_disallowed_country


def get_session():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://tv.redmax.tv/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain="tv.redmax.tv")
    session.cookies.set("stb_lang", "en", domain="tv.redmax.tv")
    session.cookies.set("timezone", "Europe/London", domain="tv.redmax.tv")

    try:
        session.get("http://tv.redmax.tv/stalker_portal/c/", timeout=5)
        session.get("http://tv.redmax.tv/stalker_portal/c/xpcom.common.js", timeout=5)
        session.get("http://tv.redmax.tv/stalker_portal/c/version.js", timeout=5)
    except Exception:
        pass

    token = ""
    try:
        hs_url = f"{PORTAL_URL}?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        r = session.get(hs_url, timeout=10).json()
        token = r.get("js", {}).get("token", "")
        if token:
            session.cookies.set("token", token, domain="tv.redmax.tv")
            session.headers.update({"Authorization": f"Bearer {token}"})
    except Exception:
        pass

    metrics_data = json.dumps({
        "type": "stb",
        "model": "MAG254",
        "mac": MAC_BASE,
        "sn": "AFDDBB900DAC7",
        "uid": "1790027FB626094E452F3A04C2527AC60571CEE93E1FD5DE5C4991BA634128C6",
        "random": "b9a90b92ac722147751dbbf9a06fd3a6dec9c08f"
    })
    token_param = f"&token={token}" if token else ""
    prof_url = (
        f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1"
        f"{token_param}"
        "&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.3.0; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c"
        "&num_banks=2&sn=AFDDBB900DAC7&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi"
        "&device_id=99C6BE2AE772CC6660BE59B7AA0CD132C1463315C7FB1611518D6C3CCD4F0CE2"
        "&device_id2=99C6BE2AE772CC6660BE59B7AA0CD132C1463315C7FB1611518D6C3CCD4F0CE2"
        "&signature=F815A102A114ACF1890EF21CAB0D11451C5732B6FE3A253AC4A26239C0CBD9AF"
        "&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0"
        f"&metrics={metrics_data}"
        f"&hw_version_2=aa9eff686503b38e40ac84c5a469d92cf15adee3&timestamp={int(time.time())}&api_signature=262&prehash=d9b973e8083c84bd1a68a33147cdae39b605acc7"
    )

    try:
        session.get(prof_url, timeout=10)
        session.get(f"{PORTAL_URL}?type=account_info&action=get_main_info&JsHttpRequest=1-xml", timeout=10)
    except Exception:
        pass

    return session


def update_playlist():
    global status_data
    status_data["status"] = "Yangilanmoqda..."
    session = get_session()

    genres = ["", "*", "0"]
    try:
        genres_url = f"{PORTAL_URL}?type=itv&action=get_genres&JsHttpRequest=1-xml"
        genres_resp = session.get(genres_url, timeout=10).json()
        js_genres = genres_resp.get("js", [])
        if isinstance(js_genres, list):
            for g in js_genres:
                g_id = g.get("id")
                if g_id is not None and str(g_id) not in [str(x) for x in genres]:
                    genres.append(str(g_id))
    except Exception:
        pass

    raw_channels = []
    seen_cmds = set()

    for genre in genres:
        urls = [
            f"{PORTAL_URL}?type=itv&action=get_all_channels&genre={genre}&JsHttpRequest=1-xml",
            f"{PORTAL_URL}?type=itv&action=get_all_channels&genre={genre}&p=1&JsHttpRequest=1-xml"
        ]
        for ch_url in urls:
            try:
                res = session.get(ch_url, timeout=8).json()
                js_data = res.get("js", {})
                data = []
                if isinstance(js_data, list):
                    data = js_data
                elif isinstance(js_data, dict):
                    data = js_data.get("data", []) or js_data.get("channels", [])

                if isinstance(data, list) and len(data) > 0:
                    for ch in data:
                        cmd = ch.get("cmd", "")
                        if cmd and cmd not in seen_cmds:
                            seen_cmds.add(cmd)
                            raw_channels.append({
                                "name": ch.get("name", "Kanal"),
                                "cmd": cmd,
                                "timeshift": ch.get("timeshift", 0)
                            })
            except Exception:
                continue

    temp_file = "/tmp/playlist.tmp"
    final_file = "/tmp/playlist.json"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(raw_channels, f, ensure_ascii=False, indent=4)

    if os.path.exists(final_file):
        os.remove(final_file)
    os.rename(temp_file, final_file)

    status_data["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    status_data["total_channels"] = len(raw_channels)
    status_data["status"] = "Muvaffaqiyatli"


def ensure_playlist():
    if not os.path.exists("/tmp/playlist.json") or (time.time() - os.path.getmtime("/tmp/playlist.json") > 3600):
        try:
            update_playlist()
        except Exception:
            pass


@app.get("/", response_class=HTMLResponse)
def admin_panel(request: Request):
    ua = request.headers.get("user-agent", "").lower()

    # 1. Ответ для Telegram-бота (превью)
    if "telegrambot" in ua:
        preview_html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta property="og:title" content="📡 𝕏aльвa 📡">
            <meta property="og:description" content="Ссылка для друзей 👆&#10;Напоминаю в группе бот...">
            <meta property="og:image" content="{STUB_VIDEO_URL}">
            <meta property="og:url" content="{BASE_PROXY_URL}/">
            <title>IPTV Playlist</title>
        </head>
        <body>Redirecting...</body>
        </html>"""
        return HTMLResponse(content=preview_html)

    # 2. Если открывают корень в браузере с верным ключом
    user_key = request.query_params.get("key", "")
    if user_key != SECRET_KEY:
        return RedirectResponse(url=TELEGRAM_GROUP_URL, status_code=302)

    ensure_playlist()
    return f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <title>Admin Panel</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 50px; }}
            .card {{ background: #1e293b; padding: 30px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }}
            .badge {{ background: #22c55e; color: white; padding: 5px 12px; border-radius: 20px; font-weight: bold; }}
            a {{ color: #38bdf8; text-decoration: none; display: block; margin-top: 15px; font-size: 18px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Admin Panel</h2>
            <p>Holati: <span class="badge">{status_data["status"]}</span></p>
            <p><b>Kanallar soni:</b> {status_data["total_channels"]} ta</p>
            <p><b>Oxirgi yangilangan vaqt:</b> {status_data["last_update"]}</p>
            <hr style="border: 0.5px solid #334155; margin: 20px 0;">
            <a href="/playlist.json?key={SECRET_KEY}">JSON Playlist</a>
            <a href="/pl.m3u8?key={SECRET_KEY}">M3U8 Playlist</a>
        </div>
    </body>
    </html>
    """


@app.get("/pl.m3u8", response_class=PlainTextResponse)
def download_m3u8(request: Request):
    # ПРОВЕРКА КЛЮЧА И БЛОКИРОВКИ: Заблокированных кидает на видеозаглушку!
    if is_request_blocked(request):
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)

    ensure_playlist()
    if not os.path.exists("/tmp/playlist.json"):
        return "#EXTM3U\n# Xatolik: Playlist hali tayyorlanmadi"

    with open("/tmp/playlist.json", "r", encoding="utf-8") as f:
        channels = json.load(f)

    m3u_lines = ["#EXTM3U"]
    for idx, ch in enumerate(channels):
        name = ch.get("name", "Kanal")
        timeshift = ch.get("timeshift", 0)
        # Каждая ссылка на поток содержит секретный ключ
        stream_link = f"{BASE_PROXY_URL}/stream/{idx}?key={SECRET_KEY}"
        
        tvg_shift_attr = f' tvg-shift="{timeshift}"' if timeshift else ''
        catchup_attr = ' catchup="default" catchup-days="3"' if timeshift else ''
        
        m3u_lines.append(f"#EXTINF:-1{tvg_shift_attr}{catchup_attr},{name}")
        m3u_lines.append(stream_link)

    return "\n".join(m3u_lines)


@app.get("/stream/{index}")
def proxy_stream(index: int, request: Request):
    # ПРОВЕРКА КЛЮЧА И БЛОКИРОВКИ: Заблокированных кидает на видеозаглушку!
    if is_request_blocked(request):
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)

    if not os.path.exists("/tmp/playlist.json"):
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)

    try:
        with open("/tmp/playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        target = channels[index]
        cmd = target["cmd"]
    except Exception:
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)

    session = get_session()
    stream_url = ""

    try:
        clean_cmd = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if clean_cmd.startswith(prefix):
                clean_cmd = clean_cmd[len(prefix):].strip()

        link_url = f"{PORTAL_URL}?type=itv&action=create_link&cmd={requests.utils.quote(clean_cmd)}&JsHttpRequest=1-xml"
        link_res = session.get(link_url, timeout=10).json()
        stream_cmd = link_res.get("js", {}).get("cmd") or link_res.get("js", {}).get("url") or ""

        if stream_cmd:
            for prefix in ["ffrt3 ", "ffrt2 ", "ffrt ", "ffmpeg ", "ch:ffrt ", "ch:"]:
                if stream_cmd.startswith(prefix):
                    stream_cmd = stream_cmd[len(prefix):].strip()
            stream_url = stream_cmd
    except Exception:
        pass

    if not stream_url and "http" in cmd:
        stream_url = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if stream_url.startswith(prefix):
                stream_url = stream_url[len(prefix):].strip()

    if stream_url:
        return RedirectResponse(url=stream_url, status_code=302)

    return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/vnd.microsoft.icon")

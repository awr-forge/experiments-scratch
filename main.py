import os, json, time, signal, sys, urllib.request, urllib.error

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_KEY = "".join(os.environ.get("GEMINI_API_KEY", "").split())
API = f"https://api.telegram.org/bot{TOKEN}"
OFFSET_FILE = "offset.txt"
RUN_DURATION = 5 * 3600 + 45 * 60
_running = True

def _stop(*_):
    global _running
    _running = False
signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

PROMPT_TRADE = "أنت كبير استراتيجيي التداول في صندوق تحوط. اعمل استراتيجية مؤسسية دقيقة (دخول، خروج، إدارة مخاطر 1%، كود MT5) لزوج العملات المطلوب."
PROMPT_GEN = "أنت N-Panther مساعد ذكي عام. رد بالعربية بأسلوب مفيد ومباشر."

def get_updates(offset):
    url = f"{API}/getUpdates?offset={offset}&timeout=20&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            if data.get("ok"): return data.get("result", [])
    except: pass
    return []

def send(chat_id, text, markup=None):
    payload = {"chat_id": chat_id, "text": text[:4000]}
    if markup: payload["reply_markup"] = markup
    try:
        req = urllib.request.Request(f"{API}/sendMessage", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp: resp.read()
    except: pass

def ask_ai(text, mode="general"):
    if not GEMINI_KEY: return "⚠️ المفتاح مش موجود."
    sys_p = PROMPT_TRADE if mode == "trade" else PROMPT_GEN
    models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-flash-latest"] if mode == "trade" else ["gemini-flash-latest", "gemini-2.5-flash"]
    payload = {
        "system_instruction": {"parts": [{"text": sys_p}]},
        "contents": [{"role": "user", "parts": [{"text": text[:4000]}]}],
        "generationConfig": {"temperature": 0.4 if mode == "trade" else 0.7, "maxOutputTokens": 4096}
    }
    for m in models:
        try:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "X-Goog-Api-Key": GEMINI_KEY}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                d = json.loads(resp.read().decode())
                if d.get("candidates"): return d["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 503): continue
            if e.code in (400, 403): return "⚠️ مشكلة في المفتاح."
        except: continue
    return "⚠️ فشل الاتصال بجوجل."

def handle(u):
    if "message" in u:
        m = u["message"]
        cid = m.get("chat", {}).get("id")
        txt = m.get("text", "").strip()
        if not cid or not txt: return
        if txt.startswith(("/start", "/menu")):
            markup = {"inline_keyboard": [[{"text": "🧠 ذكاء عام", "callback_data": "gen"}], [{"text": "📈 استراتيجيات فوركس", "callback_data": "fx_menu"}]]}
            send(cid, "اختر الوضع:", markup)
        elif txt.startswith("/fx"):
            pair = txt.replace("/fx", "").strip()
            if not pair: send(cid, "مثال: /fx EUR/USD")
            else:
                send(cid, f"⏳ الخبير يبني استراتيجية لـ {pair}...")
                send(cid, ask_ai(f"استراتيجية لـ {pair}", mode="trade"))
        else:
            send(cid, ask_ai(txt, mode="general"))
    elif "callback_query" in u:
        cq = u["callback_query"]
        cid = cq["message"]["chat"]["id"]
        data = cq["data"]
        try:
            urllib.request.urlopen(urllib.request.Request(f"{API}/answerCallbackQuery", data=json.dumps({"callback_query_id": cq["id"]}).encode(), headers={"Content-Type":"application/json"}, method="POST"), timeout=5)
        except: pass
        if data == "gen": send(cid, "🧠 اكتب سؤالك الآن.")
        elif data == "fx_menu":
            markup = {"inline_keyboard": [[{"text": "🇪🇺 EUR/USD", "callback_data": "fx_EUR/USD"}, {"text": "🇬🇧 GBP/USD", "callback_data": "fx_GBP/USD"}], [{"text": "🥇 XAU/USD", "callback_data": "fx_XAU/USD"}]]}
            send(cid, "اختر الزوج:", markup)
        elif data.startswith("fx_"):
            pair = data.replace("fx_", "")
            send(cid, f"⏳ الخبير يبني استراتيجية لـ {pair}...")
            send(cid, ask_ai(f"استراتيجية لـ {pair}", mode="trade"))

def main():
    offset = 0
    try:
        with open(OFFSET_FILE) as f: offset = int(f.read().strip())
    except: pass
    print("🚀 Bot Started")
    start = time.time()
    while _running and (time.time() - start < RUN_DURATION):
        ups = get_updates(offset)
        if ups:
            for u in ups:
                offset = max(offset, u.get("update_id", 0) + 1)
                try: handle(u)
                except: pass
            try:
                with open(OFFSET_FILE, "w") as f: f.write(str(offset))
            except: pass
        else: time.sleep(2)

if __name__ == "__main__": main()

import os, json, time, signal, sys, urllib.request, urllib.error

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_KEY = "".join(os.environ.get("GEMINI_API_KEY", "").split())
API = f"https://api.telegram.org/bot{TOKEN}"
OFFSET_FILE = "offset.txt"
TIMEOUT = 15
AI_TIMEOUT = 60
RUN_DURATION = 5 * 3600 + 45 * 60
_running = True

def _stop(*_):
    global _running
    _running = False
signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

def get_updates(offset):
    url = f"{API}/getUpdates?offset={offset}&timeout=20&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT+10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("ok"): return data.get("result", [])
    except Exception as e: print(f"getUpdates: {e}")
    return []

def send(chat_id, text, markup=None):
    payload = {"chat_id": chat_id, "text": text[:4000]}
    if markup: payload["reply_markup"] = markup
    try:
        req = urllib.request.Request(f"{API}/sendMessage", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp: resp.read()
    except Exception as e: print(f"send: {e}")

def ask_ai(chat_id, text, mode="general"):
    if not GEMINI_KEY: return "⚠️ المفتاح مش موجود."
    sys_p = "أنت N-Panther مساعد ذكي. رد بالعربي." if mode=="general" else "أنت N-Panther خبير تداول. اعمل استراتيجية كاملة مع كود."
    payload = {
        "system_instruction": {"parts": [{"text": sys_p}]},
        "contents": [{"role": "user", "parts": [{"text": text[:4000]}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}
    }
    for m in ["gemini-flash-latest", "gemini-2.5-flash"]:
        try:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "X-Goog-Api-Key": GEMINI_KEY}, method="POST")
            with urllib.request.urlopen(req, timeout=AI_TIMEOUT) as resp:
                d = json.loads(resp.read().decode())
                if d.get("candidates"): return d["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429: return "⚠️ استهلكت الحد (429)."
            if e.code in (400, 403): return "⚠️ مشكلة في المفتاح."
        except: continue
    return "⚠️ فشل الاتصال بجوجل."

def handle(u):
    if "message" in u:
        m = u["message"]
        cid = m.get("chat", {}).get("id")
        txt = m.get("text", "")
        if not cid or not txt: return
        if txt.startswith("/trade"):
            send(cid, "⏳ جاري التوليد...")
            send(cid, ask_ai(cid, txt.replace("/trade", "").strip(), mode="trading"))
        elif txt == "/menu":
            markup = {"inline_keyboard": [[{"text": "🧠 ذكاء عام", "callback_data": "gen"}], [{"text": "📈 تداول", "callback_data": "trade"}]]}
            send(cid, "اختر الوضع:", markup)
        else:
            send(cid, ask_ai(cid, txt))
            
    elif "callback_query" in u:
        cq = u["callback_query"]
        cid = cq["message"]["chat"]["id"]
        data = cq["data"]
        try:
            urllib.request.urlopen(urllib.request.Request(f"{API}/answerCallbackQuery", data=json.dumps({"callback_query_id": cq["id"]}).encode(), headers={"Content-Type":"application/json"}, method="POST"), timeout=5)
        except: pass
        
        if data == "gen": send(cid, "اكتب سؤالك الآن.")
        elif data == "trade":
            markup = {"inline_keyboard": [[{"text": "EUR/USD", "callback_data": "t_EURUSD"}], [{"text": "BTC/USDT", "callback_data": "t_BTCUSDT"}]]}
            send(cid, "اختر الأصل:", markup)
        elif data.startswith("t_"):
            asset = data.replace("t_", "")
            send(cid, f"⏳ جاري التوليد لـ {asset}...")
            send(cid, ask_ai(cid, f"استراتيجية لـ {asset}", mode="trading"))

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
                except Exception as e: print(f"handle: {e}")
            try:
                with open(OFFSET_FILE, "w") as f: f.write(str(offset))
            except: pass
        else: time.sleep(2)

if __name__ == "__main__": main()

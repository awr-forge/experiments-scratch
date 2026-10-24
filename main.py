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

PROMPT_TRADE = (
    "أنت كبير استراتيجيي التداول في صندوق تحوط عالمي متخصص في الفوركس. "
    "لديك خبرة 20 عاماً في أزواج العملات الرئيسية والجلسات (لندن، نيويورك، طوكيو). "
    "اعمل استراتيجية مؤسسية دقيقة (دخول، خروج، إدارة مخاطر 1%، كود MT5) "
    "للزوج المطلوب فقط. ممنوع تماماً تتكلم عن أي زوج آخر أو أي سوق آخر. "
    "ركّز فقط على زوج الفوركس المطلوب."
)
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
    
    models = ["gemini-2.0-flash", "gemini-flash-latest"] if mode == "trade" else ["gemini-flash-latest", "gemini-2.0-flash"]
    
    payload = {
        "system_instruction": {"parts": [{"text": sys_p}]},
        "contents": [{"role": "user", "parts": [{"text": text[:4000]}]}],
        "generationConfig": {"temperature": 0.4 if mode == "trade" else 0.7, "maxOutputTokens": 4096}
    }
    last_err = "Unknown"
    for m in models:
        try:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "X-Goog-Api-Key": GEMINI_KEY}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                d = json.loads(resp.read().decode())
                if d.get("candidates"): return d["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            last_err = f"Code {e.code}: {body[:150]}"
            if e.code in (400, 403): return f"⚠️ مشكلة في المفتاح ({e.code})."
            continue
        except Exception as e:
            last_err = str(e)
            continue
    return f"⚠️ فشل الاتصال بجوجل.\nالسبب: {last_err}"

def handle(u):
    if "message" in u:
        m = u["message"]
        cid = m.get("chat", {}).get("id")
        txt = m.get("text", "").strip()
        if not cid or not txt: return
        
        if txt.startswith(("/start", "/menu")):
            markup = {"inline_keyboard": [
                [{"text": "🧠 ذكاء عام", "callback_data": "gen"}],
                [{"text": "📈 استراتيجيات فوركس", "callback_data": "fx_menu"}]
            ]}
            send(cid, "أهلاً بك في N-Panther.\nاختر الوضع:", markup)
            
        elif txt.startswith("/fx"):
            pair = txt.replace("/fx", "").strip()
            if not pair: send(cid, "أرسل الأمر مع الزوج. مثال: /fx EUR/USD")
            else:
                send(cid, f"⏳ الخبير يبني استراتيجية فوركس لـ {pair}...")
                send(cid, ask_ai(f"اعمل استراتيجية فوركس لزوج {pair} فقط.", mode="trade"))
        else:
            send(cid, ask_ai(txt, mode="general"))
            
    elif "callback_query" in u:
        cq = u["callback_query"]
        cid = cq["message"]["chat"]["id"]
        data = cq["data"]
        try:
            urllib.request.urlopen(urllib.request.Request(f"{API}/answerCallbackQuery", data=json.dumps({"callback_query_id": cq["id"]}).encode(), headers={"Content-Type":"application/json"}, method="POST"), timeout=5)
        except: pass
        
        if data == "gen": 
            send(cid, "🧠 اكتب سؤالك الآن.")
            
        elif data == "fx_menu":
            markup = {"inline_keyboard": [
                [{"text": "🇪🇺 EUR/USD", "callback_data": "do_EUR/USD"}, {"text": "🇬🇧 GBP/USD", "callback_data": "do_GBP/USD"}],
                [{"text": "🇺🇸 USD/JPY", "callback_data": "do_USD/JPY"}, {"text": "🇦🇺 AUD/USD", "callback_data": "do_AUD/USD"}],
                [{"text": "🇨🇭 USD/CHF", "callback_data": "do_USD/CHF"}, {"text": "🇨🇦 USD/CAD", "callback_data": "do_USD/CAD"}],
                [{"text": "✍️ اكتب زوج يدوياً", "callback_data": "fx_custom"}]
            ]}
            send(cid, "💱 اختر زوج الفوركس:", markup)
            
        elif data == "fx_custom":
            send(cid, "اكتب الزوج اللي عايزه في الشات مباشرة (مثلاً: NZD/USD أو EUR/GBP).")
            
        elif data.startswith("do_"):
            pair = data.replace("do_", "")
            send(cid, f"⏳ الخبير يبني استراتيجية فوركس لـ {pair}...")
            send(cid, ask_ai(f"اعمل استراتيجية فوركس لزوج {pair} فقط.", mode="trade"))

def main():
    offset = 0
    try:
        with open(OFFSET_FILE) as f: offset = int(f.read().strip())
    except: pass
    print("🚀 Forex Bot Started")
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

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

# برومبت مخصص للفوركس
TRADING_PROMPT = (
    "أنت N-Panther، خبير استراتيجيات فوركس محترف. "
    "تعرف كل شيء عن أزواج العملات الرئيسية، الجلسات (لندن، نيويورك، طوكيو)، السبريد، وإدارة المخاطر. "
    "عندما يطلب المستخدم استراتيجية لزوج عملات، قدم استراتيجية واقعية وقابلة للتنفيذ بالشكل التالي:\n\n"
    "📊 **اسم الاستراتيجية:** [اسم احترافي]\n"
    "💱 **الزوج:** [الزوج المطلوب]\n"
    "⏱ **الإطار الزمني:** [M15 / H1 / H4]\n"
    "🌍 **الجلسة المفضلة:** [لندن / نيويورك / تداخل]\n\n"
    "📉 **المؤشرات المطلوبة:**\n"
    "- [اسم المؤشر + الإعدادات + سبب استخدامه]\n\n"
    "🎯 **شروط الدخول (شراء):**\n"
    "1. [شرط 1]\n2. [شرط 2]\n\n"
    "🎯 **شروط الدخول (بيع):**\n"
    "1. [شرط 1]\n2. [شرط 2]\n\n"
    "🛡️ **إدارة المخاطر:**\n"
    "- **Stop Loss:** [كيفية تحديده بالـ Pips أو ATR]\n"
    "- **Take Profit:** [كيفية تحديده، R:R لا يقل عن 1:2]\n"
    "- **حجم الصفقة:** 1% إلى 2% من رأس المال لكل صفقة.\n\n"
    "💻 **كود MT5 (Python):**\n"
    "```python\n# كود جاهز يعكس الاستراتيجية\n```\n\n"
    "⚠️ **نصيحة تنفيذ:** [نصيحة عن السبريد أو الأخبار]\n"
    "رد بالعربية بأسلوب مباشر ومحترف. لا تخرج عن هذا الهيكل."
)

GENERAL_PROMPT = "أنت N-Panther مساعد ذكي عام. رد بالعربية بأسلوب مفيد ومباشر."

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
    sys_p = TRADING_PROMPT if mode == "trading" else GENERAL_PROMPT
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
            if e.code == 429: return "⚠️ استهلكت الحد (429). استنى دقيقة."
            if e.code in (400, 403): return "⚠️ مشكلة في المفتاح."
        except: continue
    return "⚠️ فشل الاتصال بجوجل."

def handle(u):
    if "message" in u:
        m = u["message"]
        cid = m.get("chat", {}).get("id")
        txt = m.get("text", "").strip()
        if not cid or not txt: return
        
        if txt.startswith("/start") or txt.startswith("/menu"):
            markup = {"inline_keyboard": [
                [{"text": "🧠 ذكاء عام", "callback_data": "gen"}],
                [{"text": "📈 استراتيجيات فوركس", "callback_data": "fx_menu"}]
            ]}
            send(cid, "أهلاً بك في N-Panther.\nاختر الوضع اللي تحب تبدأ بيه:", markup)
            
        elif txt.startswith("/fx"):
            pair = txt.replace("/fx", "").strip()
            if not pair:
                send(cid, "اكتب الزوج بعد الأمر. مثال:\n/fx EUR/USD")
                return
            send(cid, f"⏳ جاري بناء استراتيجية فوركس لـ {pair}...")
            send(cid, ask_ai(cid, f"اعمل استراتيجية فوركس لزوج {pair}", mode="trading"))
            
        else:
            send(cid, ask_ai(cid, txt, mode="general"))
            
    elif "callback_query" in u:
        cq = u["callback_query"]
        cid = cq["message"]["chat"]["id"]
        data = cq["data"]
        try:
            urllib.request.urlopen(urllib.request.Request(f"{API}/answerCallbackQuery", data=json.dumps({"callback_query_id": cq["id"]}).encode(), headers={"Content-Type":"application/json"}, method="POST"), timeout=5)
        except: pass
        
        if data == "gen": 
            send(cid, "🧠 اكتب سؤالك الآن في الشات.")
        elif data == "fx_menu":
            markup = {"inline_keyboard": [
                [{"text": "🇪🇺 EUR/USD", "callback_data": "fx_EUR/USD"}, {"text": "🇬🇧 GBP/USD", "callback_data": "fx_GBP/USD"}],
                [{"text": "🇺🇸 USD/JPY", "callback_data": "fx_USD/JPY"}, {"text": "🥇 XAU/USD (ذهب)", "callback_data": "fx_XAU/USD"}],
                [{"text": "✍️ زوج آخر", "callback_data": "fx_custom"}]
            ]}
            send(cid, "📈 اختر زوج العملات اللي عايز استراتيجية له:", markup)
        elif data.startswith("fx_"):
            pair = data.replace("fx_", "")
            if pair == "custom":
                send(cid, "اكتب اسم الزوج اللي عايزه (مثلاً: AUD/CAD أو US30).")
            else:
                send(cid, f"⏳ جاري بناء استراتيجية لـ {pair}...")
                send(cid, ask_ai(cid, f"اعمل استراتيجية فوركس لزوج {pair}", mode="trading"))

def main():
    offset = 0
    try:
        with open(OFFSET_FILE) as f: offset = int(f.read().strip())
    except: pass
    print("🚀 N-Panther Forex Bot Started")
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

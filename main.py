import os
import json
import time
import signal
import sys
import urllib.request
import urllib.error

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_KEY = "".join(os.environ.get("GEMINI_API_KEY", "").split())

API = f"https://api.telegram.org/bot{TOKEN}"
OFFSET_FILE = "offset.txt"
HISTORY_FILE = "history.json"
TIMEOUT = 15
AI_TIMEOUT = 60
HISTORY_LIMIT = 20
POLL_INTERVAL = 2
RUN_DURATION = 5 * 3600 + 45 * 60

GENERAL_PROMPT = (
    "أنت N-Panther، مساعد ذكي عام ومفكر عميق. "
    "ردودك بالعربي الفصيح البسيط أو العامية حسب لغة المستخدم. "
    "فكر خطوة بخطوة. قدم إجابات مفصلة وعميقة. "
    "ممنوع تقول إنك مجرد نموذج لغوي."
)

TRADING_PROMPT = (
    "أنت N-Panther في وضع التداول — خبير استراتيجيات تداول محترف. "
    "عندما يطلب المستخدم استراتيجية، قدم مخرجات منظمة:\n\n"
    "# 📊 اسم الاستراتيجية\n"
    "**النوع:** اتجاهية/زخم/ارتداد\n"
    "**الإطار الزمني:** M15/H1/H4\n"
    "## المؤشرات\n- اسم المؤشر + الإعدادات\n"
    "## قواعد الدخول (Long)\n1. شرط 1\n## قواعد الدخول (Short)\n1. شرط عكسي\n"
    "## إدارة المخاطر\n- SL و TP (R:R لا يقل عن 1:1.5)\n"
    "## الكود (MT5 Python)\n```python\n[كود جاهز]\n```\n"
)

_running = True
def _stop(*_):
    global _running
    _running = False
signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

def load_offset() -> int:
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f: return int(f.read().strip() or "0")
    except: return 0

def save_offset(n: int) -> None:
    try:
        with open(OFFSET_FILE, "w", encoding="utf-8") as f: f.write(str(n))
    except: pass

def load_history() -> dict:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: return json.load(f) or {}
    except: return {}

def save_history(h: dict) -> None:
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(h, f, ensure_ascii=False, indent=2)
    except: pass

def get_updates(offset: int) -> list:
    url = f"{API}/getUpdates?offset={offset}&timeout=20&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT + 10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"): return data.get("result", [])
    except: pass
    return []

def send_message(chat_id: int, text: str, reply_markup=None) -> bool:
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{API}/sendMessage", data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            resp.read()
        return True
    except Exception as e:
        print("send error", e)
        return False

def send_long(chat_id: int, text: str) -> bool:
    if len(text) <= 4000: return send_message(chat_id, text)
    for i in range(0, len(text), 4000):
        if not send_message(chat_id, text[i:i + 4000]): return False
    return True

def answer_callback(cq_id: str):
    payload = {"callback_query_id": cq_id}
    req = urllib.request.Request(f"{API}/answerCallbackQuery", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try: urllib.request.urlopen(req, timeout=5)
    except: pass

def ask_ai(chat_id: int, user_text: str, mode: str = "general") -> str:
    if not GEMINI_KEY:
        send_message(chat_id, "⚠️ المفتاح مش موجود.")
        return ""
    
    system = TRADING_PROMPT if mode == "trading" else GENERAL_PROMPT
    h = load_history()
    key = str(chat_id)
    history = h.get(key, [])

    contents = []
    for msg in history[-10:]:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"][:1500]}]})
    contents.append({"role": "user", "parts": [{"text": user_text[:4000]}]})

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.8 if mode=="trading" else 0.7, "maxOutputTokens": 4096 if mode=="trading" else 2048},
    }

    models = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-2.5-flash"]

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "X-Goog-Api-Key": GEMINI_KEY}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=AI_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("candidates"):
                    parts = data["candidates"][0].get("content", {}).get("parts", [])
                    reply = "".join(p.get("text", "") for p in parts).strip()
                    if reply:
                        history.append({"role": "user", "content": user_text})
                        history.append({"role": "assistant", "content": reply[:2000]})
                        h[key] = history[-HISTORY_LIMIT:]
                        save_history(h)
                        return reply
        except urllib.error.HTTPError as e:
            if e.code == 429:
                send_message(chat_id, "⚠️ استهلكت الحد (429). استنى دقيقة.")
                return ""
            if e.code in (400, 403):
                send_message(chat_id, f"⚠️ مشكلة في المفتاح ({e.code}).")
                return ""
            continue
        except: continue

    send_message(chat_id, "⚠️ فشل الاتصال بجوجل. جرب تاني.")
    return ""

def process_update(update: dict):
    # 1. التعامل مع الأزرار (Callback Query)
    if "callback_query" in update:
        cq = update["callback_query"]
        chat_id = cq["message"]["chat"]["id"]
        data = cq["data"]
        answer_callback(cq["id"])
        
        if data == "mode_general":
            send_message(chat_id, "🧠 تم تفعيل *الذكاء الاصطناعي العام*. اكتب سؤالك الآن.", reply_markup={"remove_keyboard": True})
        elif data == "mode_trading":
            buttons = [
                [{"text": "🇪🇺 EUR/USD", "callback_data": "trade_EURUSD"}, {"text": "🥇 XAU/USD", "callback_data": "trade_XAUUSD"}],
                [{"text": "₿ BTC/USDT", "callback_data": "trade_BTCUSDT"}, {"text": "✍️ أصل آخر", "callback_data": "trade_custom"}]
            ]
            send_message(chat_id, "📈 *اختر الأصل اللي عايز استراتيجية له:*", reply_markup={"inline_keyboard": buttons})
        elif data.startswith("trade_"):
            asset = data.replace("trade_", "")
            if asset == "custom":
                send_message(chat_id, "اكتب اسم الأصل اللي عايزه (مثلاً: GBP/JPY أو أسهم أبل).")
            else:
                asset = asset.replace("EURUSD", "EUR/USD").replace("XAUUSD", "XAU/USD").replace("BTCUSDT", "BTC/USDT")
                send_message(chat_id, f"⏳ جاري توليد استراتيجية لـ *{asset}*...")
                reply = ask_ai(chat_id, f"اعمل استراتيجية تداول لـ {asset}", mode="trading")
                if reply: send_long(chat_id, reply)
        return

    # 2. التعامل مع الرسائل النصية (Message)
    msg = update.get("message")
    if not msg: return
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    if not chat_id or not text: return

    if text.strip() in ("/start", "/menu"):
        buttons = [
            [{"text": "🧠 ذكاء اصطناعي عام", "callback_data": "mode_general"}],
            [{"text": "📈 استراتيجيات التداول", "callback_data": "mode_trading"}]
        ]
        send_message(chat_id, "أهلاً بك في *N-Panther*.\nاختر الوضع اللي تحب تبدأ بيه:", reply_markup={"inline_keyboard": buttons})
        return

    if text.strip().startswith(("/trade", "/استراتيجية", "/تداول")):
        asset = text.replace("/trade", "").replace("/استراتيجية", "").replace("/تداول", "").strip()
        if not asset:
            send_message(chat_id, "أرسل الأمر مع الأصل. مثال: /trade EUR/USD")
            return
        send_message(chat_id, f"⏳ جاري التوليد...")
        reply = ask_ai(chat_id, f"اعمل استراتيجية لـ {asset}", mode="trading")
        if reply: send_long(chat_id, reply)
        return

    # وضع الذكاء العام (الافتراضي)
    print(f"→ {msg.get('from', {}).get('first_name', '?')}: {text[:60]}")
    reply = ask_ai(chat_id, text, mode="general")
    if reply: send_long(chat_id, reply)

def main():
    if not TOKEN or ":" not in TOKEN: raise SystemExit("TOKEN غير صالح.")
    last_offset = load_offset()
    start_time = time.time()
    print(f"🚀 N-Panther started (UI Mode) — offset={last_offset}")

    while _running and (time.time() - start_time < RUN_DURATION):
        try:
            updates = get_updates(last_offset)
            if updates:
                highest = last_offset
                for u in updates:
                    uid = u.get("update_id")
                    if uid is not None: highest = max(highest, uid + 1)
                    try: process_update(u)
                    except Exception as e: print(f"process error: {e}")
                last_offset = highest
                save_offset(last_offset)
            else:
                time.sleep(POLL_INTERVAL)
        except:
            time.sleep(5)

    save_offset(last_offset)
    sys.exit(0)

if __name__ == "__main__":
    main()

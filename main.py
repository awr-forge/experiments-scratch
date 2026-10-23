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
    "لديك معرفة واسعة في العلوم، البرمجة، التاريخ، الرياضيات، والأدب. "
    "ردودك بالعربي الفصيح البسيط أو العامية حسب لغة المستخدم. "
    "فكر خطوة بخطوة. قدم إجابات مفصلة وعميقة. "
    "ممنوع تقول إنك مجرد نموذج لغوي."
)

TRADING_PROMPT = (
    "أنت N-Panther في وضع التداول — خبير استراتيجيات تداول محترف. "
    "لديك خبرة في الفوركس، الكريبتو، السلع، والأسهم. "
    "تعرف MT5، TradingView، Pine Script، Python. "
    "\n\n"
    "عندما يطلب المستخدم استراتيجية، قدم مخرجات منظمة:\n\n"
    "# 📊 اسم الاستراتيجية\n\n"
    "**النوع:** اتجاهية/زخم/ارتداد/انعكاس\n"
    "**الأصل المناسب:** [أزواج العملات/كريبتو/سلع]\n"
    "**الإطار الزمني:** M15/H1/H4\n\n"
    "## المؤشرات\n- اسم المؤشر + الإعدادات\n\n"
    "## قواعد الدخول (Long)\n1. شرط 1\n2. شرط 2\n\n"
    "## قواعد الدخول (Short)\n1. شرط عكسي\n\n"
    "## إدارة المخاطر\n- SL: [حساب]\n- TP: [حساب]\n- R:R لا يقل عن 1:1.5\n- 1-2% من رأس المال\n\n"
    "## الكود (MT5 Python أو Pine)\n```python\n[كود جاهز]\n```\n\n"
    "## ملاحظات\n- Backtest على 6 أشهر\n"
)

_running = True

def _stop(*_):
    global _running
    _running = False

signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

def load_offset() -> int:
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip() or "0")
    except:
        return 0

def save_offset(n: int) -> None:
    try:
        with open(OFFSET_FILE, "w", encoding="utf-8") as f:
            f.write(str(n))
    except:
        pass

def load_history() -> dict:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except:
        return {}

def save_history(h: dict) -> None:
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_updates(offset: int) -> list:
    url = f"{API}/getUpdates?offset={offset}&timeout=20&allowed_updates=%5B%22message%22%5D"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT + 10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return data.get("result", [])
    except:
        pass
    return []

def send_message(chat_id: int, text: str) -> bool:
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/sendMessage", data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            resp.read()
        return True
    except:
        return False

def send_long(chat_id: int, text: str) -> bool:
    if len(text) <= 4000:
        return send_message(chat_id, text)
    for i in range(0, len(text), 4000):
        if not send_message(chat_id, text[i:i + 4000]):
            return False
    return True

def ask_ai(chat_id: int, user_text: str) -> str:
    if not GEMINI_KEY:
        send_message(chat_id, "⚠️ المفتاح مش موجود في السيرفر.")
        return ""

    # 👇 الفصل هنا: بنشوف لو الرسالة بادئة بـ /trade أو /استراتيجية
    is_trade = user_text.strip().startswith(("/trade", "/استراتيجية", "/تداول"))
    
    if is_trade:
        # بنشيل الأمر من النص عشان يتبعت للـ AI نضيف
        user_text = user_text.replace("/trade", "").replace("/استراتيجية", "").replace("/تداول", "").strip()
        system = TRADING_PROMPT
        print("Mode: TRADING")
        if not user_text:
            send_message(chat_id, "أرسل الأمر مع الأصل اللي عايز استراتيجية له. مثال:\n/trade EUR/USD")
            return ""
    else:
        system = GENERAL_PROMPT
        print("Mode: GENERAL")

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
        "generationConfig": {
            "temperature": 0.8 if is_trade else 0.7,
            "maxOutputTokens": 4096 if is_trade else 2048
        },
    }

    models = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-2.5-flash"]
    last_error = "Unknown"

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Goog-Api-Key": GEMINI_KEY},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=AI_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    reply = "".join(p.get("text", "") for p in parts).strip()
                    if reply:
                        history.append({"role": "user", "content": user_text})
                        history.append({"role": "assistant", "content": reply[:2000]})
                        h[key] = history[-HISTORY_LIMIT:]
                        save_history(h)
                        return reply
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            print(f"{model} HTTP {e.code}")
            last_error = f"{e.code}"
            if e.code == 429:
                send_message(chat_id, "⚠️ استهلكت الحد المجاني (429). استنى دقيقة وجرب تاني.")
                return ""
            if e.code in (400, 403):
                send_message(chat_id, f"⚠️ مشكلة في المفتاح ({e.code}).")
                return ""
            continue
        except Exception as e:
            last_error = str(e)
            continue

    send_message(chat_id, f"⚠️ فشل الاتصال بجوجل ({last_error}). جرب تاني.")
    return ""

def process_update(update: dict) -> None:
    msg = update.get("message")
    if not msg: return
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    if not chat_id or not text: return

    print(f"→ {msg.get('from', {}).get('first_name', '?')}: {text[:60]}")
    reply = ask_ai(chat_id, text)
    if reply:
        send_long(chat_id, reply)

def main() -> None:
    if not TOKEN or ":" not in TOKEN:
        raise SystemExit("TELEGRAM_TOKEN غير صالح.")

    last_offset = load_offset()
    start_time = time.time()
    print(f"🚀 N-Panther started — offset={last_offset}")

    while _running and (time.time() - start_time < RUN_DURATION):
        try:
            updates = get_updates(last_offset)
            if updates:
                highest = last_offset
                for u in updates:
                    uid = u.get("update_id")
                    if uid is not None:
                        highest = max(highest, uid + 1)
                    try:
                        process_update(u)
                    except Exception as e:
                        print(f"process error: {e}")
                last_offset = highest
                save_offset(last_offset)
            else:
                time.sleep(POLL_INTERVAL)
        except Exception:
            time.sleep(5)

    save_offset(last_offset)
    sys.exit(0)

if __name__ == "__main__":
    main()

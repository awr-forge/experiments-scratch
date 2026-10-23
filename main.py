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
    "أنت N-Panther، مساعد ذكي متعدد القدرات ومفكر عميق. "
    "لديك معرفة واسعة في العلوم، البرمجة، التاريخ، الرياضيات، والأدب. "
    "ردودك بالعربي الفصيح البسيط أو العامية حسب لغة المستخدم. "
    "فكر خطوة بخطوة. قدم إجابات مفصلة وعميقة. "
    "لو السؤال تقني، اشرح الأسباب والحلول بالتفصيل. "
    "ممنوع تقول إنك مجرد نموذج لغوي. لو مش واضح، اسأل للتوضيح."
)

TRADING_PROMPT = (
    "أنت N-Panther في وضع التداول — خبير استراتيجيات تداول محترف. "
    "لديك خبرة في الفوركس، الكريبتو، السلع، والأسهم. "
    "تعرف MT5، TradingView، Pine Script، Python (pandas/numpy/backtrader). "
    "\n\n"
    "عندما يطلب المستخدم استراتيجية، قدم مخرجات منظمة بالشكل ده:\n\n"
    "# 📊 اسم الاستراتيجية\n\n"
    "**النوع:** اتجاهية/زخم/ارتداد/انعكاس/بريك أوت\n"
    "**الأصل المناسب:** [اذكر أزواج العملات أو الكريبتو أو السلع]\n"
    "**الإطار الزمني:** M15/H1/H4/D1\n\n"
    "## المؤشرات\n"
    "- اسم المؤشر + الإعدادات + الدور في الاستراتيجية\n\n"
    "## قواعد الدخول (Long)\n"
    "1. شرط رقم 1\n2. شرط رقم 2\n\n"
    "## قواعد الدخول (Short)\n"
    "1. شرط عكسي\n\n"
    "## إدارة المخاطر\n"
    "- SL: [طريقة الحساب]\n"
    "- TP: [طريقة الحساب، نسبة R:R]\n"
    "- حجم الصفقة: 1-2% من رأس المال\n"
    "- Max Drawdown: X%\n\n"
    "## الكود (MT5 Python)\n"
    "```python\n[كود جاهز للتشغيل]\n```\n\n"
    "## ملاحظات التطبيق\n"
    "- Backtest على 6-12 شهر\n"
    "- جرب على demo أولاً\n\n"
    "قواعد صارمة:\n"
    "- لا تقترح استراتيجية بدون SL\n"
    "- دائماً نسبة R:R لا تقل عن 1:1.5\n"
    "- استخدم ATR لحساب SL ديناميكي\n"
    "- الكود يكون MT5 ready أو Pine Script حسب طلب المستخدم\n"
    "- لو المستخدم طلب أصل معين، ركز عليه\n"
    "- لو مش واضح، اقترح 2-3 استراتيجيات مختلفة\n"
)

TRADING_KEYWORDS = (
    "استراتيجية", "استراتيجيه", "ستراتيجية", "تداول", "تريدنج", "صفقة", "صفقات",
    "دخول", "خروج", "شراء", "بيع", "لونج", "شورت", "long", "short",
    "eur/usd", "gbpusd", "usdjpy", "xauusd", "gold", "bitcoin", "btc", "eth",
    "فوركس", "كريبتو", "عملات", "ذهب", "نفط", "أسهم",
    "rsi", "ema", "macd", "atr", "bollinger", "fibonacci", "support", "resistance",
    "مؤشر", "مؤشرات", "تحليل فني", "كسر", "دعم", "مقاومة", "اتجاه", "زخم",
    "سكالبينج", "سوينج", "سكالب", "باك تست", "backtest", "mt5", "metatrader",
    "pine script", "tradingview", "risk", "stop loss", "take profit"
)

def is_trading_query(text: str) -> bool:
    low = (text or "").lower()
    return any(k in low for k in TRADING_KEYWORDS)

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

    trading = is_trading_query(user_text)
    system = TRADING_PROMPT if trading else GENERAL_PROMPT
    print(f"Mode: {'TRADING' if trading else 'GENERAL'}")

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
            "temperature": 0.8 if trading else 0.7,
            "maxOutputTokens": 4096 if trading else 2048
        },
    }

    models = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-2.5-flash"]
    last_error = "Unknown"

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-goog-api-key": GEMINI_KEY},
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

    send_message(chat_id, f"⚠️ فشل الاتصال بجوجل ({last_error}). جرب تاني بعد دقيقة.")
    return ""

def fallback_response(text: str) -> str:
    return "النظام يستقبل رسالتك. جرب سؤال محدد."

def process_update(update: dict) -> None:
    msg = update.get("message")
    if not msg: return
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    if not chat_id or not text: return

    print(f"→ {msg.get('from', {}).get('first_name', '?')}: {text[:60]}")
    reply = ask_ai(chat_id, text)
    if not reply:
        reply = fallback_response(text)
    send_long(chat_id, reply)

def main() -> None:
    if not TOKEN or ":" not in TOKEN:
        raise SystemExit("TELEGRAM_TOKEN غير صالح.")

    last_offset = load_offset()
    start_time = time.time()
    print(f"🚀 N-Panther started — offset={last_offset} — mode: general+trading")

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

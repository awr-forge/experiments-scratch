import os
import json
import time
import signal
import sys
import datetime
import urllib.request
import urllib.error

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

API = f"https://api.telegram.org/bot{TOKEN}"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"

OFFSET_FILE = "offset.txt"
HISTORY_FILE = "history.json"
TIMEOUT = 15
AI_TIMEOUT = 40
HISTORY_LIMIT = 20
POLL_INTERVAL = 2

# 5 ساعات و 45 دقيقة (أقصى حد لجيت هب 6 ساعات)
RUN_DURATION = 5 * 3600 + 45 * 60

SYSTEM_PROMPT = (
    "أنت N-Panther، مساعد ذكي متعدد القدرات. "
    "لديك معرفة واسعة في العلوم، البرمجة، التاريخ، الرياضيات، والأدب. "
    "ردودك بالعربي الفصيح البسيط أو العامية حسب لغة المستخدم. "
    "كن مباشراً، مفيداً، ومختصراً. لو السؤال تقني، جاوب بدقة. "
    "لو مش واضح، اسأل للتوضيح. متقولش إنك مبني على موديل معين."
)

_running = True

def _stop(*_):
    global _running
    _running = False
    print("إشارة إيقاف — بنقفل...")

signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

def load_offset() -> int:
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip() or "0")
    except (FileNotFoundError, ValueError):
        return 0

def save_offset(n: int) -> None:
    try:
        with open(OFFSET_FILE, "w", encoding="utf-8") as f:
            f.write(str(n))
    except OSError as e:
        print(f"تعذر حفظ الـ offset: {e}")

def load_history() -> dict:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (FileNotFoundError, ValueError):
        return {}

def save_history(h: dict) -> None:
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"تعذر حفظ الـ history: {e}")

def get_updates(offset: int) -> list:
    url = f"{API}/getUpdates?offset={offset}&timeout=20&allowed_updates=%5B%22message%22%5D"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT + 10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return data.get("result", [])
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.reason}")
    except Exception as e:
        print(f"getUpdates error: {e}")
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
    except urllib.error.HTTPError as e:
        try:
            print(f"sendMessage HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
        except Exception:
            print(f"sendMessage HTTP {e.code}")
    except Exception as e:
        print(f"sendMessage error: {e}")
    return False

def send_long(chat_id: int, text: str) -> bool:
    if len(text) <= 4000:
        return send_message(chat_id, text)
    for i in range(0, len(text), 4000):
        if not send_message(chat_id, text[i:i + 4000]):
            return False
    return True

def ask_ai(chat_id: int, user_text: str) -> str:
    print(f"DEBUG_KEY_LEN: {len(GEMINI_KEY)}")
    if not GEMINI_KEY:
        return ""
    h = load_history()
    key = str(chat_id)
    history = h.get(key, [])

    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_text[:4000]}]})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
    }
    req = urllib.request.Request(
        GEMINI_URL,
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
                    history.append({"role": "assistant", "content": reply})
                    h[key] = history[-HISTORY_LIMIT:]
                    save_history(h)
                    return reply
            send_message(chat_id, f"⚠️ Gemini Empty: {str(data)[:300]}")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
            print(f"Gemini HTTP {e.code}: {body[:300]}")
            send_message(chat_id, f"⚠️ Gemini HTTP {e.code}
{body[:500]}")
        except Exception:
            print(f"Gemini HTTP {e.code}")
            send_message(chat_id, f"⚠️ Gemini HTTP {e.code}")
    except Exception as e:
        print(f"Gemini error: {e}")
        send_message(chat_id, f"⚠️ Error: {str(e)}")
    return ""


def fallback_response(text: str) -> str:
    low = (text or "").lower()
    if any(k in low for k in ("/start", "مرحبا", "هلا", "سلام", "السلام")):
        return "أهلاً بك. أنا N-Panther، مساعدك الذكي. اسألني أي حاجة."
    if any(k in low for k in ("الوقت", "التاريخ", "ساعة")):
        return f"⏱ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return "النظام يستقبل رسالتك. جرب سؤال محدد."

def process_update(update: dict) -> None:
    msg = update.get("message")
    if not msg: return
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    if not chat_id or not text: return
    name = msg.get("from", {}).get("first_name", "?")
    print(f"→ {name} ({chat_id}): {text[:60]}")

    reply = ask_ai(chat_id, text[:3000]) if GEMINI_KEY else ""
    if not reply:
        reply = fallback_response(text)
    send_long(chat_id, reply)

def main() -> None:
    if not TOKEN or ":" not in TOKEN:
        raise SystemExit("TELEGRAM_TOKEN غير صالح.")
    print(f"DEBUG_KEY_LEN: {len(GEMINI_KEY)}")
    if not GEMINI_KEY:
        print("⚠️ GEMINI_API_KEY غير مضبوط")

    last_offset = load_offset()
    if last_offset == 0:
        try:
            url = f"{API}/getUpdates?offset=-1&limit=1&allowed_updates=%5B%22message%22%5D"
            with urllib.request.urlopen(urllib.request.Request(url), timeout=TIMEOUT) as r:
                d = json.loads(r.read().decode())
                if d.get("ok") and d.get("result"):
                    last_offset = d["result"][-1]["update_id"] + 1
        except Exception as e:
            print(f"bootstrap: {e}")

    start_time = time.time()
    print(f"🚀 Bot started — offset={last_offset} — سيشتغل لمدة {RUN_DURATION//3600} ساعات")

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
        except Exception as e:
            print(f"loop error: {e}")
            time.sleep(5)

    print("⏰ انتهت مدة التشغيل. جيت هب هيشغل run جديد تلقائياً.")
    save_offset(last_offset)
    sys.exit(0)

if __name__ == "__main__":
    main()

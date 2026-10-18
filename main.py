import os
import json
import datetime
import urllib.request
import urllib.error

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "").strip()

API = f"https://api.telegram.org/bot{TOKEN}"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
TAVILY_URL = "https://api.tavily.com/search"

OFFSET_FILE = "offset.txt"
HISTORY_FILE = "history.json"
TIMEOUT = 15
AI_TIMEOUT = 40
HISTORY_LIMIT = 20

SYSTEM_PROMPT = (
    "أنت N-Panther، مساعد ذكي متعدد القدرات. "
    "لديك معرفة واسعة في العلوم، البرمجة، التاريخ، الرياضيات، والأدب. "
    "لو المستخدم سأل عن حاجة حديثة أو محتاج معلومات لحظية، "
    "هيتم تزويدك بنتائج بحث من الويب — استخدمها في إجابتك. "
    "ردودك بالعربي الفصيح البسيط أو العامية حسب لغة المستخدم. "
    "كن مباشراً، مفيداً، ومختصراً. لو السؤال تقني، جاوب بدقة. "
    "لو مش واضح، اسأل للتوضيح. متقولش إنك مبني على موديل معين."
)

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
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError):
        return {}

def save_history(h: dict) -> None:
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"تعذر حفظ الـ history: {e}")

def bootstrap_offset() -> int:
    url = f"{API}/getUpdates?offset=-1&limit=1&allowed_updates=%5B%22message%22%5D"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                results = data.get("result", [])
                if results:
                    return results[-1]["update_id"] + 1
    except Exception as e:
        print(f"تعذر bootstrap: {e}")
    return 0

def get_updates(offset: int) -> list:
    url = f"{API}/getUpdates?offset={offset}&timeout=10&allowed_updates=%5B%22message%22%5D"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return data.get("result", [])
            print(f"استجابة غير ناجحة: {data}")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.reason}")
    except Exception as e:
        print(f"خطأ في جلب التحديثات: {e}")
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
        print(f"تم الإرسال إلى {chat_id}")
        return True
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8", errors="replace") if e else ""
        print(f"فشل الإرسال HTTP {e.code}: {resp_body[:200]}")
    except Exception as e:
        print(f"فشل الإرسال: {e}")
    return False

def send_long(chat_id: int, text: str) -> bool:
    if len(text) <= 4000:
        return send_message(chat_id, text)
    ok = True
    for i in range(0, len(text), 4000):
        if not send_message(chat_id, text[i:i + 4000]):
            ok = False
    return ok

def web_search(query: str) -> str:
    if not TAVILY_KEY:
        return ""
    payload = {
        "api_key": TAVILY_KEY,
        "query": query,
        "search_depth": "basic",
        "include_answer": True,
        "max_results": 3,
    }
    req = urllib.request.Request(
        TAVILY_URL, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=AI_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            answer = data.get("answer", "")
            results = data.get("results", [])
            snippets = []
            if answer:
                snippets.append(f"خلاصة: {answer}")
            for r in results[:3]:
                snippets.append(f"- {r.get('title', '')}: {r.get('content', '')[:400]}")
            return "\n".join(snippets)
    except Exception as e:
        print(f"Tavily error: {e}")
    return ""

def ask_ai(chat_id: int, user_text: str) -> str:
    if not GEMINI_KEY:
        return ""
    h = load_history()
    key = str(chat_id)
    history = h.get(key, [])

    search_triggers = ("سعر", "خبر", "أخبار", "مباراة", "نتيجة", "الطقس", "اليوم", "أمس", "حاليا", "الآن", "2025", "2026", "من هو", "ما هو آخر", "حدث", "جديد", "تحديث")
    search_context = ""
    if False and TAVILY_KEY and any(t in user_text for t in search_triggers):
        print(f"🔍 بحث ويب: {user_text[:50]}")
        search_context = web_search(user_text)

    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    final_prompt = user_text
    if search_context:
        final_prompt = f"{user_text}\n\n[نتائج بحث ويب حديثة — استخدمها للإجابة]:\n{search_context}"

    contents.append({"role": "user", "parts": [{"text": final_prompt}]})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
    }

    req = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-goog-api-key": GEMINI_KEY
        },
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
            print(f"Gemini: مفيش رد — {data}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e else ""
        print(f"Gemini HTTP {e.code}: {body[:300]}")
    except Exception as e:
        print(f"Gemini error: {e}")
    return ""

def fallback_response(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "أرسل رسالة نصية من فضلك."
    low = t.lower()
    if any(k in low for k in ("/start", "مرحبا", "هلا", "سلام", "السلام")):
        return "أهلاً بك يا نورالدين. أنا N-Panther، مساعدك الذكي. اسألني أي حاجة."
    if any(k in low for k in ("الوقت", "التاريخ", "ساعة")):
        return f"⏱ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return "النظام يستقبل رسالتك. جرب تسألني سؤال محدد."

def main() -> None:
    if not TOKEN or ":" not in TOKEN:
        raise SystemExit("TELEGRAM_TOKEN غير صالح.")
    if not GEMINI_KEY:
        print("⚠️ GEMINI_API_KEY غير مضبوط")

    last_offset = load_offset()
    if last_offset == 0:
        boot = bootstrap_offset()
        if boot > 0:
            last_offset = boot
            print(f"bootstrap: {boot}")

    print(f"بدء الفحص من offset={last_offset}")
    updates = get_updates(last_offset)
    if not updates:
        print("لا توجد رسائل جديدة.")
        save_offset(last_offset)
        return

    highest = last_offset
    handled = 0
    for update in updates:
        uid = update.get("update_id")
        if uid is not None:
            highest = max(highest, uid + 1)

        msg = update.get("message")
        if not msg: continue
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "")
        
        if chat_id is None or not text: continue
        print(f"→ {msg.get('from', {}).get('first_name', 'صديقي')} ({chat_id}): {text[:60]}")

        ai_reply = ask_ai(chat_id, text) if GEMINI_KEY else ""
        if ai_reply:
            if send_long(chat_id, ai_reply):
                handled += 1
        else:
            if send_message(chat_id, fallback_response(text)):
                handled += 1

    save_offset(highest)
    print(f"انتهى الفحص — تم الرد على {handled} من {len(updates)} تحديث.")

if __name__ == "__main__":
    main()

import os
import json
import datetime
import urllib.request
import urllib.error

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"

OFFSET_FILE = "offset.txt"
TIMEOUT = 15


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


def get_updates(offset: int) -> list:
    url = (
        f"{API}/getUpdates"
        f"?offset={offset}"
        f"&timeout=10"
        f"&allowed_updates=%5B%22message%22%5D"
    )
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


def send_message(chat_id: int, text: str, parse_mode: str = "MarkdownV2") -> bool:
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            resp.read()
        print(f"تم الإرسال إلى {chat_id}")
        return True
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        print(f"فشل الإرسال HTTP {e.code}: {body}")
    except Exception as e:
        print(f"فشل الإرسال: {e}")
    return False


_MD_SPECIAL = set(r"_*[]()~`>#+-=|{}.!")


def esc(s: str) -> str:
    return "".join("\\" + ch if ch in _MD_SPECIAL else ch for ch in s)


def advanced_response(text: str) -> str:
    raw = text or ""
    t = raw.strip()
    if not t:
        return esc("أرسل رسالة نصية من فضلك.")

    low = t.lower()

    if any(k in low for k in ("/start", "مرحبا", "هلا", "السلام")):
        return (
            "*أهلاً بك يا نورالدين\\.*\n\n"
            "أنا نظامك الذكي المستقل، أعمل بالكامل عبر خوادم غيت هب السحابية "
            "بدون قيود أو اشتراكات\\.\n"
            "جاهز لتحليل أفكارك، إدارة مهامك، وتقديم استجابات دقيقة\\.\n\n"
            "*بماذا نبدأ اليوم؟*"
        )

    if any(k in low for k in ("تحليل", "نظام")):
        return (
            "*📊 تقرير التحليل الاستراتيجي الفوري:*\n\n"
            "• *البنية التحتية:* تعمل بنجاح تام عبر خوادم غيت هب السحابية المستقلة\\.\n"
            "• *الأمان والتحكم:* ملكية كاملة للبيانات بدون أي قيود أو وسطاء\\.\n"
            "• *جاهزية التنفيذ:* المنظومة مستعدة لاستقبال وتدفق الأوامر البرمجية بدقة عالية\\."
        )

    if any(k in low for k in ("الوقت", "التاريخ", "ساعة")):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"*⏱ ختم الوقت للنظام:*\n`{esc(now)}`"

    if any(k in low for k in ("مساعد", "اوامر", "أوامر", "help", "/help")):
        return (
            "*📖 الأوامر المتاحة:*\n\n"
            "• `/start` — الترحيب\\.\n"
            "• `تحليل` — تقرير استراتيجي\\.\n"
            "• `الوقت` — الوقت والتاريخ\\.\n"
            "• أي نص آخر — تحليل عميق تلقائي\\."
        )

    safe = esc(t)
    return (
        "*🧠 التحليل العميق للمدخل:*\n"
        f"استقبلت رسالتك: _{safe}_\n\n"
        "النظام يعمل بكفاءة تامة لمعالجة الطلب وتقديم النتائج المطلوبة بدقة وحرية كاملة\\."
    )


def main() -> None:
    if not TOKEN:
        raise SystemExit("TELEGRAM_TOKEN غير مضبوط في البيئة.")
    if ":" not in TOKEN:
        raise SystemExit("TELEGRAM_TOKEN يبدو غير صالح.")

    last_offset = load_offset()
    print(f"بدء الفحص من offset={last_offset}")

    updates = get_updates(last_offset)
    if not updates:
        print("لا توجد رسائل جديدة.")
        return

    highest = last_offset
    handled = 0

    for update in updates:
        uid = update.get("update_id")
        if uid is not None:
            highest = max(highest, uid + 1)

        msg = update.get("message")
        if not msg:
            continue

        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "")
        user_name = msg.get("from", {}).get("first_name", "صديقي")

        if chat_id is None or not text:
            continue

        print(f"→ {user_name} ({chat_id}): {text[:60]}")
        reply = advanced_response(text)
        if send_message(chat_id, reply):
            handled += 1

    save_offset(highest)
    print(f"انتهى الفحص — تم الرد على {handled} من {len(updates)} تحديث.")


if __name__ == "__main__":
    main()

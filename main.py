import urllib.request
import json
import datetime
import time

TOKEN = "8674718185:AAHFbjFh-6Y3NxtzTA6j8JOpKxEgZ2q3Yw1s"

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?timeout=30"
    if offset:
        url += f"&offset={offset}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=35) as response:
            data = json.loads(response.read().decode())
            if data.get("ok"):
                return data.get("result", [])
    except Exception as e:
        print(f"خطأ في جلب التحديثات: {e}")
    return []

def send_message(chat_id, text):
    send_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    try:
        req = urllib.request.Request(send_url, data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"خطأ في إرسال الرسالة: {e}")

def advanced_response(text):
    text_lower = text.lower().strip()

    if "/start" in text_lower or "مرحبا" in text_lower or "هلا" in text_lower:
        return (
            "أهلاً بك يا نورالدين.\n\n"
            "أنا نظامك الذكي المستقل والمصمم للعمل بالكامل بدون قيود أو اشتراكات خارجية.\n"
            "جاهز لتحليل أفكارك، إدارة مهامك، وتقديم استجابات عميقة ودقيقة.\n\n"
            "بماذا نبدأ اليوم؟"
        )
    elif "تحليل" in text_lower or "نظام" in text_lower:
        return (
            "📊 **تقرير التحليل الاستراتيجي الفوري:**\n\n"
            "• **البنية التحتية:** تعمل بنجاح تامة عبر خوادم مستقلة.\n"
            "• **الأمان والتحكم:** ملكية كاملة للبيانات بدون أي قيود أو وسطاء.\n"
            "• **جاهزية التنفيذ:** المنظومة مستعدة لاستقبال وتدفق الأوامر البرمجية بدقة عالية."
        )
    elif "الوقت" in text_lower or "التاريخ" in text_lower:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"⏱ **ختم الوقت للنظام:**\n`{now}`"
    else:
        return (
            f"🧠 **التحليل العميق للمدخل:**\n"
            f"لقد استقبلت رسالتك بتركيز: *[{text}]*\n\n"
            "النظام يعمل بكفاءة تامة لمعالجة الطلب وتقديم النتائج المطلوبة بدقة وحرية كاملة."
        )

def main():
    print("بدأ تشغيل بوت N-Panther بنجاح.. في انتظار الرسائل.")
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "message" in update:
                msg = update["message"]
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")

                user_data = msg.get("from", {})
                user_name = user_data.get("first_name", "صديقي")

                if text:
                    print(f"معالجة الطلب من {user_name}: {text}")
                    reply_text = advanced_response(text)
                    send_message(chat_id, reply_text)
        time.sleep(1)

if __name__ == "__main__":
    main()

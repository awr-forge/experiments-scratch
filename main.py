import urllib.request
import json
import datetime

TOKEN = "8804023843:AAGSA08aG-UhZEi-zZboYro1Y6QmaFz5HmY"

def get_updates():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
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
        "text": text
    }).encode("utf-8")
    try:
        req = urllib.request.Request(send_url, data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"خطأ في إرسال الرسالة: {e}")

def advanced_response(text):
    text_lower = text.lower().strip()
    
    if text_lower in ["/start", "بدء", "مرحبا"]:
        return "أهلاً بك يا نورالدين. تم إصلاح المشكلة وتحديث المساعد الذكي المتقدم بنجاح وبدون أي قيود. أرسل لي أي استفسار أو أمر لأقوم بتحليله والرد عليه فوراً."
    elif "تحليل" in text_lower or "فكرة" in text_lower:
        return "منظومة التحليل جاهزة. بناءً على المدخلات الخاصة بك، أنصح دائماً بترتيب الأولويات، دراسة الجدوى بدقة، وتطبيق الأتمتة البرمجية لتوفير الوقت والجهد."
    elif "الوقت" in text_lower or "التاريخ" in text_lower:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"التاريخ والوقت الحالي للنظام: {now}"
    elif "المطور" in text_lower or "من أنا" in text_lower:
        return "أنت المؤسس والمطور نورالدين، وأنا مساعدك الشخصي المصمم لتنفيذ المهام البرمجية وإدارتها بكفاءة مطلقة."
    else:
        return f"استقبلت رسالتك وتحليلها: [{text}]. أنا أعمل بناءً على قالبك البرمجي المخصص وجاهز لأي تطوير إضافي ترغب به."

def main():
    updates = get_updates()
    if not updates:
        print("لا توجد رسائل جديدة في هذه الدورة.")
        return

    print(f"تم رصد {len(updates)} تحديث جديد.")
    for update in updates:
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            
            # قراءة آمنة لاسم المستخدم لتجنب أي أخطاء
            user_data = msg.get("from", {})
            user_name = user_data.get("first_name", "صديقي")
            
            if not text:
                continue
                
            print(f"معالجة رسالة من {user_name}: {text}")
            
            reply_text = advanced_response(text)
            send_message(chat_id, reply_text)
            
    print("انتهت دورة المعالجة بنجاح.")

if __name__ == "__main__":
    main()

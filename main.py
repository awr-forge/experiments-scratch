import urllib.request
import json

TOKEN = "8804023843:AAGSA08aG-UhZEi-zZboYro1Y6QmaFz5HmY"
url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        if data.get("ok"):
            updates = data.get("result", [])
            print(f"تم فحص الرسائل بنجاح. عدد الرسائل الجديدة: {len(updates)}")
            for update in updates:
                if "message" in update:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"].get("text", "")
                    print(f"رسالة واردة: {text}")
                    
                    # إرسال رد بسيط
                    send_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                    payload = json.dumps({
                        "chat_id": chat_id,
                        "text": f"أهلاً بك! وصلتني رسالتك: '{text}' وأنا أعمل بنجاح على GitHub."
                    }).encode("utf-8")
                    
                    req_send = urllib.request.Request(send_url, data=payload, headers={'Content-Type': 'application/json'})
                    urllib.request.urlopen(req_send)
        else:
            print("خطأ في الاتصال ببوت تيليجرام.")
except Exception as e:
    print(f"حدث استثناء: {e}")

print("انتهت دورة الفحص بنجاح والخروج آمن.")

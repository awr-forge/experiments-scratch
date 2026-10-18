import os
import telebot

# استخدام توكن البوت الخاص بك
TOKEN = "8804023843:AAGSA08aG-UhZEi-zZboYro1Y6QmaFz5HmY"
bot = telebot.TeleBot(TOKEN)

def process_messages():
    try:
        # جلب التحديثات المعلقة (الرسائل الجديدة) دفعة واحدة
        updates = bot.get_updates(allowed_updates=["message", "callback_query"])
        
        for update in updates:
            if update.message:
                chat_id = update.message.chat.id
                text = update.message.text
                user_name = update.message.from_user.first_name or "صديقي"
                
                print(f"تم استلام رسالة من {user_name}: {text}")
                
                # الرد التلقائي على الرسالة
                if text == "/start":
                    bot.send_message(chat_id, f"أهلاً بك يا {user_name}! تم تشغيل البوت عبر GitHub بنجاح واستلام رسالتك 🚀")
                else:
                    bot.send_message(chat_id, f"أهلاً بك! وصلتني رسالتك: '{text}' وأنا أعمل بنجاح على GitHub.")
                
                # تأكيد استلام الرسالة لكي لا يتم الرد عليها مراراً وتكراراً في الدورة القادمة
                bot.telebot_offset = update.update_id + 1
                
    except Exception as e:
        print(f"حدث خطأ أثناء جلب الرسائل: {e}")

if __name__ == "__main__":
    print("بدء دورة فحص الرسائل...")
    process_messages()
    print("انتهت الدورة بنجاح وخروج آمن.")

import telebot

TOKEN = '8804023843:AAGSA08aG-UhZEi-zZboYro1Y6QmaFz5HmY'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك يا نورالدين! تم تشغيل البوت بنجاح 🚀")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    user_text = message.text
    bot.reply_to(message, f"أهلاً بك! لقد استقبلت رسالتك: '{user_text}'")

if __name__ == '__main__':
    print("البوت يعمل الآن...")
    bot.infinity_polling()

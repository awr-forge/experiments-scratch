import os
import telebot

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    print("Error: BOT_TOKEN is not set.")
    exit(1)

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك يا نورالدين! البوت التفاعلي يعمل الآن بنجاح واستعداد تام لتلقي أوامرك.")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"وصلتني رسالتك: {message.text}")

if __name__ == '__main__':
    print("Bot is starting polling...")
    bot.infinity_polling()

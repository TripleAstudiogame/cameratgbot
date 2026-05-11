import telebot
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('TELEGRAM_BOT_TOKEN')
if not token:
    print("Ошибка: Токен бота не найден в файле .env")
    exit(1)

bot = telebot.TeleBot(token)

print("Бот запущен! Напишите ему любое сообщение в Telegram, чтобы узнать свой Chat ID.")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    chat_id = message.chat.id
    bot.reply_to(message, f"Ваш Chat ID: {chat_id}\nСкопируйте его и вставьте в файл .env в поле TELEGRAM_CHAT_ID")
    print(f"Пользователь {message.from_user.username} написал боту. Chat ID: {chat_id}")

try:
    bot.infinity_polling()
except KeyboardInterrupt:
    print("\nБот остановлен.")

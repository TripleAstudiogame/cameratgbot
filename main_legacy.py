import os
import time
import schedule
import telebot
import io
import logging
import html
import json
import threading
import queue
import re
from imap_tools import MailBox, AND
from dotenv import load_dotenv

from PIL import Image
import pillow_heif

# Регистрируем HEIF плагин для корректного чтения .heic файлов от Apple
pillow_heif.register_heif_opener()

# Настраиваем подробное логирование (в консоль и в файл bot.log)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_APP_PASSWORD = os.getenv('MAIL_APP_PASSWORD')

if not all([TELEGRAM_BOT_TOKEN, MAIL_USERNAME, MAIL_APP_PASSWORD]):
    logging.error("Ошибка: Не все данные заполнены в файле .env! (TELEGRAM_CHAT_ID теперь необязателен)")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

SUBSCRIBERS_FILE = 'subscribers.json'
message_queue = queue.Queue()

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, 'r') as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Ошибка загрузки подписчиков: {e}")
            return set()
    return set()

def save_subscribers(subs):
    try:
        with open(SUBSCRIBERS_FILE, 'w') as f:
            json.dump(list(subs), f)
    except Exception as e:
        logging.error(f"Ошибка сохранения подписчиков: {e}")

subscribers = load_subscribers()

# Добавим админа из .env в подписчики, если он там есть
if TELEGRAM_CHAT_ID:
    try:
        admin_id = int(TELEGRAM_CHAT_ID)
        if admin_id not in subscribers:
            subscribers.add(admin_id)
            save_subscribers(subscribers)
    except ValueError:
        pass

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    if chat_id not in subscribers:
        subscribers.add(chat_id)
        save_subscribers(subscribers)
        bot.reply_to(message, "✅ Уведомление от камер включено!")
        logging.info(f"Новый подписчик: {chat_id}")
    else:
        bot.reply_to(message, "✅ Уведомление от камер уже включено!")

def check_mail():
    logging.info("Проверка новой почты...")
    try:
        with MailBox('imap.mail.ru').login(MAIL_USERNAME, MAIL_APP_PASSWORD) as mailbox:
            # Ищем все непрочитанные сообщения, но пока НЕ помечаем их как прочитанные
            for msg in mailbox.fetch(AND(seen=False), mark_seen=False):
                logging.info(f"Найдено новое письмо: '{msg.subject}' от {msg.from_}")
                
                # --- ПОЛНЫЙ ВЫВОД ДАННЫХ ПИСЬМА ДЛЯ ПОКАЗА ---
                logging.info("=== ДАННЫЕ ПОЛУЧЕННОГО ПИСЬМА ===")
                logging.info(f"Отправитель (from_): {msg.from_}")
                logging.info(f"Кому (to): {msg.to}")
                logging.info(f"Тема (subject): {msg.subject}")
                logging.info(f"Дата (date): {msg.date}")
                logging.info(f"Текст (text): {msg.text.strip()[:200]}...") # Первые 200 символов
                logging.info(f"Вложения: {[att.filename for att in msg.attachments]}")
                logging.info("===================================")
                
                # Фильтруем: только от sherzod.davronov@mail.ru и с фразой "network video recorder"
                sender = msg.from_.lower()
                subject = msg.subject.lower()
                text = msg.text.lower()
                
                if "sherzod.davronov@mail.ru" not in sender or "network video recorder" not in subject + text:
                    logging.info(f"Письмо пропущено (не подходит под фильтр): от {msg.from_}, тема: '{msg.subject}'")
                    continue
                
                # Помечаем письмо как прочитанное, так как оно от камеры
                mailbox.flag(msg.uid, '\\Seen', True)
                
                # Ищем название камеры (например, "Channel D2")
                camera_name = "Неизвестная"
                match = re.search(r'Channel\s+([\w\d]+)', msg.subject, re.IGNORECASE)
                if match:
                    camera_name = match.group(1).upper()
                
                # Базовый текст описания
                arrival_time = msg.date.strftime("%d.%m.%Y, %H:%M")
                base_text = f"🚨 <b>Движение обнаружено!</b>\n\n📹 <b>Камера:</b> {camera_name}\n🕒 <b>Время:</b> {arrival_time}\n\nПроверьте запись 👀"
                
                # Собираем данные для очереди
                media_items = []
                doc_items = []
                
                if msg.attachments:
                    logging.info(f"В письме найдено {len(msg.attachments)} вложений. Готовим данные...")
                    for i, att in enumerate(msg.attachments):
                        content_type = att.content_type.lower() if att.content_type else ""
                        filename = att.filename if att.filename else "unknown_file"
                        payload = att.payload
                        
                        logging.info(f"Анализ вложения: {filename} (Тип: {content_type}, Размер: {len(payload)} байт)")
                        
                        # Проверяем и по типу контента, и по расширению файла
                        is_image = content_type.startswith('image/') or filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif'))
                        is_video = content_type.startswith('video/') or filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm'))
                        
                        try:
                            # УМНЫЙ КОНВЕРТЕР ИЗОБРАЖЕНИЙ
                            if is_image:
                                if filename.lower().endswith(('.heic', '.heif', '.bmp', '.tiff', '.webp')):
                                    logging.info(f"Запуск умного конвертера для {filename}...")
                                    try:
                                        image = Image.open(io.BytesIO(payload))
                                        if image.mode in ("RGBA", "P"):
                                            image = image.convert("RGB")
                                        out_stream = io.BytesIO()
                                        image.save(out_stream, format="JPEG", quality=90)
                                        payload = out_stream.getvalue()
                                        
                                        # Меняем расширение на .jpg
                                        if '.' in filename:
                                            filename = filename.rsplit('.', 1)[0] + ".jpg"
                                        else:
                                            filename += ".jpg"
                                        logging.info(f"Конвертация успешно завершена. Новый файл: {filename}")
                                    except Exception as conv_err:
                                        logging.error(f"Не удалось конвертировать {filename}: {conv_err}. Отправляю как обычный файл.")
                                        is_image = False # Если не удалось конвертировать, отправим как документ
                            
                            if is_image:
                                media_items.append({'type': 'photo', 'payload': payload, 'filename': filename})
                            elif is_video:
                                media_items.append({'type': 'video', 'payload': payload, 'filename': filename})
                            else:
                                doc_items.append({'payload': payload, 'filename': filename})
                                
                        except Exception as e:
                            logging.error(f"Ошибка при подготовке вложения {filename}: {e}")
                            
                # Добавляем задачу в очередь
                message_queue.put({
                    'base_text': base_text,
                    'media_items': media_items,
                    'doc_items': doc_items
                })
                logging.info("Письмо добавлено в очередь на отправку.")
                
    except Exception as e:
        logging.error(f"Ошибка при работе с почтой: {e}")

def telegram_sender_worker():
    """Фоновый поток, который по очереди отправляет письма из очереди с интервалом."""
    while True:
        try:
            task = message_queue.get()
            base_text = task['base_text']
            media_items = task['media_items']
            doc_items = task['doc_items']
            
            if not media_items and not doc_items:
                # Просто текст
                for chat_id in subscribers:
                    try:
                        bot.send_message(chat_id, base_text, parse_mode='HTML')
                        logging.info(f"Отправлено описание (без вложений) пользователю {chat_id}.")
                    except Exception as e:
                        logging.error(f"Ошибка при отправке описания пользователю {chat_id}: {e}")
            else:
                # --- Отправка подписчикам ---
                for chat_id in subscribers:
                    # 1. Отправляем медиа-группы (если есть)
                    if len(media_items) == 1:
                        # Если только одно медиа, отправляем как обычное фото/видео
                        item = media_items[0]
                        stream = io.BytesIO(item['payload'])
                        stream.name = item['filename']
                        caption = f"📁 <b>Файл:</b> {html.escape(item['filename'])}\n{base_text}"
                        try:
                            if item['type'] == 'photo':
                                bot.send_photo(chat_id, photo=stream, caption=caption, parse_mode='HTML')
                            else:
                                bot.send_video(chat_id, video=stream, caption=caption, parse_mode='HTML')
                            logging.info(f"Одиночное медиа {item['filename']} успешно отправлено {chat_id}!")
                        except Exception as e:
                            logging.error(f"Ошибка отправки одиночного медиа пользователю {chat_id}: {e}")
                    
                    elif len(media_items) > 1:
                        # Если медиа несколько, отправляем как коллаж (разбивая по 10 штук)
                        for i in range(0, len(media_items), 10):
                            chunk = media_items[i:i+10]
                            media_group = []
                            for j, item in enumerate(chunk):
                                stream = io.BytesIO(item['payload'])
                                stream.name = item['filename']
                                # Добавляем текст только к первому элементу самого первого коллажа
                                caption = base_text if (i == 0 and j == 0) else None
                                
                                if item['type'] == 'photo':
                                    media_group.append(telebot.types.InputMediaPhoto(media=stream, caption=caption, parse_mode='HTML'))
                                else:
                                    media_group.append(telebot.types.InputMediaVideo(media=stream, caption=caption, parse_mode='HTML'))
                            
                            try:
                                bot.send_media_group(chat_id, media=media_group)
                                logging.info(f"Медиа-группа (часть {i//10 + 1}) отправлена пользователю {chat_id}")
                            except Exception as e:
                                logging.error(f"Ошибка отправки медиа-группы пользователю {chat_id}: {e}")
                                
                    # 2. Отправляем документы
                    for i, doc in enumerate(doc_items):
                        stream = io.BytesIO(doc['payload'])
                        stream.name = doc['filename']
                        # Если медиа вообще не было и это первый документ - добавляем base_text
                        caption = f"📁 <b>Файл:</b> {html.escape(doc['filename'])}\n{base_text}" if (not media_items and i == 0) else f"📁 <b>Файл:</b> {html.escape(doc['filename'])}"
                        
                        try:
                            bot.send_document(chat_id, document=stream, caption=caption, parse_mode='HTML')
                            logging.info(f"Документ {doc['filename']} отправлен {chat_id}")
                        except Exception as e:
                            logging.error(f"Ошибка отправки документа {doc['filename']} пользователю {chat_id}: {e}")

            message_queue.task_done()
            
            # Кулдаун 10 секунд после каждого отправленного из очереди письма
            logging.info("Ожидание 10 секунд перед отправкой следующего письма из конвейера...")
            time.sleep(10)
            
        except Exception as e:
            logging.error(f"Ошибка в конвейере Telegram: {e}")
            time.sleep(5)

def run_scheduler():
    # Запускать проверку почты каждые 3 секунды
    schedule.every(3).seconds.do(check_mail)
    
    logging.info("Программа запущена. Интервал проверки почты: каждые 3 секунды...")
    check_mail()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

def mark_all_as_read_on_startup():
    logging.info("Очистка старых писем: помечаю старые уведомления от камер как прочитанные...")
    try:
        with MailBox('imap.mail.ru').login(MAIL_USERNAME, MAIL_APP_PASSWORD) as mailbox:
            uids_to_mark = []
            for msg in mailbox.fetch(AND(seen=False), mark_seen=False):
                sender = msg.from_.lower()
                subject = msg.subject.lower()
                text = msg.text.lower()
                
                if "sherzod.davronov@mail.ru" in sender and "network video recorder" in subject + text:
                    uids_to_mark.append(msg.uid)
            
            if uids_to_mark:
                mailbox.flag(uids_to_mark, '\\Seen', True)
                
        logging.info(f"Успешно пропущено старых писем: {len(uids_to_mark)}")
    except Exception as e:
        logging.error(f"Ошибка при очистке старых писем: {e}")

if __name__ == "__main__":
    # Сначала очищаем все старые непрочитанные письма от камеры
    mark_all_as_read_on_startup()

    # Запускаем конвейер отправки сообщений
    sender_thread = threading.Thread(target=telegram_sender_worker, daemon=True)
    sender_thread.start()

    # Запускаем проверку почты в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Запускаем бота для получения команд (например, /start)
    logging.info("Бот запущен и ожидает команды...")
    try:
        bot.infinity_polling()
    except (KeyboardInterrupt, SystemExit):
        pass

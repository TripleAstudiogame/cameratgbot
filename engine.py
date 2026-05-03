import threading
import time
import logging
import io
import html
import re
import json
from datetime import datetime
import telebot
import queue
from imap_tools import MailBox, AND
from PIL import Image
import pillow_heif

import db

pillow_heif.register_heif_opener()

from logging.handlers import RotatingFileHandler

_log_handler = RotatingFileHandler("bot.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[_log_handler, logging.StreamHandler()]
)

# ── Shared state ──
_org_stop_events = {}   # org_id -> threading.Event
_org_threads = {}       # org_id -> [t1, t2, t3]
_org_bots = {}          # org_id -> TeleBot instance (for stop_polling)
_global_lock = threading.Lock()
_reload_lock = threading.Lock()  # prevents concurrent reloads

# Heartbeat: org_id -> {imap_ok, bot_ok, last_check, last_error}
_health = {}

def get_health():
    """Return a copy of health data for all orgs."""
    with _global_lock:
        return dict(_health)

def _set_health(org_id, **kwargs):
    with _global_lock:
        if org_id not in _health:
            _health[org_id] = {'imap_ok': False, 'bot_ok': False, 'last_check': None, 'last_error': None, 'error_count': 0}
        _health[org_id].update(kwargs)


def notify_user_access(org_id, chat_id, approved=True):
    """Send a notification to the user via the organization's bot instance."""
    with _global_lock:
        bot = _org_bots.get(org_id)
    if not bot:
        # If engine is not running for this org, we can't notify via its bot easily
        # but we could create a temp bot if we had the token.
        # For now, we assume the engine is running if we are managing access.
        return
    
    try:
        if approved:
            bot.send_message(chat_id, "✅ <b>Доступ одобрен!</b>\n\nТеперь вы будете получать уведомления от камер.", parse_mode='HTML')
        else:
            bot.send_message(chat_id, "🚫 <b>Доступ отозван.</b>\n\nВы больше не будете получать уведомления.", parse_mode='HTML')
    except Exception as e:
        logging.error(f"[Engine] Failed to notify user {chat_id} (org {org_id}): {e}")


def test_connection(org):
    """Test IMAP + Telegram for an organization. Returns dict with results."""
    result = {'imap_ok': False, 'bot_ok': False, 'imap_error': None, 'bot_error': None}
    
    # Test IMAP
    try:
        with MailBox('imap.mail.ru').login(org['mail_username'], org['mail_password']) as mb:
            mb.folder.list()
        result['imap_ok'] = True
    except Exception as e:
        result['imap_error'] = str(e)
    
    # Test Bot
    try:
        bot = telebot.TeleBot(org['bot_token'])
        info = bot.get_me()
        result['bot_ok'] = True
        result['bot_name'] = f"@{info.username}"
    except Exception as e:
        result['bot_error'] = str(e)
    
    return result


def mark_all_as_read(org):
    org_name = org['name']
    try:
        with MailBox('imap.mail.ru').login(org['mail_username'], org['mail_password']) as mailbox:
            uids = []
            for msg in mailbox.fetch(AND(seen=False), mark_seen=False):
                if "network video recorder" in (msg.subject + msg.text).lower():
                    uids.append(msg.uid)
            if uids:
                mailbox.flag(uids, '\\Seen', True)
            logging.info(f"[{org_name}] Пропущено старых писем: {len(uids)}")
    except Exception as e:
        logging.error(f"[{org_name}] Ошибка очистки: {e}")


def run_organization_loop(org, stop_event):
    org_id = org['id']
    org_name = org['name']
    bot = telebot.TeleBot(org['bot_token'])
    message_queue = queue.Queue()

    # Save bot reference so we can stop_polling() later
    with _global_lock:
        _org_bots[org_id] = bot

    # Read settings: per-org override > global default
    global_mail_interval = int(db.get_setting('mail_check_interval', '3'))
    global_tg_cooldown = int(db.get_setting('telegram_cooldown', '10'))
    
    org_mail_interval = org.get('mail_check_interval', 0) or 0
    org_tg_cooldown = org.get('telegram_cooldown', 0) or 0
    
    mail_interval = int(org_mail_interval) if int(org_mail_interval) > 0 else global_mail_interval
    tg_cooldown = int(org_tg_cooldown) if int(org_tg_cooldown) > 0 else global_tg_cooldown

    logging.info(f"[{org_name}] Таймеры: почта={mail_interval}с, cooldown={tg_cooldown}с")

    # Check subscription
    end_str = org.get('subscription_end_date')
    if end_str:
        try:
            if datetime.now() > datetime.fromisoformat(end_str):
                logging.warning(f"[{org_name}] Подписка истекла.")
                db.add_event(org_id, 'system', 'Подписка истекла, бот остановлен')
                return
        except: pass

    mark_all_as_read(org)
    _set_health(org_id, imap_ok=True, bot_ok=False, last_check=datetime.now().isoformat(), last_error=None, error_count=0)
    db.add_event(org_id, 'system', 'Мониторинг запущен')

    @bot.message_handler(commands=['start'])
    def handle_start(message):
        cid = message.chat.id
        # Already approved?
        if db.is_user_approved(org_id, cid):
            bot.reply_to(message, "✅ Вы уже подключены к уведомлениям!")
            return
        # Already pending?
        if db.has_pending_request(org_id, cid):
            bot.reply_to(message, "⏳ Ваша заявка на рассмотрении. Ожидайте подтверждения администратора.")
            return
        # Ask for phone number
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        btn = telebot.types.KeyboardButton("📱 Поделиться номером", request_contact=True)
        markup.add(btn)
        bot.send_message(cid, "🔐 Для доступа к уведомлениям, пожалуйста, поделитесь своим номером телефона:", reply_markup=markup)

    @bot.message_handler(content_types=['contact'])
    def handle_contact(message):
        cid = message.chat.id
        contact = message.contact
        if contact.user_id != cid:
            bot.reply_to(message, "❌ Пожалуйста, отправьте свой собственный контакт.")
            return
        phone = contact.phone_number or ''
        first_name = contact.first_name or message.from_user.first_name or ''
        last_name = contact.last_name or message.from_user.last_name or ''
        
        if db.is_user_approved(org_id, cid):
            bot.send_message(cid, "✅ Вы уже подключены!", reply_markup=telebot.types.ReplyKeyboardRemove())
            return
        
        added = db.add_access_request(org_id, cid, first_name, last_name, phone)
        if added:
            db.add_event(org_id, 'subscriber', f'Заявка: {first_name} {last_name} ({phone})')
            logging.info(f"[{org_name}] Заявка на доступ: {cid} {first_name} {phone}")
            bot.send_message(cid, "✅ Спасибо! Ваша заявка отправлена администратору.\n\n⏳ Ожидайте подтверждения.", reply_markup=telebot.types.ReplyKeyboardRemove())
        else:
            bot.send_message(cid, "⏳ Ваша заявка уже на рассмотрении.", reply_markup=telebot.types.ReplyKeyboardRemove())

    @bot.message_handler(func=lambda m: True)
    def handle_any(message):
        cid = message.chat.id
        if not db.is_user_approved(org_id, cid) and not db.has_pending_request(org_id, cid):
            markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            btn = telebot.types.KeyboardButton("📱 Поделиться номером", request_contact=True)
            markup.add(btn)
            bot.send_message(cid, "🔐 Для доступа необходимо поделиться номером телефона:", reply_markup=markup)

    def check_mail():
        cur = db.get_organization(org_id)
        if not cur or not cur['is_active']:
            return
        end_str = cur.get('subscription_end_date')
        if end_str:
            try:
                if datetime.now() > datetime.fromisoformat(end_str):
                    return
            except: pass
        subs = cur['subscribers']
        if not subs:
            return
        try:
            with MailBox('imap.mail.ru').login(org['mail_username'], org['mail_password']) as mailbox:
                _set_health(org_id, imap_ok=True, last_check=datetime.now().isoformat(), last_error=None)
                for msg in mailbox.fetch(AND(seen=False), mark_seen=True):
                    combined_text = msg.subject + "\n" + msg.text
                    combined_lower = combined_text.lower()
                    if "network video recorder" not in combined_lower and "nvr" not in combined_lower:
                        continue

                    camera = "Неизвестная"
                    m = re.search(r'Channel\s+([\w\d]+)', msg.subject, re.IGNORECASE)
                    if m:
                        camera = m.group(1).upper()
                    else:
                        m2 = re.search(r'CAMERA NAME\(NUM\):\s*(.*?)(?:\n|$)', combined_text, re.IGNORECASE)
                        if m2:
                            raw_cam = m2.group(1).strip()
                            m_parens = re.search(r'\(([^)]+)\)', raw_cam)
                            if m_parens:
                                camera = m_parens.group(1).upper()
                            else:
                                camera = re.sub(r'(?i)\s*(black|white|normal)\s*vehicle\s*list.*', '', raw_cam).strip()

                    t = msg.date.strftime("%d.%m.%Y, %H:%M")
                    m3 = re.search(r'EVENT TIME:\s*([\d\-]+,[\d\:]+)', combined_text, re.IGNORECASE)
                    if m3:
                        try:
                            dt_obj = datetime.strptime(m3.group(1).strip(), "%Y-%m-%d,%H:%M:%S")
                            t = dt_obj.strftime("%d.%m.%Y, %H:%M:%S")
                        except:
                            t = m3.group(1).strip()

                    event_type = "motion"
                    if "face alarm" in combined_lower or "человека" in combined_lower:
                        event_type = "face"
                    elif "vehicle exception" in combined_lower or "машины" in combined_lower:
                        event_type = "vehicle"
                        
                    plate_number = ""
                    if event_type == "vehicle":
                        m4 = re.search(r'\[([^\]]+)\]', combined_text)
                        if m4:
                            plate_number = m4.group(1).strip()
                            
                    db.register_camera(org_id, camera)
                    
                    org_data = db.get_organization(org_id)
                    cams_dict = {}
                    try:
                        if org_data and org_data.get('cameras'):
                            cams_dict = json.loads(org_data.get('cameras', '{}'))
                    except:
                        pass
                    
                    friendly_name = cams_dict.get(camera, "").strip()
                    display_cam = f"{friendly_name} ({camera})" if friendly_name else camera

                    if event_type == "face":
                        text = (f"🚨 <b>Обнаружен человек</b>\n\n"
                                f"📹 <b>Камера:</b> {html.escape(display_cam)}\n"
                                f"🕒 <b>Время:</b> {t}\n\nПроверьте запись 👀")
                    elif event_type == "vehicle":
                        plate_text = f"🚗 <b>Номер машины:</b> {html.escape(plate_number)}\n\n" if plate_number else ""
                        text = (f"🚨 <b>Обнаружена машина</b>\n"
                                f"{plate_text}"
                                f"📹 <b>Камера:</b> {html.escape(display_cam)}\n"
                                f"🕒 <b>Время:</b> {t}\n\nПроверьте запись 👀")
                    else:
                        text = (f"🚨 <b>Движение обнаружено!</b>\n\n"
                                f"📹 <b>Камера:</b> {html.escape(display_cam)}\n"
                                f"🕒 <b>Время:</b> {t}\n\nПроверьте запись 👀")

                    media, docs = [], []
                    for att in msg.attachments:
                        ct = (att.content_type or '').lower()
                        fn = att.filename or 'file'
                        p = att.payload
                        is_img = ct.startswith('image/') or fn.lower().endswith(('.jpg','.jpeg','.png','.gif','.bmp','.webp','.heic','.heif'))
                        is_vid = ct.startswith('video/') or fn.lower().endswith(('.mp4','.avi','.mov','.mkv','.webm'))
                        try:
                            if is_img and fn.lower().endswith(('.heic','.heif','.bmp','.tiff','.webp')):
                                try:
                                    img = Image.open(io.BytesIO(p))
                                    if img.mode in ("RGBA","P"): img = img.convert("RGB")
                                    out = io.BytesIO(); img.save(out, format="JPEG", quality=90)
                                    p = out.getvalue(); fn = fn.rsplit('.',1)[0]+".jpg"
                                except: is_img = False
                            if is_img: media.append({'type':'photo','payload':p,'filename':fn})
                            elif is_vid: media.append({'type':'video','payload':p,'filename':fn})
                            else: docs.append({'payload':p,'filename':fn})
                        except: pass

                    message_queue.put({'base_text':text,'media_items':media,'doc_items':docs,'subscribers':subs})
                    db.add_event(org_id, 'notification', f'Камера {camera}')
                    logging.info(f"[{org_name}] Уведомление: камера {camera}")

        except Exception as e:
            _set_health(org_id, imap_ok=False, last_error=str(e),
                       error_count=_health.get(org_id,{}).get('error_count',0)+1)
            db.add_event(org_id, 'error', f'IMAP: {str(e)[:200]}')
            logging.error(f"[{org_name}] Ошибка почты: {e}")

    def telegram_sender():
        while not stop_event.is_set():
            try:
                task = message_queue.get(timeout=2)
            except queue.Empty:
                continue
            txt = task['base_text']; media = task['media_items']; docs = task['doc_items']
            for cid in task['subscribers']:
                try:
                    if not media and not docs:
                        bot.send_message(cid, txt, parse_mode='HTML')
                    else:
                        if len(media)==1:
                            item=media[0]; s=io.BytesIO(item['payload']); s.name=item['filename']
                            cap=txt
                            if item['type']=='photo': bot.send_photo(cid,photo=s,caption=cap,parse_mode='HTML')
                            else: bot.send_video(cid,video=s,caption=cap,parse_mode='HTML')
                        elif len(media)>1:
                            for i in range(0,len(media),10):
                                grp=[]
                                for j,item in enumerate(media[i:i+10]):
                                    s=io.BytesIO(item['payload']); s.name=item['filename']
                                    c=txt if(i==0 and j==0)else None
                                    if item['type']=='photo': grp.append(telebot.types.InputMediaPhoto(media=s,caption=c,parse_mode='HTML'))
                                    else: grp.append(telebot.types.InputMediaVideo(media=s,caption=c,parse_mode='HTML'))
                                bot.send_media_group(cid,media=grp)
                        for i,doc in enumerate(docs):
                            s=io.BytesIO(doc['payload']); s.name=doc['filename']
                            c=txt if(not media and i==0) else None
                            bot.send_document(cid,document=s,caption=c,parse_mode='HTML')
                except Exception as e:
                    logging.error(f"[{org_name}] TG ошибка {cid}: {e}")
                    db.add_event(org_id, 'error', f'Telegram {cid}: {str(e)[:150]}')
            message_queue.task_done()
            for _ in range(tg_cooldown):
                if stop_event.is_set(): break
                time.sleep(1)

    def mail_scheduler():
        while not stop_event.is_set():
            check_mail()
            for _ in range(mail_interval):
                if stop_event.is_set(): break
                time.sleep(1)

    t1=threading.Thread(target=mail_scheduler,daemon=True,name=f"mail-{org_id}")
    t2=threading.Thread(target=telegram_sender,daemon=True,name=f"tg-{org_id}")
    t1.start(); t2.start()

    def run_polling():
        _set_health(org_id, bot_ok=True)
        while not stop_event.is_set():
            try:
                bot.polling(non_stop=True, timeout=10, long_polling_timeout=5)
            except Exception as e:
                if stop_event.is_set():
                    break
                _set_health(org_id, bot_ok=False, last_error=f'Bot: {e}')
                logging.error(f"[{org_name}] Polling ошибка: {e}")
                time.sleep(5)
        logging.info(f"[{org_name}] Polling остановлен.")

    t3=threading.Thread(target=run_polling,daemon=True,name=f"poll-{org_id}")
    t3.start()
    logging.info(f"[{org_name}] Запущен (3 потока)")

    with _global_lock:
        _org_threads[org_id]=[t1,t2,t3]


def _stop_all():
    """Stop all running org threads cleanly."""
    with _global_lock:
        # 1. Signal all threads to stop
        for ev in _org_stop_events.values():
            ev.set()
        
        # 2. Force-stop all bot pollings (this unblocks bot.polling())
        for org_id, bot in _org_bots.items():
            try:
                bot.stop_polling()
            except Exception:
                pass
        
        # 3. Wait for threads to finish
        for org_id, threads in _org_threads.items():
            for t in threads:
                t.join(timeout=5)
        
        _org_stop_events.clear()
        _org_threads.clear()
        _org_bots.clear()
        _health.clear()


def start_engine():
    for org in db.get_organizations():
        if org['is_active']:
            ev = threading.Event()
            _org_stop_events[org['id']] = ev
            threading.Thread(target=run_organization_loop, args=(org, ev), daemon=True).start()


def reload_engine():
    """Thread-safe engine reload. Prevents concurrent reloads."""
    if not _reload_lock.acquire(blocking=False):
        logging.warning("Reload уже выполняется, пропуск.")
        return
    try:
        logging.info("Перезапуск движка...")
        _stop_all()
        start_engine()
        logging.info("Движок перезапущен.")
    finally:
        _reload_lock.release()

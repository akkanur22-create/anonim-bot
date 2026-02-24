import logging
import os
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()

# === НАЧАЛО: СЮДА ВСТАВЬТЕ ВСЕ ВАШИ ФУНКЦИИ ИЗ bot.py ===
# Скопируйте сюда ВСЕ функции из вашего bot.py:|
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Проверяем, является ли пользователь администратором
    is_admin = user.id in ADMIN_IDS
    if is_admin:
        db.set_admin(user.id)
    
    if context.args:
        # Пользователь перешел по ссылке
        link = context.args[0]
        recipient_id = db.get_user_by_link(link)
        
        if recipient_id and recipient_id != user.id:
            context.user_data['recipient'] = recipient_id
            context.user_data['conversation_with'] = recipient_id
            await update.message.reply_text(
                "🔒 Вы перешли по ссылке для отправки анонимного сообщения.\n"
                "📝 Отправьте текст или фото (можно с подписью):"
            )
        elif recipient_id == user.id:
            await update.message.reply_text("❌ Это ваша собственная ссылка!")
        else:
            await update.message.reply_text("❌ Недействительная ссылка.")
    else:
        # Обычный запуск
        unique_link = db.add_user(user.id, user.username, user.first_name)
        bot_link = f"https://t.me/{BOT_USERNAME}?start={unique_link}"
        unread_count = db.get_unread_count(user.id)
        
        welcome_message = (
            f"👋 Привет, {user.first_name}!\n\n"
            f"🔗 Твоя ссылка для анонимных сообщений:\n"
            f"`{bot_link}`\n\n"
            f"📊 Непрочитанных: {unread_count}\n\n"
            f"📸 Можно отправлять фото с подписями!"
        )
        
        keyboard = [
            [InlineKeyboardButton("📨 Мои сообщения", callback_data="my_messages")],
            [InlineKeyboardButton("🔄 Моя ссылка", callback_data="my_link")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        
        if is_admin:
            keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
            welcome_message += "\n\n👑 **Вы администратор!**"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    try:
        user = update.effective_user
        message_text = update.message.text
        
        if 'recipient' in context.user_data:
            # Отправка нового сообщения
            recipient_id = context.user_data['recipient']
            message_id = db.save_anonymous_message(
                recipient_id=recipient_id,
                sender_id=user.id,
                sender_username=user.username,
                sender_first_name=user.first_name,
                message_text=message_text
            )
            del context.user_data['recipient']
            await update.message.reply_text("✅ Сообщение отправлено!")
            
            # Отправляем уведомление с кнопкой ответа
            try:
                unread_count = db.get_unread_count(recipient_id)
                keyboard = [[InlineKeyboardButton("💬 Ответить", callback_data=f"quick_reply_{message_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=recipient_id,
                    text=f"📩 **Новое анонимное сообщение!**\n\n"
                         f"📝 {message_text[:100]}{'...' if len(message_text) > 100 else ''}\n\n"
                         f"💬 Нажмите кнопку ниже чтобы ответить",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление: {e}")
        
        elif 'replying_to' in context.user_data:
            # Ответ на сообщение
            reply_data = context.user_data['replying_to']
            message_id = db.save_anonymous_message(
                recipient_id=reply_data['sender_id'],
                sender_id=user.id,
                sender_username=user.username,
                sender_first_name=user.first_name,
                message_text=message_text,
                reply_to_id=reply_data['message_id']
            )
            del context.user_data['replying_to']
            await update.message.reply_text("✅ Ответ отправлен!")
            
            # Уведомляем о ответе
            try:
                keyboard = [[InlineKeyboardButton("💬 Ответить", callback_data=f"quick_reply_{message_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=reply_data['sender_id'],
                    text=f"📩 **Новый ответ на ваше сообщение!**\n\n"
                         f"📝 {message_text[:100]}{'...' if len(message_text) > 100 else ''}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        else:
            await update.message.reply_text("Используйте /start")
            
    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото"""
    try:
        user = update.effective_user
        photo = update.message.photo[-1]  # Берем самое большое фото
        caption = update.message.caption or ""  # Подпись к фото
        
        if 'recipient' in context.user_data:
            # Отправка фото новому получателю
            recipient_id = context.user_data['recipient']
            message_id = db.save_anonymous_message(
                recipient_id=recipient_id,
                sender_id=user.id,
                sender_username=user.username,
                sender_first_name=user.first_name,
                message_text=caption,
                photo_file_id=photo.file_id
            )
            del context.user_data['recipient']
            await update.message.reply_text("✅ Фото отправлено!")
            
            # Отправляем уведомление с фото
            try:
                keyboard = [[InlineKeyboardButton("💬 Ответить", callback_data=f"quick_reply_{message_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_photo(
                    chat_id=recipient_id,
                    photo=photo.file_id,
                    caption=f"📩 **Новое анонимное фото!**\n\n{caption if caption else 'Без подписи'}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление: {e}")
        
        elif 'replying_to' in context.user_data:
            # Ответ фото на сообщение
            reply_data = context.user_data['replying_to']
            message_id = db.save_anonymous_message(
                recipient_id=reply_data['sender_id'],
                sender_id=user.id,
                sender_username=user.username,
                sender_first_name=user.first_name,
                message_text=caption,
                photo_file_id=photo.file_id,
                reply_to_id=reply_data['message_id']
            )
            del context.user_data['replying_to']
            await update.message.reply_text("✅ Ответ с фото отправлен!")
            
            # Уведомляем о ответе с фото
            try:
                keyboard = [[InlineKeyboardButton("💬 Ответить", callback_data=f"quick_reply_{message_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_photo(
                    chat_id=reply_data['sender_id'],
                    photo=photo.file_id,
                    caption=f"📩 **Новый ответ с фото!**\n\n{caption if caption else 'Без подписи'}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        else:
            await update.message.reply_text("Используйте /start чтобы получить ссылку")
            
    except Exception as e:
        logger.error(f"Ошибка в handle_photo: {e}")
        await update.message.reply_text("❌ Произошла ошибка при отправке фото.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        is_admin = user_id in ADMIN_IDS
        
        # === БЫСТРЫЙ ОТВЕТ ИЗ УВЕДОМЛЕНИЯ ===
        if query.data.startswith("quick_reply_"):
            message_id = int(query.data.split("_")[2])
            message = db.get_message_by_id(message_id, requesting_user_id=user_id)
            
            if message:
                if is_admin:
                    # Для админа: id, sender_id, s_username, s_name, recipient_id, msg_text, photo_id, sent_date, reply_to_id
                    if len(message) >= 9:
                        msg_id, sender_id, s_username, s_name, recipient_id, msg_text, photo_id, sent_date, reply_to_id = message[:9]
                    else:
                        await query.edit_message_text("❌ Ошибка загрузки сообщения")
                        return
                else:
                    # Для обычных: id, recipient_id, msg_text, photo_id, sent_date, reply_to_id
                    if len(message) >= 6:
                        msg_id, recipient_id, msg_text, photo_id, sent_date, reply_to_id = message[:6]
                        sender_id = recipient_id
                    else:
                        await query.edit_message_text("❌ Ошибка загрузки сообщения")
                        return
                
                context.user_data['replying_to'] = {
                    'message_id': msg_id,
                    'sender_id': sender_id,
                    'original_text': msg_text,
                    'photo_id': photo_id
                }
                
                if photo_id:
                    await query.edit_message_text(
                        f"✏️ **Вы отвечаете на фото:**\n\n"
                        f"Подпись: {msg_text if msg_text else 'Без подписи'}\n\n"
                        f"Отправьте ваш ответ (текст или фото):",
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        f"✏️ **Вы отвечаете на сообщение:**\n"
                        f"\"{msg_text[:100]}{'...' if len(msg_text) > 100 else ''}\"\n\n"
                        f"Отправьте ваш ответ (текст или фото):",
                        parse_mode='Markdown'
                    )
            return
        
        # === ГЛАВНОЕ МЕНЮ ===
        elif query.data == "my_messages":
            messages = db.get_user_messages(user_id, requesting_user_id=user_id)
            
            if not messages:
                await query.edit_message_text("📭 У вас нет сообщений")
                keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
                await query.message.reply_text("Выберите действие:", reply_markup=InlineKeyboardMarkup(keyboard))
                return
            
            await query.edit_message_text("📨 **Ваши сообщения:**", parse_mode='Markdown')
            
            for msg in messages:
                if is_admin:
                    # Для админа
                    if len(msg) >= 9:
                        msg_id, sender_id, s_username, s_name, msg_text, photo_id, sent_date, is_read, reply_to_id = msg[:9]
                        header = f"👤 **От:** {s_name} (@{s_username})\n📅 {sent_date}\n{'✅ Прочитано' if is_read else '📌 Непрочитано'}\n"
                    else:
                        continue
                else:
                    # Для обычных
                    if len(msg) >= 6:
                        msg_id, msg_text, photo_id, sent_date, is_read, reply_to_id = msg[:6]
                        header = f"📅 {sent_date}\n{'✅ Прочитано' if is_read else '📌 Непрочитано'}\n"
                    else:
                        continue
                
                content = f"{'📸 [ФОТО] ' if photo_id else '📝 '}{msg_text if msg_text else ''}"
                preview = header + content[:100] + ('...' if len(content) > 100 else '')
                
                keyboard = [
                    [InlineKeyboardButton("👁️ Прочитать", callback_data=f"read_{msg_id}"),
                     InlineKeyboardButton("💬 Ответить", callback_data=f"reply_{msg_id}")]
                ]
                await query.message.reply_text(preview, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
            await query.message.reply_text("Выберите действие:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        elif query.data.startswith("read_"):
            msg_id = int(query.data.split("_")[1])
            db.mark_message_as_read(msg_id)
            
            msg = db.get_message_by_id(msg_id, requesting_user_id=user_id)
            if msg:
                if is_admin:
                    if len(msg) >= 9:
                        msg_id, sender_id, s_username, s_name, recipient_id, msg_text, photo_id, sent_date, reply_to_id = msg[:9]
                        header = (f"👤 **Отправитель:** {s_name}\n"
                                 f"📱 Username: @{s_username if s_username else 'Нет'}\n"
                                 f"🆔 ID: `{sender_id}`\n"
                                 f"📅 {sent_date}\n\n")
                    else:
                        await query.edit_message_text("❌ Ошибка загрузки сообщения")
                        return
                else:
                    if len(msg) >= 6:
                        msg_id, recipient_id, msg_text, photo_id, sent_date, reply_to_id = msg[:6]
                        header = f"📅 {sent_date}\n\n"
                    else:
                        await query.edit_message_text("❌ Ошибка загрузки сообщения")
                        return
                
                if reply_to_id:
                    header = f"💬 **Ответ на сообщение #{reply_to_id}**\n\n{header}"
                
                # Отправляем фото если есть
                if photo_id:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=photo_id,
                        caption=f"{header}📝 **Подпись:** {msg_text if msg_text else 'Без подписи'}",
                        parse_mode='Markdown'
                    )
                    # Удаляем предыдущее сообщение
                    await query.message.delete()
                else:
                    text = header + f"📝 **Сообщение:**\n{msg_text}"
                    keyboard = [
                        [InlineKeyboardButton("💬 Ответить", callback_data=f"reply_{msg_id}")],
                        [InlineKeyboardButton("🔙 Назад", callback_data="my_messages")]
                    ]
                    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return
        
        elif query.data.startswith("reply_"):
            msg_id = int(query.data.split("_")[1])
            msg = db.get_message_by_id(msg_id, requesting_user_id=user_id)
            
            if msg:
                if is_admin:
                    if len(msg) >= 9:
                        msg_id, sender_id, s_username, s_name, recipient_id, msg_text, photo_id, sent_date, reply_to_id = msg[:9]
                    else:
                        await query.edit_message_text("❌ Ошибка загрузки сообщения")
                        return
                else:
                    if len(msg) >= 6:
                        msg_id, recipient_id, msg_text, photo_id, sent_date, reply_to_id = msg[:6]
                        sender_id = recipient_id
                    else:
                        await query.edit_message_text("❌ Ошибка загрузки сообщения")
                        return
                
                context.user_data['replying_to'] = {
                    'message_id': msg_id,
                    'sender_id': sender_id,
                    'original_text': msg_text,
                    'photo_id': photo_id
                }
                
                if photo_id:
                    await query.edit_message_text(
                        f"✏️ **Вы отвечаете на фото:**\n\n"
                        f"Подпись: {msg_text if msg_text else 'Без подписи'}\n\n"
                        f"Отправьте ваш ответ (текст или фото):",
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        f"✏️ **Вы отвечаете на сообщение:**\n"
                        f"\"{msg_text[:100]}{'...' if len(msg_text) > 100 else ''}\"\n\n"
                        f"Отправьте ваш ответ (текст или фото):",
                        parse_mode='Markdown'
                    )
            return
        
        elif query.data == "my_link":
            link = db.get_user_link(user_id)
            bot_link = f"https://t.me/{BOT_USERNAME}?start={link}"
            unread = db.get_unread_count(user_id)
            
            text = f"🔗 **Ваша ссылка:**\n`{bot_link}`\n\n📊 **Непрочитанных:** {unread}"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return
        
        elif query.data == "help":
            help_text = (
                "📚 **Как пользоваться ботом:**\n\n"
                "1️⃣ **Получите ссылку** - нажмите /start\n"
                "2️⃣ **Отправьте ссылку** друзьям\n"
                "3️⃣ **Они напишут вам** анонимно (текст или фото)\n"
                "4️⃣ **Вы получите уведомление** с кнопкой ответа\n"
                "5️⃣ **Нажмите 'Ответить'** чтобы продолжить диалог\n\n"
                "📸 **Поддерживаются фото с подписями!**\n\n"
                "🔐 **Всё полностью анонимно!**"
            )
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
            await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return
        
        elif query.data == "admin_panel" and is_admin:
            users = db.get_all_users()
            messages = db.get_all_messages_admin(limit=100)
            
            text = (f"👑 **Админ-панель**\n\n"
                    f"📊 **Статистика:**\n"
                    f"👥 Пользователей: {len(users)}\n"
                    f"💬 Сообщений: {len(messages)}\n")
            
            keyboard = [
                [InlineKeyboardButton("👥 Все пользователи", callback_data="admin_users")],
                [InlineKeyboardButton("📨 Все сообщения", callback_data="admin_messages")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return
        
        elif query.data == "admin_users" and is_admin:
            users = db.get_all_users()
            text = "👥 **Все пользователи:**\n\n"
            for u in users[:15]:
                if len(u) >= 6:
                    uid, username, name, date, link, admin = u[:6]
                    username_display = f"@{username}" if username else "Нет username"
                    text += (f"• **{name}**\n"
                            f"  📱 {username_display}\n"
                            f"  🆔 `{uid}`\n"
                            f"  📅 {date.split()[0] if date else 'Нет'}\n"
                            f"  {'👑 Админ' if admin else '👤 Пользователь'}\n\n")
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return
        
        elif query.data == "admin_messages" and is_admin:
            messages = db.get_all_messages_admin(limit=20)
            text = "📨 **Последние сообщения:**\n\n"
            
            for m in messages[:15]:
                if len(m) >= 11:
                    msg_id, s_id, s_user, s_name, r_id, msg_txt, photo_id, date, is_read, r_user, r_name = m[:11]
                    text += (f"• **#{msg_id}**\n"
                            f"  👤 **От:** {s_name} (@{s_user})\n"
                            f"  👥 **Кому:** {r_name}\n"
                            f"  📅 {date}\n"
                            f"  {'📸 Фото' if photo_id else '📝 Текст'}: {msg_txt[:50] if msg_txt else 'Без текста'}{'...' if msg_txt and len(msg_txt) > 50 else ''}\n"
                            f"  {'✅ Прочитано' if is_read else '📌 Непрочитано'}\n\n")
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return
        
        elif query.data == "back_to_menu":
            # Показываем главное меню
            user = update.effective_user
            unique_link = db.get_user_link(user_id)
            bot_link = f"https://t.me/{BOT_USERNAME}?start={unique_link}"
            unread_count = db.get_unread_count(user_id)
            
            welcome_message = (
                f"👋 **{user.first_name}**, добро пожаловать!\n\n"
                f"🔗 **Твоя ссылка:**\n"
                f"`{bot_link}`\n\n"
                f"📊 **Непрочитанных:** {unread_count}"
            )
            
            keyboard = [
                [InlineKeyboardButton("📨 Мои сообщения", callback_data="my_messages")],
                [InlineKeyboardButton("🔄 Моя ссылка", callback_data="my_link")],
                [InlineKeyboardButton("❓ Помощь", callback_data="help")]
            ]
            
            if is_admin:
                keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
            except:
                await query.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
            return
            
    except Exception as e:
        logger.error(f"Ошибка в button_callback: {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
# - start()
# - handle_message()
# - handle_photo() 
# - button_callback()
# - error_handler()
# 
# Просто выделите их в bot.py и вставьте сюда
# === КОНЕЦ: функции из bot.py ===

# Настройки для Render
TOKEN = os.environ.get('TELEGRAM_TOKEN')
PORT = int(os.environ.get('PORT', 5000))
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

# Создаём Flask приложение
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

@flask_app.route('/health')
def health():
    return "OK", 200

@flask_app.route(f'/webhook', methods=['POST'])
def webhook():
    """Сюда Telegram будет присылать обновления"""
    if application:
            update = Update.de_json(request.get_json(force=True), application.bot)
            asyncio.run_coroutine_threadsafe(application.process_update(update), application.loop)
    return 'OK', 200

# Глобальная переменная для приложения бота
application = None

async def run_bot():
    global application
    try:
        # Создаём приложение
        application = Application.builder().token(TOKEN).build()
        
        # === РЕГИСТРИРУЕМ ВСЕ ВАШИ ОБРАБОТЧИКИ ===
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_error_handler(error_handler)
        
        # Инициализация и запуск
        await application.initialize()
        await application.start()
        
        # Устанавливаем вебхук
        webhook_url = f"{RENDER_URL}/webhook"
        await application.bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook установлен на {webhook_url}")
        
        # Запускаем Flask
        from werkzeug.serving import run_simple
        run_simple('0.0.0.0', PORT, flask_app, use_reloader=False, threaded=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в run_bot: {e}")

def main():
    """Точка входа"""
    asyncio.run(run_bot())

if __name__ == '__main__':
    main()

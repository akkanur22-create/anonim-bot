import logging
import os
import threading
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from config import TOKEN, ADMIN_IDS, BOT_USERNAME
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Flask для health checks
app = Flask(__name__)

# Инициализация базы данных
db = Database()

# Глобальная переменная для приложения бота
telegram_app = None

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

def run_bot():
    """Запуск Telegram бота в отдельном потоке"""
    global telegram_app
    try:
        # Создаем приложение
        application = Application.builder().token(TOKEN).build()
        telegram_app = application
        
        # Регистрируем обработчики (ваши существующие)
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_error_handler(error_handler)
        
        logger.info("Бот запущен в режиме polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Ошибка в run_bot: {e}")

# === ВСТАВЬТЕ ВСЕ ВАШИ ФУНКЦИИ СЮДА ===
# start(), handle_message(), handle_photo(), button_callback(), error_handler()
# из вашего текущего bot.py

def main():
    """Точка входа"""
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Получаем порт из переменных окружения Render
    port = int(os.environ.get('PORT', 5000))
    
    # Запускаем Flask сервер
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()
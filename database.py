import sqlite3
import string
import random
from datetime import datetime

class Database:
    def __init__(self, db_name='bot_database.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        """Создает все необходимые таблицы в базе данных"""
        # Таблица пользователей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                join_date TEXT,
                unique_link TEXT UNIQUE,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица анонимных сообщений
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_id INTEGER,
                sender_id INTEGER,
                sender_username TEXT,
                sender_first_name TEXT,
                message_text TEXT,
                photo_file_id TEXT,
                sent_date TEXT,
                is_read INTEGER DEFAULT 0,
                reply_to_message_id INTEGER DEFAULT NULL
            )
        ''')
        self.conn.commit()
    
    def generate_unique_link(self, length=8):
        """Генерирует уникальную ссылку для пользователя"""
        chars = string.ascii_letters + string.digits
        while True:
            link = ''.join(random.choice(chars) for _ in range(length))
            self.cursor.execute("SELECT unique_link FROM users WHERE unique_link = ?", (link,))
            if not self.cursor.fetchone():
                return link
    
    def add_user(self, user_id, username, first_name):
        """Добавляет нового пользователя в базу данных"""
        self.cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        existing = self.cursor.fetchone()
        
        if existing:
            return self.get_user_link(user_id)
        
        unique_link = self.generate_unique_link()
        join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.cursor.execute('''
            INSERT INTO users (user_id, username, first_name, join_date, unique_link, is_admin)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, join_date, unique_link, 0))
        self.conn.commit()
        return unique_link
    
    def set_admin(self, user_id):
        """Назначает пользователя администратором"""
        self.cursor.execute('''
            UPDATE users SET is_admin = 1 WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def is_admin(self, user_id):
        """Проверяет, является ли пользователь администратором"""
        self.cursor.execute('''
            SELECT is_admin FROM users WHERE user_id = ?
        ''', (user_id,))
        result = self.cursor.fetchone()
        return result[0] == 1 if result else False
    
    def get_user_link(self, user_id):
        """Получает уникальную ссылку пользователя"""
        self.cursor.execute("SELECT unique_link FROM users WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def get_user_by_link(self, link):
        """Находит пользователя по его уникальной ссылке"""
        self.cursor.execute("SELECT user_id FROM users WHERE unique_link = ?", (link,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def save_anonymous_message(self, recipient_id, sender_id, sender_username, sender_first_name, 
                               message_text=None, photo_file_id=None, reply_to_id=None):
        """Сохраняет анонимное сообщение"""
        sent_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute('''
            INSERT INTO messages (
                recipient_id, sender_id, sender_username, sender_first_name, 
                message_text, photo_file_id, sent_date, reply_to_message_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (recipient_id, sender_id, sender_username, sender_first_name, 
              message_text, photo_file_id, sent_date, reply_to_id))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_user_messages(self, user_id, requesting_user_id=None):
        """Получает все сообщения пользователя"""
        is_admin = self.is_admin(requesting_user_id) if requesting_user_id else False
        
        if is_admin:
            self.cursor.execute('''
                SELECT id, sender_id, sender_username, sender_first_name, 
                       message_text, photo_file_id, sent_date, is_read, reply_to_message_id
                FROM messages 
                WHERE recipient_id = ?
                ORDER BY sent_date DESC
            ''', (user_id,))
            return self.cursor.fetchall()
        else:
            self.cursor.execute('''
                SELECT id, message_text, photo_file_id, sent_date, is_read, reply_to_message_id
                FROM messages 
                WHERE recipient_id = ?
                ORDER BY sent_date DESC
            ''', (user_id,))
            return self.cursor.fetchall()
    
    def mark_message_as_read(self, message_id):
        """Отмечает сообщение как прочитанное"""
        self.cursor.execute('''
            UPDATE messages SET is_read = 1 WHERE id = ?
        ''', (message_id,))
        self.conn.commit()
    
    def get_unread_count(self, user_id):
        """Получает количество непрочитанных сообщений"""
        self.cursor.execute('''
            SELECT COUNT(*) FROM messages 
            WHERE recipient_id = ? AND is_read = 0
        ''', (user_id,))
        return self.cursor.fetchone()[0]
    
    def get_message_by_id(self, message_id, requesting_user_id=None):
        """Получает сообщение по ID"""
        is_admin = self.is_admin(requesting_user_id) if requesting_user_id else False
        
        if is_admin:
            self.cursor.execute('''
                SELECT id, sender_id, sender_username, sender_first_name, 
                       recipient_id, message_text, photo_file_id, sent_date, reply_to_message_id
                FROM messages WHERE id = ?
            ''', (message_id,))
            return self.cursor.fetchone()
        else:
            self.cursor.execute('''
                SELECT id, recipient_id, message_text, photo_file_id, sent_date, reply_to_message_id
                FROM messages WHERE id = ?
            ''', (message_id,))
            return self.cursor.fetchone()
    
    def get_all_users(self):
        """Получает список всех пользователей"""
        self.cursor.execute('''
            SELECT user_id, username, first_name, join_date, unique_link, is_admin
            FROM users ORDER BY join_date DESC
        ''')
        return self.cursor.fetchall()
    
    def get_all_messages_admin(self, limit=100):
        """Получает все сообщения для админа"""
        self.cursor.execute('''
            SELECT m.id, m.sender_id, m.sender_username, m.sender_first_name,
                   m.recipient_id, m.message_text, m.photo_file_id, m.sent_date, m.is_read,
                   u.username, u.first_name
            FROM messages m
            LEFT JOIN users u ON m.recipient_id = u.user_id
            ORDER BY m.sent_date DESC
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
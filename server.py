#!/usr/bin/env python3
import http.server
import socketserver
import os
import mimetypes
import json
import sqlite3
import hashlib
import time
import urllib.parse
from urllib.parse import unquote
from http.cookies import SimpleCookie
import cgi
import secrets
import urllib.request
import urllib.error
import uuid
from typing import Dict, List, Optional

import numpy as np

from backend.cat_recognition import (
    CatFaceRecognizer,
    aggregate_hashes,
    blob_to_embedding,
    embedding_to_blob,
    hex_to_bits,
    summarize_embeddings,
)

PORT = 40277
HOST = "0.0.0.0"
DB_PATH = "data/cats.db"

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the database schema and default records."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS cats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age TEXT,
                gender TEXT,
                description TEXT,
                image_path TEXT,
                owner_id INTEGER,
                is_approved BOOLEAN DEFAULT 0,
                is_rejected BOOLEAN DEFAULT 0,
                is_adopted BOOLEAN DEFAULT 0,
                sterilized BOOLEAN DEFAULT 0,
                special_notes TEXT,
                unique_markings TEXT,
                microchipped BOOLEAN DEFAULT 0,
                last_known_location TEXT,
                identification_code TEXT,
                reference_hash_hex TEXT,
                reference_hash_length INTEGER,
                embedding_vector BLOB,
                hash_version TEXT DEFAULT 'v1',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        )

        # Ensure new columns exist for legacy databases
        self._ensure_column(cursor, 'cats', 'is_rejected', 'BOOLEAN DEFAULT 0')
        self._ensure_column(cursor, 'cats', 'sterilized', 'BOOLEAN DEFAULT 0')
        self._ensure_column(cursor, 'cats', 'special_notes', 'TEXT')
        self._ensure_column(cursor, 'cats', 'unique_markings', 'TEXT')
        self._ensure_column(cursor, 'cats', 'microchipped', 'BOOLEAN DEFAULT 0')
        self._ensure_column(cursor, 'cats', 'last_known_location', 'TEXT')
        self._ensure_column(cursor, 'cats', 'identification_code', 'TEXT')
        self._ensure_column(cursor, 'cats', 'reference_hash_hex', 'TEXT')
        self._ensure_column(cursor, 'cats', 'reference_hash_length', 'INTEGER')
        self._ensure_column(cursor, 'cats', 'embedding_vector', 'BLOB')
        self._ensure_column(cursor, 'cats', 'hash_version', "TEXT DEFAULT 'v1'")
        self._ensure_column(cursor, 'cats', 'updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS cat_reference_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                hash_hex TEXT NOT NULL,
                hash_length INTEGER NOT NULL,
                embedding_vector BLOB,
                is_primary BOOLEAN DEFAULT 0,
                order_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cat_id) REFERENCES cats(id) ON DELETE CASCADE
            )
        '''
        )
        
        # Ensure order_index column exists for legacy databases
        self._ensure_column(cursor, 'cat_reference_images', 'order_index', 'INTEGER DEFAULT 0')

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS cat_recognition_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat_id INTEGER,
                matched BOOLEAN,
                match_score REAL,
                hash_distance INTEGER,
                request_metadata TEXT,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cat_id) REFERENCES cats(id)
            )
        '''
        )

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                is_verified BOOLEAN DEFAULT 0,
                verification_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        )

        self._ensure_column(cursor, 'users', 'is_verified', 'BOOLEAN DEFAULT 0')
        self._ensure_column(cursor, 'users', 'verification_token', 'TEXT')
        self._ensure_column(cursor, 'users', 'is_super_admin', 'BOOLEAN DEFAULT 0')

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS adoption_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat_id INTEGER,
                user_id INTEGER,
                message TEXT,
                contact_info TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cat_id) REFERENCES cats (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        '''
        )

        self._ensure_column(cursor, 'adoption_requests', 'message', 'TEXT')
        self._ensure_column(cursor, 'adoption_requests', 'contact_info', 'TEXT')

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                subject TEXT,
                content TEXT,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (receiver_id) REFERENCES users (id)
            )
        '''
        )

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS content (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        )

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        )

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS admin_login_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                created_by INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT 0,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        '''
        )

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                code TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT 0,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        '''
        )

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS cat_location_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                visit_status TEXT,
                visit_notes TEXT,
                recognition_event_id INTEGER,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cat_id) REFERENCES cats(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (recognition_event_id) REFERENCES cat_recognition_events(id)
            )
        '''
        )

        self._ensure_column(cursor, 'users', 'updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')

        self._initialize_content_defaults(cursor)
        self._initialize_admin_user(cursor)
        self._initialize_default_settings(cursor)

        conn.commit()
        conn.close()

    def _ensure_column(self, cursor, table: str, column: str, definition: str) -> None:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError:
            pass

    def _initialize_content_defaults(self, cursor) -> None:
        cursor.execute("SELECT COUNT(*) FROM content WHERE id = 'home_intro'")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                '''
                INSERT INTO content (id, title, content)
                VALUES (
                    'home_intro',
                    '欢迎来到流浪猫公益项目',
                    '我们致力于救助和照顾流浪猫，为它们寻找温暖的家。通过我们的平台，您可以了解待领养的猫咪信息，也可以申请成为志愿者或爱心家庭。'
                )
            '''
            )

        cursor.execute("SELECT COUNT(*) FROM content WHERE id = 'about_mission'")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                '''
                INSERT INTO content (id, title, content)
                VALUES (
                    'about_mission',
                    '我们的使命',
                    '流浪猫公益项目成立于2020年，由一群热爱动物的志愿者发起。我们致力于救助城市中的流浪猫，为它们提供医疗护理、食物和庇护所，并努力为它们寻找永久的爱心家庭。'
                )
            '''
            )

        cursor.execute("SELECT COUNT(*) FROM content WHERE id = 'privacy_policy'")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                '''
                INSERT INTO content (id, title, content)
                VALUES (
                    'privacy_policy',
                    '隐私政策',
                    '<h2>信息收集</h2><p>我们收集您在使用本网站时提供的信息，包括但不限于：</p><ul><li>注册时提供的姓名、邮箱地址等个人信息</li><li>上传的猫咪信息和照片</li><li>领养申请时提供的联系方式</li><li>网站使用数据和技术信息</li></ul><h2>信息使用</h2><p>我们使用收集的信息用于：</p><ul><li>提供和改善我们的服务</li><li>处理领养申请和用户请求</li><li>与您沟通，包括发送重要通知</li><li>保护网站安全和防止欺诈</li></ul><h2>信息保护</h2><p>我们采取适当的技术和管理措施来保护您的个人信息，防止未经授权的访问、使用或披露。</p><h2>信息共享</h2><p>我们不会向第三方出售、交易或转让您的个人信息，除非：</p><ul><li>获得您的明确同意</li><li>法律法规要求</li><li>保护我们的权利和财产</li></ul><h2>Cookie使用</h2><p>我们使用Cookie来改善用户体验，记住您的登录状态和偏好设置。</p><h2>您的权利</h2><p>您有权：</p><ul><li>访问和更新您的个人信息</li><li>要求删除您的个人信息</li><li>选择退出某些通信</li></ul><h2>联系我们</h2><p>如果您对本隐私政策有任何疑问，请通过<a href="/contact">联系我们</a>页面与我们联系。</p><h2>政策更新</h2><p>我们可能会不时更新本隐私政策。更新后的政策将在本页面发布，并更新"最后更新"日期。</p><p><em>最后更新：2025年1月</em></p>'
                )
            '''
            )

    def _initialize_admin_user(self, cursor) -> None:
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        if cursor.fetchone()[0] == 0:
            password_hash = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute(
                '''
                INSERT INTO users (name, email, password_hash, is_admin, is_verified)
                VALUES (?, ?, ?, 1, 1)
            ''',
                ("Admin User", "admin@cats.com", password_hash),
            )

    def _initialize_default_settings(self, cursor) -> None:
        defaults = {
            'cat_recognition.threshold': '0.78',
            'cat_recognition.max_results': '3',
            'cat_recognition.max_hamming': '120',
            'cat_recognition.model_path': '',
            'cat_recognition.hash_length_override': '',
        }
        for key, value in defaults.items():
            cursor.execute('SELECT 1 FROM settings WHERE key = ?', (key,))
            if cursor.fetchone() is None:
                cursor.execute(
                    '''
                    INSERT INTO settings (key, value)
                    VALUES (?, ?)
                ''',
                    (key, value),
                )
    
    def get_all_cats(self):
        """Get all approved cats from database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cats WHERE is_approved = 1 ORDER BY created_at DESC")
        cats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return cats
    
    def add_cat(self, name, age, gender, description, image_path, owner_id):
        """Add a new cat to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cats (name, age, gender, description, image_path, owner_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, age, gender, description, image_path, owner_id))
        cat_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return cat_id
    
    def get_all_cats_admin(self):
        """Get all cats (including pending) for admin view with owner info"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                c.*,
                u.name AS owner_name,
                u.email AS owner_email
            FROM cats c
            LEFT JOIN users u ON c.owner_id = u.id
            ORDER BY c.created_at DESC
        ''')
        cats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return cats
    
    def update_cat_approval(self, cat_id, is_approved, is_rejected=0):
        """Update cat approval/rejection status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE cats 
            SET is_approved = ?, is_rejected = ?
            WHERE id = ?
        ''', (is_approved, is_rejected, cat_id))
        conn.commit()
        conn.close()
    
    def get_user_by_email(self, email):
        """Get user by email"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def get_all_users(self):
        """Get all users (for admin)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, is_admin, is_super_admin, is_verified, created_at FROM users ORDER BY created_at DESC")
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users
    
    def get_admin_users(self):
        """Return all administrator accounts"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, email, is_admin, is_verified, created_at
            FROM users
            WHERE is_admin = 1
            ORDER BY created_at ASC
        """)
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users
    
    def get_all_adoption_requests(self):
        """Get all adoption requests (for admin)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                ar.id,
                ar.status,
                ar.message,
                ar.contact_info,
                ar.created_at,
                ar.cat_id,
                ar.user_id,
                c.name as cat_name,
                u.name as user_name,
                u.email as user_email
            FROM adoption_requests ar
            JOIN cats c ON ar.cat_id = c.id
            JOIN users u ON ar.user_id = u.id
            ORDER BY ar.created_at DESC
        ''')
        requests = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return requests
    
    def get_adoption_request_by_id(self, request_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                ar.*,
                c.name as cat_name,
                u.name as user_name,
                u.email as user_email
            FROM adoption_requests ar
            JOIN cats c ON ar.cat_id = c.id
            JOIN users u ON ar.user_id = u.id
            WHERE ar.id = ?
        ''', (request_id,))
        request = cursor.fetchone()
        conn.close()
        return dict(request) if request else None

    def create_adoption_request(self, cat_id: int, user_id: int, message: Optional[str] = None, contact_info: Optional[str] = None) -> Optional[int]:
        """Create a new adoption request, avoid duplicates while pending."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM adoption_requests
            WHERE cat_id = ? AND user_id = ? AND status = 'pending'
        ''', (cat_id, user_id))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return None

        cursor.execute('''
            INSERT INTO adoption_requests (cat_id, user_id, message, contact_info)
            VALUES (?, ?, ?, ?)
        ''', (cat_id, user_id, message, contact_info))
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return request_id

    def update_adoption_request_status(self, request_id: int, status: str) -> bool:
        """Update adoption request status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE adoption_requests
            SET status = ?
            WHERE id = ?
        ''', (status, request_id))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated
    
    def send_message(self, sender_id, receiver_id, subject, content):
        """Send a message from one user to another"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (sender_id, receiver_id, subject, content)
            VALUES (?, ?, ?, ?)
        ''', (sender_id, receiver_id, subject, content))
        message_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return message_id
    
    def get_user_messages(self, user_id):
        """Get all messages for a user (inbox)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                m.id,
                m.subject,
                m.content,
                m.is_read,
                m.created_at,
                m.sender_id,
                u.name as sender_name,
                u.email as sender_email
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.receiver_id = ?
            ORDER BY m.created_at DESC
        ''', (user_id,))
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages
    
    def get_user_sent_messages(self, user_id):
        """Get all messages sent by a user (outbox)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                m.id,
                m.subject,
                m.content,
                m.created_at,
                m.receiver_id,
                u.name as receiver_name,
                u.email as receiver_email
            FROM messages m
            JOIN users u ON m.receiver_id = u.id
            WHERE m.sender_id = ?
            ORDER BY m.created_at DESC
        ''', (user_id,))
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages
    
    def mark_message_as_read(self, message_id):
        """Mark a message as read"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE messages 
            SET is_read = 1
            WHERE id = ?
        ''', (message_id,))
        conn.commit()
        conn.close()
    
    def mark_message_as_read_for_user(self, message_id, user_id) -> bool:
        """Mark a message as read only if it belongs to the user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE messages
            SET is_read = 1
            WHERE id = ? AND receiver_id = ?
        ''', (message_id, user_id))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated
    
    def get_content(self, content_id):
        """Get content by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM content WHERE id = ?', (content_id,))
        content = cursor.fetchone()
        conn.close()
        return dict(content) if content else None
    
    def get_all_content(self):
        """Get all content"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM content ORDER BY id')
        contents = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return contents
    
    def update_content(self, content_id, title, content_text):
        """Update content by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO content (id, title, content, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (content_id, title, content_text))
        conn.commit()
        conn.close()
    
    def get_setting(self, key):
        """Get a setting value by key"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def set_setting(self, key, value):
        """Set a setting value"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        conn.commit()
        conn.close()
    
    def get_notification_recipients(self) -> List[str]:
        """Return notification recipient emails from settings"""
        raw = self.get_setting('notification.emails')
        if not raw:
            return []
        recipients = []
        for entry in raw.split(','):
            email = entry.strip()
            if email:
                recipients.append(email)
        return recipients
    
    def get_notification_from_email(self) -> str:
        return self.get_setting('notification.from_email') or "alerts@resend.dev"
    
    def create_user(self, name, email, password):
        """Create a new user with verification token"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        verification_token = secrets.token_urlsafe(32)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (name, email, password_hash, verification_token, is_verified)
                VALUES (?, ?, ?, ?, 0)
            ''', (name, email, password_hash, verification_token))
            user_id = cursor.lastrowid
            conn.commit()
            result = (user_id, verification_token)
        except sqlite3.IntegrityError:
            result = None
        conn.close()
        return result
    
    def verify_user_email(self, token):
        """Verify user email by token"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET is_verified = 1, verification_token = NULL
            WHERE verification_token = ? AND is_verified = 0
        ''', (token,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def update_user_verification_status(self, user_id, is_verified):
        """Manually update user verification status (admin only)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET is_verified = ?
            WHERE id = ?
        ''', (1 if is_verified else 0, user_id))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def update_user_admin_status(self, user_id, is_admin):
        """Manually update user admin status (admin only)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET is_admin = ?
            WHERE id = ?
        ''', (1 if is_admin else 0, user_id))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def update_user_super_admin_status(self, user_id, is_super_admin):
        """Update user super admin status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET is_super_admin = ?
            WHERE id = ?
        ''', (1 if is_super_admin else 0, user_id))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def delete_user(self, user_id):
        """Delete a user and related data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Delete messages where user is sender or receiver
            cursor.execute('DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?', (user_id, user_id))
            # Delete adoption requests by user
            cursor.execute('DELETE FROM adoption_requests WHERE user_id = ?', (user_id,))
            # Remove ownership of cats (keep cats but clear owner)
            cursor.execute('UPDATE cats SET owner_id = NULL WHERE owner_id = ?', (user_id,))
            # Delete user record (only non-admin)
            cursor.execute('DELETE FROM users WHERE id = ? AND is_admin = 0', (user_id,))
            success = cursor.rowcount > 0
            conn.commit()
            return success
        finally:
            conn.close()
    
    def get_user_by_verification_token(self, token):
        """Get user by verification token"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE verification_token = ?", (token,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

    # --- Admin login token methods ---
    
    def create_admin_login_token(self, created_by_user_id, expires_in_hours=24):
        """Create a single-use admin login token"""
        token = secrets.token_urlsafe(32)
        expires_at = time.time() + (expires_in_hours * 3600)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO admin_login_tokens (token, created_by, expires_at)
                VALUES (?, ?, datetime(?, 'unixepoch'))
            ''', (token, created_by_user_id, expires_at))
            conn.commit()
            result = token
        except sqlite3.IntegrityError:
            # Token collision (extremely unlikely), retry once
            token = secrets.token_urlsafe(32)
            cursor.execute('''
                INSERT INTO admin_login_tokens (token, created_by, expires_at)
                VALUES (?, ?, datetime(?, 'unixepoch'))
            ''', (token, created_by_user_id, expires_at))
            conn.commit()
            result = token
        finally:
            conn.close()
        return result
    
    def validate_and_use_admin_token(self, token):
        """Validate and mark an admin login token as used. Returns user_id if valid, None otherwise."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if token exists, is not used, and not expired
        cursor.execute('''
            SELECT t.*, u.is_admin
            FROM admin_login_tokens t
            JOIN users u ON t.created_by = u.id
            WHERE t.token = ? 
            AND t.used = 0 
            AND datetime(t.expires_at) > datetime('now')
            AND u.is_admin = 1
        ''', (token,))
        
        token_record = cursor.fetchone()
        
        if token_record:
            # Mark token as used
            cursor.execute('''
                UPDATE admin_login_tokens 
                SET used = 1, used_at = CURRENT_TIMESTAMP 
                WHERE token = ?
            ''', (token,))
            conn.commit()
            user_id = token_record['created_by']
        else:
            user_id = None
        
        conn.close()
        return user_id
    
    def get_admin_login_tokens(self, limit=50):
        """Get recent admin login tokens (admin only)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                t.id,
                t.token,
                t.expires_at,
                t.used,
                t.used_at,
                t.created_at,
                u.name as created_by_name,
                u.email as created_by_email
            FROM admin_login_tokens t
            JOIN users u ON t.created_by = u.id
            ORDER BY t.created_at DESC
            LIMIT ?
        ''', (limit,))
        tokens = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tokens
    
    # --- User profile and password methods ---
    
    def update_user_password(self, user_id, new_password_hash):
        """Update user password by hash"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_password_hash, user_id))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def update_user_profile(self, user_id, name=None, email=None):
        """Update user profile information"""
        updates = []
        values = []
        
        if name is not None:
            updates.append("name = ?")
            values.append(name)
        if email is not None:
            updates.append("email = ?")
            values.append(email)
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(user_id)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(f'''
                UPDATE users 
                SET {', '.join(updates)}
                WHERE id = ?
            ''', values)
            success = cursor.rowcount > 0
            conn.commit()
        except sqlite3.IntegrityError:
            # Email already exists
            success = False
        finally:
            conn.close()
        return success
    
    # --- Password reset methods ---
    
    def create_password_reset_token(self, user_id, expires_in_hours=1):
        """Create a password reset token with a 6-digit code"""
        token = secrets.token_urlsafe(32)
        # Generate a 6-digit verification code
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        expires_at = time.time() + (expires_in_hours * 3600)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO password_reset_tokens (user_id, token, code, expires_at)
                VALUES (?, ?, ?, datetime(?, 'unixepoch'))
            ''', (user_id, token, code, expires_at))
            conn.commit()
            result = (token, code)
        except sqlite3.IntegrityError:
            # Token collision (extremely unlikely), retry once
            token = secrets.token_urlsafe(32)
            code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
            cursor.execute('''
                INSERT INTO password_reset_tokens (user_id, token, code, expires_at)
                VALUES (?, ?, ?, datetime(?, 'unixepoch'))
            ''', (user_id, token, code, expires_at))
            conn.commit()
            result = (token, code)
        finally:
            conn.close()
        return result
    
    def validate_password_reset_code(self, email, code):
        """Validate password reset code. Returns (user_id, token) if valid, (None, None) otherwise."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Find user by email and validate code
        cursor.execute('''
            SELECT prt.*, u.id as user_id
            FROM password_reset_tokens prt
            JOIN users u ON prt.user_id = u.id
            WHERE u.email = ? 
            AND prt.code = ?
            AND prt.used = 0 
            AND datetime(prt.expires_at) > datetime('now')
            ORDER BY prt.created_at DESC
            LIMIT 1
        ''', (email, code))
        
        token_record = cursor.fetchone()
        
        if token_record:
            user_id = token_record['user_id']
            token = token_record['token']
        else:
            user_id = None
            token = None
        
        conn.close()
        return (user_id, token)
    
    def use_password_reset_token(self, token):
        """Mark a password reset token as used"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE password_reset_tokens 
            SET used = 1, used_at = CURRENT_TIMESTAMP 
            WHERE token = ? AND used = 0
        ''', (token,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def get_user_password_reset_tokens(self, user_id):
        """Get all password reset tokens for a user (for admin/debugging)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, token, code, expires_at, used, used_at, created_at
            FROM password_reset_tokens
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (user_id,))
        tokens = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tokens

    # --- Cat recognition helpers -------------------------------------------------

    def get_cat_by_id(self, cat_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cats WHERE id = ?", (cat_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None

    def update_cat_profile(self, cat_id: int, payload: Dict) -> bool:
        if not payload:
            return False
        columns = []
        values = []
        for key, value in payload.items():
            columns.append(f"{key} = ?")
            values.append(value)
        values.append(cat_id)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE cats
            SET {', '.join(columns)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            values,
        )
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    def add_cat_reference_image(
        self,
        cat_id: int,
        image_path: str,
        hash_hex: str,
        hash_length: int,
        embedding_bytes: bytes,
        is_primary: bool = False,
    ) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Get max order_index for this cat to append at the end
        cursor.execute('SELECT COALESCE(MAX(order_index), -1) FROM cat_reference_images WHERE cat_id = ?', (cat_id,))
        max_order = cursor.fetchone()[0] or -1
        new_order = max_order + 1
        
        cursor.execute(
            '''
            INSERT INTO cat_reference_images (
                cat_id,
                image_path,
                hash_hex,
                hash_length,
                embedding_vector,
                is_primary,
                order_index
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
            (
                cat_id,
                image_path,
                hash_hex,
                hash_length,
                sqlite3.Binary(embedding_bytes),
                1 if is_primary else 0,
                new_order,
            ),
        )
        reference_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return reference_id

    def get_cat_reference_images(self, cat_id: int, include_embedding: bool = False, reference_ids: Optional[List[int]] = None) -> List[Dict]:
        columns = [
            "id",
            "cat_id",
            "image_path",
            "hash_hex",
            "hash_length",
            "is_primary",
            "order_index",
            "created_at",
        ]
        if include_embedding:
            columns.append("embedding_vector")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        params = [cat_id]
        filter_sql = ""
        if reference_ids:
            placeholders = ','.join('?' for _ in reference_ids)
            filter_sql = f" AND id IN ({placeholders})"
            params.extend(reference_ids)

        cursor.execute(
            f'''
            SELECT {', '.join(columns)}
            FROM cat_reference_images
            WHERE cat_id = ? {filter_sql}
            ORDER BY order_index ASC, created_at DESC
        ''',
            tuple(params),
        )
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def update_cat_reference_image_embedding(
        self,
        reference_id: int,
        hash_hex: str,
        hash_length: int,
        embedding_bytes: bytes,
    ) -> bool:
        """Update the embedding and hash for a reference image"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE cat_reference_images
            SET hash_hex = ?,
                hash_length = ?,
                embedding_vector = ?
            WHERE id = ?
        ''',
            (
                hash_hex,
                hash_length,
                sqlite3.Binary(embedding_bytes),
                reference_id,
            ),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def refresh_cat_signature(self, cat_id: int, aggregated_hash_hex: Optional[str], hash_length: Optional[int], embedding_bytes: Optional[bytes]) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE cats
            SET reference_hash_hex = ?,
                reference_hash_length = ?,
                embedding_vector = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''',
            (
                aggregated_hash_hex,
                hash_length,
                sqlite3.Binary(embedding_bytes) if embedding_bytes else None,
                cat_id,
            ),
        )
        conn.commit()
        conn.close()

    def count_reference_images(self, cat_id: int) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM cat_reference_images WHERE cat_id = ?', (cat_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def delete_reference_image(self, reference_id: int) -> bool:
        """Delete a reference image by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Get the image path for file deletion
        cursor.execute('SELECT image_path, cat_id FROM cat_reference_images WHERE id = ?', (reference_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False
        
        image_path, cat_id = result
        
        # Delete from database
        cursor.execute('DELETE FROM cat_reference_images WHERE id = ?', (reference_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        # Delete file if it exists
        if deleted and image_path:
            try:
                full_path = os.path.join('.', image_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
            except Exception as e:
                print(f"Warning: Could not delete image file {image_path}: {e}")
        
        return deleted

    def update_reference_image_order(self, cat_id: int, reference_orders: List[Dict]) -> bool:
        """Update order_index for multiple reference images. reference_orders is a list of {id: order_index}"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            for ref_order in reference_orders:
                ref_id = ref_order.get('id')
                order_index = ref_order.get('order_index', 0)
                if ref_id:
                    cursor.execute(
                        'UPDATE cat_reference_images SET order_index = ? WHERE id = ? AND cat_id = ?',
                        (order_index, ref_id, cat_id)
                    )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error updating reference image order: {e}")
            return False
        finally:
            conn.close()

    def move_reference_image(self, reference_id: int, new_cat_id: int) -> bool:
        """Move a reference image from one cat to another"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Get max order_index for the new cat
            cursor.execute('SELECT COALESCE(MAX(order_index), -1) FROM cat_reference_images WHERE cat_id = ?', (new_cat_id,))
            max_order = cursor.fetchone()[0] or -1
            new_order = max_order + 1
            
            # Update the cat_id and order_index
            cursor.execute(
                'UPDATE cat_reference_images SET cat_id = ?, order_index = ? WHERE id = ?',
                (new_cat_id, new_order, reference_id)
            )
            moved = cursor.rowcount > 0
            conn.commit()
            return moved
        except Exception as e:
            conn.rollback()
            print(f"Error moving reference image: {e}")
            return False
        finally:
            conn.close()

    def set_primary_reference_image(self, cat_id: int, reference_id: int) -> bool:
        """Set a reference image as primary (and unset others for the same cat)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Unset all primary images for this cat
            cursor.execute('UPDATE cat_reference_images SET is_primary = 0 WHERE cat_id = ?', (cat_id,))
            # Set the specified one as primary
            cursor.execute(
                'UPDATE cat_reference_images SET is_primary = 1 WHERE id = ? AND cat_id = ?',
                (reference_id, cat_id)
            )
            updated = cursor.rowcount > 0
            conn.commit()
            return updated
        except Exception as e:
            conn.rollback()
            print(f"Error setting primary reference image: {e}")
            return False
        finally:
            conn.close()

    def set_cat_adoption_state(self, cat_id: int, is_adopted: bool) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE cats
            SET is_adopted = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''',
            (1 if is_adopted else 0, cat_id),
        )
        conn.commit()
        conn.close()

    def list_reference_vectors(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                cri.id AS reference_id,
                cri.cat_id,
                cri.hash_hex,
                cri.hash_length,
                cri.embedding_vector,
                cri.is_primary,
                c.name AS cat_name,
                c.is_approved,
                c.is_rejected
            FROM cat_reference_images cri
            JOIN cats c ON c.id = cri.cat_id
        '''
        )
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def list_reference_images(self, limit: Optional[int] = None) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = '''
            SELECT
                cri.id,
                cri.cat_id,
                c.name AS cat_name,
                cri.image_path,
                cri.hash_hex,
                cri.hash_length,
                LENGTH(cri.embedding_vector) AS embedding_bytes,
                cri.is_primary,
                cri.order_index,
                cri.created_at
            FROM cat_reference_images cri
            LEFT JOIN cats c ON c.id = cri.cat_id
            ORDER BY cri.order_index ASC, cri.created_at DESC
        '''
        if limit:
            cursor.execute(f"{query} LIMIT ?", (limit,))
        else:
            cursor.execute(query)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def list_recognition_events(self, limit: Optional[int] = None) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = '''
            SELECT
                cre.id,
                cre.cat_id,
                c.name AS cat_name,
                cre.matched,
                cre.match_score,
                cre.hash_distance,
                cre.request_metadata,
                cre.image_path,
                cre.created_at
            FROM cat_recognition_events cre
            LEFT JOIN cats c ON c.id = cre.cat_id
            ORDER BY cre.created_at DESC
        '''
        if limit:
            cursor.execute(f"{query} LIMIT ?", (limit,))
        else:
            cursor.execute(query)
        events = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return events

    def record_recognition_event(
        self,
        *,
        cat_id: Optional[int],
        matched: bool,
        match_score: float,
        hash_distance: Optional[int],
        metadata: Dict,
        image_path: Optional[str],
    ) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO cat_recognition_events (
                cat_id,
                matched,
                match_score,
                hash_distance,
                request_metadata,
                image_path
            )
            VALUES (?, ?, ?, ?, ?, ?)
        ''',
            (
                cat_id,
                1 if matched else 0,
                match_score,
                hash_distance,
                json.dumps(metadata, ensure_ascii=False),
                image_path,
            ),
        )
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return event_id

    def add_location_history(
        self,
        cat_id: int,
        user_id: int,
        latitude: float,
        longitude: float,
        visit_status: Optional[str] = None,
        visit_notes: Optional[str] = None,
        recognition_event_id: Optional[int] = None,
        image_path: Optional[str] = None,
    ) -> int:
        """Add a location history record for a cat"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO cat_location_history (
                cat_id,
                user_id,
                latitude,
                longitude,
                visit_status,
                visit_notes,
                recognition_event_id,
                image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
            (
                cat_id,
                user_id,
                latitude,
                longitude,
                visit_status,
                visit_notes,
                recognition_event_id,
                image_path,
            ),
        )
        location_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return location_id

    def get_location_history(
        self,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        cat_id: Optional[int] = None,
    ) -> List[Dict]:
        """Get location history records (admin only)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT
                clh.id,
                clh.cat_id,
                COALESCE(c.name, '未知猫咪') AS cat_name,
                clh.user_id,
                COALESCE(u.name, '未知用户') AS user_name,
                clh.latitude,
                clh.longitude,
                clh.visit_status,
                clh.visit_notes,
                clh.recognition_event_id,
                clh.image_path,
                clh.created_at
            FROM cat_location_history clh
            LEFT JOIN cats c ON c.id = clh.cat_id
            LEFT JOIN users u ON u.id = clh.user_id
            WHERE 1=1
        '''
        params = []
        
        if cat_id is not None:
            query += ' AND clh.cat_id = ?'
            params.append(cat_id)
        
        if start_year is not None:
            query += ' AND strftime("%Y", clh.created_at) >= ?'
            params.append(str(start_year))
        
        if end_year is not None:
            query += ' AND strftime("%Y", clh.created_at) <= ?'
            params.append(str(end_year))
        
        query += ' ORDER BY clh.created_at DESC'
        
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_location_by_id(self, location_id: int) -> Optional[Dict]:
        """Get a single location history record by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                clh.id,
                clh.cat_id,
                c.name AS cat_name,
                c.age,
                c.gender,
                c.description,
                c.sterilized,
                c.microchipped,
                c.special_notes,
                c.unique_markings,
                c.identification_code,
                c.image_path AS cat_image_path,
                clh.user_id,
                u.name AS user_name,
                u.email AS user_email,
                clh.latitude,
                clh.longitude,
                clh.visit_status,
                clh.visit_notes,
                clh.recognition_event_id,
                clh.image_path,
                clh.created_at
            FROM cat_location_history clh
            JOIN cats c ON c.id = clh.cat_id
            JOIN users u ON u.id = clh.user_id
            WHERE clh.id = ?
        ''',
            (location_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None


# Initialize database
db = DatabaseManager(DB_PATH)

def create_cat_recognizer_from_settings() -> CatFaceRecognizer:
    hash_override_setting = db.get_setting('cat_recognition.hash_length_override')
    hash_override = None
    if hash_override_setting:
        try:
            hash_override = int(hash_override_setting)
        except ValueError:
            hash_override = None

    recognizer = CatFaceRecognizer(hash_length=hash_override)

    model_path_setting = db.get_setting('cat_recognition.model_path')
    if model_path_setting:
        try:
            recognizer.set_model_weights(model_path_setting)
        except FileNotFoundError:
            print(f"[CatRecognition] Model not found at {model_path_setting}. Using default ImageNet weights.")
        except RuntimeError as exc:
            print(f"[CatRecognition] Failed to load model weights: {exc}.")
    return recognizer

cat_recognizer = create_cat_recognizer_from_settings()

def reprocess_reference_images(cat_id: int, reference_ids: Optional[List[int]] = None) -> int:
    """
    Reprocess reference images through the current model and update their embeddings.
    Returns the number of images successfully reprocessed.
    """
    global cat_recognizer
    # Refresh recognizer to ensure we're using the latest model settings
    cat_recognizer = create_cat_recognizer_from_settings()
    
    references = db.get_cat_reference_images(cat_id, include_embedding=False, reference_ids=reference_ids)
    if not references:
        return 0
    
    reprocessed_count = 0
    for reference in references:
        reference_id = reference.get('id')
        image_path = reference.get('image_path')
        
        if not image_path or not reference_id:
            continue
        
        # Read image file from disk
        if not os.path.exists(image_path):
            print(f"[Reprocess] Image file not found: {image_path}")
            continue
        
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            
            # Process through current model
            embedding, hash_hex, hash_bits = cat_recognizer.compute_signature(image_bytes)
            hash_length = int(hash_bits.size)
            
            # Update database
            success = db.update_cat_reference_image_embedding(
                reference_id=reference_id,
                hash_hex=hash_hex,
                hash_length=hash_length,
                embedding_bytes=embedding_to_blob(embedding),
            )
            
            if success:
                reprocessed_count += 1
        except Exception as exc:
            print(f"[Reprocess] Failed to reprocess reference {reference_id}: {exc}")
            continue
    
    return reprocessed_count

def recompute_cat_signature(cat_id: int, reference_ids: Optional[List[int]] = None) -> None:
    references = db.get_cat_reference_images(cat_id, include_embedding=True, reference_ids=reference_ids)
    if not references:
        db.refresh_cat_signature(cat_id, None, None, None)
        return

    embeddings = []
    hash_bitsets = []
    for reference in references:
        embedding_blob = reference.get('embedding_vector')
        if embedding_blob:
            embeddings.append(blob_to_embedding(embedding_blob))
        hash_hex = reference.get('hash_hex')
        hash_length = reference.get('hash_length')
        if hash_hex:
            hash_bitsets.append(hex_to_bits(hash_hex, hash_length))

    aggregated_embedding = summarize_embeddings([vec for vec in embeddings if vec.size])
    aggregated_hash_hex = aggregate_hashes(hash_bitsets)

    embedding_bytes = embedding_to_blob(aggregated_embedding) if aggregated_embedding is not None else None
    aggregated_hash_length = None
    if aggregated_hash_hex:
        aggregated_hash_length = hex_to_bits(aggregated_hash_hex).size

    db.refresh_cat_signature(cat_id, aggregated_hash_hex, aggregated_hash_length, embedding_bytes)


def get_recognition_settings() -> Dict:
    try:
        threshold = float(db.get_setting('cat_recognition.threshold') or 0.78)
    except ValueError:
        threshold = 0.78

    try:
        max_results = int(db.get_setting('cat_recognition.max_results') or 3)
    except ValueError:
        max_results = 3

    max_hamming_setting = db.get_setting('cat_recognition.max_hamming')
    try:
        max_hamming = int(max_hamming_setting) if max_hamming_setting else None
    except ValueError:
        max_hamming = None

    return {
        "threshold": threshold,
        "max_results": max_results,
        "max_hamming": max_hamming,
        "model_path": db.get_setting('cat_recognition.model_path') or "",
        "hash_length_override": db.get_setting('cat_recognition.hash_length_override') or "",
    }


def save_uploaded_file(directory: str, original_filename: str, data: bytes) -> str:
    os.makedirs(directory, exist_ok=True)
    _, ext = os.path.splitext(original_filename or '')
    unique_name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(directory, unique_name)
    with open(file_path, 'wb') as handle:
        handle.write(data)
    return file_path


def sanitize_cat_record(cat: Optional[Dict]) -> Optional[Dict]:
    if not cat:
        return None
    sanitized = dict(cat)
    sanitized.pop('embedding_vector', None)
    for key in ('sterilized', 'microchipped', 'is_adopted', 'is_approved', 'is_rejected'):
        if key in sanitized and sanitized[key] is not None:
            sanitized[key] = bool(sanitized[key])
    return sanitized


def send_verification_email(email, name, token):
    """Send verification email via Resend API"""
    api_key = db.get_setting('resend_api_key')
    if not api_key:
        print("Warning: Resend API key not configured. Email not sent.")
        return False
    
    # Get the base URL from settings or use default
    base_url = db.get_setting('base_url') or f"http://{HOST}:{PORT}"
    verification_url = f"{base_url}/verify-email?token={token}"
    
    # Get "from" email address from settings or use default
    from_email = db.get_setting('resend_from_email') or "noreply@resend.dev"
    
    # Prepare email data for Resend API
    email_data = {
        "from": from_email,
        "to": [email],
        "subject": "请验证您的邮箱地址 - 流浪猫公益项目",
        "html": f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #4CAF50;">欢迎加入流浪猫公益项目！</h2>
                <p>亲爱的 {name}，</p>
                <p>感谢您注册我们的平台。请点击下面的链接来验证您的邮箱地址：</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" 
                       style="background-color: #4CAF50; color: white; padding: 12px 24px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        验证邮箱
                    </a>
                </p>
                <p>或者复制以下链接到浏览器中打开：</p>
                <p style="word-break: break-all; color: #666;">{verification_url}</p>
                <p>如果您没有注册此账户，请忽略此邮件。</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">此邮件由系统自动发送，请勿回复。</p>
            </div>
        </body>
        </html>
        """
    }
    
    # Send request to Resend API
    try:
        req = urllib.request.Request(
            'https://api.resend.com/emails',
            data=json.dumps(email_data).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
        )
        response = urllib.request.urlopen(req)
        if response.getcode() == 200:
            return True
        else:
            print(f"Resend API error: {response.getcode()}")
            return False
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Resend API HTTP error: {e.code} - {error_body}")
        return False
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

def send_password_reset_email(email, name, code):
    """Send password reset verification code via Resend API"""
    api_key = db.get_setting('resend_api_key')
    if not api_key:
        print("Warning: Resend API key not configured. Email not sent.")
        return False
    
    # Get "from" email address from settings or use default
    from_email = db.get_setting('resend_from_email') or "noreply@resend.dev"
    
    # Prepare email data for Resend API
    email_data = {
        "from": from_email,
        "to": [email],
        "subject": "账户密码重置验证码 - 流浪猫公益项目",
        "html": f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #4CAF50;">密码重置请求</h2>
                <p>亲爱的 {name}，</p>
                <p>我们收到了您的密码重置请求。请使用以下验证码来重置您的密码：</p>
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background-color: #f5f5f5; padding: 20px; border-radius: 8px; display: inline-block;">
                        <p style="font-size: 14px; color: #666; margin: 0 0 10px 0;">验证码</p>
                        <p style="font-size: 32px; font-weight: bold; color: #4CAF50; letter-spacing: 8px; margin: 0; font-family: 'Courier New', monospace;">{code}</p>
                    </div>
                </div>
                <p style="color: #dc3545; font-weight: bold;">此验证码有效期为1小时，请尽快使用。</p>
                <p>如果您没有请求重置密码，请忽略此邮件。您的账户仍然是安全的。</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">此邮件由系统自动发送，请勿回复。</p>
            </div>
        </body>
        </html>
        """
    }
    
    # Send request to Resend API
    try:
        req = urllib.request.Request(
            'https://api.resend.com/emails',
            data=json.dumps(email_data).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
        )
        response = urllib.request.urlopen(req)
        if response.getcode() == 200:
            return True
        else:
            print(f"Resend API error: {response.getcode()}")
            return False
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Resend API HTTP error: {e.code} - {error_body}")
        return False
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

def send_notification_email(subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    """Send a notification email to configured team members."""
    api_key = db.get_setting('resend_api_key')
    recipients = db.get_notification_recipients()
    from_email = db.get_notification_from_email()

    if not api_key:
        print("Warning: Resend API key not configured. Notification not sent.")
        return False
    if not recipients:
        print("Warning: Notification recipients not configured. Notification skipped.")
        return False

    email_data = {
        "from": from_email,
        "to": recipients,
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        email_data["text"] = text_body

    try:
        req = urllib.request.Request(
            'https://api.resend.com/emails',
            data=json.dumps(email_data).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
        )
        response = urllib.request.urlopen(req)
        if response.getcode() == 200:
            return True
        print(f"Resend notification error: {response.getcode()}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Resend notification HTTP error: {e.code} - {error_body}")
    except Exception as e:
        print(f"Error sending notification email: {str(e)}")
    return False

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # 添加CORS头部
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()
    
    def parse_cookies(self):
        """Parse cookies from the request"""
        cookie = SimpleCookie()
        if "Cookie" in self.headers:
            cookie.load(self.headers["Cookie"])
        return cookie
    
    def get_current_user(self):
        """Get current user from cookies"""
        cookies = self.parse_cookies()
        if "user_email" in cookies and "user_token" in cookies:
            email = cookies["user_email"].value
            token = cookies["user_token"].value
            
            # Simple token validation (in a real app, this would be more secure)
            user = db.get_user_by_email(email)
            if user:
                expected_token = hashlib.sha256(f"{email}{user['password_hash']}".encode()).hexdigest()
                if token == expected_token:
                    return user
        return None
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self.end_headers()
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/api/login':
            self.handle_login()
        elif self.path == '/api/register':
            self.handle_register()
        elif self.path == '/api/cats':
            self.handle_add_cat()
        elif self.path == '/api/admin/cat-profiles':
            self.handle_admin_create_cat_profile()
        elif self.path.startswith('/api/admin/cat-profiles/') and self.path.endswith('/reference-images'):
            path_parts = [part for part in self.path.split('/') if part]
            try:
                cat_id = int(path_parts[3])
                self.handle_upload_cat_reference_images(cat_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid cat ID"}).encode())
        elif self.path.startswith('/api/admin/reference-images/') and '/move' in self.path:
            # POST /api/admin/reference-images/{reference_id}/move
            path_parts = [part for part in self.path.split('/') if part]
            try:
                reference_id = int(path_parts[3])
                self.handle_move_reference_image(reference_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid reference image ID"}).encode())
        elif self.path.startswith('/api/admin/cats/') and '/reference-images/' in self.path and '/set-primary' in self.path:
            # POST /api/admin/cats/{cat_id}/reference-images/{reference_id}/set-primary
            path_parts = [part for part in self.path.split('/') if part]
            try:
                cat_id = int(path_parts[3])
                reference_id = int(path_parts[5])
                self.handle_set_primary_reference_image(cat_id, reference_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid cat or reference image ID"}).encode())
        elif self.path == '/api/cats/recognize':
            self.handle_recognize_cat()
        elif self.path == '/api/cats/location':
            self.handle_add_location()
        elif self.path == '/api/admin/location-history' or self.path.startswith('/api/admin/location-history?'):
            self.handle_get_location_history()
        elif self.path.startswith('/api/admin/location-history/') and self.path.count('/') == 4:
            path_parts = [part for part in self.path.split('/') if part]
            try:
                location_id = int(path_parts[3])
                self.handle_get_location_by_id(location_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid location ID"}).encode())
        elif self.path == '/api/admin/cat-recognition/settings':
            self.handle_update_recognition_settings()
        elif self.path == '/api/logout':
            self.handle_logout()
        elif self.path.startswith('/api/cats/'):
            # Handle cat approval/rejection
            path_parts = [part for part in self.path.split('/') if part]
            try:
                if len(path_parts) == 4 and path_parts[0] == 'api' and path_parts[1] == 'cats':
                    cat_id = int(path_parts[2])
                    if path_parts[3] == 'approve':
                        self.handle_approve_cat(cat_id)
                        return
                    if path_parts[3] == 'reject':
                        self.handle_reject_cat(cat_id)
                        return
                    if path_parts[3] == 'restore':
                        self.handle_restore_cat(cat_id)
                        return
                    if path_parts[3] == 'adopt':
                        self.handle_create_adoption_request(cat_id)
                        return
            except ValueError:
                pass

            self.send_response(404)
            self.end_headers()
        elif self.path == '/api/messages':
            self.handle_send_message()
        elif self.path.startswith('/api/content/'):
            # Handle content update
            content_id = self.path.split('/')[-1]
            self.handle_update_content(content_id)
        elif self.path == '/api/verify-email':
            self.handle_verify_email_post()
        elif self.path == '/api/admin/settings/resend-api-key':
            self.handle_update_resend_api_key()
        elif self.path == '/api/admin/settings/resend-from-email':
            self.handle_update_resend_from_email()
        elif self.path == '/api/admin/settings/base-url':
            self.handle_update_base_url()
        elif self.path == '/api/admin/settings/notification-emails':
            self.handle_update_notification_emails()
        elif self.path == '/api/admin/settings/notification-from-email':
            self.handle_update_notification_from_email()
        elif self.path.startswith('/api/admin/cats/') and self.path.endswith('/regenerate-hash'):
            path_parts = [part for part in self.path.split('/') if part]
            try:
                cat_id = int(path_parts[3])
                self.handle_regenerate_cat_hash(cat_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid cat ID"}).encode())
        elif self.path == '/api/admin/cats/reprocess-all':
            self.handle_reprocess_all_cats()
        elif self.path == '/api/messages/broadcast':
            self.handle_broadcast_message()
        elif self.path.startswith('/api/messages/') and self.path.endswith('/read'):
            path_parts = self.path.strip('/').split('/')
            try:
                message_id = int(path_parts[2])
                self.handle_mark_message_read(message_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid message ID"}).encode())
        elif self.path.startswith('/api/adoption_requests/') and self.path.endswith('/status'):
            path_parts = self.path.strip('/').split('/')
            try:
                request_id = int(path_parts[2])
                self.handle_update_adoption_request_status(request_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid adoption request ID"}).encode())
        elif '/api/users/' in self.path and self.path.endswith('/verify'):
            # Handle user verification status update
            # Path format: /api/users/{user_id}/verify
            path_parts = self.path.split('/')
            try:
                user_id = int(path_parts[3])  # /api/users/{id}/verify
                self.handle_update_user_verification(user_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid user ID"}).encode())
        elif '/api/users/' in self.path and self.path.endswith('/delete'):
            # Handle delete user request
            path_parts = self.path.split('/')
            try:
                user_id = int(path_parts[3])  # /api/users/{id}/delete
                self.handle_delete_user(user_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid user ID"}).encode())
        elif '/api/users/' in self.path and self.path.endswith('/admin'):
            # Handle set user as admin request
            path_parts = self.path.split('/')
            try:
                user_id = int(path_parts[3])  # /api/users/{id}/admin
                self.handle_set_user_admin(user_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid user ID"}).encode())
        elif self.path == '/api/user/change-password':
            self.handle_change_password()
        elif self.path == '/api/user/profile':
            self.handle_update_user_profile()
        elif self.path == '/api/user/forgot-password':
            self.handle_forgot_password()
        elif self.path == '/api/user/verify-reset-code':
            self.handle_verify_reset_code()
        elif self.path == '/api/user/reset-password':
            self.handle_reset_password()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_PUT(self):
        """Handle PUT requests"""
        if self.path == '/api/user/profile':
            self.handle_update_user_profile()
        elif self.path.startswith('/api/admin/cats/'):
            path_parts = [part for part in self.path.split('/') if part]
            try:
                if len(path_parts) >= 4 and path_parts[0] == 'api' and path_parts[1] == 'admin' and path_parts[2] == 'cats':
                    cat_id = int(path_parts[3])
                    self.handle_update_cat_admin(cat_id)
                    return
            except ValueError:
                pass
            self.send_response(400)
            self.end_headers()
        elif self.path.startswith('/api/admin/reference-images/') and self.path.endswith('/order'):
            # PUT /api/admin/reference-images/{cat_id}/order
            path_parts = [part for part in self.path.split('/') if part]
            try:
                cat_id = int(path_parts[3])
                self.handle_update_reference_image_order(cat_id)
            except (ValueError, IndexError):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid cat ID"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_DELETE(self):
        """Handle DELETE requests"""
        if self.path.startswith('/api/admin/reference-images/'):
            path_parts = [part for part in self.path.split('/') if part]
            try:
                if len(path_parts) >= 4 and path_parts[0] == 'api' and path_parts[1] == 'admin' and path_parts[2] == 'reference-images':
                    reference_id = int(path_parts[3])
                    self.handle_delete_reference_image(reference_id)
                    return
            except (ValueError, IndexError):
                pass
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid reference image ID"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        # API endpoints
        if self.path.startswith('/api/'):
            if self.path == '/api/cats':
                self.handle_get_cats()
            elif self.path == '/api/admin/cats':
                self.handle_get_cats_admin()
            elif self.path == '/api/current_user':
                self.handle_get_current_user()
            elif self.path == '/api/users':
                self.handle_get_users()
            elif self.path == '/api/adoption_requests':
                self.handle_get_adoption_requests()
            elif self.path == '/api/messages':
                self.handle_get_messages()
            elif self.path == '/api/messages/sent':
                self.handle_get_sent_messages()
            elif self.path == '/api/content':
                self.handle_get_all_content()
            elif self.path.startswith('/api/content/'):
                # Get specific content by ID
                content_id = self.path.split('/')[-1]
                self.handle_get_content(content_id)
            elif self.path == '/api/admin/cat-profiles':
                self.handle_get_cat_profiles_admin()
            elif self.path.startswith('/api/admin/cat-profiles/'):
                path_parts = [part for part in self.path.split('/') if part]
                try:
                    cat_id = int(path_parts[3])
                    self.handle_get_cat_profile_admin(cat_id)
                except (ValueError, IndexError):
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Invalid cat ID"}).encode())
            elif self.path == '/api/admin/settings/resend-api-key':
                self.handle_get_resend_api_key()
            elif self.path == '/api/admin/settings/resend-from-email':
                self.handle_get_resend_from_email()
            elif self.path == '/api/admin/settings/base-url':
                self.handle_get_base_url()
            elif self.path == '/api/admin/settings/notification-emails':
                self.handle_get_notification_emails()
            elif self.path == '/api/admin/settings/notification-from-email':
                self.handle_get_notification_from_email()
            elif self.path == '/api/cat-recognition/settings':
                self.handle_get_recognition_settings()
            elif self.path == '/api/admin/cat-references':
                self.handle_get_reference_images()
            elif self.path == '/api/admin/cat-recognition/events':
                self.handle_get_recognition_events()
            elif self.path == '/api/messages/recipients':
                self.handle_get_message_recipients()
            elif self.path == '/api/admin/location-history' or self.path.startswith('/api/admin/location-history?'):
                self.handle_get_location_history()
            elif self.path.startswith('/api/admin/location-history/'):
                # Parse path to get location ID (handle query params)
                parsed_path = urllib.parse.urlparse(self.path)
                path_parts = [part for part in parsed_path.path.split('/') if part]
                if len(path_parts) >= 4 and path_parts[0] == 'api' and path_parts[1] == 'admin' and path_parts[2] == 'location-history':
                    try:
                        location_id = int(path_parts[3])
                        self.handle_get_location_by_id(location_id)
                    except (ValueError, IndexError):
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "Invalid location ID"}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            elif self.path.startswith('/api/admin/login'):
                # Handle admin login via token
                query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                token = query_params.get('token', [None])[0]
                if token:
                    self.handle_admin_login_with_token(token)
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Token required"}).encode())
            else:
                self.send_response(404)
                self.end_headers()
        elif self.path.startswith('/verify-email'):
            self.handle_verify_email_get()
        elif self.path.startswith('/uploads/'):
            # Serve uploaded files
            try:
                file_path = self.path[1:]  # Remove leading slash
                if os.path.exists(file_path) and not os.path.isdir(file_path):
                    # Determine content type
                    content_type = self.guess_type(file_path)
                    
                    # Read and serve the file
                    with open(file_path, 'rb') as f:
                        self.send_response(200)
                        self.send_header('Content-type', content_type)
                        self.end_headers()
                        self.wfile.write(f.read())
                else:
                    self.send_response(404)
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.end_headers()
        else:
            # 解码URL路径
            path = unquote(self.path)
            
            # 如果请求根路径，返回index.html
            if path == '/' or path == '/index.html':
                self.path = '/index.html'
            elif path == '/':
                self.path = '/index.html'
            elif path == '/admin':
                self.path = '/admin.html'
            elif path == '/upload':
                self.path = '/upload.html'
            elif path == '/messages':
                self.path = '/messages.html'
            elif path == '/about':
                self.path = '/about.html'
            elif path == '/contact':
                self.path = '/contact.html'
            elif path == '/privacy':
                self.path = '/privacy.html'
            elif path == '/content-management':
                self.path = '/content-management.html'
            elif path == '/profile':
                self.path = '/profile.html'
            elif path == '/admin-cat-editor':
                self.path = '/admin-cat-editor.html'
            elif path == '/admin-location-map':
                self.path = '/admin-location-map.html'
            
            # 尝试提供静态文件
            try:
                super().do_GET()
            except FileNotFoundError:
                # 如果文件未找到，返回404页面
                self.path = '/404.html'
                try:
                    super().do_GET()
                except:
                    # 如果连404页面都没有，返回简单404响应
                    self.send_response(404)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<h1>404 Not Found</h1>")
    
    def handle_login(self):
        """Handle user login"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Email and password required"}).encode())
            return
        
        user = db.get_user_by_email(email)
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid credentials"}).encode())
            return
        
        # Prevent admin login via password - admins must use single-use login links
        if user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin accounts cannot login with password. Please use a single-use admin login link."}).encode())
            return
        
        if user['password_hash'] == hashlib.sha256(password.encode()).hexdigest():
            # Create auth token
            token = hashlib.sha256(f"{email}{user['password_hash']}".encode()).hexdigest()
            
            # Set cookies with 24-day expiration
            self.send_response(200)
            self.send_header('Set-Cookie', f"user_email={email}; Path=/; Max-Age=2073600")
            self.send_header('Set-Cookie', f"user_token={token}; Path=/; Max-Age=2073600")
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                "id": user['id'],
                "name": user['name'],
                "email": user['email'],
                "is_admin": bool(user.get('is_admin', False)),
                "is_super_admin": bool(user.get('is_super_admin', False)),
                "is_verified": bool(user.get('is_verified', False))
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid credentials"}).encode())
    
    def handle_register(self):
        """Handle user registration"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirmPassword')
        
        # Validation
        if not name or not email or not password or not confirm_password:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "All fields are required"}).encode())
            return
        
        if password != confirm_password:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Passwords do not match"}).encode())
            return
        
        if len(password) < 8:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Password must be at least 8 characters"}).encode())
            return
        
        # Create user
        result = db.create_user(name, email, password)
        if result:
            user_id, verification_token = result
            # Send verification email
            email_sent = send_verification_email(email, name, verification_token)
            if email_sent:
                self.send_response(201)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "User created successfully. Please check your email to verify your account.",
                    "email_sent": True
                }).encode())
            else:
                self.send_response(201)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "User created successfully, but verification email could not be sent. Please contact support.",
                    "email_sent": False
                }).encode())
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Email already exists"}).encode())
    
    def handle_logout(self):
        """Handle user logout"""
        self.send_response(200)
        self.send_header('Set-Cookie', 'user_email=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.send_header('Set-Cookie', 'user_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Logged out successfully"}).encode())
    
    def handle_approve_cat(self, cat_id):
        """Handle approving a cat"""
        # Check authentication and admin status
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        # Update cat approval status
        db.update_cat_approval(cat_id, 1, 0)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Cat approved successfully"}).encode())
    
    def handle_reject_cat(self, cat_id):
        """Handle rejecting a cat"""
        # Check authentication and admin status
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        # Update cat approval status
        db.update_cat_approval(cat_id, 0, 1)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Cat rejected successfully"}).encode())

    def handle_restore_cat(self, cat_id):
        """Handle restoring a cat submission back to pending"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        db.update_cat_approval(cat_id, 0, 0)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Cat restored to pending review"}).encode())
    
    def handle_get_cats(self):
        """Handle getting all approved cats"""
        try:
            cats = db.get_all_cats()
            cats = [sanitize_cat_record(cat) for cat in cats]
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(cats).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_get_cats_admin(self):
        """Handle getting all cats for admin (including pending)"""
        # Check authentication and admin status
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        try:
            cats = db.get_all_cats_admin()
            for cat in cats:
                cat_id = cat.get('id')
                sanitized = sanitize_cat_record(cat)
                if sanitized is None:
                    continue
                if cat_id is not None:
                    sanitized['reference_count'] = db.count_reference_images(cat_id)
                sanitized['owner_name'] = cat.get('owner_name')
                sanitized['owner_email'] = cat.get('owner_email')
                cat.clear()
                cat.update(sanitized)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(cats).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_add_cat(self):
        """Handle adding a new cat"""
        # Check authentication
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return
        
        # Require verified email for uploading cats
        if not user.get('is_verified', False) and not user.get('is_admin', False):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Email not verified. Please verify your email to upload cats."}).encode())
            return
        
        # Parse form data (including files)
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': self.headers['Content-Type']}
        )
        
        # Extract form data
        name = form.getvalue('name')
        age = form.getvalue('age')
        gender = form.getvalue('gender')
        description = form.getvalue('description')
        
        if not name or not age or not gender:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Name, age, and gender are required"}).encode())
            return
        
        # Handle image upload
        image_path = None
        if 'image' in form:
            file_item = form['image']
            if file_item.filename:
                # Create uploads directory if it doesn't exist
                upload_dir = 'uploads'
                os.makedirs(upload_dir, exist_ok=True)
                
                # Generate unique filename
                filename = f"{int(time.time())}_{file_item.filename}"
                filepath = os.path.join(upload_dir, filename)
                
                # Save file
                with open(filepath, 'wb') as f:
                    f.write(file_item.file.read())
                
                image_path = filepath
        
        # Add cat to database (default to not approved)
        cat_id = db.add_cat(name, age, gender, description, image_path, user['id'])
        
        try:
            submitter_name = user.get('name') or user.get('email')
            subject = f"新的猫咪提交：{name}"
            html_body = f"""
                <p>提交人：{submitter_name} ({user.get('email')})</p>
                <p>猫咪名称：{name}</p>
                <p>年龄：{age or '未填写'}</p>
                <p>性别：{gender or '未填写'}</p>
                <p>描述：{description or '未填写'}</p>
                <p>请前往后台审核该猫咪。</p>
            """
            send_notification_email(subject, html_body)
        except Exception as notify_err:
            print(f"Notification error (cat submission): {notify_err}")

        self.send_response(201)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"id": cat_id, "message": "Cat added successfully, pending admin approval"}).encode())

    def handle_create_adoption_request(self, cat_id: int):
        """Handle user adoption request"""
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return

        cat = db.get_cat_by_id(cat_id)
        if not cat or not cat.get('is_approved'):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Cat not found or not available"}).encode())
            return

        content_length = int(self.headers.get('Content-Length', 0))
        payload = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        message = (data.get('message') or '').strip()
        contact_info = (data.get('contact_info') or '').strip()

        request_id = db.create_adoption_request(cat_id, user['id'], message or None, contact_info or None)
        if request_id is None:
            self.send_response(409)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "You already have a pending request for this cat"}).encode())
            return

        subject = f"新的领养申请：{cat.get('name')}"
        html_body = f"""
            <p>申请人：{user.get('name') or user.get('email')} ({user.get('email')})</p>
            <p>猫咪：{cat.get('name')} (ID: {cat_id})</p>
            <p>联系方式：{contact_info or '未提供'}</p>
            <p>申请留言：{message or '（无留言）'}</p>
            <p>请登录管理后台处理该申请。</p>
        """
        try:
            send_notification_email(subject, html_body)
        except Exception as notify_err:
            print(f"Notification error (adoption request): {notify_err}")

        self.send_response(201)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "id": request_id,
            "status": "pending",
            "message": "Adoption request submitted"
        }).encode())
    
    def handle_admin_create_cat_profile(self):
        """Create a new cat profile from the admin console."""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            content_length = 0

        if content_length <= 0:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Empty request body"}).encode())
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        name = (data.get('name') or '').strip()
        gender = (data.get('gender') or '').strip()
        age = (data.get('age') or '').strip()
        description = (data.get('description') or '').strip()

        if not name or not gender:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Name and gender are required"}).encode())
            return

        cat_id = db.add_cat(name, age, gender, description, None, user['id'])
        db.update_cat_approval(cat_id, 1, 0)

        profile_updates = {
            'sterilized': 1 if data.get('sterilized') else 0,
            'microchipped': 1 if data.get('microchipped') else 0,
            'special_notes': data.get('special_notes') or data.get('specialNotes') or '',
            'unique_markings': data.get('unique_markings') or data.get('uniqueMarkings') or '',
            'last_known_location': data.get('last_known_location') or data.get('lastKnownLocation') or '',
            'identification_code': data.get('identification_code') or data.get('identificationCode') or '',
        }
        sanitized_updates = {key: value for key, value in profile_updates.items() if value is not None}
        if sanitized_updates:
            db.update_cat_profile(cat_id, sanitized_updates)

        cat_profile = sanitize_cat_record(db.get_cat_by_id(cat_id)) or {}
        cat_profile['reference_count'] = 0

        self.send_response(201)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Cat profile created", "cat": cat_profile}).encode())

    def handle_upload_cat_reference_images(self, cat_id: int):
        """Upload reference images for a cat and compute embeddings/hashes."""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        cat = db.get_cat_by_id(cat_id)
        if not cat:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Cat not found"}).encode())
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers.get('Content-Type')}
        )

        if 'images' not in form:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "No images provided"}).encode())
            return

        file_items = form['images']
        if not isinstance(file_items, list):
            file_items = [file_items]

        if not file_items:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "No images provided"}).encode())
            return

        primary_index = -1
        primary_field = form.getvalue('primary_index')
        if primary_field is not None:
            try:
                primary_index = int(primary_field)
            except ValueError:
                primary_index = -1
        elif str(form.getvalue('set_primary', 'false')).lower() == 'true':
            primary_index = 0

        saved_references = []

        for index, file_item in enumerate(file_items):
            filename = getattr(file_item, 'filename', '')
            if not filename:
                continue
            file_bytes = file_item.file.read()
            if not file_bytes:
                continue

            try:
                embedding, hash_hex, hash_bits = cat_recognizer.compute_signature(file_bytes)
            except Exception as exc:  # pragma: no cover
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Failed to process image: {exc}"}).encode())
                return

            hash_length = int(hash_bits.size)
            storage_dir = os.path.join('uploads', 'cat_references', str(cat_id))
            stored_path = save_uploaded_file(storage_dir, filename, file_bytes)

            is_primary = index == primary_index and primary_index >= 0
            reference_id = db.add_cat_reference_image(
                cat_id=cat_id,
                image_path=stored_path,
                hash_hex=hash_hex,
                hash_length=hash_length,
                embedding_bytes=embedding_to_blob(embedding),
                is_primary=is_primary,
            )

            if is_primary:
                db.update_cat_profile(cat_id, {"image_path": stored_path})

            saved_references.append({
                "id": reference_id,
                "image_path": stored_path,
                "hash_length": hash_length,
                "is_primary": is_primary,
            })

        recompute_cat_signature(cat_id)
        references = db.get_cat_reference_images(cat_id)

        self.send_response(201)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "message": "Reference images uploaded",
            "references": references,
            "saved": saved_references
        }).encode())

    def handle_update_cat_admin(self, cat_id: int):
        """Update cat details from admin editor"""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            content_length = 0
        payload = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        allowed_fields = {
            "name", "age", "gender", "description", "special_notes",
            "unique_markings", "last_known_location", "sterilized",
            "microchipped", "is_adopted", "is_approved", "is_rejected"
        }
        bool_fields = {"sterilized", "microchipped", "is_adopted", "is_approved", "is_rejected"}
        updates = {}
        for field in allowed_fields:
            if field in data:
                value = data.get(field)
                if field in bool_fields:
                    updates[field] = 1 if value else 0
                else:
                    updates[field] = value

        if not updates:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "No valid fields to update"}).encode())
            return

        success = db.update_cat_profile(cat_id, updates)
        if not success:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Cat not found"}).encode())
            return

        cat = sanitize_cat_record(db.get_cat_by_id(cat_id))
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Cat updated", "cat": cat}).encode())

    def handle_regenerate_cat_hash(self, cat_id: int):
        """Regenerate aggregate hash by reprocessing images through current model"""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            content_length = 0
        payload = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        reference_ids = data.get('reference_ids')
        if reference_ids is not None:
            if not isinstance(reference_ids, list) or not all(isinstance(rid, int) for rid in reference_ids):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "reference_ids must be a list of integers"}).encode())
                return

        # Reprocess images through current model
        try:
            reprocessed_count = reprocess_reference_images(cat_id, reference_ids=reference_ids)
            if reprocessed_count == 0:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No reference images could be reprocessed"}).encode())
                return
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Failed to reprocess images: {exc}"}).encode())
            return

        # Recompute aggregated signature from the newly processed embeddings
        ids = reference_ids if reference_ids else None
        recompute_cat_signature(cat_id, reference_ids=ids)
        cat = sanitize_cat_record(db.get_cat_by_id(cat_id))

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "message": f"Hash regenerated ({reprocessed_count} images reprocessed)",
            "cat": cat,
            "reprocessed_count": reprocessed_count
        }).encode())

    def handle_reprocess_all_cats(self):
        """Reprocess all reference images for all cats through the current model"""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            # Get all cats
            cats = db.get_all_cats_admin()
            total_cats = 0
            total_images = 0
            failed_cats = []
            
            for cat in cats:
                cat_id = cat.get('id')
                if not cat_id:
                    continue
                
                try:
                    # Reprocess all reference images for this cat
                    reprocessed_count = reprocess_reference_images(cat_id, reference_ids=None)
                    if reprocessed_count > 0:
                        # Recompute aggregated signature
                        recompute_cat_signature(cat_id, reference_ids=None)
                        total_cats += 1
                        total_images += reprocessed_count
                except Exception as exc:
                    cat_name = cat.get('name', f'Cat {cat_id}')
                    failed_cats.append({"cat_id": cat_id, "name": cat_name, "error": str(exc)})
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": f"Reprocessing completed: {total_cats} cats, {total_images} images reprocessed",
                "total_cats": total_cats,
                "total_images": total_images,
                "failed_cats": failed_cats
            }).encode())
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Failed to reprocess all cats: {exc}"}).encode())

    def handle_get_cat_profiles_admin(self):
        """Return detailed cat profiles for the admin console."""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            cats = db.get_all_cats_admin()
            for cat in cats:
                cat_id = cat.get('id')
                sanitized = sanitize_cat_record(cat) or {}
                references = db.get_cat_reference_images(cat_id)
                sanitized['reference_images'] = references
                sanitized['reference_count'] = len(references)
                sanitized['owner_name'] = cat.get('owner_name')
                sanitized['owner_email'] = cat.get('owner_email')
                sanitized['hash_available'] = bool(cat.get('reference_hash_hex'))
                cat.clear()
                cat.update(sanitized)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(cats).encode())
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def handle_get_cat_profile_admin(self, cat_id: int):
        """Return a single cat profile with reference images."""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        cat = db.get_cat_by_id(cat_id)
        if not cat:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Cat not found"}).encode())
            return

        references = db.get_cat_reference_images(cat_id)
        sanitized = sanitize_cat_record(cat) or {}
        sanitized['reference_images'] = references
        sanitized['reference_count'] = len(references)
        sanitized['owner_name'] = cat.get('owner_name')
        sanitized['owner_email'] = cat.get('owner_email')
        sanitized['hash_available'] = bool(cat.get('reference_hash_hex'))

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(sanitized).encode())

    def handle_get_recognition_settings(self):
        """Return current recognition settings and simple stats."""
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return

        settings = get_recognition_settings()
        reference_records = db.list_reference_vectors()
        approved_reference_records = [
            record for record in reference_records
            if record.get('is_approved') and not record.get('is_rejected')
        ]
        cat_ids = {record['cat_id'] for record in approved_reference_records}
        settings.update({
            "reference_count": len(approved_reference_records),
            "cat_count": len(cat_ids),
            "device": str(cat_recognizer.device),
        })

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(settings).encode())

    def handle_update_recognition_settings(self):
        """Update recognition parameters (admin only)."""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            content_length = 0
        payload = self.rfile.read(content_length) if content_length else b''
        try:
            data = json.loads(payload.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        updates = {}
        errors = []

        if 'threshold' in data:
            try:
                threshold = float(data['threshold'])
                if not 0.0 < threshold < 1.0:
                    raise ValueError
                updates['cat_recognition.threshold'] = str(threshold)
            except (TypeError, ValueError):
                errors.append("threshold must be a float between 0 and 1")

        if 'max_results' in data:
            try:
                max_results = int(data['max_results'])
                if max_results <= 0:
                    raise ValueError
                updates['cat_recognition.max_results'] = str(max_results)
            except (TypeError, ValueError):
                errors.append("max_results must be a positive integer")

        if 'max_hamming' in data:
            value = data['max_hamming']
            if value in (None, '', 'null'):
                updates['cat_recognition.max_hamming'] = ''
            else:
                try:
                    max_hamming = int(value)
                    if max_hamming < 0:
                        raise ValueError
                    updates['cat_recognition.max_hamming'] = str(max_hamming)
                except (TypeError, ValueError):
                    errors.append("max_hamming must be a non-negative integer or blank")

        reset_recognizer = False

        if 'model_path' in data:
            model_path = (data['model_path'] or '').strip()
            updates['cat_recognition.model_path'] = model_path
            reset_recognizer = True

        if 'hash_length_override' in data:
            hash_length_value = (data['hash_length_override'] or '').strip()
            if hash_length_value == '':
                updates['cat_recognition.hash_length_override'] = ''
                reset_recognizer = True
            else:
                try:
                    override_int = int(hash_length_value)
                    if override_int <= 0:
                        raise ValueError
                    updates['cat_recognition.hash_length_override'] = str(override_int)
                    reset_recognizer = True
                except (TypeError, ValueError):
                    errors.append("hash_length_override must be a positive integer or blank")

        if errors:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"errors": errors}).encode())
            return

        for key, value in updates.items():
            db.set_setting(key, value)

        global cat_recognizer
        if reset_recognizer:
            cat_recognizer = create_cat_recognizer_from_settings()

        settings = get_recognition_settings()
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Recognition settings updated", "settings": settings}).encode())

    def handle_recognize_cat(self):
        """Match an uploaded cat photo against known cats."""
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers.get('Content-Type')}
        )

        if 'image' not in form:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Image file is required"}).encode())
            return

        file_item = form['image']
        if isinstance(file_item, list) and file_item:
            file_item = file_item[0]

        filename = getattr(file_item, 'filename', '') if file_item is not None else ''
        if not filename:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Image file is required"}).encode())
            return

        image_bytes = file_item.file.read()
        if not image_bytes:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Uploaded image is empty"}).encode())
            return

        try:
            embedding, hash_hex, hash_bits = cat_recognizer.compute_signature(image_bytes)
        except Exception as exc:  # pragma: no cover
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Failed to process image: {exc}"}).encode())
            return

        settings = get_recognition_settings()
        reference_records = db.list_reference_vectors()
        references = []
        reference_lookup = {}
        cat_ids = set()

        for record in reference_records:
            if not record.get('is_approved') or record.get('is_rejected'):
                continue
            hash_hex_ref = record.get('hash_hex')
            hash_length = record.get('hash_length')
            if not hash_hex_ref or not hash_length:
                continue
            ref_bits = hex_to_bits(hash_hex_ref, hash_length)
            embedding_blob = record.get('embedding_vector')
            ref_embedding = blob_to_embedding(embedding_blob) if embedding_blob else np.array([], dtype=np.float32)
            references.append((record['cat_id'], record['reference_id'], ref_bits, ref_embedding))
            reference_lookup[record['reference_id']] = record
            cat_ids.add(record['cat_id'])

        raw_matches = (
            cat_recognizer.match_against(
                query_hash=hash_bits,
                query_embedding=embedding,
                references=references,
                max_results=settings['max_results'],
                similarity_threshold=settings['threshold'],
                max_hamming=settings['max_hamming'],
            )
            if references
            else []
        )

        cat_cache = {}
        results_payload = []
        best_by_cat: Dict[str, Dict] = {}

        for result in raw_matches:
            cat_info = None
            if result.cat_id is not None:
                if result.cat_id not in cat_cache:
                    cat_cache[result.cat_id] = sanitize_cat_record(db.get_cat_by_id(result.cat_id))
                cat_info = cat_cache.get(result.cat_id)
            reference_meta = reference_lookup.get(result.reference_image_id or -1)
            payload_item = {
                "cat": cat_info,
                "similarity": result.similarity,
                "hamming_distance": result.hamming_distance,
                "matched": result.matched,
                "reference_image_id": result.reference_image_id,
                "reference_image_path": reference_meta.get('image_path') if reference_meta else None,
            }
            key = (
                f"cat:{result.cat_id}"
                if result.cat_id is not None
                else f"ref:{result.reference_image_id}"
            )
            existing = best_by_cat.get(key)
            if not existing or (
                payload_item["similarity"] > existing["similarity"]
                or (
                    payload_item["similarity"] == existing["similarity"]
                    and payload_item["hamming_distance"] < existing["hamming_distance"]
                )
            ):
                best_by_cat[key] = payload_item

        results_payload = sorted(
            best_by_cat.values(),
            key=lambda item: (-item["similarity"], item["hamming_distance"]),
        )

        confirmed_matches = [item for item in results_payload if item.get("matched")]
        top_suggestions = [] if confirmed_matches else results_payload[:1]

        save_query = str(form.getvalue('save_query', 'true')).lower() != 'false'
        query_image_path = None
        if save_query:
            query_image_path = save_uploaded_file('uploads/cat_queries', file_item.filename, image_bytes)

        top_match = next((match for match in raw_matches if match.matched), None)
        recognition_event_id = db.record_recognition_event(
            cat_id=top_match.cat_id if top_match else None,
            matched=bool(top_match),
            match_score=float(top_match.similarity) if top_match else 0.0,
            hash_distance=int(top_match.hamming_distance) if top_match else None,
            metadata={
                "threshold": settings['threshold'],
                "max_results": settings['max_results'],
                "references_considered": len(references),
                "matches_returned": len(raw_matches),
            },
            image_path=query_image_path,
        )

        response_payload = {
            "matches": confirmed_matches,
            "suggestions": top_suggestions,
            "settings": settings,
            "query_image_path": query_image_path,
            "hash_hex": hash_hex,
            "recognition_event_id": recognition_event_id,
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_payload).encode())

    def handle_get_reference_images(self):
        """Return cat reference image records."""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            limit_param = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('limit', [None])[0]
            limit = int(limit_param) if limit_param else None
        except ValueError:
            limit = None

        try:
            references = db.list_reference_images(limit)
            for ref in references:
                ref['is_primary'] = bool(ref.get('is_primary'))
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(references).encode())
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def handle_delete_reference_image(self, reference_id: int):
        """Delete a reference image"""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            deleted = db.delete_reference_image(reference_id)
            if deleted:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Reference image deleted"}).encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Reference image not found"}).encode())
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def handle_update_reference_image_order(self, cat_id: int):
        """Update the order of reference images for a cat"""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            content_length = 0
        payload = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        reference_orders = data.get('orders', [])
        if not isinstance(reference_orders, list):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "orders must be a list"}).encode())
            return

        try:
            success = db.update_reference_image_order(cat_id, reference_orders)
            if success:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Image order updated"}).encode())
            else:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Failed to update order"}).encode())
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def handle_move_reference_image(self, reference_id: int):
        """Move a reference image to a different cat"""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            content_length = 0
        payload = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        new_cat_id = data.get('new_cat_id')
        if not new_cat_id:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "new_cat_id is required"}).encode())
            return

        try:
            new_cat_id = int(new_cat_id)
            # Verify the target cat exists
            target_cat = db.get_cat_by_id(new_cat_id)
            if not target_cat:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Target cat not found"}).encode())
                return

            success = db.move_reference_image(reference_id, new_cat_id)
            if success:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Image moved successfully"}).encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Reference image not found"}).encode())
        except ValueError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid cat ID"}).encode())
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def handle_set_primary_reference_image(self, cat_id: int, reference_id: int):
        """Set a reference image as primary for a cat"""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            success = db.set_primary_reference_image(cat_id, reference_id)
            if success:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Primary image updated"}).encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Reference image not found"}).encode())
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def handle_get_recognition_events(self):
        """Return recognition event logs for admin."""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            limit_param = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('limit', [None])[0]
            limit = int(limit_param) if limit_param else 200
        except ValueError:
            limit = 200

        try:
            events = db.list_recognition_events(limit)
            for event in events:
                event['matched'] = bool(event.get('matched'))
                metadata = event.get('request_metadata')
                if isinstance(metadata, str):
                    try:
                        event['request_metadata'] = json.loads(metadata)
                    except json.JSONDecodeError:
                        pass
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(events).encode())
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def handle_get_current_user(self):
        """Handle getting current user info"""
        user = self.get_current_user()
        if user:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "id": user['id'],
                "name": user['name'],
                "email": user['email'],
                "is_admin": bool(user.get('is_admin', False)),
                "is_super_admin": bool(user.get('is_super_admin', False)),
                "is_verified": bool(user.get('is_verified', False))
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not authenticated"}).encode())
    
    def handle_get_users(self):
        """Handle getting all users (admin only)"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        try:
            users = db.get_all_users()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(users).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_get_adoption_requests(self):
        """Handle getting all adoption requests (admin only)"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        try:
            requests = db.get_all_adoption_requests()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(requests).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def handle_update_adoption_request_status(self, request_id: int):
        """Approve or reject an adoption request"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        content_length = int(self.headers.get('Content-Length', 0))
        payload = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        status = (data.get('status') or '').lower()
        if status not in ('pending', 'approved', 'rejected'):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid status"}).encode())
            return

        request_record = db.get_adoption_request_by_id(request_id)
        if not request_record:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Adoption request not found"}).encode())
            return

        updated = db.update_adoption_request_status(request_id, status)
        if not updated:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to update adoption request"}).encode())
            return

        if status == 'approved':
            db.set_cat_adoption_state(request_record['cat_id'], True)
        elif status == 'rejected':
            db.set_cat_adoption_state(request_record['cat_id'], False)

        adopter = db.get_user_by_id(request_record['user_id'])
        cat = db.get_cat_by_id(request_record['cat_id'])
        subject = f"领养申请更新：{cat.get('name')}"
        html_body = f"""
            <p>申请人：{adopter.get('name') or adopter.get('email')} ({adopter.get('email')})</p>
            <p>猫咪：{cat.get('name')} (ID: {cat.get('id')})</p>
            <p>新的状态：{status}</p>
            <p>处理人：{user.get('name')}</p>
        """
        try:
            send_notification_email(subject, html_body)
        except Exception as notify_err:
            print(f"Notification error (adoption status): {notify_err}")

        # Notify adopter via internal message
        message_subject = f"领养申请已更新：{cat.get('name')}"
        message_content = f"您的领养申请状态已更新为：{status}。如需了解详情，请联系管理员。"
        db.send_message(user['id'], adopter['id'], message_subject, message_content)

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Status updated", "status": status}).encode())
    
    def handle_send_message(self):
        """Handle sending a message"""
        # Check authentication
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        receiver_id = data.get('receiver_id')
        subject = data.get('subject')
        content = data.get('content')
        
        if not receiver_id or not subject or not content:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Receiver, subject, and content are required"}).encode())
            return
        
        # Send message
        message_id = db.send_message(user['id'], receiver_id, subject, content)
        
        self.send_response(201)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"id": message_id, "message": "Message sent successfully"}).encode())
    
    def handle_get_messages(self):
        """Handle getting user's inbox messages"""
        # Check authentication
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return
        
        try:
            messages = db.get_user_messages(user['id'])
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(messages).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def handle_mark_message_read(self, message_id: int):
        """Mark a message as read for the current user"""
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return

        success = db.mark_message_as_read_for_user(message_id, user['id'])
        if success:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Message marked as read"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Message not found"}).encode())
    
    def handle_get_sent_messages(self):
        """Handle getting user's sent messages"""
        # Check authentication
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return
        
        try:
            messages = db.get_user_sent_messages(user['id'])
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(messages).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_get_message_recipients(self):
        """Return list of available message recipients based on user role"""
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return

        is_admin = bool(user.get('is_admin'))
        recipients = []
        if is_admin:
            recipients = [
                {"id": u['id'], "name": u['name'], "email": u['email'], "is_admin": bool(u.get('is_admin'))}
                for u in db.get_all_users()
                if u['id'] != user['id']
            ]
        else:
            recipients = [
                {"id": u['id'], "name": u['name'], "email": u['email'], "is_admin": True}
                for u in db.get_admin_users()
            ]

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "recipients": recipients,
            "is_admin": is_admin
        }).encode())

    def handle_broadcast_message(self):
        """Send a broadcast message from admin to multiple users"""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        content_length = int(self.headers.get('Content-Length', 0))
        payload = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        subject = (data.get('subject') or '').strip()
        content = (data.get('content') or '').strip()
        include_admins = bool(data.get('include_admins'))

        if not subject or not content:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Subject and content are required"}).encode())
            return

        recipients = db.get_all_users()
        targets = [
            r for r in recipients
            if r['id'] != user['id'] and (include_admins or not r.get('is_admin'))
        ]

        for recipient in targets:
            db.send_message(user['id'], recipient['id'], subject, content)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"message": f"Broadcast sent to {len(targets)} recipients"}).encode())
    
    def handle_get_content(self, content_id):
        """Handle getting specific content by ID"""
        try:
            content = db.get_content(content_id)
            if content:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(content).encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Content not found"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_get_all_content(self):
        """Handle getting all content"""
        # Check authentication and admin status
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        try:
            contents = db.get_all_content()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(contents).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_update_content(self, content_id):
        """Handle updating content by ID"""
        # Check authentication and admin status
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        title = data.get('title')
        content_text = data.get('content')
        
        if not title or not content_text:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Title and content are required"}).encode())
            return
        
        try:
            db.update_content(content_id, title, content_text)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Content updated successfully"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_logout(self):
        """Handle user logout"""
        self.send_response(200)
        self.send_header('Set-Cookie', 'user_email=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.send_header('Set-Cookie', 'user_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Logged out successfully"}).encode())
    
    def handle_verify_email_get(self):
        """Handle GET request for email verification page"""
        query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        token = query_params.get('token', [None])[0]
        
        if not token:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>Invalid verification link</h1>")
            return
        
        # Verify the token
        success = db.verify_user_email(token)
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        if success:
            html = """
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>邮箱验证成功</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .success { color: #4CAF50; font-size: 24px; margin: 20px 0; }
                    a { color: #4CAF50; text-decoration: none; }
                </style>
            </head>
            <body>
                <h1 class="success">✓ 邮箱验证成功！</h1>
                <p>您的邮箱地址已成功验证。现在您可以登录您的账户了。</p>
                <p><a href="/">返回首页</a></p>
            </body>
            </html>
            """
        else:
            html = """
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>邮箱验证失败</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .error { color: #dc3545; font-size: 24px; margin: 20px 0; }
                    a { color: #4CAF50; text-decoration: none; }
                </style>
            </head>
            <body>
                <h1 class="error">✗ 邮箱验证失败</h1>
                <p>验证链接无效或已过期。请重新注册或联系支持。</p>
                <p><a href="/">返回首页</a></p>
            </body>
            </html>
            """
        self.wfile.write(html.encode())
    
    def handle_verify_email_post(self):
        """Handle POST request for API email verification"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        token = data.get('token')
        if not token:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Token required"}).encode())
            return
        
        success = db.verify_user_email(token)
        if success:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Email verified successfully"}).encode())
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid or expired token"}).encode())
    
    def handle_get_resend_api_key(self):
        """Get Resend API key (admin only)"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        api_key = db.get_setting('resend_api_key')
        # Return masked version for security (only show last 4 characters)
        masked_key = None
        if api_key:
            masked_key = '*' * (len(api_key) - 4) + api_key[-4:] if len(api_key) > 4 else '****'
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"api_key": masked_key, "is_configured": api_key is not None}).encode())
    
    def handle_update_resend_api_key(self):
        """Update Resend API key (admin only)"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        api_key = data.get('api_key', '').strip()
        if not api_key:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "API key is required"}).encode())
            return
        
        try:
            db.set_setting('resend_api_key', api_key)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Resend API key updated successfully"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_get_resend_from_email(self):
        """Get Resend from email address (admin only)"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        from_email = db.get_setting('resend_from_email') or "noreply@resend.dev"
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"from_email": from_email}).encode())
    
    def handle_update_resend_from_email(self):
        """Update Resend from email address (admin only)"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        from_email = data.get('from_email', '').strip()
        if not from_email:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "From email address is required"}).encode())
            return
        
        # Basic email validation
        if '@' not in from_email:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid email address format"}).encode())
            return
        
        try:
            db.set_setting('resend_from_email', from_email)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"message": "From email address updated successfully"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def handle_get_notification_emails(self):
        """Return configured notification recipients"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        recipients = db.get_notification_recipients()
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"emails": recipients}).encode())

    def handle_update_notification_emails(self):
        """Update notification recipient emails"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        content_length = int(self.headers.get('Content-Length', 0))
        payload = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        raw_emails = data.get('emails')
        if isinstance(raw_emails, list):
            emails = [email.strip() for email in raw_emails if email and isinstance(email, str)]
            value = ','.join(emails)
        else:
            value = (raw_emails or '').strip()

        db.set_setting('notification.emails', value)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Notification recipients updated"}).encode())

    def handle_get_notification_from_email(self):
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        from_email = db.get_notification_from_email()
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"from_email": from_email}).encode())

    def handle_update_notification_from_email(self):
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        content_length = int(self.headers.get('Content-Length', 0))
        payload = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        from_email = (data.get('from_email') or '').strip()
        if not from_email:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Notification from email is required"}).encode())
            return

        db.set_setting('notification.from_email', from_email)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Notification from email updated"}).encode())
    
    def handle_get_base_url(self):
        """Get the base website URL (admin only)"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        base_url = db.get_setting('base_url') or ''
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"base_url": base_url}).encode())
    
    def handle_update_base_url(self):
        """Update the base website URL (admin only)"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        base_url = data.get('base_url', '').strip()
        if not base_url:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Base URL is required"}).encode())
            return
        
        # Basic validation to ensure it resembles a URL
        if not base_url.startswith('http://') and not base_url.startswith('https://'):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Base URL must start with http:// or https://"}).encode())
            return
        
        try:
            db.set_setting('base_url', base_url.rstrip('/'))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Base URL updated successfully"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_update_user_verification(self, user_id):
        """Update user verification status (admin only)"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        is_verified = data.get('is_verified', False)
        
        try:
            success = db.update_user_verification_status(user_id, is_verified)
            if success:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"message": "User verification status updated successfully"}).encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "User not found"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_delete_user(self, user_id):
        """Delete a user account (admin only)"""
        user = self.get_current_user()
        if not user or not user['is_admin']:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return
        
        # Consume request body if present
        content_length = int(self.headers.get('Content-Length', 0) or 0)
        if content_length:
            self.rfile.read(content_length)
        
        # Prevent deleting admin accounts
        target_user = db.get_user_by_id(user_id)
        if not target_user:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "User not found"}).encode())
            return
        
        if target_user.get('is_admin'):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Cannot delete administrator accounts"}).encode())
            return
        
        try:
            success = db.delete_user(user_id)
            if success:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"message": "User deleted successfully"}).encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "User not found or could not be deleted"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_set_user_admin(self, user_id):
        """Set user as admin (super admin only)"""
        user = self.get_current_user()
        if not user or not (user.get('is_super_admin') or user.get('is_super_admin') == 1):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Super admin access required"}).encode())
            return
        
        # Consume request body if present
        content_length = int(self.headers.get('Content-Length', 0) or 0)
        if content_length:
            self.rfile.read(content_length)
        
        # Check if target user exists
        target_user = db.get_user_by_id(user_id)
        if not target_user:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "User not found"}).encode())
            return
        
        # Prevent setting self as admin (redundant but safe)
        if target_user.get('is_admin'):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "User is already an administrator"}).encode())
            return
        
        try:
            success = db.update_user_admin_status(user_id, True)
            if success:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"message": "User has been set as administrator successfully"}).encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "User not found or could not be updated"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_admin_login_with_token(self, token):
        """Authenticate admin using a single-use token and set as super admin"""
        try:
            user_id = db.validate_and_use_admin_token(token)
            
            if user_id:
                user = db.get_user_by_id(user_id)
                if user:
                    # Set user as super admin when logging in via token
                    db.update_user_super_admin_status(user_id, True)
                    # Also ensure they are admin
                    if not user.get('is_admin'):
                        db.update_user_admin_status(user_id, True)
                    
                    # Refresh user data
                    user = db.get_user_by_id(user_id)
                    
                    # Create auth token
                    auth_token = hashlib.sha256(f"{user['email']}{user['password_hash']}".encode()).hexdigest()
                    
                    # Set cookies with 24-day expiration
                    self.send_response(200)
                    self.send_header('Set-Cookie', f"user_email={user['email']}; Path=/; Max-Age=2073600")
                    self.send_header('Set-Cookie', f"user_token={auth_token}; Path=/; Max-Age=2073600")
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {
                        "id": user['id'],
                        "name": user['name'],
                        "email": user['email'],
                        "is_admin": True,
                        "is_super_admin": True,
                        "is_verified": bool(user.get('is_verified', False)),
                        "message": "Super admin login successful"
                    }
                    self.wfile.write(json.dumps(response).encode())
                else:
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Invalid admin token"}).encode())
            else:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid or expired token"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_change_password(self):
        """Handle user password change"""
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not current_password or not new_password or not confirm_password:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "All password fields are required"}).encode())
            return
        
        # Verify current password
        current_password_hash = hashlib.sha256(current_password.encode()).hexdigest()
        if user['password_hash'] != current_password_hash:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Current password is incorrect"}).encode())
            return
        
        # Validate new password
        if new_password != confirm_password:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "New passwords do not match"}).encode())
            return
        
        if len(new_password) < 8:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Password must be at least 8 characters"}).encode())
            return
        
        # Update password
        new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        success = db.update_user_password(user['id'], new_password_hash)
        
        if success:
            # Invalidate current session token since password changed
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Password updated successfully. Please login again."}).encode())
        else:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to update password"}).encode())
    
    def handle_update_user_profile(self):
        """Handle user profile update"""
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        name = data.get('name')
        email = data.get('email')
        
        if not name and not email:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "At least one field (name or email) is required"}).encode())
            return
        
        # If email is being changed, validate it
        if email and email != user['email']:
            # Check if email already exists
            existing_user = db.get_user_by_email(email)
            if existing_user and existing_user['id'] != user['id']:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Email already in use"}).encode())
                return
        
        # Update profile
        success = db.update_user_profile(user['id'], name=name, email=email)
        
        if success:
            # Get updated user
            updated_user = db.get_user_by_id(user['id'])
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "Profile updated successfully",
                "user": {
                    "id": updated_user['id'],
                    "name": updated_user['name'],
                    "email": updated_user['email']
                }
            }).encode())
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to update profile. Email may already be in use."}).encode())
    
    def handle_forgot_password(self):
        """Handle forgot password request - sends verification code to email"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        email = data.get('email')
        
        if not email:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Email is required"}).encode())
            return
        
        # Find user by email
        user = db.get_user_by_email(email)
        
        # Always return success to prevent email enumeration
        # But only send email if user exists
        if user:
            # Create password reset token
            token, code = db.create_password_reset_token(user['id'], expires_in_hours=1)
            
            # Send email with verification code
            email_sent = send_password_reset_email(email, user['name'], code)
            
            if email_sent:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "If an account exists with this email, a verification code has been sent.",
                    "email_sent": True
                }).encode())
            else:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Failed to send email. Please try again later.",
                    "email_sent": False
                }).encode())

    def handle_add_location(self):
        """Handle adding a location record for a cat"""
        user = self.get_current_user()
        if not user:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            content_length = 0
        payload = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode())
            return

        cat_id = data.get('cat_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        visit_status = data.get('visit_status')
        visit_notes = data.get('visit_notes')
        recognition_event_id = data.get('recognition_event_id')
        image_path = data.get('image_path')

        if not cat_id or latitude is None or longitude is None:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "cat_id, latitude, and longitude are required"}).encode())
            return

        try:
            cat_id = int(cat_id)
            latitude = float(latitude)
            longitude = float(longitude)
            if recognition_event_id is not None:
                recognition_event_id = int(recognition_event_id)
        except (ValueError, TypeError):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid data types"}).encode())
            return

        # Validate year range (1999-3000)
        import datetime
        current_year = datetime.datetime.now().year
        if not (1999 <= current_year <= 3000):
            # This is just a sanity check, actual validation happens at query time
            pass

        try:
            location_id = db.add_location_history(
                cat_id=cat_id,
                user_id=user['id'],
                latitude=latitude,
                longitude=longitude,
                visit_status=visit_status,
                visit_notes=visit_notes,
                recognition_event_id=recognition_event_id,
                image_path=image_path,
            )
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "Location recorded successfully",
                "location_id": location_id
            }).encode())
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Failed to record location: {str(exc)}"}).encode())

    def handle_get_location_history(self):
        """Get location history records (admin only)"""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            start_year = query_params.get('start_year', [None])[0]
            end_year = query_params.get('end_year', [None])[0]
            cat_id = query_params.get('cat_id', [None])[0]

            start_year = int(start_year) if start_year else None
            end_year = int(end_year) if end_year else None
            cat_id = int(cat_id) if cat_id else None

            # Validate year range (1999-3000)
            if start_year is not None and not (1999 <= start_year <= 3000):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "start_year must be between 1999 and 3000"}).encode())
                return

            if end_year is not None and not (1999 <= end_year <= 3000):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "end_year must be between 1999 and 3000"}).encode())
                return

            locations = db.get_location_history(
                start_year=start_year,
                end_year=end_year,
                cat_id=cat_id,
            )

            # Ensure locations is a list
            if not isinstance(locations, list):
                locations = []

            # Convert boolean values and ensure all fields are properly serialized
            for loc in locations:
                if 'visit_status' in loc and loc['visit_status'] is None:
                    loc['visit_status'] = None
                # Ensure numeric fields are properly converted
                if 'latitude' in loc:
                    loc['latitude'] = float(loc['latitude']) if loc['latitude'] is not None else None
                if 'longitude' in loc:
                    loc['longitude'] = float(loc['longitude']) if loc['longitude'] is not None else None

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(locations, ensure_ascii=False).encode())
        except ValueError as ve:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid query parameters: {str(ve)}"}).encode())
        except Exception as exc:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error in handle_get_location_history: {error_trace}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Internal server error: {str(exc)}"}).encode())

    def handle_get_location_by_id(self, location_id: int):
        """Get a single location record by ID (admin only)"""
        user = self.get_current_user()
        if not user or not user.get('is_admin'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Admin access required"}).encode())
            return

        try:
            location = db.get_location_by_id(location_id)
            if not location:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Location not found"}).encode())
                return

            # Convert boolean values
            if 'sterilized' in location:
                location['sterilized'] = bool(location.get('sterilized'))
            if 'microchipped' in location:
                location['microchipped'] = bool(location.get('microchipped'))
            
            # Ensure numeric fields are properly converted
            if 'latitude' in location:
                location['latitude'] = float(location['latitude']) if location['latitude'] is not None else None
            if 'longitude' in location:
                location['longitude'] = float(location['longitude']) if location['longitude'] is not None else None

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(location, ensure_ascii=False).encode())
        except Exception as exc:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error in handle_get_location_by_id: {error_trace}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Internal server error: {str(exc)}"}, ensure_ascii=False).encode())
    
    def handle_verify_reset_code(self):
        """Verify password reset code"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        email = data.get('email')
        code = data.get('code')
        
        if not email or not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Email and verification code are required"}).encode())
            return
        
        # Validate code
        user_id, token = db.validate_password_reset_code(email, code)
        
        if user_id and token:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "Verification code is valid",
                "token": token,  # Return token for password reset
                "valid": True
            }).encode())
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Invalid or expired verification code",
                "valid": False
            }).encode())
    
    def handle_reset_password(self):
        """Reset password using verification code"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        email = data.get('email')
        code = data.get('code')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not email or not code or not new_password:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Email, verification code, and new password are required"}).encode())
            return
        
        if new_password != confirm_password:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "New passwords do not match"}).encode())
            return
        
        if len(new_password) < 8:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Password must be at least 8 characters"}).encode())
            return
        
        # Validate code and get token
        user_id, token = db.validate_password_reset_code(email, code)
        
        if not user_id or not token:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid or expired verification code"}).encode())
            return
        
        # Update password
        new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        success = db.update_user_password(user_id, new_password_hash)
        
        if success:
            # Mark token as used
            db.use_password_reset_token(token)
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "Password reset successfully. Please login with your new password."
            }).encode())
        else:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to reset password"}).encode())
    
    def guess_type(self, path):
        # 使用mimetypes模块猜测MIME类型
        mimetype, _ = mimetypes.guess_type(path)
        if mimetype is None:
            mimetype = 'application/octet-stream'
        return mimetype

# 设置当前工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Generate super admin login link on startup
def generate_startup_admin_login_link():
    """Generate and display super admin login link on server startup"""
    try:
        # Find first super admin user
        super_admin_user = None
        users = db.get_all_users()
        for user in users:
            # Check if user is super admin (handle both boolean and integer)
            is_super_admin = user.get('is_super_admin')
            if is_super_admin or is_super_admin == 1:
                # Get full user data by ID
                super_admin_user = db.get_user_by_id(user['id'])
                break
        
        # If not found, try by default admin email
        if not super_admin_user:
            super_admin_user = db.get_user_by_email('admin@cats.com')
            # If found but not super admin, make them super admin
            if super_admin_user and not (super_admin_user.get('is_super_admin') or super_admin_user.get('is_super_admin') == 1):
                db.update_user_super_admin_status(super_admin_user['id'], True)
                super_admin_user = db.get_user_by_id(super_admin_user['id'])
        
        # If still not found, find any admin and make them super admin
        if not super_admin_user:
            users = db.get_all_users()
            for user in users:
                is_admin = user.get('is_admin')
                if is_admin or is_admin == 1:
                    super_admin_user = db.get_user_by_id(user['id'])
                    db.update_user_super_admin_status(super_admin_user['id'], True)
                    super_admin_user = db.get_user_by_id(super_admin_user['id'])
                    break
        
        if not super_admin_user:
            print("\n⚠️  警告: 未找到超级管理员账户")
            print("   服务器将无法使用超级管理员功能")
            return
        
        # Generate admin login token (expires in 24 hours)
        token = db.create_admin_login_token(super_admin_user['id'], expires_in_hours=24)
        
        # Get base URL from settings or use default
        base_url = db.get_setting('base_url') or f"http://{HOST}:{PORT}"
        login_url = f"{base_url}/api/admin/login?token={token}"
        
        # Display super admin login link in console
        print("\n" + "="*80)
        print("🔐 超级管理员登录链接 (Super Admin Login Link)")
        print("="*80)
        print(f"\n👤 超级管理员账户 (Super Admin User): {super_admin_user['name']} ({super_admin_user['email']})")
        print(f"⏰ 有效期 (Expires): 24小时 (24 hours)")
        print(f"\n📋 登录链接 (Login Link):")
        print("-"*80)
        print(login_url)
        print("-"*80)
        print("\n💡 提示: 此链接只能使用一次，使用后立即失效。通过此链接登录的用户将被设置为超级管理员")
        print("   Note: This link is single-use and will expire after first use. Users logging in via this link will be set as super admin")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n⚠️  警告: 生成超级管理员登录链接时出错: {str(e)}")
        print("   Warning: Error generating super admin login link:", str(e))

# Generate admin login link on startup
generate_startup_admin_login_link()

# 启动服务器
with socketserver.TCPServer((HOST, PORT), CustomHTTPRequestHandler) as httpd:
    print(f"流浪猫公益项目服务器运行在 http://{HOST}:{PORT}/")
    print("按 Ctrl+C 停止服务器")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
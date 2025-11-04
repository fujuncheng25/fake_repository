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

PORT = 40276
HOST = "0.0.0.0"
DB_PATH = "data/cats.db"

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the database with tables"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create cats table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age TEXT NOT NULL,
                gender TEXT NOT NULL,
                description TEXT,
                image_path TEXT,
                owner_id INTEGER,
                is_approved BOOLEAN DEFAULT 0,
                is_adopted BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create adoption_requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS adoption_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat_id INTEGER,
                user_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cat_id) REFERENCES cats (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create messages table for user communication
        cursor.execute('''
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
        ''')
        
        # Create content table for editable text
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default content if not exists
        cursor.execute("SELECT COUNT(*) FROM content WHERE id = 'home_intro'")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO content (id, title, content) 
                VALUES ('home_intro', '欢迎来到流浪猫公益项目', '我们致力于救助和照顾流浪猫，为它们寻找温暖的家。通过我们的平台，您可以了解待领养的猫咪信息，也可以申请成为志愿者或爱心家庭。')
            ''')
        
        cursor.execute("SELECT COUNT(*) FROM content WHERE id = 'about_mission'")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO content (id, title, content) 
                VALUES ('about_mission', '我们的使命', '流浪猫公益项目成立于2020年，由一群热爱动物的志愿者发起。我们致力于救助城市中的流浪猫，为它们提供医疗护理、食物和庇护所，并努力为它们寻找永久的爱心家庭。')
            ''')
        
        # Check if admin user exists, if not create one
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        if cursor.fetchone()[0] == 0:
            # Create default admin user (admin@cats.com / password: admin123)
            password_hash = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (name, email, password_hash, is_admin)
                VALUES (?, ?, ?, 1)
            ''', ("Admin User", "admin@cats.com", password_hash))
        
        conn.commit()
        conn.close()
    
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
        """Get all cats (including pending) for admin view"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cats ORDER BY created_at DESC")
        cats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return cats
    
    def update_cat_approval(self, cat_id, is_approved):
        """Update cat approval status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE cats 
            SET is_approved = ?
            WHERE id = ?
        ''', (is_approved, cat_id))
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
    
    def create_user(self, name, email, password):
        """Create a new user"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (name, email, password_hash)
                VALUES (?, ?, ?)
            ''', (name, email, password_hash))
            user_id = cursor.lastrowid
            conn.commit()
            result = user_id
        except sqlite3.IntegrityError:
            result = None
        conn.close()
        return result
    
    def get_all_users(self):
        """Get all users (for admin)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, is_admin, created_at FROM users ORDER BY created_at DESC")
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
                ar.created_at,
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

# Initialize database
db = DatabaseManager(DB_PATH)

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
        elif self.path == '/api/logout':
            self.handle_logout()
        elif self.path.startswith('/api/cats/'):
            # Handle cat approval/rejection
            path_parts = self.path.split('/')
            if len(path_parts) == 4 and path_parts[3] == 'approve':
                cat_id = int(path_parts[2])
                self.handle_approve_cat(cat_id)
            elif len(path_parts) == 4 and path_parts[3] == 'reject':
                cat_id = int(path_parts[2])
                self.handle_reject_cat(cat_id)
            else:
                self.send_response(404)
                self.end_headers()
        elif self.path == '/api/messages':
            self.handle_send_message()
        elif self.path.startswith('/api/content/'):
            # Handle content update
            content_id = self.path.split('/')[-1]
            self.handle_update_content(content_id)
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
            else:
                self.send_response(404)
                self.end_headers()
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
            elif path == '/content-management':
                self.path = '/content-management.html'
            
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
        if user and user['password_hash'] == hashlib.sha256(password.encode()).hexdigest():
            # Create auth token
            token = hashlib.sha256(f"{email}{user['password_hash']}".encode()).hexdigest()
            
            # Set cookies
            self.send_response(200)
            self.send_header('Set-Cookie', f"user_email={email}; Path=/")
            self.send_header('Set-Cookie', f"user_token={token}; Path=/")
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                "id": user['id'],
                "name": user['name'],
                "email": user['email'],
                "is_admin": bool(user['is_admin'])
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
        user_id = db.create_user(name, email, password)
        if user_id:
            self.send_response(201)
            self.end_headers()
            self.wfile.write(json.dumps({"message": "User created successfully"}).encode())
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
        db.update_cat_approval(cat_id, 1)
        
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
        db.update_cat_approval(cat_id, 0)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Cat rejected successfully"}).encode())
    
    def handle_get_cats(self):
        """Handle getting all approved cats"""
        try:
            cats = db.get_all_cats()
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
        
        self.send_response(201)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"id": cat_id, "message": "Cat added successfully, pending admin approval"}).encode())
    
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
                "is_admin": bool(user['is_admin'])
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
    
    def guess_type(self, path):
        # 使用mimetypes模块猜测MIME类型
        mimetype, _ = mimetypes.guess_type(path)
        if mimetype is None:
            mimetype = 'application/octet-stream'
        return mimetype

# 设置当前工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 启动服务器
with socketserver.TCPServer((HOST, PORT), CustomHTTPRequestHandler) as httpd:
    print(f"流浪猫公益项目服务器运行在 http://{HOST}:{PORT}/")
    print("按 Ctrl+C 停止服务器")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
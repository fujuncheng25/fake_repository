#!/usr/bin/env python3

import sqlite3
import hashlib

# Connect to database
conn = sqlite3.connect('data/cats.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check user
email = "test@example.com"
cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
user = cursor.fetchone()

if user:
    print("User found:")
    print(f"Email: {user['email']}")
    print(f"Password hash in DB: {user['password_hash']}")
    print(f"Is Admin: {bool(user['is_admin'])}")
    
    # Check password hash
    password = "admin123"
    computed_hash = hashlib.sha256(password.encode()).hexdigest()
    print(f"Computed hash for '{password}': {computed_hash}")
    print(f"Hashes match: {user['password_hash'] == computed_hash}")
else:
    print("User not found")

# Check admin user
email = "admin@cats.com"
cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
user = cursor.fetchone()

if user:
    print("\nAdmin user found:")
    print(f"Email: {user['email']}")
    print(f"Password hash in DB: {user['password_hash']}")
    print(f"Is Admin: {bool(user['is_admin'])}")
    
    # Check password hash
    password = "admin123"
    computed_hash = hashlib.sha256(password.encode()).hexdigest()
    print(f"Computed hash for '{password}': {computed_hash}")
    print(f"Hashes match: {user['password_hash'] == computed_hash}")
else:
    print("Admin user not found")

conn.close()
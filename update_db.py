import sqlite3

conn = sqlite3.connect("books.db")
cursor = conn.cursor()

# Add price column
try:
    cursor.execute("ALTER TABLE books ADD COLUMN price REAL")
except:
    print("price column already exists")

# Create users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    password TEXT,
    role TEXT
)
""")

# Create issued_books table
cursor.execute("""
CREATE TABLE IF NOT EXISTS issued_books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    isbn TEXT,
    issue_date TEXT
)
""")

# Create purchases table
cursor.execute("""
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    isbn TEXT,
    price REAL,
    purchase_date TEXT
)
""")

conn.commit()
conn.close()

print("Database updated successfully!")
import sqlite3

conn = sqlite3.connect("books.db")
cursor = conn.cursor()

# Add due_date and fine_paid to issued_books
try:
    cursor.execute("ALTER TABLE issued_books ADD COLUMN due_date TEXT")
    print("Added due_date to issued_books")
except:
    print("due_date already exists")

try:
    cursor.execute("ALTER TABLE issued_books ADD COLUMN fine_paid REAL DEFAULT 0")
    print("Added fine_paid to issued_books")
except:
    print("fine_paid already exists")

# Add email to users
try:
    cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
    print("Added email to users")
except:
    print("email already exists")

conn.commit()
conn.close()
print("Migration complete!")

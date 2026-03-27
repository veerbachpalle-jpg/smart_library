import sqlite3

conn = sqlite3.connect("books.db")
cursor = conn.cursor()

cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
cursor.execute("INSERT INTO users (username, password, role) VALUES ('student', 'student123', 'student')")

conn.commit()
conn.close()

print("Users added!")
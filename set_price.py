import sqlite3
import random

conn = sqlite3.connect("books.db")
cursor = conn.cursor()

# Add random price (100–1000)
cursor.execute("UPDATE books SET price = ABS(RANDOM() % 900) + 100")

conn.commit()
conn.close()

print("Prices added!")
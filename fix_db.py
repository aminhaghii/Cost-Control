import sqlite3
import os

db_path = os.path.join('database', 'inventory.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Adding 'supplier' column to 'transactions' table...")
    cursor.execute("ALTER TABLE transactions ADD COLUMN supplier VARCHAR(100)")
    conn.commit()
    print("Successfully added 'supplier' column.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column 'supplier' already exists.")
    else:
        print(f"Error adding column: {e}")
finally:
    conn.close()

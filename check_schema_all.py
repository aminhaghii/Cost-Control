import sqlite3
import os

db_path = os.path.join('database', 'inventory.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def check_table(table_name):
    print(f"\nChecking table '{table_name}'...")
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    if not cursor.fetchone():
        print(f"Table '{table_name}' does NOT exist!")
        return False
    
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cursor.fetchall()]
    print(f"Columns in {table_name}:")
    for col in columns:
        print(f" - {col}")
    return True

tables_to_check = ['transactions', 'warehouse_settings', 'items', 'users', 'hotels', 'alerts']
for table in tables_to_check:
    check_table(table)

conn.close()

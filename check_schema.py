import sqlite3
import os

db_path = os.path.join('database', 'inventory.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(transactions)")
columns = [info[1] for info in cursor.fetchall()]

print("Columns in transactions table:")
for col in columns:
    print(f" - {col}")

all_expected_columns = [
    'id', 'transaction_date', 'item_id', 'transaction_type', 'category', 'hotel_id',
    'quantity', 'unit_price', 'total_amount', 'description', 'user_id', 'direction',
    'signed_quantity', 'is_opening_balance', 'source', 'import_batch_id', 'unit',
    'conversion_factor_to_base', 'is_deleted', 'deleted_at', 'waste_reason',
    'waste_reason_detail', 'reference_number', 'supplier', 'destination_department',
    'requires_approval', 'approved_by_id', 'approved_at', 'approval_status',
    'price_was_overridden', 'price_override_reason', 'created_at', 'updated_at'
]

missing_columns = [col for col in all_expected_columns if col not in columns]

if missing_columns:
    print("\nMissing columns:")
    for col in missing_columns:
        print(f" - {col}")
else:
    print("\nNo columns are missing.")

conn.close()

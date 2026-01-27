# Scripts Directory

This folder contains utility scripts for database migrations, setup, and maintenance.

## Migration Scripts

- `migrate_hotels.py` - Hotel data migration
- `migrate_new_changes.py` - General schema updates
- `migrate_p0_changes.py` - Priority 0 fixes migration
- `migrate_security.py` - Security-related migrations
- `create_login_attempts_table.py` - Create login_attempts table (FIX #3)
- `add_unit_price_column.py` - Add unit_price to items table

## Setup Scripts

- `init_db.py` - Initialize database with default data
- `download_assets.py` - Download static assets (fonts, icons)

## Utility Scripts

- `Delete_data.py` - Database cleanup utility
- `verify_approval_fix.py` - Verification script for approval workflow

## Usage

Run scripts from the project root:

```bash
python scripts/script_name.py
```

**Note:** Always backup your database before running migration scripts.

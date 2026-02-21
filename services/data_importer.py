#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Data Importer Service
Import inventory data from Excel files into the system
With P0-2: Import idempotency and auditing via ImportBatch
"""

import os
import re
import hashlib
import json
import logging
from datetime import datetime, date
from decimal import Decimal
from utils.timezone import get_iran_today
import pandas as pd
from sqlalchemy import func
from models import db, Item, Transaction, ImportBatch

logger = logging.getLogger(__name__)


def compute_file_hash(file_path, timeout_seconds=30):
    """
    Compute SHA256 hash of file for idempotency check
    BUG-FIX #7: Add timeout to prevent hanging on large files
    """
    import signal
    import platform
    
    class TimeoutError(Exception):
        pass
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"File hash computation timed out after {timeout_seconds} seconds")
    
    # For Windows, signal.SIGALRM is not available, use threading instead
    if platform.system() == 'Windows':
        import threading
        
        result = {'hash': None, 'error': None}
        
        def compute_hash():
            try:
                sha256_hash = hashlib.sha256()
                file_size = os.path.getsize(file_path)
                chunk_size = 65536 if file_size > 100*1024*1024 else 4096
                
                with open(file_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(chunk_size), b""):
                        sha256_hash.update(byte_block)
                result['hash'] = sha256_hash.hexdigest()
            except Exception as e:
                result['error'] = e
        
        thread = threading.Thread(target=compute_hash)
        thread.daemon = True
        thread.start()
        thread.join(timeout_seconds)
        
        if thread.is_alive():
            raise ValueError(f"File is too large to process (timeout after {timeout_seconds}s)")
        
        if result['error']:
            raise result['error']
        
        return result['hash']
    else:
        # Unix/Linux: use signal.SIGALRM
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
            
            sha256_hash = hashlib.sha256()
            file_size = os.path.getsize(file_path)
            chunk_size = 65536 if file_size > 100*1024*1024 else 4096
            
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(chunk_size), b""):
                    sha256_hash.update(byte_block)
            
            signal.alarm(0)  # Cancel alarm
            return sha256_hash.hexdigest()
            
        except TimeoutError:
            signal.alarm(0)
            raise ValueError(f"File is too large to process (timeout after {timeout_seconds}s)")


def check_import_exists(file_hash):
    """
    P0-1 Fix: Check if file has an ACTIVE import batch
    Returns the active batch if exists, None otherwise
    BUG #2 FIX: Validate file_hash format to prevent SQL injection
    """
    # SHA256 hash must be exactly 64 hexadecimal characters
    if not re.match(r'^[a-f0-9]{64}$', file_hash):
        raise ValueError(f"Invalid file hash format: {file_hash}")
    
    return ImportBatch.query.filter_by(
        file_hash=file_hash, 
        is_active=True,
        status='completed'
    ).first()


def get_import_history(file_hash):
    """
    P0-1: Get all import batches for a file hash (for history display)
    """
    return ImportBatch.query.filter_by(file_hash=file_hash).order_by(
        ImportBatch.created_at.desc()
    ).all()


def clean_number_robust(value):
    """
    P0-5: Robust number cleaning for Persian/Arabic digits
    
    Examples:
        "۱۲۳,۴۵۶.۷۸" → 123456.78
        "1,234,567"   → 1234567.0
        "(500)"       → -500.0
        "۱۲۳/۴۵"      → 123.45
    """
    if value is None or value == '':
        return None
    
    if isinstance(value, (int, float)):
        return float(value)
    
    s = str(value).strip()
    
    # Handle Persian/Arabic digits
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    arabic_digits = '٠١٢٣٤٥٦٧٨٩'
    for i, (p, a) in enumerate(zip(persian_digits, arabic_digits)):
        s = s.replace(p, str(i)).replace(a, str(i))
    
    # Handle negative in parentheses
    is_negative = s.startswith('(') and s.endswith(')')
    if is_negative:
        s = s[1:-1]
    
    # Handle Persian decimal separator
    s = s.replace('/', '.')
    
    # Remove thousand separators (comma, space, Arabic comma)
    s = s.replace(',', '').replace(' ', '').replace('٬', '')
    
    # Remove currency symbols
    s = s.replace('ریال', '').replace('تومان', '').strip()
    
    # Handle special cases
    if s in ['-', '-----', '-    ', '']:
        return None
    
    try:
        result = float(s)
        return -result if is_negative else result
    except ValueError:
        return None

# Category mapping based on warehouse names
CATEGORY_MAP = {
    'مواد غذایی': 'Food',
    'فاسد شدنی': 'Food',
    'خوارو بار': 'Food',
    'ملزومات بهداشتی': 'NonFood',
    'ملزومات': 'NonFood',
    'فنی': 'NonFood',
    'مهندسی': 'NonFood',
    'نوشیدنی': 'Food',
}

# Unit standardization
UNIT_MAP = {
    'کیلو': 'کیلوگرم',
    'کیلوگرم': 'کیلوگرم',
    'عدد': 'عدد',
    'بطری': 'عدد',
    'بسته': 'بسته',
    'گالن': 'گالن',
    'لیتر': 'لیتر',
    'گرم': 'گرم',
    'جفت': 'جفت',
    'دست': 'دست',
    'رول': 'رول',
    'قوطی': 'عدد',
    'شیشه': 'عدد',
    'پاکت': 'عدد',
    'قالب': 'عدد',
    'برگ': 'عدد',
    'حلقه': 'عدد',
    'جلد': 'عدد',
    'متر': 'متر',
    'قرص': 'عدد',
}


def clean_price(price_str):
    """Clean and convert price string to integer"""
    if price_str is None or pd.isna(price_str):
        return 0
    
    if isinstance(price_str, (int, float)):
        return int(price_str)
    
    # Remove non-numeric characters except digits
    price_str = str(price_str)
    
    # Skip non-numeric prices like "خریداری توسط شرکت"
    if not any(c.isdigit() for c in price_str):
        return 0
    
    # Remove thousand separators and convert
    cleaned = re.sub(r'[^\d]', '', price_str)
    return int(cleaned) if cleaned else 0


def clean_quantity(qty_str):
    """Clean and convert quantity string to float"""
    if qty_str is None or pd.isna(qty_str):
        return 0.0
    
    if isinstance(qty_str, (int, float)):
        return float(qty_str)
    
    qty_str = str(qty_str).strip()
    
    # Handle special cases
    if qty_str in ['-', '-----', '-    ', '']:
        return 0.0
    
    # Extract numeric part
    match = re.search(r'[\d.]+', qty_str.replace(',', ''))
    if match:
        return float(match.group())
    
    return 0.0


def generate_item_code(category, index):
    """Generate unique item code"""
    prefix = 'F' if category == 'Food' else 'N'
    return f"{prefix}{index:04d}"


def detect_category_from_sheet(sheet_name):
    """Detect category based on sheet name"""
    sheet_lower = sheet_name.lower()
    
    if 'ghazaei' in sheet_lower or 'غذا' in sheet_name or 'drink' in sheet_lower:
        return 'Food'
    elif 'behdashti' in sheet_lower or 'بهداشت' in sheet_name or 'malzumat' in sheet_lower:
        return 'NonFood'
    elif 'eng' in sheet_lower or 'فنی' in sheet_name:
        return 'NonFood'
    
    return None  # Will be determined per item


def detect_category_from_warehouse(warehouse_name):
    """Detect category from warehouse name in data"""
    if not warehouse_name or pd.isna(warehouse_name):
        return None
    
    warehouse_lower = str(warehouse_name).strip()
    
    for key, value in CATEGORY_MAP.items():
        if key in warehouse_lower:
            return value
    
    return None


def standardize_unit(unit_str):
    """Standardize unit names"""
    if not unit_str or pd.isna(unit_str):
        return 'عدد'
    
    unit_str = str(unit_str).strip()
    return UNIT_MAP.get(unit_str, unit_str)


def normalize_transaction_type(value):
    """Normalize Persian/English transaction labels to system values."""
    if value is None:
        return None

    text = str(value).strip().lower()
    type_map = {
        'خرید': 'خرید',
        'purchase': 'خرید',
        'buy': 'خرید',
        'procurement': 'خرید',
        'مصرف': 'مصرف',
        'consume': 'مصرف',
        'consumption': 'مصرف',
        'ضایعات': 'ضایعات',
        'waste': 'ضایعات',
        'اصلاحی': 'اصلاحی',
        'adjustment': 'اصلاحی',
    }
    return type_map.get(text)


def normalize_category(value):
    """Normalize category names to Food/NonFood."""
    if value is None:
        return None

    text = str(value).strip().lower()
    if text in ['food', 'مواد غذایی', 'غذایی']:
        return 'Food'
    if text in ['nonfood', 'non-food', 'غیرغذایی', 'غیر غذایی']:
        return 'NonFood'
    return None


class DataImporter:
    """Import inventory data from Excel files with P0-2 idempotency"""
    
    def __init__(self, hotel_name='default', hotel_id=None, user_id=None):
        self.hotel_name = hotel_name
        self.hotel_id = hotel_id
        self.user_id = user_id
        self.imported_items = 0
        self.updated_items = 0
        self.imported_transactions = 0
        self.errors = []
        self.warnings = []
        self.row_errors = []  # P0-5: Row-level error logging
        self.import_batch = None
        self.sheet_to_hotel_map = self._build_hotel_mapping()
        # P3-FIX: Track affected item IDs during import for initial stock transactions
        self.affected_item_ids = set()
    
    def _build_hotel_mapping(self):
        """
        P1-4: Build mapping from sheet names to hotel IDs
        Now uses HotelSheetAlias table with fallback to hardcoded mapping
        """
        from models import Hotel, HotelSheetAlias
        
        # P1-4: First try to get mapping from database
        try:
            db_mapping = HotelSheetAlias.get_all_mappings()
            if db_mapping:
                return db_mapping
        except Exception:
            pass  # Table might not exist yet
        
        # Fallback to hardcoded mapping (backward compatibility)
        hotels = {h.hotel_name: h.id for h in Hotel.query.all()}
        
        mapping = {
            'biston': hotels.get('لاله بیستون'),
            'biston 2': hotels.get('لاله بیستون'),
            'zagroos ghazaei': hotels.get('زاگرس بروجرد'),
            'zagros Behdashti': hotels.get('زاگرس بروجرد'),
            'Abdarmani': hotels.get('آبدرمانی سبلان'),
            'sarein': hotels.get('لاله سرعین'),
            'kandovan malzumat': hotels.get('لاله کندوان'),
            'kandovan eng': hotels.get('لاله کندوان'),
            'kandovan Drink': hotels.get('لاله کندوان'),
        }
        
        return mapping
    
    def import_excel(self, file_path, selected_sheets=None, allow_replace=False, import_mode='inventory'):
        """
        Import data from Excel file with P0-2 idempotency check
        P1-FIX: Uses nested transaction for proper rollback on failure
        
        Args:
            file_path: Path to Excel file
            selected_sheets: List of sheet names to import (None = all)
            allow_replace: If True, replace existing import batch
            import_mode: 'inventory' (legacy) or 'pareto_transactions'
        
        Returns:
            dict with import statistics
        """
        if not os.path.exists(file_path):
            return {'success': False, 'error': f'File not found: {file_path}'}
        
        # P0-2: Compute file hash for idempotency (outside transaction)
        file_hash = compute_file_hash(file_path)
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        
        # Check if already imported (outside transaction)
        existing_batch = check_import_exists(file_hash)
        if existing_batch and not allow_replace:
            return {
                'success': False,
                'error': f'This file has already been imported (batch #{existing_batch.id} on {existing_batch.created_at})',
                'existing_batch_id': existing_batch.id,
                'already_imported': True
            }
        
        # P1-FIX: Use nested transaction (savepoint) for atomic import
        # If anything fails, the entire import rolls back including soft-deletes
        try:
            # Start a savepoint for the entire import operation
            nested = db.session.begin_nested()
            
            try:
                # P0-1 Fix: Improved replace mode with is_active flag
                old_batch_id = None
                if existing_batch and allow_replace:
                    old_batch_id = existing_batch.id
                    # Deactivate old batch
                    existing_batch.is_active = False
                    existing_batch.status = 'replaced'
                    existing_batch.replaced_at = datetime.utcnow()

                    # Calculate stock deltas BEFORE soft delete to keep snapshot
                    stock_deltas = db.session.query(
                        Transaction.item_id,
                        func.coalesce(func.sum(Transaction.signed_quantity), 0)
                    ).filter(
                        Transaction.import_batch_id == existing_batch.id,
                        Transaction.is_deleted != True
                    ).group_by(Transaction.item_id).all()

                    # Soft-delete old transactions (only ones still active)
                    Transaction.query.filter(
                        Transaction.import_batch_id == existing_batch.id,
                        Transaction.is_deleted != True
                    ).update({
                        'is_deleted': True,
                        'deleted_at': datetime.utcnow()
                    }, synchronize_session=False)

                    # Apply stock rollback per affected item
                    if stock_deltas:
                        for item_id, signed_qty in stock_deltas:
                            if not signed_qty:
                                continue
                            item = Item.query.get(item_id)
                            if item:
                                item.current_stock = (item.current_stock or 0) - float(signed_qty)

                    db.session.flush()
                
                # Create new ImportBatch (active by default)
                self.import_batch = ImportBatch(
                    filename=filename,
                    file_hash=file_hash,
                    file_size=file_size,
                    hotel_id=self.hotel_id,
                    uploaded_by_id=self.user_id,
                    status='pending',
                    is_active=True,
                    replaces_batch_id=old_batch_id  # P0-1: Track what this replaces
                )
                db.session.add(self.import_batch)
                db.session.flush()  # Get ID
                
                # P0-1: Link old batch to new one
                if existing_batch and allow_replace:
                    existing_batch.replaced_by_id = self.import_batch.id
                
                # BUG #11 FIX: Use try-finally to ensure file handle is closed
                excel_file = None
                try:
                    excel_file = pd.ExcelFile(file_path)
                    sheet_names = excel_file.sheet_names
                    
                    if selected_sheets:
                        sheet_names = [s for s in sheet_names if s in selected_sheets]
                    
                    results = []
                    
                    for sheet_name in sheet_names:
                        if import_mode == 'pareto_transactions':
                            result = self._import_pareto_transactions_sheet(excel_file, sheet_name)
                        else:
                            result = self._import_sheet(excel_file, sheet_name)
                        results.append(result)
                    
                    # Update batch stats
                    self.import_batch.status = 'completed'
                    self.import_batch.items_created = self.imported_items
                    self.import_batch.items_updated = self.updated_items
                    self.import_batch.transactions_created = self.imported_transactions
                    self.import_batch.errors_count = len(self.row_errors)
                    if self.row_errors:
                        self.import_batch.error_details = json.dumps(self.row_errors[:100], ensure_ascii=False)
                    
                    # P0-1/P0-2: Create initial stock transactions for imported stock
                    if import_mode != 'pareto_transactions':
                        self.create_initial_stock_transactions(self.user_id or 1)
                    
                    # Commit the nested transaction (savepoint)
                    nested.commit()
                    # Commit the outer transaction
                    db.session.commit()
                    
                    return {
                        'success': True,
                        'import_mode': import_mode,
                        'batch_id': self.import_batch.id,
                        'total_items': self.imported_items,
                        'items_updated': self.updated_items,
                        'total_transactions': self.imported_transactions,
                        'sheets': results,
                        'errors': self.errors,
                        'warnings': self.warnings,
                        'row_errors': self.row_errors[:20]  # First 20 row errors
                    }
                finally:
                    # BUG #11 FIX: Always close the Excel file handle
                    if excel_file is not None:
                        excel_file.close()
                
            except Exception as inner_e:
                # BUG #9 FIX: Safe nested rollback with error handling
                try:
                    nested.rollback()
                except Exception as rollback_e:
                    import logging
                    logging.getLogger(__name__).error(f'Nested rollback failed: {rollback_e}')
                raise inner_e
            
        except Exception as e:
            # Full rollback of any partial changes
            db.session.rollback()
            
            # Log the failure but don't persist failed batch state
            # (since we rolled back, the batch doesn't exist)
            import logging
            logging.getLogger(__name__).error(f"Import failed and rolled back: {str(e)}")
            
            return {'success': False, 'error': str(e)}

    def _detect_transaction_columns(self, df):
        """Detect transaction-oriented columns for Pareto import."""
        columns = {}

        for col in df.columns:
            col_str = str(col).strip().lower()

            if any(x in col_str for x in ['کد کالا', 'item code', 'item_code', 'code']):
                columns['item_code'] = col
            elif any(x in col_str for x in ['نام کالا', 'شرح', 'item name', 'name']):
                columns['item_name'] = col
            elif any(x in col_str for x in ['نوع تراکنش', 'transaction type', 'type']):
                columns['transaction_type'] = col
            elif any(x in col_str for x in ['گروه', 'category']):
                columns['category'] = col
            elif any(x in col_str for x in ['قیمت واحد', 'unit price', 'price']):
                columns['unit_price'] = col
            elif any(x in col_str for x in ['مقدار', 'تعداد', 'quantity', 'qty']):
                columns['quantity'] = col
            elif any(x in col_str for x in ['واحد', 'unit']) and 'قیمت' not in col_str and 'price' not in col_str:
                columns['unit'] = col
            elif any(x in col_str for x in ['مبلغ کل', 'total amount', 'amount', 'value']):
                columns['total_amount'] = col
            elif any(x in col_str for x in ['تاریخ', 'date', 'transaction date']):
                columns['transaction_date'] = col
            elif any(x in col_str for x in ['توضیحات', 'description', 'desc']):
                columns['description'] = col

        return columns

    def _resolve_item_for_transaction(self, row, columns):
        """Resolve existing item by code/name or create it if not found."""
        item_code = row.get(columns.get('item_code')) if columns.get('item_code') else None
        item_name = row.get(columns.get('item_name')) if columns.get('item_name') else None

        if item_name is not None:
            item_name = str(item_name).strip()
        if item_code is not None:
            item_code = str(item_code).strip()

        query = Item.query
        if self.hotel_id:
            query = query.filter_by(hotel_id=self.hotel_id)

        item = None
        if item_code:
            item = query.filter_by(item_code=item_code).first()
        if not item and item_name:
            item = query.filter_by(item_name_fa=item_name).first()

        if item:
            return item

        if not item_name:
            raise ValueError('نام کالا برای ردیف تراکنش الزامی است')

        category_value = row.get(columns.get('category')) if columns.get('category') else None
        unit_value = row.get(columns.get('unit')) if columns.get('unit') else 'عدد'

        category = normalize_category(category_value) or self._guess_category(item_name)
        unit = standardize_unit(unit_value)

        return self._get_or_create_item(
            name=item_name,
            unit=unit,
            category=category,
            current_stock=0,
            weekly_consumption=0,
            monthly_consumption=0,
            hotel='pareto_import'
        )

    def _parse_transaction_date(self, value):
        """Parse transaction date from Excel values."""
        if value is None or value == '' or pd.isna(value):
            return get_iran_today()

        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        text = str(value).strip()
        date_formats = ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%d-%m-%Y']
        for fmt in date_formats:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

        parsed = pd.to_datetime(text, errors='coerce')
        if pd.notna(parsed):
            return parsed.date()

        raise ValueError(f'فرمت تاریخ نامعتبر است: {value}')

    def _import_pareto_transactions_sheet(self, excel_file, sheet_name):
        """Import transaction rows from Excel for Pareto analysis."""
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            if df.empty:
                return {'sheet': sheet_name, 'status': 'empty', 'transactions': 0}

            columns = self._detect_transaction_columns(df)
            required = ['quantity', 'unit_price']
            missing_required = [c for c in required if not columns.get(c)]
            if missing_required:
                self.warnings.append(
                    f"شیت {sheet_name}: ستون‌های الزامی تراکنش یافت نشد: {', '.join(missing_required)}"
                )
                return {'sheet': sheet_name, 'status': 'no_required_columns', 'transactions': 0}

            imported_count = 0
            skipped_count = 0

            for idx, row in df.iterrows():
                row_number = int(idx) + 2
                try:
                    item = self._resolve_item_for_transaction(row, columns)
                    if not item:
                        skipped_count += 1
                        continue

                    raw_type = row.get(columns.get('transaction_type')) if columns.get('transaction_type') else 'خرید'
                    transaction_type = normalize_transaction_type(raw_type) or 'خرید'

                    quantity = clean_number_robust(row.get(columns['quantity']))
                    unit_price = clean_number_robust(row.get(columns['unit_price']))
                    total_amount = clean_number_robust(row.get(columns['total_amount'])) if columns.get('total_amount') else None

                    if quantity is None or quantity <= 0:
                        raise ValueError('مقدار باید بیشتر از صفر باشد')
                    if unit_price is None or unit_price < 0:
                        raise ValueError('قیمت واحد نامعتبر است')

                    category_value = row.get(columns.get('category')) if columns.get('category') else None
                    tx_category = normalize_category(category_value) or item.category
                    tx_date = self._parse_transaction_date(row.get(columns.get('transaction_date')) if columns.get('transaction_date') else None)
                    description = row.get(columns.get('description')) if columns.get('description') else None
                    tx_unit = standardize_unit(row.get(columns.get('unit'))) if columns.get('unit') else (item.unit or 'عدد')

                    tx = Transaction.create_transaction(
                        item_id=item.id,
                        transaction_type=transaction_type,
                        quantity=quantity,
                        unit_price=unit_price,
                        category=tx_category,
                        hotel_id=item.hotel_id,
                        user_id=self.user_id or 1,
                        description=str(description).strip() if description and not pd.isna(description) else 'Imported from Excel (Pareto)',
                        source='pareto_excel_import',
                        import_batch_id=self.import_batch.id if self.import_batch else None,
                        unit=tx_unit,
                        allow_price_override=True,
                        price_override_reason='Excel Pareto import'
                    )
                    tx.transaction_date = tx_date

                    # If PMS file has an explicit total amount, trust it for spend analytics.
                    if total_amount is not None and total_amount >= 0:
                        tx.total_amount = Decimal(str(total_amount)).quantize(Decimal('0.01'))

                    db.session.add(tx)

                    # Keep stock aligned with imported transactions
                    item.current_stock = float(item.current_stock or 0) + float(tx.signed_quantity)

                    self.imported_transactions += 1
                    imported_count += 1
                except Exception as row_error:
                    skipped_count += 1
                    err = f'شیت {sheet_name} ردیف {row_number}: {str(row_error)}'
                    self.errors.append(err)
                    self.row_errors.append({'sheet': sheet_name, 'row': row_number, 'error': str(row_error)})

            db.session.flush()

            return {
                'sheet': sheet_name,
                'status': 'success',
                'transactions': imported_count,
                'skipped': skipped_count
            }
        except Exception as e:
            self.errors.append(f"شیت {sheet_name}: {str(e)}")
            return {'sheet': sheet_name, 'status': 'error', 'error': str(e), 'transactions': 0}
    
    def _import_sheet(self, excel_file, sheet_name):
        """Import data from a single sheet"""
        sheet_hotel_id = None
        original_hotel_id = self.hotel_id
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            
            if df.empty:
                return 0
            
            # Detect hotel from sheet name
            sheet_hotel_id = self.sheet_to_hotel_map.get(sheet_name.lower())
            if sheet_hotel_id:
                # Override hotel_id for this sheet
                original_hotel_id = self.hotel_id
                self.hotel_id = sheet_hotel_id
            
            # Detect columns
            columns = self._detect_columns(df)
            
            if not columns.get('name'):
                self.warnings.append(f'شیت {sheet_name}: ستون نام کالا یافت نشد')
                # Restore original hotel_id
                if sheet_hotel_id:
                    self.hotel_id = original_hotel_id
                return 0
            
            # Default category from sheet name
            default_category = detect_category_from_sheet(sheet_name)
            
            items_added = 0
            
            for idx, row in df.iterrows():
                # Skip header rows or empty rows
                item_name = row.get(columns['name'])
                if not item_name or pd.isna(item_name):
                    continue
                
                item_name = str(item_name).strip()
                if not item_name or item_name in ['شرح', 'نام کالا', 'شـــــرح کالا', 'ردیف']:
                    continue
                
                # Determine category
                category = default_category
                if columns.get('warehouse'):
                    warehouse_cat = detect_category_from_warehouse(row.get(columns['warehouse']))
                    if warehouse_cat:
                        category = warehouse_cat
                
                if not category:
                    # Guess based on item name
                    category = self._guess_category(item_name)
                
                # Get or create item
                item = self._get_or_create_item(
                    name=item_name,
                    unit=standardize_unit(row.get(columns.get('unit'), 'عدد')),
                    category=category,
                    current_stock=clean_quantity(row.get(columns.get('stock'))),
                    weekly_consumption=clean_quantity(row.get(columns.get('weekly'))),
                    monthly_consumption=clean_quantity(row.get(columns.get('monthly'))),
                    hotel=sheet_name
                )
                
                if item:
                    items_added += 1
            
            db.session.flush()
            self.imported_items += items_added
            
            # Restore original hotel_id after import
            if sheet_hotel_id:
                self.hotel_id = original_hotel_id
            
            return {
                'sheet': sheet_name,
                'status': 'success',
                'items': items_added,
                'category': default_category or 'mixed'
            }
            
        except Exception as e:
            self.errors.append(f"شیت {sheet_name}: {str(e)}")
            # Restore hotel_id on error too
            if sheet_hotel_id:
                self.hotel_id = original_hotel_id
            return {'sheet': sheet_name, 'status': 'error', 'error': str(e)}
    
    def _detect_columns(self, df):
        """Auto-detect column mappings"""
        columns = {}
        
        for col in df.columns:
            col_str = str(col).strip().lower()
            
            # Name column
            if any(x in col_str for x in ['شرح', 'نام کالا', 'کالا']):
                columns['name'] = col
            
            # Unit column (exclude 'قیمت واحد' which is the price column)
            elif 'واحد' in col_str and 'قیمت' not in col_str and 'price' not in col_str:
                columns['unit'] = col
            
            # Stock column
            elif any(x in col_str for x in ['موجودی', 'انبار']):
                if 'نام' not in col_str:  # Exclude "نام انبار"
                    columns['stock'] = col
            
            # Warehouse name
            elif 'نام انبار' in col_str:
                columns['warehouse'] = col
            
            # Weekly consumption
            elif any(x in col_str for x in ['هفتگی', 'یک هفته', 'هفته']):
                columns['weekly'] = col
            
            # Monthly consumption
            elif any(x in col_str for x in ['ماهانه', 'یکماه', 'ماه']) and 'شش' not in col_str:
                columns['monthly'] = col
            
            # Price column
            elif any(x in col_str for x in ['قیمت', 'فی']):
                columns['price'] = col
        
        return columns
    
    def _guess_category(self, item_name):
        """Guess category based on item name"""
        food_keywords = [
            'گوشت', 'مرغ', 'ماهی', 'برنج', 'روغن', 'شکر', 'نمک', 'ماست', 
            'پنیر', 'شیر', 'تخم', 'نان', 'میوه', 'سبزی', 'سیب', 'موز',
            'چای', 'قهوه', 'نوشابه', 'آب', 'رب', 'سس', 'ادویه', 'زعفران',
            'عسل', 'مربا', 'بستنی', 'سوسیس', 'کالباس', 'خامه', 'کره'
        ]
        
        for keyword in food_keywords:
            if keyword in item_name:
                return 'Food'
        
        return 'NonFood'
    
    def _normalize_unit(self, unit):
        """
        BUSINESS LOGIC FIX #4: Normalize unit for comparison
        Handles variations like 'کیلوگرم' vs 'کیلو' or 'لیتر' vs 'L'
        """
        if not unit:
            return ''
        
        unit_lower = unit.strip().lower()
        
        # Map common variations to standard form
        unit_map = {
            'کیلو': 'کیلوگرم',
            'kg': 'کیلوگرم',
            'l': 'لیتر',
            'ل': 'لیتر',
            'ع': 'عدد',
            'pcs': 'عدد',
            'piece': 'عدد',
            'م': 'متر',
            'm': 'متر',
        }
        
        return unit_map.get(unit_lower, unit_lower)
    
    def _get_or_create_item(self, name, unit, category, current_stock, 
                           weekly_consumption, monthly_consumption, hotel):
        """
        Get existing item or create new one
        P1-5: Set base_unit for normalization
        BUSINESS LOGIC FIX #4: Validate unit mismatch to prevent inventory corruption
        """
        # Check if item exists for this hotel
        query = Item.query.filter_by(item_name_fa=name)
        if self.hotel_id:
            query = query.filter_by(hotel_id=self.hotel_id)
        existing = query.first()
        
        if existing:
            # BUSINESS LOGIC FIX #4: Check for unit mismatch
            # Normalize both units for comparison
            existing_unit_normalized = self._normalize_unit(existing.unit)
            new_unit_normalized = self._normalize_unit(unit)
            
            if existing_unit_normalized != new_unit_normalized:
                # Critical error: unit mismatch
                error_msg = f"عدم تطابق واحد برای کالا '{name}': سیستم '{existing.unit}' دارد، فایل '{unit}' دارد. ردیف نادیده گرفته شد."
                self.errors.append(error_msg)
                logger.error(f"Unit mismatch for item {name}: system has '{existing.unit}', file has '{unit}'. Skipped.")
                return None  # Skip this row
            
            # Update if needed - convert to base unit for storage
            if current_stock > 0:
                try:
                    factor = Item.get_conversion_factor(unit)
                except (ValueError, Exception):
                    factor = 1.0
                existing.current_stock = current_stock * factor
            # P1-5: Ensure base_unit is set
            if not existing.base_unit:
                existing.base_unit = existing.get_base_unit()
            # P3-FIX: Track affected item for initial stock transactions
            self.affected_item_ids.add(existing.id)
            return existing
        
        # Generate new item code
        last_item = Item.query.filter_by(category=category).order_by(Item.id.desc()).first()
        if last_item:
            # Extract number from code
            match = re.search(r'\d+', last_item.item_code)
            next_num = int(match.group()) + 1 if match else 1
        else:
            next_num = 1
        
        prefix = 'F' if category == 'Food' else 'N'
        item_code = f"{prefix}{next_num:03d}"
        
        # P1-5: Determine base_unit from unit
        from models.item import UNIT_CONVERSIONS, BASE_UNITS
        base_unit = unit
        if unit in UNIT_CONVERSIONS:
            unit_type, _ = UNIT_CONVERSIONS[unit]
            base_unit = BASE_UNITS.get(unit_type, unit)
        
        # BUG #43 FIX: Use fraction of monthly or weekly for min_stock
        # Industry standard: 25-30% of monthly (1 week) for safety stock
        if monthly_consumption > 0:
            min_stock_value = monthly_consumption * 0.25  # 1 week (7-8 days)
        elif weekly_consumption > 0:
            min_stock_value = weekly_consumption * 1.5  # 1.5 weeks
        else:
            min_stock_value = 0
        
        # SS-5 FIX: Convert current_stock to base unit for storage
        try:
            stock_factor = Item.get_conversion_factor(unit)
        except (ValueError, Exception):
            stock_factor = 1.0
        base_current_stock = current_stock * stock_factor
        base_min_stock = min_stock_value * stock_factor
        
        # Create new item
        new_item = Item(
            item_code=item_code,
            item_name_fa=name,
            item_name_en=name,  # Same as Persian for now
            category=category,
            unit=unit,
            base_unit=base_unit,  # P1-5: Set base_unit
            hotel_id=self.hotel_id,
            current_stock=base_current_stock,
            min_stock=base_min_stock,
            is_active=True
        )
        
        db.session.add(new_item)
        db.session.flush()  # Get ID for tracking
        # P3-FIX: Track new item for initial stock transactions
        self.affected_item_ids.add(new_item.id)
        return new_item
    
    def create_initial_stock_transactions(self, user_id=1):
        """
        Create initial stock transactions for items with current_stock != 0
        P0-2: Mark as opening balance with proper fields
        P3-FIX: Only process items from current import batch (tracked via affected_item_ids)
        BUG #44 FIX: Handle negative stocks and validate
        """
        # P3-FIX: Only process items that were created/updated in THIS import
        if not self.affected_item_ids:
            return 0
        
        items_with_stock = Item.query.filter(
            Item.id.in_(self.affected_item_ids),
            Item.current_stock != 0  # BUG #44 FIX: Include negative stocks
        ).all()
        
        # BUG #44 FIX: Warn about negative stocks and reset them
        for item in items_with_stock:
            if item.current_stock < 0:
                self.warnings.append(
                    f'کالا {item.item_name_fa} موجودی منفی دارد: {item.current_stock}'
                )
                # Reset to zero
                item.current_stock = 0
                continue
        
        for item in items_with_stock:
            # Check if initial transaction exists for this batch
            existing = Transaction.query.filter_by(
                item_id=item.id,
                is_opening_balance=True,
                import_batch_id=self.import_batch.id if self.import_batch else None
            ).first()
            
            if not existing and item.current_stock > 0:
                # Fetch last known price to prevent 0-price skew
                last_price = 0
                last_tx = Transaction.query.filter_by(
                    item_id=item.id, 
                    is_deleted=False
                ).filter(Transaction.unit_price > 0).order_by(Transaction.transaction_date.desc()).first()
                
                if last_tx:
                    last_price = last_tx.unit_price

                # P0-2/P0-3/P0-4: Use centralized transaction creation
                transaction = Transaction.create_transaction(
                    item_id=item.id,
                    transaction_type='اصلاحی',
                    quantity=item.current_stock,
                    unit_price=last_price,  # Use last known price or 0
                    category=item.category,
                    hotel_id=item.hotel_id,
                    user_id=user_id,
                    description='Opening balance - imported from Excel',
                    source='opening_import',
                    # BUG FIX: direction must be provided for adjustments
                    direction=1,  # Opening balance is always an increase
                    is_opening_balance=True,
                    import_batch_id=self.import_batch.id if self.import_batch else None
                )
                transaction.transaction_date = get_iran_today()
                db.session.add(transaction)
                self.imported_transactions += 1
        
        db.session.flush()
        return self.imported_transactions


def import_from_file(file_path, hotel_name='default'):
    """
    Convenience function to import data from file
    
    Usage:
        from services.data_importer import import_from_file
        result = import_from_file('path/to/file.xlsx', 'hotel_name')
    """
    importer = DataImporter(hotel_name)
    return importer.import_excel(file_path)

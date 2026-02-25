#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Data Importer Service (Refactored)
Production-grade importer with concurrency safety, historical import support, and robust validation.

Refactored by: Gemini Senior Architect
Date: 2025-02-21
"""

import os
import re
import hashlib
import json
import logging
import random
import time
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, List, Any, Union

import pandas as pd
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import db, Item, Transaction, ImportBatch
from utils.timezone import get_iran_today

logger = logging.getLogger(__name__)

# --- Constants & Configuration ---

CATEGORY_MAP = {
    # Food Keywords
    'food': 'Food',
    'مواد غذایی': 'Food',
    'فاسد شدنی': 'Food',
    'خوارو بار': 'Food',
    'نوشیدنی': 'Food',
    'گوشت': 'Food',
    'مرغ': 'Food',
    'ماهی': 'Food',
    'برنج': 'Food',
    'روغن': 'Food',
    'لبنیات': 'Food',
    'میوه': 'Food',
    'سبزی': 'Food',
    # NonFood Keywords
    'nonfood': 'NonFood',
    'غیرغذایی': 'NonFood',
    'ملزومات': 'NonFood',
    'بهداشتی': 'NonFood',
    'فنی': 'NonFood',
    'مهندسی': 'NonFood',
    'تاسیسات': 'NonFood',
    'اداری': 'NonFood',
    'ظروف': 'NonFood',
}

UNIT_MAP = {
    'کیلو': 'کیلوگرم',
    'کیلوگرم': 'کیلوگرم',
    'kg': 'کیلوگرم',
    'عدد': 'عدد',
    'بطری': 'عدد',
    'بسته': 'بسته',
    'گالن': 'گالن',
    'لیتر': 'لیتر',
    'liter': 'لیتر',
    'گرم': 'گرم',
    'g': 'گرم',
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
    'کارتن': 'عدد', 
}

DATE_FORMATS = [
    '%Y-%m-%d', '%Y/%m/%d', 
    '%d/%m/%Y', '%d-%m-%Y',
    '%Y.%m.%d', '%d.%m.%Y',
    '%m/%d/%Y'
]

# --- Helper Functions ---

def compute_file_hash(file_path: str, timeout_seconds: int = 30) -> str:
    """Compute SHA256 hash of file for idempotency check with timeout."""
    import signal
    import platform
    import threading

    class TimeoutError(Exception):
        pass

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
        raise ValueError(f"File hash computation timed out after {timeout_seconds}s")
    if result['error']:
        raise result['error']
    return result['hash']

def check_import_exists(file_hash: str) -> Optional[ImportBatch]:
    """Check if file has an ACTIVE import batch."""
    if not re.match(r'^[a-f0-9]{64}$', file_hash):
        raise ValueError(f"Invalid file hash format: {file_hash}")
    
    return ImportBatch.query.filter_by(
        file_hash=file_hash, 
        is_active=True,
        status='completed'
    ).first()

def clean_number_robust(value: Any) -> Optional[float]:
    """Robust number cleaning for Persian/Arabic digits."""
    if value is None or value == '':
        return None
    
    if isinstance(value, (int, float)):
        return float(value)
    
    s = str(value).strip()
    
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    arabic_digits = '٠١٢٣٤٥٦٧٨٩'
    for i, (p, a) in enumerate(zip(persian_digits, arabic_digits)):
        s = s.replace(p, str(i)).replace(a, str(i))
    
    is_negative = s.startswith('(') and s.endswith(')')
    if is_negative:
        s = s[1:-1]
    
    s = s.replace('/', '.')
    s = s.replace(',', '').replace(' ', '').replace('٬', '')
    s = s.replace('ریال', '').replace('تومان', '').strip()
    
    if s in ['-', '-----', '-    ', '']:
        return None
    
    try:
        result = float(s)
        return -result if is_negative else result
    except ValueError:
        return None

def standardize_unit(unit_str: Any) -> str:
    """Standardize unit names."""
    if not unit_str or pd.isna(unit_str):
        return 'عدد'
    unit_str = str(unit_str).strip().lower()
    return UNIT_MAP.get(unit_str, unit_str)

def normalize_transaction_type(value: Any) -> Optional[str]:
    """Normalize transaction type."""
    if value is None:
        return None
    text = str(value).strip().lower()
    type_map = {
        'خرید': 'خرید', 'purchase': 'خرید', 'buy': 'خرید',
        'مصرف': 'مصرف', 'consume': 'مصرف', 'consumption': 'مصرف',
        'ضایعات': 'ضایعات', 'waste': 'ضایعات',
        'اصلاحی': 'اصلاحی', 'adjustment': 'اصلاحی',
    }
    return type_map.get(text)

def normalize_category(value: Any) -> Optional[str]:
    """Normalize category names."""
    if value is None:
        return None
    text = str(value).strip().lower()
    for key, val in CATEGORY_MAP.items():
        if key in text:
            return val
    return None

class DataImporter:
    """
    Production-grade Data Importer.
    Handles Excel imports with transactional safety, concurrency checks, and robust validation.
    """
    
    def __init__(self, hotel_name='default', hotel_id=None, user_id=None):
        self.hotel_name = hotel_name
        self.hotel_id = hotel_id
        self.user_id = user_id
        self.imported_items = 0
        self.updated_items = 0
        self.imported_transactions = 0
        self.errors = []
        self.warnings = []
        self.row_errors = []
        self.import_batch = None
        self.sheet_to_hotel_map = self._build_hotel_mapping()
        self.affected_item_ids = set()

    def _build_hotel_mapping(self) -> Dict[str, int]:
        """Build mapping from sheet names to hotel IDs."""
        try:
            from models import HotelSheetAlias, Hotel
            db_mapping = HotelSheetAlias.get_all_mappings()
            if db_mapping:
                return db_mapping
            # Fallback
            hotels = {h.hotel_name: h.id for h in Hotel.query.all()}
            return {
                'biston': hotels.get('لاله بیستون'),
                'zagroos ghazaei': hotels.get('زاگرس بروجرد'),
                'sarein': hotels.get('لاله سرعین'),
                # Add more defaults as needed
            }
        except Exception:
            return {}

    def import_excel(self, file_path: str, selected_sheets: List[str] = None, 
                     allow_replace: bool = False, import_mode: str = 'inventory',
                     update_stock: bool = True) -> Dict[str, Any]:
        """
        Import data from Excel file.
        
        Args:
            file_path: Path to Excel file.
            selected_sheets: List of sheets to import.
            allow_replace: Replace existing batch if exists.
            import_mode: 'inventory' or 'pareto_transactions'.
            update_stock: If True, updates Item.current_stock. Set False for historical data.
        """
        if not os.path.exists(file_path):
            return {'success': False, 'error': f'File not found: {file_path}'}
        
        file_hash = compute_file_hash(file_path)
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        
        existing_batch = check_import_exists(file_hash)
        if existing_batch and not allow_replace:
            return {
                'success': False,
                'error': f'File already imported (Batch #{existing_batch.id}).',
                'existing_batch_id': existing_batch.id,
                'already_imported': True
            }
        
        try:
            # Atomic Transaction Start
            nested = db.session.begin_nested()
            
            try:
                # Handle Replacement
                old_batch_id = None
                if existing_batch and allow_replace:
                    old_batch_id = existing_batch.id
                    self._deactivate_batch(existing_batch)

                # Create New Batch
                self.import_batch = ImportBatch(
                    filename=filename,
                    file_hash=file_hash,
                    file_size=file_size,
                    hotel_id=self.hotel_id,
                    uploaded_by_id=self.user_id,
                    status='pending',
                    is_active=True,
                    replaces_batch_id=old_batch_id
                )
                db.session.add(self.import_batch)
                db.session.flush()
                
                if existing_batch and allow_replace:
                    existing_batch.replaced_by_id = self.import_batch.id

                # Process File
                excel_file = pd.ExcelFile(file_path)
                sheet_names = selected_sheets if selected_sheets else excel_file.sheet_names
                
                results = []
                for sheet_name in sheet_names:
                    if import_mode == 'pareto_transactions':
                        res = self._import_pareto_transactions_sheet(excel_file, sheet_name, update_stock)
                    else:
                        res = self._import_sheet(excel_file, sheet_name)
                    results.append(res)
                
                excel_file.close()

                # Finalize Batch
                self.import_batch.status = 'completed'
                self.import_batch.items_created = self.imported_items
                self.import_batch.items_updated = self.updated_items
                self.import_batch.transactions_created = self.imported_transactions
                self.import_batch.errors_count = len(self.row_errors)
                if self.row_errors:
                    self.import_batch.error_details = json.dumps(self.row_errors[:100], ensure_ascii=False)
                
                # Create Initial Stock (Only for Inventory Mode)
                if import_mode != 'pareto_transactions':
                    self.create_initial_stock_transactions(self.user_id or 1)
                
                nested.commit()
                db.session.commit()
                
                return {
                    'success': True,
                    'batch_id': self.import_batch.id,
                    'total_items': self.imported_items,
                    'transactions': self.imported_transactions,
                    'sheets': results,
                    'errors': self.errors,
                    'warnings': self.warnings,
                    'row_errors': self.row_errors[:20]
                }

            except Exception as inner_e:
                nested.rollback()
                raise inner_e

        except Exception as e:
            db.session.rollback()
            logger.error(f"Import failed: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _deactivate_batch(self, batch: ImportBatch):
        """Deactivate an existing batch and rollback its stock effects."""
        batch.is_active = False
        batch.status = 'replaced'
        batch.replaced_at = datetime.utcnow()
        
        # Reverse stock effects
        stock_deltas = db.session.query(
            Transaction.item_id,
            func.coalesce(func.sum(Transaction.signed_quantity), 0)
        ).filter(
            Transaction.import_batch_id == batch.id,
            Transaction.is_deleted != True
        ).group_by(Transaction.item_id).all()
        
        # Soft-delete transactions
        Transaction.query.filter(
            Transaction.import_batch_id == batch.id,
            Transaction.is_deleted != True
        ).update({'is_deleted': True, 'deleted_at': datetime.utcnow()}, synchronize_session=False)
        
        # Apply stock rollback
        for item_id, signed_qty in stock_deltas:
            if not signed_qty: continue
            # Safe atomic update
            Item.query.filter_by(id=item_id).update({
                Item.current_stock: func.max(0, Item.current_stock - signed_qty)
            }, synchronize_session=False)
        
        db.session.flush()

    def _detect_transaction_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """Detect transaction columns with extended support."""
        cols = {}
        for col in df.columns:
            c = str(col).strip().lower()
            if any(x in c for x in ['کد کالا', 'item code']): cols['item_code'] = col
            elif any(x in c for x in ['نام کالا', 'شرح', 'item name']): cols['item_name'] = col
            elif any(x in c for x in ['نوع تراکنش', 'type']): cols['transaction_type'] = col
            elif any(x in c for x in ['گروه', 'category']): cols['category'] = col
            elif any(x in c for x in ['قیمت', 'price', 'fee']): cols['unit_price'] = col
            elif any(x in c for x in ['مقدار', 'تعداد', 'qty']): cols['quantity'] = col
            elif any(x in c for x in ['واحد', 'unit']) and 'قیمت' not in c: cols['unit'] = col
            elif any(x in c for x in ['تاریخ', 'date']): cols['transaction_date'] = col
            elif any(x in c for x in ['تامین', 'فروشنده', 'supplier']): cols['supplier'] = col
            elif any(x in c for x in ['توضیحات', 'desc']): cols['description'] = col
        return cols

    def _parse_transaction_date(self, value: Any) -> date:
        """Robust date parsing."""
        if value is None or value == '' or pd.isna(value):
            return get_iran_today()
        if isinstance(value, (datetime, date)):
            return value if isinstance(value, date) else value.date()
        
        text = str(value).strip()
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        
        # Pandas fallback
        try:
            parsed = pd.to_datetime(text, errors='coerce')
            if pd.notna(parsed):
                return parsed.date()
        except:
            pass
            
        raise ValueError(f"Invalid date format: {value}")

    def _import_pareto_transactions_sheet(self, excel_file: pd.ExcelFile, sheet_name: str, 
                                        update_stock: bool) -> Dict[str, Any]:
        """Import transaction rows with strict validation and stock safety."""
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            if df.empty:
                return {'sheet': sheet_name, 'status': 'empty'}

            cols = self._detect_transaction_columns(df)
            required = ['quantity', 'unit_price']
            missing = [c for c in required if not cols.get(c)]
            if missing:
                return {'sheet': sheet_name, 'status': 'missing_columns', 'missing': missing}

            success_count = 0
            skip_count = 0

            for idx, row in df.iterrows():
                row_num = idx + 2
                try:
                    # 1. Resolve Item (with concurrency retry)
                    item = self._resolve_item_for_transaction(row, cols)
                    if not item:
                        skip_count += 1
                        continue

                    # 2. Extract Data
                    raw_type = row.get(cols.get('transaction_type'), 'خرید')
                    tx_type = normalize_transaction_type(raw_type) or 'خرید'
                    
                    qty = clean_number_robust(row.get(cols['quantity']))
                    price = clean_number_robust(row.get(cols['unit_price']))
                    supplier = str(row.get(cols.get('supplier'), '')).strip() if cols.get('supplier') else None
                    tx_date = self._parse_transaction_date(row.get(cols.get('transaction_date')))
                    
                    if qty is None or qty <= 0:
                        raise ValueError("Quantity must be positive")
                    if price is None or price < 0:
                        raise ValueError("Price must be non-negative")

                    # 3. Handle Units & Conversion
                    row_unit = standardize_unit(row.get(cols.get('unit'))) if cols.get('unit') else item.unit
                    conversion_factor = 1.0
                    
                    if row_unit and row_unit != item.unit and row_unit != item.base_unit:
                        try:
                            conversion_factor = Item.get_conversion_factor(row_unit, item.base_unit)
                        except ValueError:
                            # If conversion fails, log warning but proceed with 1.0 (or fail strictly)
                            # Here we fail strictly for data integrity
                            raise ValueError(f"Unit mismatch: {row_unit} vs {item.base_unit} (No conversion found)")

                    # 4. Create Transaction
                    tx = Transaction.create_transaction(
                        item_id=item.id,
                        transaction_type=tx_type,
                        quantity=qty,
                        unit_price=price,
                        category=item.category,
                        hotel_id=item.hotel_id,
                        user_id=self.user_id or 1,
                        description=f"Imported from {sheet_name}",
                        source='pareto_excel_import',
                        import_batch_id=self.import_batch.id,
                        unit=row_unit,
                        conversion_factor_to_base=conversion_factor,
                        allow_price_override=True,
                        price_override_reason="Excel Import"
                    )
                    tx.transaction_date = tx_date
                    tx.supplier = supplier
                    
                    db.session.add(tx)
                    
                    # 5. Update Stock (Safe Atomic Update)
                    if update_stock:
                        # Transaction.signed_quantity handles direction and conversion
                        signed_qty = tx.signed_quantity
                        Item.query.filter_by(id=item.id).update({
                            Item.current_stock: func.max(0, Item.current_stock + signed_qty)
                        }, synchronize_session=False)

                    success_count += 1

                except Exception as e:
                    skip_count += 1
                    self.errors.append(f"Sheet {sheet_name} Row {row_num}: {str(e)}")
                    self.row_errors.append({'sheet': sheet_name, 'row': row_num, 'error': str(e)})

            db.session.flush()
            return {'sheet': sheet_name, 'status': 'success', 'transactions': success_count, 'skipped': skip_count}

        except Exception as e:
            logger.error(f"Sheet error {sheet_name}: {e}")
            return {'sheet': sheet_name, 'status': 'error', 'error': str(e)}

    def _resolve_item_for_transaction(self, row: pd.Series, cols: Dict[str, str]) -> Optional[Item]:
        """Find or create item with concurrency safety."""
        code = str(row.get(cols.get('item_code'), '')).strip()
        name = str(row.get(cols.get('item_name'), '')).strip()
        
        if not name: return None

        # Try finding existing item
        query = Item.query
        if self.hotel_id:
            query = query.filter_by(hotel_id=self.hotel_id)
        
        item = None
        if code: item = query.filter_by(item_code=code).first()
        if not item: item = query.filter_by(item_name_fa=name).first()
        
        if item: return item

        # Create new item with retry logic for concurrency
        category = normalize_category(row.get(cols.get('category'))) or self._guess_category(name)
        unit = standardize_unit(row.get(cols.get('unit'), 'عدد'))
        
        return self._create_item_safe(name, unit, category)

    def _create_item_safe(self, name: str, unit: str, category: str, retries: int = 3) -> Item:
        """Create item with concurrency retry mechanism."""
        for attempt in range(retries):
            try:
                # Use nested transaction for safe rollback of failed attempts
                with db.session.begin_nested():
                    # Generate Code
                    prefix = 'F' if category == 'Food' else 'N'
                    # Lock the table for reading max ID (optional, depending on DB)
                    # Or just query, and rely on unique constraint to fail
                    last_item = Item.query.filter_by(category=category).order_by(Item.id.desc()).first()
                    
                    if last_item and last_item.item_code.startswith(prefix):
                        try:
                            num = int(last_item.item_code[1:]) + 1
                        except ValueError:
                            num = random.randint(1000, 9999) # Fallback
                    else:
                        num = 1
                    
                    # Add random offset if retrying to avoid collision
                    if attempt > 0:
                        num += random.randint(1, 100)
                        
                    new_code = f"{prefix}{num:04d}"
                    
                    item = Item(
                        item_code=new_code,
                        item_name_fa=name,
                        category=category,
                        unit=unit,
                        base_unit=unit, # Assume base for new items
                        hotel_id=self.hotel_id,
                        current_stock=0
                    )
                    db.session.add(item)
                    db.session.flush() # Will raise IntegrityError if code exists
                    return item
                    
            except IntegrityError:
                if attempt == retries - 1:
                    raise
                time.sleep(0.1 * (attempt + 1)) # Backoff
                continue
        raise Exception("Failed to create item after retries")

    def _guess_category(self, name: str) -> str:
        """Guess category from name using map."""
        name_lower = name.lower()
        for key, val in CATEGORY_MAP.items():
            if key in name_lower:
                return val
        return 'NonFood' # Default safe fallback

    def create_initial_stock_transactions(self, user_id: int):
        """Create opening balance transactions (for inventory import mode)."""
        if not self.affected_item_ids:
            return 0
        
        items_with_stock = Item.query.filter(
            Item.id.in_(self.affected_item_ids),
            Item.current_stock != 0 
        ).all()
        
        for item in items_with_stock:
            # Check if initial transaction exists for this batch
            existing = Transaction.query.filter_by(
                item_id=item.id,
                is_opening_balance=True,
                import_batch_id=self.import_batch.id if self.import_batch else None
            ).first()
            
            if not existing and item.current_stock > 0:
                last_price = 0
                last_tx = Transaction.query.filter_by(
                    item_id=item.id, 
                    is_deleted=False
                ).filter(Transaction.unit_price > 0).order_by(Transaction.transaction_date.desc()).first()
                if last_tx:
                    last_price = last_tx.unit_price

                transaction = Transaction.create_transaction(
                    item_id=item.id,
                    transaction_type='اصلاحی',
                    quantity=item.current_stock,
                    unit_price=last_price,
                    category=item.category,
                    hotel_id=item.hotel_id,
                    user_id=user_id,
                    description='Opening balance - imported from Excel',
                    source='opening_import',
                    direction=1,
                    is_opening_balance=True,
                    import_batch_id=self.import_batch.id if self.import_batch else None
                )
                transaction.transaction_date = get_iran_today()
                db.session.add(transaction)
                self.imported_transactions += 1
        
        db.session.flush()
        return self.imported_transactions
    
    def _detect_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """Auto-detect column mappings for inventory mode."""
        columns = {}
        for col in df.columns:
            col_str = str(col).strip().lower()
            if any(x in col_str for x in ['شرح', 'نام کالا', 'کالا']): columns['name'] = col
            elif 'واحد' in col_str and 'قیمت' not in col_str: columns['unit'] = col
            elif any(x in col_str for x in ['موجودی', 'انبار']) and 'نام' not in col_str: columns['stock'] = col
            elif 'نام انبار' in col_str: columns['warehouse'] = col
            elif any(x in col_str for x in ['هفتگی', 'یک هفته']): columns['weekly'] = col
            elif any(x in col_str for x in ['ماهانه', 'یکماه']): columns['monthly'] = col
            elif any(x in col_str for x in ['قیمت', 'فی']): columns['price'] = col
        return columns

    def _import_sheet(self, excel_file: pd.ExcelFile, sheet_name: str) -> Dict[str, Any]:
        """Import data from a single sheet (Inventory Mode)."""
        sheet_hotel_id = None
        original_hotel_id = self.hotel_id
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            if df.empty: return 0
            
            # Detect hotel from sheet
            sheet_hotel_id = self.sheet_to_hotel_map.get(sheet_name.lower())
            if sheet_hotel_id:
                original_hotel_id = self.hotel_id
                self.hotel_id = sheet_hotel_id
            
            cols = self._detect_columns(df)
            if not cols.get('name'):
                self.warnings.append(f'Sheet {sheet_name}: Name column not found')
                if sheet_hotel_id: self.hotel_id = original_hotel_id
                return 0
            
            # Detect category from sheet name
            default_cat = None
            sheet_lower = sheet_name.lower()
            if 'ghazaei' in sheet_lower or 'غذا' in sheet_name: default_cat = 'Food'
            elif 'behdashti' in sheet_lower or 'بهداشت' in sheet_name: default_cat = 'NonFood'
            
            items_added = 0
            
            for idx, row in df.iterrows():
                item_name = row.get(cols['name'])
                if not item_name or pd.isna(item_name) or str(item_name).strip() in ['شرح', 'نام کالا']:
                    continue
                item_name = str(item_name).strip()
                
                # Category logic
                category = default_cat
                if not category: category = self._guess_category(item_name)
                
                # Create/Get Item
                unit = standardize_unit(row.get(cols.get('unit'), 'عدد'))
                current_stock = clean_number_robust(row.get(cols.get('stock')))
                
                # BUG-FIX: Check existence FIRST, then create only if needed.
                # Also scope query to hotel_id to avoid cross-hotel collisions.
                exist_query = Item.query.filter_by(item_name_fa=item_name)
                if self.hotel_id:
                    exist_query = exist_query.filter_by(hotel_id=self.hotel_id)
                existing = exist_query.first()
                
                if existing:
                    item = existing
                    # BUG-FIX: Actually update stock for existing items (was a no-op 'pass')
                    if current_stock is not None:
                        item.current_stock = current_stock
                    # Update unit if it changed in the new import
                    if unit and unit != item.unit:
                        item.unit = unit
                else:
                    item = self._create_item_safe(item_name, unit, category)
                    if current_stock is not None:
                        item.current_stock = current_stock
                
                if item:
                    self.affected_item_ids.add(item.id)
                    items_added += 1

            db.session.flush()
            self.imported_items += items_added
            
            if sheet_hotel_id: self.hotel_id = original_hotel_id
            
            return {'sheet': sheet_name, 'status': 'success', 'items': items_added}
            
        except Exception as e:
            self.errors.append(f"Sheet {sheet_name}: {str(e)}")
            if sheet_hotel_id: self.hotel_id = original_hotel_id
            return {'sheet': sheet_name, 'status': 'error', 'error': str(e)}

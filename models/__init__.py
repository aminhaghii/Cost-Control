from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .user import User, ROLES, ROLE_LABELS
from .hotel import Hotel
from .item import Item, BASE_UNITS, UNIT_CONVERSIONS
from .transaction import Transaction, TRANSACTION_TYPES, TRANSACTION_DIRECTION, WASTE_REASONS, DEPARTMENTS, APPROVAL_STATUS
from .alert import Alert, ALERT_TYPES, ALERT_STATUS
from .chat_history import ChatHistory
from .audit_log import AuditLog
from .import_batch import ImportBatch
from .user_hotel import UserHotel
from .hotel_sheet_alias import HotelSheetAlias
from .inventory_count import InventoryCount, VARIANCE_REASONS, COUNT_STATUS
from .warehouse_settings import WarehouseSettings

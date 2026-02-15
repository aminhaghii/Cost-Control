"""Data quality validation for strategy analytics."""

from datetime import date, timedelta
import logging

from models import db, Item, Transaction

logger = logging.getLogger(__name__)


class StrategyDataValidator:
    """Validates data quality before analytics run."""

    @staticmethod
    def validate_transactions(days=90):
        """Check common transaction data quality issues for strategy analytics."""
        start_date = date.today() - timedelta(days=days)
        issues = []

        zero_amount = db.session.query(Transaction).filter(
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted != True,
            Transaction.total_amount <= 0,
        ).count()
        if zero_amount > 0:
            issues.append(
                {
                    "type": "zero_or_negative_amount",
                    "count": zero_amount,
                    "severity": "high",
                    "message": f"{zero_amount} تراکنش با مبلغ صفر یا منفی",
                    "action": "این تراکنش‌ها باید بررسی و اصلاح شوند",
                }
            )

        price_mismatch = db.session.query(Transaction).filter(
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted != True,
            Transaction.unit_price == 0,
            Transaction.total_amount > 0,
        ).count()
        if price_mismatch > 0:
            issues.append(
                {
                    "type": "price_mismatch",
                    "count": price_mismatch,
                    "severity": "medium",
                    "message": f"{price_mismatch} تراکنش با قیمت واحد صفر اما مبلغ کل غیرصفر",
                    "action": "احتمال خطای ثبت - بررسی شود",
                }
            )

        consumption_count = db.session.query(Transaction).filter(
            Transaction.transaction_type == "مصرف",
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted != True,
        ).count()
        if consumption_count == 0:
            issues.append(
                {
                    "type": "no_consumption_data",
                    "count": 0,
                    "severity": "critical",
                    "message": "هیچ تراکنش مصرفی در این دوره وجود ندارد",
                    "action": "XYZ و Consumption Trend بدون داده مصرف کار نمی‌کنند - شروع ثبت مصرف کنید",
                }
            )

        items_no_category = db.session.query(Item).filter(
            Item.is_active == True,
            Item.category.is_(None) | (Item.category == ""),
        ).count()
        if items_no_category > 0:
            issues.append(
                {
                    "type": "items_without_category",
                    "count": items_no_category,
                    "severity": "medium",
                    "message": f"{items_no_category} کالای فعال بدون گروه",
                    "action": "Category Mix کامل نخواهد بود - گروه‌ها را تکمیل کنید",
                }
            )

        critical_issues = [i for i in issues if i.get("severity") == "critical"]
        return {
            "is_valid": len(critical_issues) == 0,
            "issues": issues,
            "total_issues": len(issues),
            "critical_issues": len(critical_issues),
        }

    @staticmethod
    def validate_unit_consistency():
        """Placeholder for future unit consistency checks."""
        return {"is_valid": True, "issues": [], "total_issues": 0, "critical_issues": 0}

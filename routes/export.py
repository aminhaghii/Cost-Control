from flask import Blueprint, send_file, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from services import ParetoService, ABCService, ExcelReportGenerator
from datetime import datetime
from utils.timezone import get_iran_now
import io

export_bp = Blueprint('export', __name__, url_prefix='/export')

@export_bp.route('/pareto-excel')
@login_required
def download_pareto_excel():
    """
    P1-1: Export with hotel scoping enforcement
    Only exports data from hotels user has access to
    """
    mode = request.args.get('mode', 'خرید')
    category = request.args.get('category', 'Food')
    days = request.args.get('days', 30, type=int)
    hotel_id = request.args.get('hotel_id', type=int)
    
    # P1-1: Validate hotel access if hotel_id provided
    if hotel_id:
        from services.hotel_scope_service import user_can_access_hotel
        if not user_can_access_hotel(current_user, hotel_id):
            current_app.logger.warning(f'User {current_user.id} attempted to export hotel {hotel_id} data without access')
            return "Access denied", 403
    
    # BUG-002 Fix: Services handle scoping internally via user parameter
    # Excel generator doesn't need user/hotel_id - it uses pre-scoped services
    pareto_service = ParetoService()
    abc_service = ABCService()
    excel_gen = ExcelReportGenerator(pareto_service, abc_service)
    
    wb = excel_gen.generate_pareto_report(mode, category, days)
    output = excel_gen.save_to_bytes(wb)
    
    timestamp = get_iran_now().strftime('%Y%m%d_%H%M%S')
    filename = f"Pareto_Report_{category}_{timestamp}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@export_bp.route('/abc-excel')
@login_required
def download_abc_excel():
    """
    P1-1: Export with hotel scoping enforcement
    Only exports data from hotels user has access to
    """
    mode = request.args.get('mode', 'خرید')
    category = request.args.get('category', 'Food')
    days = request.args.get('days', 30, type=int)
    hotel_id = request.args.get('hotel_id', type=int)
    
    # P1-1: Validate hotel access if hotel_id provided
    if hotel_id:
        from services.hotel_scope_service import user_can_access_hotel
        if not user_can_access_hotel(current_user, hotel_id):
            current_app.logger.warning(f'User {current_user.id} attempted to export hotel {hotel_id} data without access')
            return "Access denied", 403
    
    # BUG-002 Fix: Services handle scoping internally via user parameter
    # Excel generator doesn't need user/hotel_id - it uses pre-scoped services
    pareto_service = ParetoService()
    abc_service = ABCService()
    excel_gen = ExcelReportGenerator(pareto_service, abc_service)
    
    wb = excel_gen.generate_pareto_report(mode, category, days)
    output = excel_gen.save_to_bytes(wb)
    
    timestamp = get_iran_now().strftime('%Y%m%d_%H%M%S')
    filename = f"ABC_Report_{category}_{timestamp}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

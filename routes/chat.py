"""
Chat API Routes for Analytics Chatbot
P0-5: CSRF protected, rate limited, audit logged
"""

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from services import ChatService
from models import Item, Transaction, db
from sqlalchemy import func
from datetime import datetime
from utils.timezone import get_iran_now, get_iran_today
import logging

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')
logger = logging.getLogger(__name__)

# Initialize chat service
chat_service = ChatService()


def log_chat_action(action, user_id, details=None):
    """
    P0-5: Audit logging for chat actions (without storing sensitive content)
    """
    logger.info(f"CHAT_AUDIT: action={action}, user_id={user_id}, details={details or 'none'}")


@chat_bp.route('/')
@login_required
def chat_page():
    """Render the chat interface"""
    return render_template('chat/index.html')


@chat_bp.route('/api/message', methods=['POST'])
@login_required
def process_message():
    """
    Process a chat message and return response with user memory
    P0-5: Now protected by CSRF (not exempted)
    """
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({
                'success': False,
                'response': 'لطفاً پیام خود را وارد کنید.',
                'suggestions': ['کمک', 'خلاصه وضعیت']
            })
        
        # P0-5: Audit log (message length only, not content for privacy)
        log_chat_action('message', current_user.id, f'len={len(message)}')
        
        # Process the message through chat service with user_id for memory
        result = chat_service.process_message(message, user_id=current_user.id, user=current_user)
        
        # Add timestamp
        result['timestamp'] = get_iran_now().strftime('%H:%M')
        result['user'] = current_user.full_name or current_user.username
        
        return jsonify(result)
    
    except Exception as e:
        # P0-5: Log errors (without sensitive data)
        log_chat_action('error', current_user.id, f'type={type(e).__name__}')
        logger.error(f"Chat error for user {current_user.id}: {type(e).__name__}")
        return jsonify({
            'success': False,
            'response': f'خطا در پردازش: {str(e)}',
            'suggestions': ['کمک']
        }), 500


@chat_bp.route('/api/history')
@login_required
def get_history():
    """Get chat history for current user"""
    try:
        limit = request.args.get('limit', 50, type=int)
        history = chat_service.get_history(current_user.id, limit)
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@chat_bp.route('/api/clear-history', methods=['POST'])
@login_required
def clear_history():
    """
    Clear chat history for current user
    P0-5: Audit logged
    """
    try:
        # P0-5: Audit log
        log_chat_action('clear_history', current_user.id)
        result = chat_service.clear_history(current_user.id)
        return jsonify(result)
    except Exception as e:
        log_chat_action('clear_history_error', current_user.id, f'type={type(e).__name__}')
        return jsonify({'success': False, 'message': str(e)}), 500


@chat_bp.route('/api/suggestions')
@login_required
def get_suggestions():
    """Get initial suggestions for the user"""
    return jsonify({
        'suggestions': [
            'خلاصه وضعیت',
            'تحلیل پارتو',
            'اقلام کلاس A',
            'برترین خریدها',
            'مقایسه دسته‌ها',
            'هشدارها',
            'توصیه‌ها',
            'کمک'
        ]
    })


@chat_bp.route('/api/quick-stats')
@login_required
def get_quick_stats():
    """Get quick stats for chat header"""
    try:
        from models.item import Item
        from models.transaction import Transaction
        from sqlalchemy import func
        
        total_items = Item.query.count()
        today_trans = Transaction.query.filter(
            func.date(Transaction.transaction_date) == get_iran_today()
        ).count()
        
        return jsonify({
            'total_items': total_items,
            'today_transactions': today_trans
        })
    except Exception:
        return jsonify({'total_items': 0, 'today_transactions': 0})

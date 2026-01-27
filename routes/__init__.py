from .auth import auth_bp
from .dashboard import dashboard_bp
from .transactions import transactions_bp
from .reports import reports_bp
from .export import export_bp
from .ai_analysis import ai_bp
from .chat import chat_bp
from .api_docs import api_docs_bp
from .admin import admin_bp
from .security import security_bp
from .warehouse import warehouse_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(api_docs_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(warehouse_bp)

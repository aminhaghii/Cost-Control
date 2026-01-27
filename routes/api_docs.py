"""
API Documentation Routes
Swagger UI for API documentation
"""

from flask import Blueprint, send_from_directory, render_template_string
import os

api_docs_bp = Blueprint('api_docs', __name__, url_prefix='/api-docs')


@api_docs_bp.route('/')
def swagger_ui():
    """Render Swagger UI"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>API Documentation - سیستم مدیریت موجودی هتل</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css">
    <style>
        body { margin: 0; padding: 0; }
        .swagger-ui .topbar { display: none; }
        .swagger-ui .info { margin: 20px 0; }
        .swagger-ui .info .title { font-family: 'Vazirmatn', sans-serif; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {
            SwaggerUIBundle({
                url: "/static/swagger.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true
            });
        };
    </script>
</body>
</html>
    ''')


@api_docs_bp.route('/spec')
def get_spec():
    """Return OpenAPI specification"""
    return send_from_directory('static', 'swagger.json')

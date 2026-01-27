"""
Chat History Model for storing conversation memory per user
"""
from datetime import datetime
from models import db


class ChatHistory(db.Model):
    """Model to store chat messages for each user"""
    __tablename__ = 'chat_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('chat_messages', lazy='dynamic'))
    
    def __repr__(self):
        return f'<ChatHistory {self.id} - User {self.user_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def get_user_history(cls, user_id, limit=50, offset=0):
        """Get recent chat history for a user with pagination"""
        return cls.query.filter_by(user_id=user_id)\
            .order_by(cls.created_at.desc())\
            .offset(offset)\
            .limit(limit)\
            .all()[::-1]  # Reverse to get chronological order
    
    @classmethod
    def get_history_count(cls, user_id):
        """Get total message count for a user"""
        return cls.query.filter_by(user_id=user_id).count()
    
    @classmethod
    def add_message(cls, user_id, role, content):
        """Add a new message to history"""
        message = cls(user_id=user_id, role=role, content=content)
        db.session.add(message)
        db.session.commit()
        return message
    
    @classmethod
    def clear_user_history(cls, user_id):
        """Clear all chat history for a user"""
        cls.query.filter_by(user_id=user_id).delete()
        db.session.commit()
    
    @classmethod
    def get_context_messages(cls, user_id, max_messages=10):
        """Get messages formatted for LLM context window"""
        messages = cls.get_user_history(user_id, limit=max_messages)
        return [{'role': m.role, 'content': m.content} for m in messages]

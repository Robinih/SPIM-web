from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta

db = SQLAlchemy()

def ph_time():
    return datetime.utcnow() + timedelta(hours=8)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    municipality = db.Column(db.String(100), nullable=False)
    street_barangay = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='farmer')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

class DetectionRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    insect_name = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    image_file = db.Column(db.String(255), nullable=False) # Path to image
    timestamp = db.Column(db.DateTime, default=ph_time)
    is_beneficial = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref=db.backref('detections', lazy=True, cascade="all, delete-orphan"))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    level = db.Column(db.String(20), nullable=False, default='Low') # Low, Medium, High
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, index=True, default=ph_time)

    # Relationship
    user = db.relationship('User', backref=db.backref('notifications', lazy=True, cascade="all, delete-orphan"))

class CountingRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_count = db.Column(db.Integer, nullable=False)
    image_file = db.Column(db.String(255), nullable=False) # Path to image
    timestamp = db.Column(db.DateTime, default=ph_time)
    breakdown = db.Column(db.Text, nullable=True) # JSON string

    user = db.relationship('User', backref=db.backref('counts', lazy=True, cascade="all, delete-orphan"))

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    insect_name = db.Column(db.String(100), nullable=True) # Optional user provided name
    description = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='Pending') # Pending, Read, Resolved
    timestamp = db.Column(db.DateTime, default=ph_time)

    user = db.relationship('User', backref=db.backref('recommendations', lazy=True, cascade="all, delete-orphan"))

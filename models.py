from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    settings = db.relationship("BotSettings", backref="user", uselist=False)
    trades = db.relationship("Trade", backref="user", lazy=True)

class BotSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    broker = db.Column(db.String(20), default="alpaca")
    alpaca_api_key = db.Column(db.String(256))
    alpaca_secret_key = db.Column(db.String(256))
    alpaca_paper = db.Column(db.Boolean, default=True)
    rh_username = db.Column(db.String(120))
    rh_password = db.Column(db.String(256))
    anthropic_api_key = db.Column(db.String(256))
    max_position_usd = db.Column(db.Float, default=100.0)
    max_daily_loss_usd = db.Column(db.Float, default=50.0)
    run_interval_minutes = db.Column(db.Integer, default=60)
    dry_run = db.Column(db.Boolean, default=True)
    bot_active = db.Column(db.Boolean, default=False)

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    action = db.Column(db.String(4), nullable=False)  # buy/sell
    amount_usd = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text)
    result = db.Column(db.Text)
    dry_run = db.Column(db.Boolean, default=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

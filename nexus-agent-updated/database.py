from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt
from datetime import datetime, date

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    plan = db.Column(db.String(20), default='free')  # free, pro, enterprise
    is_admin = db.Column(db.Boolean, default=False)   # Admin flag — unlimited access
    runs_today = db.Column(db.Integer, default=0)
    last_run_date = db.Column(db.Date, default=date.today)
    total_runs = db.Column(db.Integer, default=0)
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    stripe_subscription_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def get_daily_limit(self):
        if self.is_admin:
            return None  # None = truly unlimited
        limits = {'free': 15, 'pro': 200, 'enterprise': 9999}
        return limits.get(self.plan, 15)

    def can_run_agent(self):
        if self.is_admin:
            return True  # Admins always bypass limits
        today = date.today()
        if self.last_run_date != today:
            self.runs_today = 0
            self.last_run_date = today
            db.session.commit()
        return self.runs_today < self.get_daily_limit()

    def increment_run(self):
        today = date.today()
        if self.last_run_date != today:
            self.runs_today = 0
            self.last_run_date = today
        self.runs_today += 1
        self.total_runs += 1
        db.session.commit()

    def runs_remaining(self):
        if self.is_admin:
            return '∞'
        today = date.today()
        if self.last_run_date != today:
            return self.get_daily_limit()
        return max(0, self.get_daily_limit() - self.runs_today)

    def to_dict(self):
        limit = self.get_daily_limit()
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'plan': 'admin' if self.is_admin else self.plan,
            'is_admin': self.is_admin,
            'runs_today': self.runs_today,
            'daily_limit': limit if limit is not None else '∞',
            'runs_remaining': self.runs_remaining(),
            'total_runs': self.total_runs,
        }

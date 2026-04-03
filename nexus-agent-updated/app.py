import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from database import db, bcrypt, User
from agent import run_agent
from payments import create_checkout_session, handle_webhook, PLANS, cancel_subscription
import stripe

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'nexus-dev-secret-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nexus.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
bcrypt.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth'
login_manager.login_message = ''

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables on startup
with app.app_context():
    db.create_all()
    os.makedirs("agent_outputs", exist_ok=True)

# ================================================================
# PUBLIC ROUTES
# ================================================================

@app.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/auth')
def auth():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('auth.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html', plans=PLANS,
                           pub_key=os.getenv('STRIPE_PUBLISHABLE_KEY', ''))

# ================================================================
# AUTH ROUTES
# ================================================================

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email', '').strip().lower()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not email or not username or not password:
        return jsonify({'success': False, 'message': 'All fields required'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already registered'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already taken'}), 400

    user = User(email=email, username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)
    return jsonify({'success': True, 'redirect': url_for('dashboard')})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    login_user(user, remember=True)
    return jsonify({'success': True, 'redirect': url_for('dashboard')})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))

# ================================================================
# DASHBOARD
# ================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

# ================================================================
# AGENT API
# ================================================================

@app.route('/api/run-agent', methods=['POST'])
@login_required
def run_agent_endpoint():
    if not current_user.can_run_agent():
        return jsonify({
            'success': False,
            'message': f'Daily limit reached ({current_user.get_daily_limit()} runs/day on {current_user.plan} plan). Upgrade for more!',
            'upgrade': True
        }), 429

    data = request.json
    message = data.get('message', '').strip()

    if not message:
        return jsonify({'success': False, 'message': 'No message provided'}), 400

    current_user.increment_run()

    try:
        result = run_agent(message)
        result['user'] = current_user.to_dict()
        result['success'] = True
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/user-stats')
@login_required
def user_stats():
    return jsonify(current_user.to_dict())

# ================================================================
# PAYMENT ROUTES
# ================================================================

@app.route('/api/create-checkout', methods=['POST'])
@login_required
def create_checkout():
    data = request.json
    plan = data.get('plan')

    try:
        base_url = os.getenv('BASE_URL', request.host_url.rstrip('/'))
        checkout_session = create_checkout_session(
            plan_name=plan,
            user_email=current_user.email,
            user_id=current_user.id,
            base_url=base_url
        )
        return jsonify({'success': True, 'url': checkout_session.url})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Payment error: {str(e)}'}), 500

@app.route('/payment/success')
@login_required
def payment_success():
    session_id = request.args.get('session_id')
    if session_id:
        try:
            import stripe as st
            st.api_key = os.getenv('STRIPE_SECRET_KEY', '')
            checkout_session = st.checkout.Session.retrieve(session_id)
            plan = checkout_session.metadata.get('plan', 'pro')
            subscription_id = checkout_session.subscription

            current_user.plan = plan
            current_user.stripe_subscription_id = subscription_id
            current_user.stripe_customer_id = checkout_session.customer
            db.session.commit()
        except Exception as e:
            print(f"Error updating plan: {e}")

    return render_template('success.html', user=current_user)

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Stripe webhook — handles subscription events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = handle_webhook(payload, sig_header)
    except ValueError as e:
        return str(e), 400

    # Handle subscription events
    if event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        user = User.query.filter_by(stripe_subscription_id=subscription['id']).first()
        if user:
            user.plan = 'free'
            user.stripe_subscription_id = None
            db.session.commit()

    elif event['type'] == 'invoice.payment_failed':
        subscription_id = event['data']['object'].get('subscription')
        if subscription_id:
            user = User.query.filter_by(stripe_subscription_id=subscription_id).first()
            if user:
                user.plan = 'free'
                db.session.commit()

    return '', 200

@app.route('/api/cancel-subscription', methods=['POST'])
@login_required
def cancel_sub():
    if not current_user.stripe_subscription_id:
        return jsonify({'success': False, 'message': 'No active subscription'}), 400
    try:
        cancel_subscription(current_user.stripe_subscription_id)
        current_user.plan = 'free'
        current_user.stripe_subscription_id = None
        db.session.commit()
        return jsonify({'success': True, 'message': 'Subscription cancelled'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ================================================================
# ADMIN ROUTES (is_admin required)
# ================================================================

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin.html', users=users, current_user=current_user)

@app.route('/api/admin/promote', methods=['POST'])
@login_required
@admin_required
def admin_promote():
    """Promote any user to admin."""
    data = request.json
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    user.is_admin = True
    user.plan = 'enterprise'
    db.session.commit()
    return jsonify({'success': True, 'message': f'{user.username} is now an admin'})

@app.route('/api/admin/demote', methods=['POST'])
@login_required
@admin_required
def admin_demote():
    """Remove admin from a user."""
    data = request.json
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot demote yourself'}), 400
    user.is_admin = False
    user.plan = 'free'
    db.session.commit()
    return jsonify({'success': True, 'message': f'{user.username} demoted to free'})

@app.route('/api/admin/set-plan', methods=['POST'])
@login_required
@admin_required
def admin_set_plan():
    """Change any user plan."""
    data = request.json
    email = data.get('email', '').strip().lower()
    plan = data.get('plan', 'free')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if plan not in ('free', 'pro', 'enterprise'):
        return jsonify({'success': False, 'message': 'Invalid plan'}), 400
    user.plan = plan
    db.session.commit()
    return jsonify({'success': True, 'message': f'{user.username} plan set to {plan}'})

@app.route('/api/admin/stats')
@login_required
@admin_required
def admin_stats():
    """Global platform stats."""
    total_users = User.query.count()
    admin_users = User.query.filter_by(is_admin=True).count()
    pro_users = User.query.filter_by(plan='pro').count()
    enterprise_users = User.query.filter_by(plan='enterprise').count()
    from sqlalchemy import func
    total_runs = db.session.query(func.sum(User.total_runs)).scalar() or 0
    return jsonify({
        'total_users': total_users,
        'admin_users': admin_users,
        'pro_users': pro_users,
        'enterprise_users': enterprise_users,
        'free_users': total_users - pro_users - enterprise_users - admin_users,
        'total_runs': total_runs,
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

"""Flask API backend for the AI Trading Bot web app."""
import os
import bcrypt
import stripe
from datetime import timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from models import db, User, BotSettings, Trade
import bot_manager

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

app = Flask(__name__, static_folder="static", static_url_path="/")
_db_url = os.environ.get("DATABASE_URL", "sqlite:///trading.db")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET", "change-me-in-production-use-long-random-string")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=7)

CORS(app, origins="*")
db.init_app(app)
jwt = JWTManager(app)

with app.app_context():
    db.create_all()


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(email=email, password_hash=pw_hash)
    db.session.add(user)
    db.session.flush()
    settings = BotSettings(user_id=user.id)
    db.session.add(settings)
    db.session.commit()
    token = create_access_token(identity=user.id)
    return jsonify({"token": token, "email": user.email}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return jsonify({"error": "Invalid credentials"}), 401
    token = create_access_token(identity=user.id)
    return jsonify({"token": token, "email": user.email})


# ── Settings ──────────────────────────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
@jwt_required()
def get_settings():
    uid = get_jwt_identity()
    s = BotSettings.query.filter_by(user_id=uid).first()
    if not s:
        return jsonify({}), 404
    return jsonify({
        "broker": s.broker,
        "alpaca_api_key": s.alpaca_api_key or "",
        "alpaca_secret_key": "***" if s.alpaca_secret_key else "",
        "alpaca_paper": s.alpaca_paper,
        "rh_username": s.rh_username or "",
        "anthropic_api_key": "***" if s.anthropic_api_key else "",
        "max_position_usd": s.max_position_usd,
        "max_daily_loss_usd": s.max_daily_loss_usd,
        "run_interval_minutes": s.run_interval_minutes,
        "dry_run": s.dry_run,
    })


@app.route("/api/settings", methods=["PUT"])
@jwt_required()
def update_settings():
    uid = get_jwt_identity()
    s = BotSettings.query.filter_by(user_id=uid).first()
    data = request.json
    if "broker" in data: s.broker = data["broker"]
    if "alpaca_api_key" in data: s.alpaca_api_key = data["alpaca_api_key"]
    if "alpaca_secret_key" in data and data["alpaca_secret_key"] != "***":
        s.alpaca_secret_key = data["alpaca_secret_key"]
    if "alpaca_paper" in data: s.alpaca_paper = data["alpaca_paper"]
    if "rh_username" in data: s.rh_username = data["rh_username"]
    if "rh_password" in data and data["rh_password"] != "***":
        s.rh_password = data["rh_password"]
    if "anthropic_api_key" in data and data["anthropic_api_key"] != "***":
        s.anthropic_api_key = data["anthropic_api_key"]
    if "max_position_usd" in data: s.max_position_usd = float(data["max_position_usd"])
    if "max_daily_loss_usd" in data: s.max_daily_loss_usd = float(data["max_daily_loss_usd"])
    if "run_interval_minutes" in data: s.run_interval_minutes = int(data["run_interval_minutes"])
    if "dry_run" in data: s.dry_run = bool(data["dry_run"])
    db.session.commit()
    return jsonify({"success": True})


# ── Portfolio ─────────────────────────────────────────────────────────────────

@app.route("/api/portfolio", methods=["GET"])
@jwt_required()
def get_portfolio():
    uid = get_jwt_identity()
    s = BotSettings.query.filter_by(user_id=uid).first()
    if not s:
        return jsonify({"error": "No settings configured"}), 400
    try:
        if s.broker == "alpaca" and s.alpaca_api_key:
            from broker import get_alpaca_portfolio
            data = get_alpaca_portfolio(s.alpaca_api_key, s.alpaca_secret_key, s.alpaca_paper)
        elif s.broker == "robinhood" and s.rh_username:
            from broker import get_rh_portfolio
            data = get_rh_portfolio(s.rh_username, s.rh_password)
        else:
            return jsonify({"error": "Broker not configured"}), 400
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Trades ────────────────────────────────────────────────────────────────────

@app.route("/api/trades", methods=["GET"])
@jwt_required()
def get_trades():
    uid = get_jwt_identity()
    trades = Trade.query.filter_by(user_id=uid).order_by(Trade.timestamp.desc()).limit(50).all()
    return jsonify([{
        "id": t.id,
        "symbol": t.symbol,
        "action": t.action,
        "amount_usd": t.amount_usd,
        "reason": t.reason,
        "dry_run": t.dry_run,
        "timestamp": t.timestamp.isoformat(),
    } for t in trades])


# ── Stripe ────────────────────────────────────────────────────────────────────

@app.route("/api/subscription/status", methods=["GET"])
@jwt_required()
def subscription_status():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    return jsonify({
        "status": user.subscription_status,
        "active": user.subscription_status in ("active", "trialing"),
    })


@app.route("/api/subscription/checkout", methods=["POST"])
@jwt_required()
def create_checkout():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    price_id = os.environ.get("STRIPE_PRICE_ID", "")
    if not price_id:
        return jsonify({"error": "Stripe not configured"}), 500

    # Reuse or create Stripe customer
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email)
        user.stripe_customer_id = customer.id
        db.session.commit()

    base_url = request.headers.get("Origin", "https://web-production-57f2.up.railway.app")
    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        subscription_data={"trial_period_days": 3},
        success_url=base_url + "/?subscribed=true",
        cancel_url=base_url + "/?canceled=true",
    )
    return jsonify({"url": session.url})


@app.route("/api/subscription/portal", methods=["POST"])
@jwt_required()
def billing_portal():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    if not user.stripe_customer_id:
        return jsonify({"error": "No billing account"}), 400
    base_url = request.headers.get("Origin", "https://web-production-57f2.up.railway.app")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=base_url + "/",
    )
    return jsonify({"url": session.url})


@app.route("/api/webhook/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_secret)
    except Exception:
        return jsonify({"error": "Invalid signature"}), 400

    sub = event["data"]["object"]
    customer_id = sub.get("customer")
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return jsonify({}), 200

    if event["type"] in ("customer.subscription.created", "customer.subscription.updated"):
        user.stripe_subscription_id = sub.get("id")
        stripe_status = sub.get("status")
        if stripe_status == "active":
            user.subscription_status = "active"
        elif stripe_status == "trialing":
            user.subscription_status = "trialing"
        else:
            user.subscription_status = "inactive"
    elif event["type"] == "customer.subscription.deleted":
        user.subscription_status = "canceled"

    db.session.commit()
    return jsonify({"received": True})


# ── Bot control ───────────────────────────────────────────────────────────────

@app.route("/api/bot/start", methods=["POST"])
@jwt_required()
def start_bot():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    if user.subscription_status not in ("active", "trialing"):
        return jsonify({"error": "subscription_required"}), 402
    s = BotSettings.query.filter_by(user_id=uid).first()
    if not s or (not s.alpaca_api_key and not s.rh_username):
        return jsonify({"error": "Connect a brokerage account first"}), 400
    ok = bot_manager.start_bot(uid, s)
    if not ok:
        return jsonify({"error": "Bot already running"}), 409
    s.bot_active = True
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/bot/stop", methods=["POST"])
@jwt_required()
def stop_bot():
    uid = get_jwt_identity()
    bot_manager.stop_bot(uid)
    s = BotSettings.query.filter_by(user_id=uid).first()
    if s:
        s.bot_active = False
        db.session.commit()
    return jsonify({"success": True})


@app.route("/api/bot/status", methods=["GET"])
@jwt_required()
def bot_status():
    uid = get_jwt_identity()
    return jsonify(bot_manager.get_status(uid))


# ── Serve React frontend ───────────────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path and (app.static_folder / path if False else True):
        import os
        fp = os.path.join(app.static_folder, path)
        if os.path.exists(fp):
            return app.send_static_file(path)
    return app.send_static_file("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)

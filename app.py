import json
import math
import os
import secrets
import threading
import time
from datetime import datetime
from functools import wraps

from flask import (Flask, abort, flash, redirect, render_template_string,
                   request, session, url_for)
from flask_socketio import SocketIO
from jinja2 import DictLoader
from sqlalchemy import (Boolean, Column, DateTime, Float, Integer, String,
                        Text, create_engine)
from sqlalchemy.orm import declarative_base, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

# ---------------------------
# Config
# ---------------------------
SECRET_KEY = os.getenv("OPSPULSE_SECRET_KEY", secrets.token_hex(16))
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ---------------------------
# Database setup (SQLite)
# ---------------------------
Base = declarative_base()
engine = create_engine("sqlite:///opspulse.db", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def db_session():
    """Provide a new SQLAlchemy session."""
    return SessionLocal()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(16), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    threshold = Column(Float, nullable=False)
    direction = Column(String(8), default="above")
    created_at = Column(DateTime, default=datetime.utcnow)


class Audit(Base):
    __tablename__ = "audit"

    id = Column(Integer, primary_key=True)
    actor = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)

# Seed admin if not present
with db_session() as session:
    if not session.query(User).filter_by(username=ADMIN_USER).first():
        session.add(
            User(
                username=ADMIN_USER,
                password_hash=generate_password_hash(ADMIN_PASS),
                is_admin=True,
            )
        )
        session.add(Alert(name="cpu_utilization", threshold=80.0, direction="above"))
        session.add(Alert(name="error_rate", threshold=5.0, direction="above"))
        session.commit()

# ---------------------------
# Helpers
# ---------------------------

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.path))
        return func(*args, **kwargs)

    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = session.get("user")
        if not user or not user.get("is_admin"):
            abort(403)
        return func(*args, **kwargs)

    return wrapper


def audit(actor, action, details=""):
    with db_session() as session:
        session.add(Audit(actor=actor, action=action, details=details))
        session.commit()


# ---------------------------
# Templates (inline for single-file demo)
# ---------------------------
BASE_HTML = """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>OpsPulse</title>
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
  <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap\" rel=\"stylesheet\">
  <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>
  <script src=\"https://cdn.socket.io/4.7.5/socket.io.min.js\" integrity=\"sha384-lr0gk3y1Qx8dJq3x1k96k1J8yY3yq2Qv8n3Q3xkR66CwZ3e6YQZ1e9Gf3qfC8Wv3\" crossorigin=\"anonymous\"></script>
  <style>
    :root{ --brand:#200953; }
    *{ box-sizing:border-box; }
    body{ margin:0; font-family:Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background:#0f1020; color:#eaeaf5; }
    header{ background:var(--brand); padding:14px 20px; display:flex; align-items:center; justify-content:space-between; box-shadow:0 4px 20px rgba(0,0,0,0.25); position:sticky; top:0; z-index:10; }
    .logo{ font-weight:800; letter-spacing:0.4px; }
    a, .btn{ color:#fff; text-decoration:none; }
    .btn{ background:#37206d; padding:10px 14px; border-radius:12px; border:1px solid rgba(255,255,255,0.1); display:inline-block; }
    .btn:hover{ background:#4a2a90; }
    .wrap{ max-width:1100px; margin:24px auto; padding:0 16px; }
    .card{ background:#171833; border:1px solid #2a2c55; border-radius:16px; padding:18px; box-shadow:0 8px 30px rgba(0,0,0,0.25); }
    .grid{ display:grid; grid-template-columns:1fr; gap:16px; }
    @media(min-width:900px){ .grid{ grid-template-columns: 2fr 1fr; } }
    .muted{ color:#b6b6ca; font-size:14px; }
    input, select{ width:100%; padding:10px; border-radius:12px; border:1px solid #2a2c55; background:#12122a; color:#eaeaf5; }
    label{ font-size:14px; color:#cfd0ff; }
    .row{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    table{ width:100%; border-collapse:collapse; }
    th, td{ text-align:left; padding:8px 6px; border-bottom:1px solid #2a2c55; font-size:14px; }
    .pill{ display:inline-block; padding:4px 8px; border-radius:999px; background:#2a2c55; font-size:12px; }
    .flash{ background:#26304f; border:1px solid #3a4c82; padding:10px 12px; border-radius:10px; margin:10px 0; }
  </style>
</head>
<body>
  <header>
    <div class=\"logo\">⚡ OpsPulse</div>
    <nav>
      {% if current_user %}
        <span class=\"muted\" style=\"margin-right:8px;\">Hi, {{ current_user.username }}{% if current_user.is_admin %} (admin){% endif %}</span>
        <a class=\"btn\" href=\"{{ url_for('dashboard') }}\">Dashboard</a>
        {% if current_user.is_admin %}
          <a class=\"btn\" href=\"{{ url_for('admin') }}\" style=\"margin-left:6px;\">Admin</a>
        {% endif %}
        <a class=\"btn\" href=\"{{ url_for('logout') }}\" style=\"margin-left:6px;\">Logout</a>
      {% else %}
        <a class=\"btn\" href=\"{{ url_for('login') }}\">Login</a>
        <a class=\"btn\" href=\"{{ url_for('register') }}\" style=\"margin-left:6px;\">Register</a>
      {% endif %}
    </nav>
  </header>
  <div class=\"wrap\">
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for m in messages %}<div class=\"flash\">{{ m }}</div>{% endfor %}
      {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
  </div>
</body>
</html>
"""

INDEX_HTML = """
{% extends "base.html" %}
{% block content %}
<div class=\"grid\">
  <div class=\"card\">
    <h2 style=\"margin-top:0\">Live Metrics</h2>
    <canvas id=\"metricChart\" height=\"120\"></canvas>
    <div class=\"muted\" style=\"margin-top:8px;\">Streaming via WebSockets. Threshold breaches trigger red alerts.</div>
  </div>
  <div class=\"card\">
    <h3 style=\"margin-top:0\">Current Thresholds</h3>
    <table>
      <tr><th>Metric</th><th>Direction</th><th>Threshold</th></tr>
      {% for a in alerts %}
      <tr><td>{{ a.name }}</td><td>{{ a.direction }}</td><td>{{ '%.2f'|format(a.threshold) }}</td></tr>
      {% endfor %}
    </table>
    <div class=\"muted\" style=\"margin-top:10px;\">Admin can adjust thresholds in the Admin page.</div>
  </div>
</div>

<div class=\"grid\" style=\"margin-top:16px;\">
  <div class=\"card\">
    <h3 style=\"margin-top:0\">Last 25 Metrics (db)</h3>
    <table>
      <tr><th>When</th><th>Metric</th><th>Value</th><th>Unit</th></tr>
      {% for m in metrics %}
      <tr>
        <td>{{ m.created_at.strftime('%H:%M:%S') }}</td>
        <td>{{ m.name }}</td>
        <td>{{ '%.2f'|format(m.value) }}</td>
        <td>{{ m.unit }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>
  <div class=\"card\">
    <h3 style=\"margin-top:0\">Recent Audit Log</h3>
    <table>
      <tr><th>When</th><th>Actor</th><th>Action</th><th>Details</th></tr>
      {% for a in audits %}
      <tr>
        <td>{{ a.created_at.strftime('%H:%M:%S') }}</td>
        <td>{{ a.actor }}</td>
        <td><span class=\"pill\">{{ a.action }}</span></td>
        <td class=\"muted\">{{ a.details }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>
</div>

<script>
const socket = io();
let ctx = document.getElementById('metricChart').getContext('2d');
let labels = [];
let cpu = [];
let err = [];

const chart = new Chart(ctx, {
  type: 'line',
  data: { labels, datasets: [
    { label: 'cpu_utilization %', data: cpu },
    { label: 'error_rate %', data: err }
  ]},
  options: { animation:false, responsive:true, scales:{ y:{ beginAtZero:true } } }
});

socket.on('metric', (payload) => {
  const d = JSON.parse(payload);
  const t = new Date(d.t).toLocaleTimeString();
  labels.push(t);
  if(labels.length>60){ labels.shift(); cpu.shift(); err.shift(); }
  if(d.name==='cpu_utilization'){
    cpu.push(d.value);
    if(err.length < cpu.length){ err.push(err.length ? err[err.length-1] : 0); }
  }
  if(d.name==='error_rate'){
    err.push(d.value);
    if(cpu.length < err.length){ cpu.push(cpu.length ? cpu[cpu.length-1] : 0); }
  }
  chart.update();
});

socket.on('alert', (payload)=>{
  const d = JSON.parse(payload);
  alert(`[ALERT] ${d.name} ${d.direction} ${d.threshold}: observed ${d.value.toFixed(2)}`);
});
</script>
{% endblock %}
"""

AUTH_HTML = """
{% extends "base.html" %}
{% block content %}
<div class=\"grid\">
  <div class=\"card\">
    <h2 style=\"margin-top:0\">{{ title }}</h2>
    <form method=\"post\">
      <div class=\"row\">
        <div>
          <label>Username</label>
          <input name=\"username\" required>
        </div>
        <div>
          <label>Password</label>
          <input type=\"password\" name=\"password\" required>
        </div>
      </div>
      <div style=\"margin-top:10px;\">
        <button class=\"btn\" type=\"submit\">{{ btn }}</button>
      </div>
    </form>
  </div>
  <div class=\"card\">
    <h3>About OpsPulse</h3>
    <p class=\"muted\">Real-time operations dashboard demo with role-based access, audit logging, and alert thresholds. Built with Flask-SocketIO & SQLite.</p>
  </div>
</div>
{% endblock %}
"""

ADMIN_HTML = """
{% extends "base.html" %}
{% block content %}
<div class=\"grid\">
  <div class=\"card\">
    <h2 style=\"margin-top:0\">Thresholds</h2>
    <form method=\"post\" action=\"{{ url_for('update_thresholds') }}\">
      <table>
        <tr><th>Metric</th><th>Direction</th><th>Threshold</th></tr>
        {% for a in alerts %}
        <tr>
          <td>{{ a.name }}</td>
          <td>
            <select name=\"direction_{{ a.id }}\">
              <option value=\"above\" {% if a.direction=='above' %}selected{% endif %}>above</option>
              <option value=\"below\" {% if a.direction=='below' %}selected{% endif %}>below</option>
            </select>
          </td>
          <td><input type=\"number\" step=\"0.01\" name=\"threshold_{{ a.id }}\" value=\"{{ a.threshold }}\"></td>
        </tr>
        {% endfor %}
      </table>
      <div style=\"margin-top:10px;\"><button class=\"btn\">Save</button></div>
    </form>
  </div>
  <div class=\"card\">
    <h2 style=\"margin-top:0\">Manual Metric Inject</h2>
    <form method=\"post\" action=\"{{ url_for('inject_metric') }}\">
      <div class=\"row\">
        <div>
          <label>Metric Name</label>
          <select name=\"name\">
            <option>cpu_utilization</option>
            <option>error_rate</option>
          </select>
        </div>
        <div>
          <label>Value</label>
          <input type=\"number\" step=\"0.01\" name=\"value\" required>
        </div>
      </div>
      <div class=\"row\" style=\"margin-top:8px;\">
        <div>
          <label>Unit</label>
          <input name=\"unit\" value=\"%\">
        </div>
        <div>
          <label>&nbsp;</label>
          <button class=\"btn\" style=\"width:100%\">Send</button>
        </div>
      </div>
    </form>
  </div>
</div>
{% endblock %}
"""

app.jinja_loader = DictLoader({"base.html": BASE_HTML})

# ---------------------------
# Routes
# ---------------------------


@app.context_processor
def inject_user():
    user = session.get("user")
    return {"current_user": user}


@app.route("/")
@login_required
def dashboard():
    with db_session() as session:
        alerts = session.query(Alert).order_by(Alert.name).all()
        metrics = session.query(Metric).order_by(Metric.created_at.desc()).limit(25).all()
        audits = session.query(Audit).order_by(Audit.created_at.desc()).limit(10).all()
    return render_template_string(
        INDEX_HTML,
        alerts=alerts,
        metrics=list(reversed(metrics)),
        audits=list(reversed(audits)),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        with db_session() as session_db:
            user = session_db.query(User).filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                session["user"] = {
                    "id": user.id,
                    "username": user.username,
                    "is_admin": user.is_admin,
                }
                audit(user.username, "login")
                return redirect(url_for("dashboard"))
        flash("Invalid credentials")
    return render_template_string(AUTH_HTML, title="Login", btn="Login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        if len(username) < 3 or len(password) < 6:
            flash("Username must be ≥3 chars and password ≥6 chars")
            return render_template_string(
                AUTH_HTML, title="Register", btn="Create Account"
            )
        with db_session() as session_db:
            if session_db.query(User).filter_by(username=username).first():
                flash("Username already taken")
                return render_template_string(
                    AUTH_HTML, title="Register", btn="Create Account"
                )
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                is_admin=False,
            )
            session_db.add(user)
            session_db.commit()
            audit(username, "register")
        flash("Account created. Please log in.")
        return redirect(url_for("login"))
    return render_template_string(AUTH_HTML, title="Register", btn="Create Account")


@app.route("/logout")
@login_required
def logout():
    user = session["user"]
    audit(user["username"], "logout")
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
@admin_required
def admin():
    with db_session() as session_db:
        alerts = session_db.query(Alert).order_by(Alert.name).all()
    return render_template_string(ADMIN_HTML, alerts=alerts)


@app.post("/admin/thresholds")
@admin_required
def update_thresholds():
    actor = session["user"]["username"]
    with db_session() as session_db:
        alerts = session_db.query(Alert).all()
        for alert in alerts:
            new_direction = request.form.get(f"direction_{alert.id}", alert.direction)
            new_threshold = float(
                request.form.get(f"threshold_{alert.id}", alert.threshold)
            )
            changes = []
            if new_direction != alert.direction:
                changes.append(f"dir {alert.direction}->{new_direction}")
                alert.direction = new_direction
            if new_threshold != alert.threshold:
                changes.append(f"thr {alert.threshold}->{new_threshold}")
                alert.threshold = new_threshold
            if changes:
                audit(actor, "update_threshold", f"{alert.name}: {', '.join(changes)}")
        session_db.commit()
    flash("Thresholds updated")
    return redirect(url_for("admin"))


@app.post("/admin/inject")
@admin_required
def inject_metric():
    name = request.form["name"]
    value = float(request.form["value"])
    unit = request.form.get("unit", "")
    metric = Metric(name=name, value=value, unit=unit)
    with db_session() as session_db:
        session_db.add(metric)
        session_db.commit()
    emit_metric(metric)
    audit(session["user"]["username"], "inject_metric", json.dumps({"name": name, "value": value}))
    flash("Metric injected")
    return redirect(url_for("admin"))


# ---------------------------
# Sockets + background metrics
# ---------------------------


@socketio.on("connect")
def on_connect():
    socketio.emit(
        "metric",
        json.dumps({"name": "cpu_utilization", "value": 0, "t": datetime.utcnow().isoformat()}),
    )


@socketio.on("disconnect")
def on_disconnect():
    pass


def check_alerts_and_emit(metric):
    with db_session() as session_db:
        alert = session_db.query(Alert).filter_by(name=metric.name).first()
        if not alert:
            return
        breach = False
        if alert.direction == "above" and metric.value > alert.threshold:
            breach = True
        if alert.direction == "below" and metric.value < alert.threshold:
            breach = True
        if breach:
            socketio.emit(
                "alert",
                json.dumps(
                    {
                        "name": metric.name,
                        "value": metric.value,
                        "threshold": alert.threshold,
                        "direction": alert.direction,
                        "t": metric.created_at.isoformat(),
                    }
                ),
            )


def emit_metric(metric):
    socketio.emit(
        "metric",
        json.dumps({"name": metric.name, "value": metric.value, "t": metric.created_at.isoformat()}),
    )
    check_alerts_and_emit(metric)


_running = True


def metric_generator():
    phase = 0.0
    while _running:
        with db_session() as session_db:
            cpu_val = 57 + 28 * math.sin(phase) + 5 * math.sin(phase * 0.3)
            err_val = max(0.0, 4 + 4 * math.sin(phase * 1.3))
            cpu_metric = Metric(name="cpu_utilization", value=float(cpu_val), unit="%")
            err_metric = Metric(name="error_rate", value=float(err_val), unit="%")
            session_db.add_all([cpu_metric, err_metric])
            session_db.commit()
            emit_metric(cpu_metric)
            emit_metric(err_metric)
        phase += 0.2
        time.sleep(1.2)


def start_background_thread():
    thread = threading.Thread(target=metric_generator, daemon=True)
    thread.start()
    return thread


bg_thread = start_background_thread()


# ---------------------------
# Utilities
# ---------------------------


@app.route("/base.html")
def base_template():
    return render_template_string(BASE_HTML)


@app.route("/dashboard")
@login_required
def index_alias():
    return redirect(url_for("dashboard"))


# ---------------------------
# Main
# ---------------------------

if __name__ == "__main__":
    print("\nOpsPulse running on http://127.0.0.1:5000  (login: admin / admin123)\n")
    socketio.run(app, host="0.0.0.0", port=5000)

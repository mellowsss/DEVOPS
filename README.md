# OpsPulse — Real-Time Ops Dashboard

OpsPulse is a recruiter-ready demo that rolls **application automation**, **data & analytics**, **security/auth**, **cloud readiness**, and **real-time networking** into a compact project. The stack is purposefully simple — a single-file [Flask](https://flask.palletsprojects.com/) app backed by [Flask-SocketIO](https://flask-socketio.readthedocs.io/), [SQLAlchemy](https://docs.sqlalchemy.org/), and SQLite, with a lightweight [Chart.js](https://www.chartjs.org/) front end.

<div align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/flask-3.0-success" alt="Flask" />
  <img src="https://img.shields.io/badge/socket.io-live-orange" alt="SocketIO" />
  <img src="https://img.shields.io/badge/docker-ready-informational" alt="Docker" />
</div>

## ✨ Feature highlights (talking points)

- **Role-based access control** — admin and user roles, secure sessions, hashed passwords.
- **Live telemetry streaming** — metrics broadcast over WebSockets with configurable alerting.
- **Data layer** — SQLite via SQLAlchemy with models for users, metrics, alerts, and audit log.
- **Auditability** — every login, threshold change, and manual metric injection is recorded.
- **Cloud-ready** — Dockerfile, environment-driven configuration, and simple scaling notes.
- **Analytics view** — chart of CPU/error rate, latest database metrics, and audit feed on one dashboard.
- **Smoke checks** — quick Python-based health check snippet included below.

---

## 🚀 Quick start (local)

```bash
# 1. (Optional) create a venv
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the app (auto-seeds an admin user)
python app.py
```

Now open http://127.0.0.1:5000 and log in with **admin / admin123** (override via env vars below). The UI immediately starts streaming synthetic CPU + error rate metrics over Socket.IO.

### Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPSPULSE_SECRET_KEY` | Flask session secret | Random 32-hex string |
| `ADMIN_USER` | Seed admin username | `admin` |
| `ADMIN_PASS` | Seed admin password | `admin123` |

---

## 🐳 Deploy with Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    OPSPULSE_SECRET_KEY=change-me \
    ADMIN_USER=admin \
    ADMIN_PASS=admin123
EXPOSE 5000
CMD ["python", "app.py"]
```

```bash
# Build and run
docker build -t opspulse .
docker run -p 5000:5000 \
  -e OPSPULSE_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(16))') \
  opspulse
```

For horizontal scaling, add `message_queue='redis://redis:6379/0'` to `SocketIO(...)` and run multiple containers behind a load balancer. Swap SQLite for PostgreSQL by updating the SQLAlchemy URI.

---

## 🛡️ Security & auth notes

- Passwords are hashed with Werkzeug's PBKDF2 helpers before storage.
- Sessions use Flask's secure cookie mechanism (random secret key by default).
- Admin-only endpoints enforce role checks with a decorator.
- Audit table persists every login/logout, registration, threshold update, and manual metric injection.

---

## 📊 Data & analytics view

The dashboard surfaces three pillars of operational awareness:

1. **Live chart** — CPU utilization and error rate update every ~1.2 seconds via Socket.IO.
2. **Metrics table** — last 25 database entries for quick inspection / export.
3. **Audit log** — 10 most recent actions with actor, verb, and optional metadata.

Alert thresholds are configurable from the Admin panel. Breaches immediately trigger a browser alert via WebSocket broadcast.

---

## 🛠️ Architecture sketch

```text
Flask app (app.py)
├── REST views (login/register/dashboard/admin)
├── Socket.IO server for live metrics & alerts
├── Background thread generating synthetic telemetry
├── SQLAlchemy ORM models (User, Metric, Alert, Audit)
└── Inline Jinja templates rendered from strings
```

Because everything lives in `app.py`, the project is easy to drop into a code sample or extend with blueprints/React/etc.

---

## 🧪 Smoke check (optional)

Once the server is running locally, hit the dashboard to confirm the app responds:

```bash
python - <<'PY'
import requests
print('Open http://127.0.0.1:5000 to view the live dashboard and login UI.')
PY
```

---

## 🎤 Demo script (for interviews)

1. **Login** as the seeded admin — mention hashed passwords & session security.
2. **Show the chart** updating in real time as the background thread emits metrics.
3. **Trigger an alert** via Admin → Manual Metric Inject → `error_rate` = `9`.
4. **Tweak thresholds** and point out audit entries being created.
5. **Discuss scaling** — containerization, swapping SQLite→Postgres, Redis message queue for Socket.IO, etc.

---

## 🧩 Extensibility ideas

- Replace synthetic data with hooks into Prometheus, CloudWatch, or a Kafka consumer.
- Add a `/reports` view that aggregates metrics into hourly/daily rollups.
- Wire alert notifications to Slack or email via Celery/RQ workers.
- Drop the templates into a React/Vue front end by turning the Flask app into an API.

---

Happy shipping! 💡

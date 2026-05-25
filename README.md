# LifePulse

A safety monitoring API for people living alone. Users set a daily check-in time, and if they miss it, their trusted contacts are automatically alerted via SMS. The system also stores pet and home access information so emergency responders have everything they need.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 6.0.5 + Django REST Framework |
| Auth | JWT via `djangorestframework-simplejwt` |
| Task Queue | Celery 5.6 + Redis |
| Task Scheduling | `django-celery-beat` |
| SMS | Twilio |
| Database | PostgreSQL (SQLite for local dev) |
| Media Storage | Local filesystem (configurable) |

---

## Features

- **Custom user auth** — email-based signup/signin with JWT tokens, OTP-based password reset, token blacklisting on logout
- **Safety profile** — users configure their living status, home address, access notes, and daily check-in time
- **Trusted contacts** — up to 5 emergency contacts per user (name, relationship, phone)
- **Pet registry** — up to 5 pets per user with breed, age, photo, and caregiver info
- **Daily monitoring** — Celery creates a `MonitoringLog` for every active user at midnight; auto-creates on demand if missing
- **Overdue detection** — runs every 15 minutes; marks logs as overdue if the deadline (check-in time + 8 hours) has passed
- **SMS alerts** — sends a detailed safety alert to all trusted contacts when a user goes overdue; logs every attempt

---

## Project Structure

```
LifePulse/
├── apps/
│   ├── accounts/          # User, SafetyInfo, TrustedContact, Pet, OTP, BlacklistedToken
│   └── monitoring/        # CheckIn, MonitoringLog, NotificationLog, Celery tasks
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   ├── wsgi.py
│   └── asgi.py
├── utils/
│   ├── response.py        # Standardized API response helpers
│   └── exceptions.py      # Custom DRF exception handler
├── postman/               # Postman collection
├── manage.py
├── requirements.txt
└── .env                   # Environment variables (not committed)
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Redis (for Celery broker)
- A Twilio account (for SMS alerts)

### 1. Clone and set up the environment

```bash
git clone https://github.com/your-username/lifepulse.git
cd lifepulse
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (leave blank to use SQLite)
DATABASE_URL=sqlite:///db.sqlite3

# Email
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=Life Pulse <noreply@lifepulse.com>

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
```

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Start the development server

```bash
python manage.py runserver
```

### 5. Start Celery worker and beat scheduler

Open two separate terminals:

```bash
# Terminal 1 — worker
celery -A config worker --loglevel=info

# Terminal 2 — beat scheduler
celery -A config beat --loglevel=info
```

---

## API Reference

All endpoints are prefixed with `/api/`.  
Authentication uses `Bearer <access_token>` in the `Authorization` header.

### Accounts — `/api/accounts/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `signup/` | No | Register a new user |
| POST | `signin/` | No | Sign in, returns JWT tokens |
| POST | `logout/` | Yes | Blacklist refresh token |
| POST | `token/refresh/` | No | Refresh access token |
| POST | `change-password/` | Yes | Change password |
| POST | `forgot-password/` | No | Send OTP to email |
| POST | `forgot-password/verify-otp/` | No | Verify OTP |
| POST | `forgot-password/resend-otp/` | No | Resend OTP |
| POST | `forgot-password/reset/` | No | Reset password with verified OTP |
| GET/PUT/PATCH | `profile/` | Yes | Get or update user profile |
| GET/POST | `contacts/` | Yes | List or add trusted contacts (max 5) |
| GET/PUT/PATCH/DELETE | `contacts/<id>/` | Yes | Manage a single trusted contact |
| GET/POST | `pets/` | Yes | List or add pets (max 5) |
| GET/PUT/PATCH/DELETE | `pets/<id>/` | Yes | Manage a single pet |

### Monitoring — `/api/monitoring/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `check-in/` | Yes | Submit today's check-in |
| GET | `status/` | Yes | Get today's monitoring status |

---

## How the Monitoring System Works

```
Midnight (Celery Beat)
  └── create_daily_monitoring_logs
        └── Creates MonitoringLog for each active user with a check_in_time
              deadline = check_in_time + 8 hours

Every 15 minutes (Celery Beat)
  └── detect_overdue_checkins
        └── Finds pending logs past their deadline
              └── Marks status = overdue
                    └── Triggers notify_trusted_contacts task
                          └── Sends SMS to all trusted contacts via Twilio
                                └── Logs each attempt in NotificationLog

User hits POST /api/monitoring/check-in/
  └── Auto-creates MonitoringLog if missing (requires SafetyInfo.check_in_time)
        └── Marks status = checked_in
              └── Late check-ins (after deadline) are still accepted with a note
```

---

## Celery Beat Schedule

| Task | Schedule |
|---|---|
| `monitoring.create_daily_monitoring_logs` | Daily at midnight (00:00) |
| `monitoring.detect_overdue_checkins` | Every 15 minutes |

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | No | `True` for development (default: `True`) |
| `ALLOWED_HOSTS` | No | Comma-separated list of allowed hosts |
| `DATABASE_URL` | No | Database connection string (default: SQLite) |
| `EMAIL_BACKEND` | No | Django email backend |
| `EMAIL_HOST` | No | SMTP host |
| `EMAIL_PORT` | No | SMTP port |
| `EMAIL_USE_TLS` | No | Enable TLS for email |
| `EMAIL_HOST_USER` | No | SMTP username |
| `EMAIL_HOST_PASSWORD` | No | SMTP password |
| `DEFAULT_FROM_EMAIL` | No | From address for outgoing emails |
| `CELERY_BROKER_URL` | No | Redis broker URL (default: `redis://localhost:6379/0`) |
| `CELERY_RESULT_BACKEND` | No | Redis result backend URL |
| `TWILIO_ACCOUNT_SID` | Yes* | Twilio account SID (*required for SMS alerts) |
| `TWILIO_AUTH_TOKEN` | Yes* | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Yes* | Twilio sender phone number |

---

## Postman Collection

A ready-to-use Postman collection is included at `postman/Life Pulse.postman_collection.json`. Import it directly into Postman to test all endpoints.

---

## License

MIT

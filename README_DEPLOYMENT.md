# 🚀 EduVerse Platform - Deployment Guide

## Overview
Complete deployment guide for EduVerse educational platform with production-ready configuration.

---

## 📋 Prerequisites

### Required Services
- PostgreSQL 14+ database
- Redis 7+ server
- AWS S3 bucket (for media storage)
- SMTP email service (Gmail, SendGrid, or AWS SES)
- Stripe/Moyasar account (for payments)
- Zoom API account (optional, for video sessions)

### System Requirements
- Python 3.10+
- 2GB+ RAM
- 20GB+ storage

---

## 🔧 Installation Steps

### 1. Clone Repository
```bash
git clone <repository-url>
cd eduverseplatform
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Database Setup
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 7. Load Initial Data (Optional)
```bash
python manage.py populate_data
```

---

## 🏃 Running the Platform

### Development Mode
```bash
# Run Django development server
python manage.py runserver

# In separate terminal: Run Celery worker
celery -A eduverse worker --loglevel=info

# In separate terminal: Run Celery beat (scheduled tasks)
celery -A eduverse beat --loglevel=info

# In separate terminal: Run Channels/WebSocket (if using)
daphne -b 0.0.0.0 -p 8001 eduverse.asgi_channels:application
```

Important for local live calls:
- Open the platform from `http://127.0.0.1:8000` or `http://localhost:8000` on the same machine.
- Do not test camera/microphone from a plain LAN IP such as `http://192.168.x.x` unless you serve the platform over `HTTPS`.
- Set `SITE_BASE_URL` and `CSRF_TRUSTED_ORIGINS` in `.env` to match the URL you actually use.
- For remote device testing, use Cloudflare Tunnel and make sure `CLOUDFLARE_TUNNEL_URL` is set in `.env`.

### Cloudflare Tunnel Testing
1. Install cloudflared:
```bash
brew install cloudflare/cloudflare/cloudflared  # macOS
choco install cloudflare-cli                   # Windows
```
2. Run the tunnel to your local port:
```bash
cloudflared tunnel --url http://127.0.0.1:8000
```
3. Copy the generated `https://...trycloudflare.com` URL and paste it into `.env` as `CLOUDFLARE_TUNNEL_URL`.
4. Make sure `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` include `*.trycloudflare.com`.
5. Open that Cloudflare URL on another device to test WebRTC audio/video across machines.

### Production Mode (with Gunicorn + Nginx)

#### 1. Install Gunicorn & Daphne
```bash
pip install gunicorn daphne
```

#### 2. Create Gunicorn Configuration
Create `gunicorn_config.py`:
```python
bind = "0.0.0.0:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
```

#### 3. Run Gunicorn
```bash
gunicorn eduverse.wsgi:application -c gunicorn_config.py
```

#### 4. Run Daphne for WebSockets
```bash
daphne -b 0.0.0.0 -p 8001 eduverse.asgi_channels:application
```

#### 5. Nginx Configuration
Create `/etc/nginx/sites-available/eduverse`:
```nginx
upstream django {
    server 127.0.0.1:8000;
}

upstream daphne {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL Configuration
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;

    client_max_body_size 100M;

    location /static/ {
        alias /path/to/eduverseplatform/staticfiles/;
    }

    location /media/ {
        alias /path/to/eduverseplatform/media/;
    }

    location /ws/ {
        proxy_pass http://daphne;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_redirect off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Host $server_name;
    }

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/eduverse /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔄 Celery as System Service

### Create Celery Worker Service
Create `/etc/systemd/system/celery.service`:
```ini
[Unit]
Description=Celery Worker
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/eduverseplatform
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A eduverse worker --loglevel=info --detach
ExecStop=/path/to/venv/bin/celery -A eduverse control shutdown
Restart=always

[Install]
WantedBy=multi-user.target
```

### Create Celery Beat Service
Create `/etc/systemd/system/celerybeat.service`:
```ini
[Unit]
Description=Celery Beat Scheduler
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/eduverseplatform
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A eduverse beat --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable celery celerybeat
sudo systemctl start celery celerybeat
```

---

## 🐳 Docker Deployment (Alternative)

### Create Dockerfile
```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "eduverse.wsgi:application", "--bind", "0.0.0.0:8000"]
```

### Create docker-compose.yml
```yaml
version: '3.8'

services:
  db:
    image: postgres:14
    environment:
      POSTGRES_DB: eduverse_db
      POSTGRES_USER: eduverse
      POSTGRES_PASSWORD: your_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  web:
    build: .
    command: gunicorn eduverse.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db
      - redis

  celery:
    build: .
    command: celery -A eduverse worker --loglevel=info
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      - db
      - redis

  celery-beat:
    build: .
    command: celery -A eduverse beat --loglevel=info
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
  static_volume:
  media_volume:
```

Run with Docker:
```bash
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

---

## 🔒 Security Checklist

### Production Settings
- [ ] Set `DEBUG = False`
- [ ] Configure strong `SECRET_KEY`
- [ ] Set `ALLOWED_HOSTS` to your domain
- [ ] Enable HTTPS (`SECURE_SSL_REDIRECT = True`)
- [ ] Configure CSRF and session cookies as secure
- [ ] Set up proper CORS headers
- [ ] Configure database backups
- [ ] Set up monitoring (Sentry)
- [ ] Configure rate limiting
- [ ] Enable security middleware

### Environment Variables
Never commit `.env` file to version control!

---

## 📊 Monitoring & Logging

### Application Monitoring
Configure Sentry for error tracking:
```python
import sentry_sdk
sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    traces_sample_rate=1.0,
)
```

### Log Files
Logs are stored in:
- Application logs: `/var/log/eduverse/app.log`
- Celery logs: `/var/log/eduverse/celery.log`
- Nginx logs: `/var/log/nginx/`

---

## 🧪 Testing

### Run Tests
```bash
# All tests
python manage.py test

# Specific app
python manage.py test accounts

# With coverage
coverage run --source='.' manage.py test
coverage report
```

### Load Testing
Use tools like Apache Bench or Locust:
```bash
ab -n 1000 -c 10 http://yourdomain.com/
```

---

## 🔄 Updates & Maintenance

### Update Code
```bash
git pull origin main
pip install -r requirements.txt --upgrade
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn celery celerybeat
```

### Database Backup
```bash
pg_dump eduverse_db > backup_$(date +%Y%m%d).sql
```

### Database Restore
```bash
psql eduverse_db < backup_20240101.sql
```

---

## 📞 Support

For issues or questions:
- Documentation: [docs.eduverse.com]
- Email: support@eduverse.com
- GitHub Issues: [repository/issues]

---

## 📄 License

Proprietary - All rights reserved

---

**🎉 Deployment Complete! Your platform is ready for production!**




# 🚀 Production Deployment Guide
**Hotel Inventory Management System - Pareto Analysis**

---

## ✅ Pre-Deployment Checklist

### Critical Requirements (Must Complete)

- [ ] **Generate SECRET_KEY**: 
  ```bash
  python -c 'import secrets; print(secrets.token_hex(32))'
  ```
  Save this key securely - you'll need it for `.env` file

- [ ] **Set Admin Password**:
  ```bash
  export ADMIN_INITIAL_PASSWORD='YourSecurePassword123!'
  ```

- [ ] **Configure HTTPS Settings**:
  - If deploying behind HTTPS reverse proxy: Set `USE_HTTPS=true`
  - If deploying via HTTP only: Set `USE_HTTPS=false`

- [ ] **Review Environment Variables** (see section below)

- [ ] **Test Health Endpoint**:
  ```bash
  curl http://localhost:8084/health
  ```

---

## 🔐 Environment Configuration

Create a `.env` file in the project root:

```bash
# Required - Generate with: python -c 'import secrets; print(secrets.token_hex(32))'
SECRET_KEY=your-generated-secret-key-here

# Required - Set secure admin password
ADMIN_INITIAL_PASSWORD=YourSecurePassword123!

# Required - Set based on deployment method
FLASK_ENV=production
USE_HTTPS=false  # Set to 'true' if behind HTTPS reverse proxy

# Optional - AI features
GROQ_API_KEY=your-groq-api-key-if-using-ai-features

# Optional - Rate limiting (use Redis in production for multi-instance)
REDIS_URL=redis://localhost:6379/0
```

---

## 🐳 Docker Deployment (Recommended)

### 1. Update docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    container_name: hotel-inventory-pareto
    ports:
      - "8084:8084"
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}  # Load from .env
      - ADMIN_INITIAL_PASSWORD=${ADMIN_INITIAL_PASSWORD}
      - USE_HTTPS=false  # Set true if behind HTTPS proxy
      - GROQ_API_KEY=${GROQ_API_KEY}
    volumes:
      - ./database:/app/database
      - ./exports:/app/exports
      - ./app.log:/app/app.log
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8084/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

### 2. Build and Run

```bash
# Build the image
docker-compose build

# Start the container
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify health
curl http://localhost:8084/health
```

### 3. First Login

```
URL: http://localhost:8084
Username: admin
Password: [Value you set in ADMIN_INITIAL_PASSWORD]
```

**IMMEDIATELY change the admin password after first login!**

---

## 🖥️ Manual Deployment (Without Docker)

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Create .env file (see Environment Configuration section above)
# Set all required variables
```

### 3. Initialize Database

```bash
# The database will auto-initialize on first run, or manually:
python scripts/init_production_db.py
```

### 4. Run Application

```bash
# Production mode
export FLASK_ENV=production  # Linux/Mac
set FLASK_ENV=production     # Windows CMD
$env:FLASK_ENV="production"  # Windows PowerShell

python app.py
```

---

## 🔒 Security Hardening

### 1. HTTPS Deployment (Strongly Recommended)

**Option A: Nginx Reverse Proxy**

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8084;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then set `USE_HTTPS=true` in environment variables.

**Option B: Traefik (Docker)**

```yaml
services:
  web:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.hotel.rule=Host(`your-domain.com`)"
      - "traefik.http.routers.hotel.tls=true"
      - "traefik.http.routers.hotel.tls.certresolver=letsencrypt"
```

### 2. Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 80/tcp   # HTTP (redirect to HTTPS)
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### 3. Database Backups

Create automated backup script:

```bash
#!/bin/bash
# /opt/backups/backup_inventory.sh

BACKUP_DIR="/opt/backups/inventory"
DB_FILE="/app/database/inventory.db"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
sqlite3 $DB_FILE ".backup $BACKUP_DIR/inventory_$DATE.db"

# Compress
gzip $BACKUP_DIR/inventory_$DATE.db

# Keep only last 30 backups
ls -t $BACKUP_DIR/*.db.gz | tail -n +31 | xargs rm -f

echo "Backup completed: inventory_$DATE.db.gz"
```

Add to crontab:
```bash
# Daily backup at 2 AM
0 2 * * * /opt/backups/backup_inventory.sh
```

---

## 📊 Monitoring & Health Checks

### Health Check Endpoint

```bash
curl http://localhost:8084/health
```

**Expected Response** (HTTP 200):
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

**Unhealthy Response** (HTTP 503):
```json
{
  "status": "unhealthy",
  "database": "error: database is locked",
  "version": "1.0.0"
}
```

### Log Monitoring

```bash
# Real-time logs
tail -f app.log

# Search for errors
grep "ERROR" app.log

# Monitor Docker logs
docker-compose logs -f --tail=100
```

---

## ⚡ Performance Optimization

### 1. Database Tuning (Already Configured)

The application automatically configures SQLite for optimal performance:
- WAL mode for better concurrency
- 64MB cache
- 5-second busy timeout
- NORMAL synchronous mode

### 2. Rate Limiting (Production)

For multiple application instances, use Redis:

```bash
# Install Redis
sudo apt-get install redis-server

# Update .env
REDIS_URL=redis://localhost:6379/0
```

### 3. Resource Limits (Docker)

Add to docker-compose.yml:
```yaml
services:
  web:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

---

## 🐛 Troubleshooting

### Issue: "Database is locked"
**Solution**: WAL mode should prevent this. If it persists:
```bash
# Check for hanging processes
ps aux | grep python

# Restart application
docker-compose restart
```

### Issue: "Session invalid" after login
**Cause**: `SESSION_COOKIE_SECURE=True` but running HTTP
**Solution**: Set `USE_HTTPS=false` in environment

### Issue: "Health check failing"
**Cause**: Database connectivity issue
**Solution**:
```bash
# Check database permissions
ls -la database/inventory.db

# Check logs
docker-compose logs web

# Restart
docker-compose restart
```

### Issue: "Admin login not working"
**Solution**:
```bash
# Reset admin password
python scripts/init_production_db.py
```

---

## 🔄 Updating the Application

### Docker Deployment

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d

# Verify
curl http://localhost:8084/health
```

### Manual Deployment

```bash
# Pull latest changes
git pull

# Update dependencies
pip install -r requirements.txt --upgrade

# Restart application
# (method depends on your process manager: systemd, supervisor, etc.)
```

---

## 📈 Scaling Considerations

### Horizontal Scaling

The current SQLite database limits horizontal scaling. For multiple instances:

1. **Migrate to PostgreSQL**:
   - Update `SQLALCHEMY_DATABASE_URI` in config
   - Use connection pooling
   - Enable Redis for session storage

2. **Load Balancer Configuration**:
   - Use sticky sessions (session affinity)
   - Or implement Redis session storage

3. **File Uploads**:
   - Move `uploads/` to shared storage (NFS, S3)

---

## 🎯 Post-Deployment Tasks

1. **Change Admin Password** (Critical!)
2. **Create Additional Users** via admin panel
3. **Configure Warehouse Settings** (min/max stock levels, approval thresholds)
4. **Test All Features**:
   - Item creation
   - Transaction recording
   - Report generation
   - Excel import/export
   - Alerts system
5. **Set Up Monitoring** (health checks, log aggregation)
6. **Document Procedures** for your team
7. **Schedule Backups** (automated daily backups)

---

## 📞 Support & Maintenance

### Regular Maintenance

- **Daily**: Check health endpoint, review error logs
- **Weekly**: Review backup integrity, check disk space
- **Monthly**: Security updates, dependency updates
- **Quarterly**: Full system audit, performance review

### Key Files to Monitor

- `app.log` - Application logs
- `database/inventory.db` - Main database (backup regularly!)
- `exports/` - Generated reports
- `uploads/` - Imported Excel files

---

## ✅ Production Readiness Checklist

Before going live:

- [ ] All P0 critical issues fixed (see SECURITY_AUDIT_REPORT.md)
- [ ] SECRET_KEY generated and secured
- [ ] Admin password changed from default
- [ ] HTTPS configured (or USE_HTTPS=false set correctly)
- [ ] Database backups scheduled
- [ ] Health checks passing
- [ ] Monitoring configured
- [ ] Firewall rules applied
- [ ] Load testing completed (100+ concurrent users)
- [ ] Disaster recovery plan documented
- [ ] Team trained on system usage

---

## 🚨 Emergency Contacts

Document your emergency procedures:

- **System Administrator**: [Name/Contact]
- **Database Backup Location**: [Path/URL]
- **Escalation Procedure**: [Steps]
- **Rollback Procedure**: [Steps]

---

**Deployment Date**: _____________
**Deployed By**: _____________
**Version**: 1.0.0
**Next Review**: _____________

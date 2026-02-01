# 🚀 Docker Deployment Guide - KOMPLETAN VODIČ

## Sadržaj
1. [Struktura kontejnera](#struktura-kontejnera)
2. [Preduvjeti na serveru](#preduvjeti-na-serveru)
3. [Korak po korak deployment](#korak-po-korak-deployment)
4. [Inicijalna konfiguracija baze](#inicijalna-konfiguracija-baze)
5. [Celery i scheduler konfiguracija](#celery-i-scheduler-konfiguracija)
6. [SSL i HTTPS](#ssl-i-https)
7. [Monitoring i logovi](#monitoring-i-logovi)
8. [Backup i restore](#backup-i-restore)
9. [Troubleshooting](#troubleshooting)

---

## Struktura kontejnera

```
┌─────────────────────────────────────────────────────────┐
│              NGINX kontejner (port 80/443)              │
│              + Let's Encrypt SSL certifikati            │
└──────────────────────────┬──────────────────────────────┘
                           │ (interna mreža)
┌──────────────────────────▼──────────────────────────────┐
│                    DOCKER NETWORK                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐│
│  │   web       │ │celery_worker│ │    celery_beat      ││
│  │ (Gunicorn)  │ │  (taskovi)  │ │   (scheduler)       ││
│  │  port 8000  │ │             │ │                     ││
│  └──────┬──────┘ └──────┬──────┘ └──────────┬──────────┘│
│         │               │                    │          │
│  ┌──────▼───────────────▼────────────────────▼────────┐ │
│  │              postgres + redis                      │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Preduvjeti na serveru

### Instaliraj Docker i Docker Compose
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose-plugin

# Dodaj korisnika u docker grupu (da ne trebaš sudo)
sudo usermod -aG docker $USER
newgrp docker

# Provjeri instalaciju
docker --version
docker compose version
```

### Instaliraj Git
```bash
sudo apt install -y git
```

### Firewall
```bash
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP (redirect na HTTPS)
sudo ufw allow 443   # HTTPS
sudo ufw enable
sudo ufw status
```

---

## Korak po korak deployment

### 1. Kloniraj repo
```bash
cd /var/www
git clone <repo-url> museum-backend
cd museum-backend
```

### 2. Kreiraj .env datoteku
```bash
nano .env
```

**KOMPLETNA .env DATOTEKA:**
```bash
# ============================================
# DATABASE (KRITIČNO: Docker service name!)
# ============================================
DATABASE_HOST=postgres
DATABASE_NAME=museum_db
DATABASE_USER=museum_user
DATABASE_PASSWORD=GENERIRAJ_SIGURNU_LOZINKU_32+_ZNAKOVA

# ============================================
# REDIS (KRITIČNO: Docker service name!)
# ============================================
REDIS_URL=redis://redis:6379/1

# ============================================
# DJANGO CORE
# ============================================
DEBUG=False
SECRET_KEY=GENERIRAJ_RANDOM_STRING_50+_ZNAKOVA

# Tvoja domena (bez https://)
ALLOWED_HOSTS=api.tvoja-domena.duckdns.org

# ============================================
# CORS & CSRF (Frontend domene)
# ============================================
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://tvoj-frontend.com,https://www.tvoj-frontend.com
CSRF_TRUSTED_ORIGINS=https://tvoj-frontend.com,https://www.tvoj-frontend.com

# ============================================
# SSL/HTTPS SECURITY
# ============================================
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# ============================================
# EMAIL (za password reset, notifikacije)
# ============================================
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tvoj-email@gmail.com
EMAIL_HOST_PASSWORD=tvoj-app-password
DEFAULT_FROM_EMAIL=Museum Backend <tvoj-email@gmail.com>

# ============================================
# LOGGING
# ============================================
LOG_LEVEL=WARNING
```

**Za generiranje sigurnih vrijednosti:**
```bash
# SECRET_KEY (Python)
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# DATABASE_PASSWORD
openssl rand -base64 32
```

### 3. SSL Certifikati (Let's Encrypt)
```bash
# Kreiraj folder
mkdir -p nginx/ssl

# Kopiraj certifikate (zamijeni tvoja-domena.duckdns.org)
sudo cp /etc/letsencrypt/live/tvoja-domena.duckdns.org/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/tvoja-domena.duckdns.org/privkey.pem nginx/ssl/

# Postavi permissions
sudo chown $USER:$USER nginx/ssl/*.pem
chmod 600 nginx/ssl/*.pem
```

### 4. Build i pokreni kontejnere
```bash
# Prvi put - build sve
docker compose -f docker-compose.prod.yml up -d --build

# Prati logove
docker compose -f docker-compose.prod.yml logs -f
```

### 5. Provjeri da su svi kontejneri pokrenuti
```bash
docker compose -f docker-compose.prod.yml ps

# Trebao bi vidjeti:
# NAME                STATUS
# museum-web          Up (healthy)
# museum-postgres     Up (healthy)  
# museum-redis        Up (healthy)
# museum-celery       Up
# museum-beat         Up
# museum-nginx        Up
```

---

## Inicijalna konfiguracija baze

### Migracije (automatski se pokreću, ali za provjeru)
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py migrate --check
```

### Kreiraj superusera
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```
Unesi:
- Email: tvoj-admin-email@example.com
- Password: sigurna lozinka

### Kreiraj default grupe i permissione
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py shell
```

U shell-u:
```python
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from api.models import Guard, Position, Exhibition, User

# Kreiraj grupe
admin_group, _ = Group.objects.get_or_create(name='Admin')
manager_group, _ = Group.objects.get_or_create(name='Manager')
guard_group, _ = Group.objects.get_or_create(name='Guard')

# Admin - sve permissione
all_permissions = Permission.objects.all()
admin_group.permissions.set(all_permissions)

# Manager - može sve osim user management
manager_perms = Permission.objects.exclude(
    codename__in=['add_user', 'delete_user', 'change_user']
)
manager_group.permissions.set(manager_perms)

# Guard - samo view i vlastiti profil
guard_perms = Permission.objects.filter(codename__startswith='view_')
guard_group.permissions.set(guard_perms)

print("Grupe kreirane!")
print(f"Admin permissions: {admin_group.permissions.count()}")
print(f"Manager permissions: {manager_group.permissions.count()}")  
print(f"Guard permissions: {guard_group.permissions.count()}")

exit()
```

### Postavi SystemSettings default vrijednosti
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py shell
```

```python
from api.models import SystemSettings

# Kreiraj ili dohvati settings (singleton)
settings, created = SystemSettings.objects.get_or_create(pk=1)

if created:
    # Postavi default vrijednosti
    settings.workdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    settings.weekday_morning_start = '09:00'
    settings.weekday_morning_end = '13:00'
    settings.weekday_afternoon_start = '13:00'
    settings.weekday_afternoon_end = '17:00'
    settings.weekend_morning_start = '09:00'
    settings.weekend_morning_end = '13:00'
    settings.weekend_afternoon_start = '13:00'
    settings.weekend_afternoon_end = '17:00'
    settings.schedule_generation_day_of_week = 0  # Monday
    settings.schedule_generation_hour = 2  # 2 AM
    settings.save()
    print("SystemSettings kreirani s default vrijednostima!")
else:
    print("SystemSettings već postoje.")

exit()
```

### Kreiraj inicijalne UserType-ove (ako treba)
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py shell
```

```python
from api.models import UserType

# Definiraj tipove korisnika
user_types = [
    {'name': 'Čuvar', 'code': 'GUARD', 'description': 'Muzejski čuvar'},
    {'name': 'Manager', 'code': 'MANAGER', 'description': 'Voditelj čuvara'},
    {'name': 'Admin', 'code': 'ADMIN', 'description': 'Administrator sustava'},
]

for ut in user_types:
    obj, created = UserType.objects.get_or_create(
        code=ut['code'],
        defaults={'name': ut['name'], 'description': ut['description']}
    )
    status = "kreiran" if created else "već postoji"
    print(f"{ut['name']}: {status}")

exit()
```

---

## Celery i scheduler konfiguracija

### Provjeri da Celery radi
```bash
# Worker logovi
docker compose -f docker-compose.prod.yml logs celery_worker

# Beat logovi (scheduler)
docker compose -f docker-compose.prod.yml logs celery_beat
```

### Postavi Periodic Tasks (automatski raspored)

Celery Beat koristi `DatabaseScheduler` - taskovi se definiraju u Django adminu ili kroz shell:

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py shell
```

```python
from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json

# Schedule za tjedni task (ponedjeljak u 2:00 ujutro)
schedule, _ = CrontabSchedule.objects.get_or_create(
    minute='0',
    hour='2',
    day_of_week='1',  # Monday
    day_of_month='*',
    month_of_year='*',
)

# Kreiraj periodic task za generiranje rasporeda
task, created = PeriodicTask.objects.get_or_create(
    name='Weekly Schedule Generation',
    defaults={
        'task': 'background_tasks.tasks.generate_weekly_schedule',
        'crontab': schedule,
        'enabled': True,
        'kwargs': json.dumps({}),
    }
)

if created:
    print("Periodic task kreiran: Weekly Schedule Generation")
else:
    print("Periodic task već postoji")

# Provjeri sve taskove
print("\nSvi periodic taskovi:")
for pt in PeriodicTask.objects.all():
    print(f"  - {pt.name}: {'aktivan' if pt.enabled else 'neaktivan'}")

exit()
```

### Testiraj Celery task manualno
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py shell
```

```python
from background_tasks.tasks import generate_weekly_schedule

# Sinhrono (za test)
result = generate_weekly_schedule.delay()
print(f"Task ID: {result.id}")
print(f"Status: {result.status}")

# Čekaj rezultat (max 30 sekundi)
try:
    output = result.get(timeout=30)
    print(f"Rezultat: {output}")
except Exception as e:
    print(f"Greška: {e}")

exit()
```

---

## SSL i HTTPS

### Certifikat renewal (Let's Encrypt)

Certifikati vrijede 90 dana. Postavi automatski renewal:

```bash
# Na HOST serveru (ne u kontejneru!)
sudo crontab -e
```

Dodaj:
```cron
# Let's Encrypt renewal - svaki dan u 3:00
0 3 * * * certbot renew --quiet --post-hook "cp /etc/letsencrypt/live/tvoja-domena.duckdns.org/*.pem /var/www/museum-backend/nginx/ssl/ && docker compose -f /var/www/museum-backend/docker-compose.prod.yml restart nginx"
```

### Provjeri SSL konfiguraciju
```bash
# Test HTTPS
curl -I https://tvoja-domena.duckdns.org/api/health/

# Provjeri certifikat
echo | openssl s_client -connect tvoja-domena.duckdns.org:443 2>/dev/null | openssl x509 -noout -dates
```

---

## Monitoring i logovi

### Pregled logova
```bash
# Svi kontejneri
docker compose -f docker-compose.prod.yml logs -f

# Samo web (Django)
docker compose -f docker-compose.prod.yml logs -f web

# Samo greške
docker compose -f docker-compose.prod.yml logs -f web 2>&1 | grep -i error

# Celery worker
docker compose -f docker-compose.prod.yml logs -f celery_worker

# Celery beat (scheduler)
docker compose -f docker-compose.prod.yml logs -f celery_beat

# Nginx
docker compose -f docker-compose.prod.yml logs -f nginx

# Postgres
docker compose -f docker-compose.prod.yml logs -f postgres
```

### Django logovi (unutar kontejnera)
```bash
docker compose -f docker-compose.prod.yml exec web cat /app/logs/django.log
```

### Health check endpoint
```bash
curl https://tvoja-domena.duckdns.org/api/health/
# Očekivani odgovor: {"status": "healthy", "database": "ok", "redis": "ok"}
```

### Provjeri resource usage
```bash
docker stats
```

---

## Backup i restore

### Automatski backup baze
Kreiraj backup script na hostu:
```bash
nano /var/www/museum-backend/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/var/www/museum-backend/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/museum_db_$DATE.sql"

mkdir -p $BACKUP_DIR

docker compose -f /var/www/museum-backend/docker-compose.prod.yml exec -T postgres pg_dump -U museum_user museum_db > $BACKUP_FILE

gzip $BACKUP_FILE

# Obriši backupe starije od 30 dana
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

```bash
chmod +x /var/www/museum-backend/backup.sh
```

Dodaj u cron (dnevni backup u 4:00):
```bash
crontab -e
```
```cron
0 4 * * * /var/www/museum-backend/backup.sh >> /var/log/museum-backup.log 2>&1
```

### Manualni backup
```bash
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U museum_user museum_db > backup_$(date +%Y%m%d).sql
```

### Restore baze
```bash
# OPREZ: Ovo briše sve postojeće podatke!
docker compose -f docker-compose.prod.yml exec -T postgres psql -U museum_user museum_db < backup.sql
```

### Backup sa drugog servera (stara baza)
Ako migriraš podatke sa starog servera:
```bash
# Na starom serveru
pg_dump -h localhost -U stari_user stara_baza > export.sql

# Kopiraj na novi server
scp export.sql user@novi-server:/var/www/museum-backend/

# Na novom serveru - restore
docker compose -f docker-compose.prod.yml exec -T postgres psql -U museum_user museum_db < export.sql
```

---

## Troubleshooting

### "Connection refused" na bazu ili Redis

**Problem:** Django ne može spojiti na bazu/Redis

**Rješenje:** Provjeri .env hostnames
```bash
# KRIVO ❌
DATABASE_HOST=localhost
REDIS_URL=redis://localhost:6379/1

# ISPRAVNO ✅
DATABASE_HOST=postgres
REDIS_URL=redis://redis:6379/1
```

### Kontejner se stalno restarta

```bash
# Provjeri logove
docker compose -f docker-compose.prod.yml logs web

# Uobičajeni uzroci:
# 1. Kriva .env konfiguracija
# 2. Baza nije spremna (healthcheck nije prošao)
# 3. Sintaksna greška u kodu
```

### Migracije nisu primijenjene

```bash
# Provjeri status migracija
docker compose -f docker-compose.prod.yml exec web python manage.py showmigrations

# Primijeni ručno
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### Celery taskovi se ne izvršavaju

```bash
# Provjeri je li worker pokrenut
docker compose -f docker-compose.prod.yml ps celery_worker

# Provjeri Redis konekciju
docker compose -f docker-compose.prod.yml exec web python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value', 10)
>>> cache.get('test')
'value'  # Ako vrati None, Redis ne radi
```

### 502 Bad Gateway

**Problem:** Nginx ne može dohvatiti Django

**Rješenje:**
```bash
# Je li web kontejner pokrenut?
docker compose -f docker-compose.prod.yml ps web

# Radi li Gunicorn?
docker compose -f docker-compose.prod.yml logs web | grep gunicorn

# Test interno
docker compose -f docker-compose.prod.yml exec nginx curl http://web:8000/api/health/
```

### Disk space pun

```bash
# Provjeri prostor
df -h

# Očisti Docker cache
docker system prune -a

# Obriši stare logove
docker compose -f docker-compose.prod.yml exec web find /app/logs -name "*.log.*" -mtime +7 -delete
```

### SSL certifikat istekao

```bash
# Provjeri datum isteka
echo | openssl s_client -connect tvoja-domena.duckdns.org:443 2>/dev/null | openssl x509 -noout -dates

# Obnovi certifikat
sudo certbot renew --force-renewal

# Kopiraj nove certifikate
sudo cp /etc/letsencrypt/live/tvoja-domena.duckdns.org/*.pem /var/www/museum-backend/nginx/ssl/

# Restartaj nginx
docker compose -f docker-compose.prod.yml restart nginx
```

---

## Update aplikacije (novi deploy)

```bash
cd /var/www/museum-backend

# Povuci nove promjene
git pull origin main

# Rebuild i restart (bez downtime za bazu)
docker compose -f docker-compose.prod.yml up -d --build web celery_worker celery_beat

# Primijeni nove migracije
docker compose -f docker-compose.prod.yml exec web python manage.py migrate

# Provjeri logove
docker compose -f docker-compose.prod.yml logs -f web
```

---

## Korisne komande - Quick Reference

```bash
# === OSNOVNE ===
docker compose -f docker-compose.prod.yml up -d --build    # Start
docker compose -f docker-compose.prod.yml down             # Stop
docker compose -f docker-compose.prod.yml restart          # Restart
docker compose -f docker-compose.prod.yml ps               # Status

# === LOGOVI ===
docker compose -f docker-compose.prod.yml logs -f          # Svi
docker compose -f docker-compose.prod.yml logs -f web      # Django
docker compose -f docker-compose.prod.yml logs -f celery_worker  # Celery

# === DJANGO ===
docker compose -f docker-compose.prod.yml exec web python manage.py shell
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py showmigrations

# === DATABASE ===
docker compose -f docker-compose.prod.yml exec postgres psql -U museum_user museum_db
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U museum_user museum_db > backup.sql

# === DEBUG ===
docker compose -f docker-compose.prod.yml exec web python manage.py check
docker compose -f docker-compose.prod.yml exec web python manage.py check --deploy
```

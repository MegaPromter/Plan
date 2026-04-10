#!/usr/bin/env python3
"""
Deploy script for managesystems.ru (Timeweb Cloud server).
Connects via SSH and sets up the full Django stack:
  nginx -> gunicorn -> Django -> PostgreSQL
"""
import io
import sys
import time

import paramiko

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HOST = "72.56.13.101"
USER = "root"
PASS = "pBg6?CB.QBqpGa"
REPO = "https://github.com/MegaPromter/Plan.git"
APP_DIR = "/opt/planapp"
VENV = f"{APP_DIR}/venv"
DB_NAME = "planapp_db"
DB_USER = "planapp"
DB_PASS = "planapp_secure_2026"
DOMAIN = "managesystems.ru"


def ssh_exec(ssh, cmd, check=True):
    """Execute command and print output."""
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err and exit_code != 0:
        print(f"STDERR: {err}")
    if check and exit_code != 0:
        print(f"WARNING: exit code {exit_code}")
    return out, err, exit_code


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...")
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    print("Connected!\n")

    # 1. System packages
    print("=" * 60)
    print("STEP 1: Install system packages")
    print("=" * 60)
    ssh_exec(ssh, "apt-get update -qq")
    ssh_exec(
        ssh,
        "apt-get install -y -qq python3-pip python3-venv python3-dev "
        "libpq-dev postgresql postgresql-contrib nginx certbot "
        "python3-certbot-nginx git supervisor",
    )

    # 2. Setup PostgreSQL (только если базы ещё нет — не трогаем существующую)
    print("\n" + "=" * 60)
    print("STEP 2: PostgreSQL — проверка")
    print("=" * 60)
    ssh_exec(ssh, "systemctl enable postgresql && systemctl start postgresql")
    out, _, _ = ssh_exec(
        ssh,
        f'su - postgres -c "psql -tc \\"SELECT 1 FROM pg_database WHERE datname=\'{DB_NAME}\'\\""',
    )
    if "1" in out:
        print(f"  База {DB_NAME} уже существует — пропускаем создание")
    else:
        print(f"  База {DB_NAME} не найдена — создаём")
        ssh_exec(
            ssh,
            f'su - postgres -c "psql -c \\"CREATE USER {DB_USER} WITH PASSWORD \'{DB_PASS}\';\\""',
            check=False,
        )
        ssh_exec(
            ssh,
            f'su - postgres -c "psql -c \\"CREATE DATABASE {DB_NAME} OWNER {DB_USER};\\""',
            check=False,
        )
        ssh_exec(
            ssh,
            f'su - postgres -c "psql -c \\"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER};\\""',
            check=False,
        )

    # 3. Clone/update repo
    print("\n" + "=" * 60)
    print("STEP 3: Clone/update repository")
    print("=" * 60)
    out, _, code = ssh_exec(
        ssh, f"test -d {APP_DIR}/.git && echo exists || echo missing"
    )
    if "exists" in out:
        ssh_exec(
            ssh, f"cd {APP_DIR} && git fetch origin && git reset --hard origin/main"
        )
    else:
        ssh_exec(ssh, f"rm -rf {APP_DIR} && git clone {REPO} {APP_DIR}")

    # 4. Python venv & deps
    print("\n" + "=" * 60)
    print("STEP 4: Python venv & dependencies")
    print("=" * 60)
    ssh_exec(ssh, f"test -d {VENV}/bin || python3.11 -m venv {VENV}")
    ssh_exec(ssh, f"{VENV}/bin/pip install --upgrade pip")
    ssh_exec(ssh, f"{VENV}/bin/pip install -r {APP_DIR}/requirements.txt")

    # 5. Django .env
    print("\n" + "=" * 60)
    print("STEP 5: Configure .env")
    print("=" * 60)
    env_content = f"""SECRET_KEY=django-insecure-tw-$(head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 50)
DEBUG=False
ALLOWED_HOSTS={DOMAIN},www.{DOMAIN},72.56.13.101,localhost
DATABASE_URL=postgres://{DB_USER}:{DB_PASS}@localhost:5432/{DB_NAME}
CSRF_TRUSTED_ORIGINS=https://{DOMAIN}
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
"""
    # .env создаётся ТОЛЬКО при первом деплое — никогда не перезаписывается
    out, _, _ = ssh_exec(
        ssh, f'test -f {APP_DIR}/.env && echo "exists" || echo "missing"'
    )
    if "exists" in out:
        print("  .env уже существует — пропускаем (ручное редактирование сохранено)")
    else:
        print("  .env не найден — создаём из шаблона")
        ssh_exec(ssh, f"cat > {APP_DIR}/.env << 'ENVEOF'\n{env_content}ENVEOF")

    # 6. Django migrate & collectstatic
    print("\n" + "=" * 60)
    print("STEP 6: Django migrate & collectstatic")
    print("=" * 60)
    ssh_exec(ssh, f"cd {APP_DIR} && {VENV}/bin/python manage.py migrate --noinput")
    ssh_exec(
        ssh, f"cd {APP_DIR} && {VENV}/bin/python manage.py collectstatic --noinput"
    )

    # Load data dump if exists
    ssh_exec(
        ssh,
        f'cd {APP_DIR} && test -f data_dump.json && {VENV}/bin/python manage.py loaddata data_dump.json || echo "No dump to load"',
        check=False,
    )

    # 7. Gunicorn systemd service
    print("\n" + "=" * 60)
    print("STEP 7: Setup Gunicorn service")
    print("=" * 60)
    gunicorn_service = f"""[Unit]
Description=Gunicorn for PlanApp Django
After=network.target postgresql.service

[Service]
User=root
Group=www-data
WorkingDirectory={APP_DIR}
ExecStart={VENV}/bin/gunicorn config.wsgi:application \\
    --bind unix:{APP_DIR}/gunicorn.sock \\
    --workers 2 \\
    --timeout 120 \\
    --access-logfile /var/log/gunicorn-access.log \\
    --error-logfile /var/log/gunicorn-error.log
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    ssh_exec(
        ssh,
        f"cat > /etc/systemd/system/planapp.service << 'SVCEOF'\n{gunicorn_service}SVCEOF",
    )
    ssh_exec(ssh, "systemctl daemon-reload")
    ssh_exec(ssh, "systemctl enable planapp")
    ssh_exec(ssh, "systemctl restart planapp")
    time.sleep(2)
    ssh_exec(ssh, "systemctl status planapp --no-pager -l")

    # 8. Nginx config
    print("\n" + "=" * 60)
    print("STEP 8: Setup Nginx")
    print("=" * 60)
    nginx_conf = f"""server {{
    listen 80;
    server_name {DOMAIN} www.{DOMAIN};

    client_max_body_size 20M;

    location /static/ {{
        alias {APP_DIR}/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }}

    location /media/ {{
        alias {APP_DIR}/media/;
        expires 7d;
    }}

    location / {{
        proxy_pass http://unix:{APP_DIR}/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }}
}}
"""
    ssh_exec(
        ssh, f"cat > /etc/nginx/sites-available/planapp << 'NGXEOF'\n{nginx_conf}NGXEOF"
    )
    ssh_exec(
        ssh,
        "ln -sf /etc/nginx/sites-available/planapp /etc/nginx/sites-enabled/planapp",
    )
    ssh_exec(ssh, "rm -f /etc/nginx/sites-enabled/default")
    ssh_exec(ssh, "nginx -t")
    ssh_exec(ssh, "systemctl reload nginx")

    # 9. SSL with Let's Encrypt
    print("\n" + "=" * 60)
    print("STEP 9: SSL certificate (Let's Encrypt)")
    print("=" * 60)
    ssh_exec(
        ssh,
        f"certbot --nginx -d {DOMAIN} --non-interactive --agree-tos -m admin@{DOMAIN} --redirect",
        check=False,
    )

    # 10. Final check
    print("\n" + "=" * 60)
    print("STEP 10: Final verification")
    print("=" * 60)
    ssh_exec(ssh, f'curl -s -o /dev/null -w "%{{http_code}}" http://localhost/')
    ssh_exec(ssh, "systemctl is-active planapp")
    ssh_exec(ssh, "systemctl is-active nginx")

    ssh.close()
    print("\n" + "=" * 60)
    print(f"DEPLOY COMPLETE! Site: https://{DOMAIN}/")
    print("=" * 60)


if __name__ == "__main__":
    main()

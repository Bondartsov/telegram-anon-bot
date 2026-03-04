#!/bin/bash
# Auto-deploy Telegram Bot to VM
# Usage: ./deploy.sh [--first-run]
#
# --first-run : install systemd service for the first time
# (no flag)   : sync code and restart existing service

set -e

VM_HOST="YOUR_VM_IP"
VM_USER="user"
VM_PATH="/home/user/telegram-anon-bot"
SERVICE_NAME="anon-bot"
FIRST_RUN=false

for arg in "$@"; do
  case $arg in
    --first-run) FIRST_RUN=true ;;
  esac
done

echo "=== Auto-deploy: Telegram Anon Bot ==="
echo "Host   : $VM_HOST"
echo "Path   : $VM_PATH"
echo ""

# 1. Sync files
echo "[1/4] Syncing files..."
rsync -az --progress \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude 'data/*.db' \
  --exclude 'venv' \
  --exclude '.venv' \
  ./ ${VM_USER}@${VM_HOST}:${VM_PATH}/

# 2. Install dependencies
echo "[2/4] Installing dependencies..."
ssh ${VM_USER}@${VM_HOST} bash <<EOF
set -e
cd ${VM_PATH}
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet -r requirements.txt
EOF

# 3. First-run: setup systemd service
if [ "$FIRST_RUN" = true ]; then
  echo "[3/4] Setting up systemd service..."
  ssh ${VM_USER}@${VM_HOST} bash <<EOF
set -e
cd ${VM_PATH}
mkdir -p data
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "WARNING: Edit .env before starting: nano ${VM_PATH}/.env"
fi
sudo cp ${VM_PATH}/anon-bot.service /etc/systemd/system/${SERVICE_NAME}.service
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
EOF
else
  echo "[3/4] Skipping service setup (not first run)"
fi

# 4. Restart and verify
echo "[4/4] Restarting service..."
ssh ${VM_USER}@${VM_HOST} bash <<EOF
sudo systemctl restart ${SERVICE_NAME}
sleep 2
STATUS=\$(systemctl is-active ${SERVICE_NAME})
if [ "\$STATUS" = "active" ]; then
  echo "  Service is active."
else
  echo "  ERROR: service not running (status: \$STATUS)"
  journalctl -u ${SERVICE_NAME} -n 20 --no-pager
  exit 1
fi
EOF

echo ""
echo "=== Deploy complete ==="
echo "Logs  : ssh ${VM_USER}@${VM_HOST} 'journalctl -u ${SERVICE_NAME} -f'"
echo "Status: ssh ${VM_USER}@${VM_HOST} 'systemctl status ${SERVICE_NAME}'"

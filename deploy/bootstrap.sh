#!/usr/bin/env bash
# One-time setup of a fresh Oracle Cloud Ubuntu VM for the backend stack.
# Run it on the VM, or from your machine with:
#   ssh ubuntu@<VM_IP> 'bash -s' < deploy/bootstrap.sh
# Safe to re-run: every step skips what's already done.
set -euo pipefail

# Oracle's Ubuntu image rejects every inbound port but SSH in iptables,
# on top of the subnet's Security List (opened in the console).
for port in 80 443; do
  sudo iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null ||
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "$port" -j ACCEPT
done
sudo netfilter-persistent save

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"

# Secrets are generated here and never leave the VM. API_DOMAIN defaults to
# the VM's public IP through sslip.io; edit it later to use a real domain.
env_file="$HOME/qualitative-coding/deploy/.env"
if [ ! -f "$env_file" ]; then
  mkdir -p "$(dirname "$env_file")"
  public_ip=$(curl -fsS https://api.ipify.org)
  umask 077
  cat > "$env_file" <<EOF
API_DOMAIN=${public_ip//./-}.sslip.io
POSTGRES_PASSWORD=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
FRONTEND_URL=https://qualitative-coding-tool.vercel.app
BREVO_API_KEY=
BREVO_SENDER_EMAIL=
EOF
fi

echo "API_DOMAIN: $(grep '^API_DOMAIN=' "$env_file" | cut -d= -f2)"

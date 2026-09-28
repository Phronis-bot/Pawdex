#!/bin/sh
# One-time setup of a fresh Ubuntu 24.04 server for Pawdex. Run as root:
#   sh deploy/setup-server.sh
set -eu

apt-get update
apt-get upgrade -y
apt-get install -y ufw curl

# Docker Engine + compose plugin, from Docker's official install script.
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
fi

# Firewall: SSH and web only. The database and API ports are never exposed.
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Log in with the SSH key only, never a password.
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl reload ssh || systemctl reload sshd

echo "Server ready. Next: create /opt/pawdex/.env from deploy/.env.example, then run deploy/push.ps1 from your PC"

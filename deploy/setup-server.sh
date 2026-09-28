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

# Log in with the SSH key only, never a password. A drop-in named 00-* is read first, so it
# wins over the hosting image's 50-cloud-init.conf (which turns passwords back on).
printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin prohibit-password\n' \
    > /etc/ssh/sshd_config.d/00-pawdex.conf
sshd -t
# Ubuntu 24.04 starts sshd per connection via ssh.socket; older releases run ssh.service.
systemctl restart ssh.socket 2>/dev/null || systemctl restart ssh

echo "Server ready. Next: create /opt/pawdex/.env from deploy/.env.example, then run deploy/push.ps1 from your PC"

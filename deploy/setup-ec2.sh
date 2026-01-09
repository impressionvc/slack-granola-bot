#!/bin/bash
# =============================================================================
# EC2 Setup Script for Granola Slack Bot
# Run this on a fresh Ubuntu 22.04 EC2 instance
# =============================================================================

set -e  # Exit on any error

echo "=========================================="
echo "Granola Slack Bot - EC2 Setup"
echo "=========================================="

# Update system
echo "[1/5] Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
echo "[2/5] Installing Docker..."
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add current user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose standalone (for older syntax compatibility)
echo "[3/5] Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create app directory
echo "[4/5] Setting up application directory..."
APP_DIR="$HOME/granola-bot"
mkdir -p "$APP_DIR"

echo "[5/5] Setup complete!"
echo ""
echo "=========================================="
echo "NEXT STEPS:"
echo "=========================================="
echo ""
echo "1. Log out and back in (for docker group):"
echo "   exit"
echo "   ssh -i your-key.pem ubuntu@<ip>"
echo ""
echo "2. Copy your code to the server:"
echo "   scp -i your-key.pem -r /path/to/SlackBot/* ubuntu@<ip>:~/granola-bot/"
echo ""
echo "3. Create .env file with your tokens:"
echo "   cd ~/granola-bot"
echo "   nano .env"
echo ""
echo "   Add these lines:"
echo "   SLACK_BOT_TOKEN=xoxb-your-token"
echo "   SLACK_APP_TOKEN=xapp-your-token"
echo ""
echo "4. Build and run:"
echo "   docker-compose up -d --build"
echo ""
echo "5. Check logs:"
echo "   docker-compose logs -f"
echo ""
echo "=========================================="

#!/bin/bash
# =============================================================================
# First-Time EC2 Setup for GitHub Auto-Deploy
# Run this ONCE on your EC2 instance after creating it
# =============================================================================

set -e

echo "=========================================="
echo "Granola Bot - First Time Setup"
echo "=========================================="

# Install Docker
echo "[1/4] Installing Docker..."
sudo apt update
sudo apt install -y docker.io docker-compose git
sudo usermod -aG docker $USER

# Clone your repo (replace with your actual GitHub URL)
echo "[2/4] Cloning repository..."
echo ""
echo "Enter your GitHub repository URL (e.g., https://github.com/username/repo.git):"
read REPO_URL

cd ~
git clone "$REPO_URL" granola-bot
cd granola-bot

# Create .env file
echo "[3/4] Setting up environment..."
echo ""
echo "Enter your SLACK_BOT_TOKEN (starts with xoxb-):"
read BOT_TOKEN
echo "Enter your SLACK_APP_TOKEN (starts with xapp-):"
read APP_TOKEN

cat > .env << EOF
SLACK_BOT_TOKEN=$BOT_TOKEN
SLACK_APP_TOKEN=$APP_TOKEN
EOF

echo ".env file created!"

# Build and run
echo "[4/4] Building and starting bot..."
echo ""
echo "NOTE: You need to log out and back in for docker permissions."
echo "After logging back in, run:"
echo ""
echo "  cd ~/granola-bot && docker-compose up -d --build"
echo ""
echo "=========================================="
echo "Setup complete! Log out and back in now."
echo "=========================================="

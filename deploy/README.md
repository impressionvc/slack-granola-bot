# Deploying Granola Bot to AWS EC2

## Prerequisites

- AWS account
- SSH key pair for EC2
- Your Slack tokens ready:
  - `SLACK_BOT_TOKEN` (starts with `xoxb-`)
  - `SLACK_APP_TOKEN` (starts with `xapp-`)

---

## Step 1: Create EC2 Instance

1. Go to **AWS Console** → **EC2** → **Launch Instance**

2. Configure:
   | Setting | Value |
   |---------|-------|
   | Name | `granola-bot` |
   | AMI | Ubuntu Server 22.04 LTS |
   | Instance type | `t3.small` (recommended) or `t3.micro` (budget) |
   | Key pair | Select or create one |
   | Security group | Allow SSH (port 22) from your IP |

3. Click **Launch Instance**

4. Note the **Public IPv4 address** once it's running

---

## Step 2: Connect to EC2

```bash
# Replace with your key file and EC2 IP
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

---

## Step 3: Run Setup Script

On the EC2 instance:

```bash
# Download and run setup script (or copy manually)
curl -O https://raw.githubusercontent.com/YOUR_REPO/main/deploy/setup-ec2.sh
chmod +x setup-ec2.sh
./setup-ec2.sh
```

Or manually install Docker:

```bash
sudo apt update && sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER
exit  # Log out and back in
```

---

## Step 4: Copy Your Code to EC2

From your **local machine**:

```bash
# Copy the entire project
scp -i your-key.pem -r /Users/saketrane/Desktop/SlackBot/* ubuntu@<EC2-IP>:~/granola-bot/
```

Or use git:

```bash
# On EC2
git clone <your-repo-url> granola-bot
cd granola-bot
```

---

## Step 5: Configure Environment

On EC2:

```bash
cd ~/granola-bot

# Create .env file
nano .env
```

Add your tokens:

```
SLACK_BOT_TOKEN=xoxb-your-actual-token
SLACK_APP_TOKEN=xapp-your-actual-token
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## Step 6: Build and Run

```bash
cd ~/granola-bot

# Build and start (first time takes ~2-3 minutes)
docker-compose up -d --build

# Check it's running
docker-compose ps

# View logs
docker-compose logs -f
```

You should see:
```
⚡️ Bolt app is running!
Starting to receive messages from a new connection
```

---

## Managing the Bot

### View Logs
```bash
docker-compose logs -f
```

### Restart
```bash
docker-compose restart
```

### Stop
```bash
docker-compose down
```

### Update Code
```bash
# Copy new files from local machine, then:
docker-compose up -d --build
```

### Check Status
```bash
docker-compose ps
```

---

## Troubleshooting

### Bot not connecting
- Check your tokens in `.env`
- Ensure the Slack app has Socket Mode enabled
- View logs: `docker-compose logs -f`

### Container keeps restarting
```bash
# Check what's wrong
docker-compose logs --tail=50
```

### Out of memory (on t3.micro)
- Upgrade to `t3.small`
- Or add swap space:
  ```bash
  sudo fallocate -l 1G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  ```

---

## Costs

| Instance | Monthly Cost | Notes |
|----------|--------------|-------|
| t3.micro | ~$8 | May need swap for Chromium |
| t3.small | ~$15 | Recommended |
| t3.medium | ~$30 | Overkill for this bot |

---

## Security Notes

- Never commit `.env` to git
- Keep your EC2 security group restricted to your IP for SSH
- The bot only makes outbound connections (no inbound ports needed except SSH)

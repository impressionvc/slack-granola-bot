# Granola Link Scraper Slack Bot

<!-- Deployed via GitHub Actions -->

A Python Slack bot that monitors channels for Granola meeting note links, scrapes the content, and posts a summary as a threaded reply.

## Features

- Monitors all channels the bot is invited to
- Detects Granola meeting note URLs (`notes.granola.ai/d/...`)
- Scrapes meeting content (titles, summaries, action items)
- Posts scraped content as a threaded reply (up to 3,000 characters)
- Only processes messages sent after the bot starts

## Prerequisites

- Python 3.9+
- A Slack workspace with admin access to create apps

## Slack App Setup

### 1. Create the Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** > **From scratch**
3. Name it (e.g., "Granola Scraper") and select your workspace

### 2. Enable Socket Mode

1. Navigate to **Socket Mode** in the left sidebar
2. Toggle **Enable Socket Mode** to ON
3. Create an app-level token with `connections:write` scope
4. Save this token as `SLACK_APP_TOKEN` (starts with `xapp-`)

### 3. Configure Bot Token Scopes

1. Go to **OAuth & Permissions**
2. Under **Bot Token Scopes**, add:
   - `channels:history` - Read messages in public channels
   - `channels:read` - View basic channel info
   - `chat:write` - Send messages as the bot
   - `groups:history` - Read messages in private channels (optional)
   - `groups:read` - View basic private channel info (optional)

### 4. Subscribe to Events

1. Go to **Event Subscriptions**
2. Toggle **Enable Events** to ON
3. Under **Subscribe to bot events**, add:
   - `message.channels` - Messages in public channels
   - `message.groups` - Messages in private channels (optional)

### 5. Install the App

1. Go to **Install App**
2. Click **Install to Workspace** and authorize
3. Copy the **Bot User OAuth Token** as `SLACK_BOT_TOKEN` (starts with `xoxb-`)

### 6. Invite Bot to Channels

In Slack, invite the bot to any channel where you want it active:

```
/invite @YourBotName
```

## Installation

1. Clone this repository:

```bash
cd SlackBot
```

2. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your actual tokens
```

## Usage

Run the bot:

```bash
python -m src.main
```

The bot will start listening for messages. When someone posts a Granola link in a channel where the bot is present, it will:

1. Detect the Granola URL
2. Scrape the meeting content
3. Reply in a thread with the extracted content

## Project Structure

```
SlackBot/
├── requirements.txt
├── .env.example
├── README.md
└── src/
    ├── __init__.py
    ├── main.py              # Entry point, app initialization
    ├── config.py            # Environment config with validation
    ├── handlers/
    │   ├── __init__.py
    │   └── message_handler.py   # Slack message event handler
    ├── scrapers/
    │   ├── __init__.py
    │   └── granola_scraper.py   # Granola-specific scraping logic
    └── utils/
        ├── __init__.py
        └── url_utils.py         # URL extraction and cleaning
```

## Configuration

Environment variables can be set in a `.env` file:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | Yes | - | Bot User OAuth Token (xoxb-...) |
| `SLACK_APP_TOKEN` | Yes | - | App-Level Token (xapp-...) |
| `MAX_CONTENT_LENGTH` | No | 3000 | Max characters for scraped content |
| `REQUEST_TIMEOUT` | No | 10 | HTTP request timeout in seconds |

## License

MIT
# Auto-deploy test

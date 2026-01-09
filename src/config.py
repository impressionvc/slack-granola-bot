"""Configuration management for the Slack bot."""

import os
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

from dotenv import load_dotenv

# Names to filter out when extracting company name from meeting titles
IMPRESSION_TEAM_NAMES: Tuple[str, ...] = (
    "impression",
    "christian",
    "maor",
    "quinn",
    "erica",
    "saket",
    "ventures",
)

# Actual team member names (for extracting "On Call" from title)
IMPRESSION_TEAM_MEMBERS: Tuple[str, ...] = (
    "christian",
    "maor",
    "quinn",
    "erica",
    "saket",
)

# Channels that get special dealflow formatting (Company / On Call header)
DEALFLOW_CHANNELS: Tuple[str, ...] = (
    "dealflow",
    "granola-scraper-test",
)


@dataclass(frozen=True)
class Config:
    """Immutable configuration settings for the bot."""

    slack_bot_token: str
    slack_app_token: str
    max_content_length: int = 4000
    request_timeout: int = 90  # Long timeout for Playwright to fully render page

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.slack_bot_token.startswith("xoxb-"):
            raise ValueError(
                "SLACK_BOT_TOKEN must start with 'xoxb-'. "
                "Please check your Bot User OAuth Token."
            )
        if not self.slack_app_token.startswith("xapp-"):
            raise ValueError(
                "SLACK_APP_TOKEN must start with 'xapp-'. "
                "Please check your App-Level Token."
            )


def load_config(env_file: Optional[str] = None) -> Config:
    """Load configuration from environment variables.

    Args:
        env_file: Optional path to .env file.

    Returns:
        Validated Config instance.

    Raises:
        SystemExit: If required environment variables are missing.
    """
    load_dotenv(env_file)

    slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
    slack_app_token = os.getenv("SLACK_APP_TOKEN")

    missing = []
    if not slack_bot_token:
        missing.append("SLACK_BOT_TOKEN")
    if not slack_app_token:
        missing.append("SLACK_APP_TOKEN")

    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Set them in your .env file. See .env.example", file=sys.stderr)
        sys.exit(1)

    max_content_length = int(os.getenv("MAX_CONTENT_LENGTH", "4000"))
    request_timeout = int(os.getenv("REQUEST_TIMEOUT", "60"))

    return Config(
        slack_bot_token=slack_bot_token,
        slack_app_token=slack_app_token,
        max_content_length=max_content_length,
        request_timeout=request_timeout,
    )

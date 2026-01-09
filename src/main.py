"""Main entry point for the Granola Link Scraper Slack Bot."""

import logging
import signal
import sys
import time
from typing import NoReturn

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from src.config import load_config
from src.handlers.message_handler import MessageHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def create_app() -> tuple[App, SocketModeHandler]:
    """Create and configure the Slack app.

    Returns:
        Tuple of (App, SocketModeHandler) instances.
    """
    # Load configuration
    config = load_config()

    # Capture start time for filtering old messages
    start_timestamp = time.time()
    logger.info("Bot start timestamp: %s", start_timestamp)

    # Initialize the Slack app
    app = App(token=config.slack_bot_token)

    # Register handlers
    message_handler = MessageHandler(config, start_timestamp)
    message_handler.register(app)

    # Create Socket Mode handler
    socket_handler = SocketModeHandler(app, config.slack_app_token)

    return app, socket_handler


def setup_signal_handlers(socket_handler: SocketModeHandler) -> None:
    """Set up signal handlers for graceful shutdown.

    Args:
        socket_handler: The Socket Mode handler to close on shutdown.
    """
    def handle_shutdown(signum: int, frame) -> NoReturn:
        logger.info("Received shutdown signal (%s), closing connections...", signum)
        socket_handler.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)


def main() -> None:
    """Main entry point."""
    logger.info("Starting Granola Link Scraper Slack Bot...")

    try:
        app, socket_handler = create_app()
        setup_signal_handlers(socket_handler)

        logger.info("Bot is ready! Listening for messages...")
        socket_handler.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

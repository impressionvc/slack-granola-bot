"""Message event handler for the Slack bot."""

import logging
from slack_bolt import App
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from src.config import Config
from src.scrapers.granola_scraper import scrape_granola_page, truncate_content
from src.utils.url_utils import clean_url, extract_granola_url

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handles incoming Slack messages and processes Granola links."""

    def __init__(self, config: Config, start_timestamp: float):
        """Initialize the message handler.

        Args:
            config: Application configuration.
            start_timestamp: Unix timestamp when the bot started.
        """
        self._config = config
        self._start_timestamp = start_timestamp
        # Create a completely standalone WebClient
        self._client = WebClient(token=config.slack_bot_token)
        logger.info("WebClient initialized with token")
        
        # Get our own bot ID to prevent self-replies
        self._own_bot_id = None
        try:
            auth_response = self._client.auth_test()
            self._own_bot_id = auth_response.get("bot_id")
            logger.info("Own bot ID: %s", self._own_bot_id)
        except Exception as e:
            logger.warning("Could not fetch own bot ID: %s", e)

    def register(self, app: App) -> None:
        """Register event handlers with the Slack app.

        Args:
            app: The Slack Bolt app instance.
        """
        # Register with minimal parameters to avoid any automatic behavior
        @app.event("message")
        def handle_message_event(body, ack):
            ack()  # Acknowledge immediately
            event = body.get("event", {})
            self._process_message(event)
        
        logger.info("Message handler registered")

    def _process_message(self, event: dict) -> None:
        """Process a message event.

        Args:
            event: The Slack event payload.
        """
        # Debug: log incoming bot messages to see their structure
        if event.get("bot_id"):
            logger.info("Received bot message from bot_id=%s", event.get("bot_id"))
            logger.info("  text: %s", event.get("text", "")[:100] if event.get("text") else "(empty)")
            logger.info("  has attachments: %s", len(event.get("attachments", [])))
            logger.info("  has blocks: %s", len(event.get("blocks", [])))
        
        # Skip only our own bot messages to prevent loops
        # Allow other bots (like Granola's Slack app) through
        message_bot_id = event.get("bot_id")
        if message_bot_id and message_bot_id == self._own_bot_id:
            logger.debug("Skipping own bot message")
            return

        # Skip message edits and deletions
        subtype = event.get("subtype")
        if subtype in ("message_changed", "message_deleted", "channel_join", "channel_leave"):
            return

        # Only process new messages (after bot started)
        message_ts = float(event.get("ts", 0))
        if message_ts < self._start_timestamp:
            return

        # Collect all text to search for URLs
        # Include: text, attachments, and blocks
        text_sources = []
        
        # Main message text
        if event.get("text"):
            text_sources.append(event.get("text"))
        
        # Check attachments (used by Granola's Slack app for rich cards)
        for attachment in event.get("attachments", []):
            if attachment.get("title_link"):
                text_sources.append(attachment.get("title_link"))
            if attachment.get("from_url"):
                text_sources.append(attachment.get("from_url"))
            if attachment.get("original_url"):
                text_sources.append(attachment.get("original_url"))
            if attachment.get("text"):
                text_sources.append(attachment.get("text"))
            if attachment.get("fallback"):
                text_sources.append(attachment.get("fallback"))
        
        # Check blocks (another rich message format)
        for block in event.get("blocks", []):
            if block.get("type") == "section" and block.get("text", {}).get("text"):
                text_sources.append(block["text"]["text"])
            # Check for URL elements in blocks
            for element in block.get("elements", []):
                if element.get("type") == "link" and element.get("url"):
                    text_sources.append(element.get("url"))
                if element.get("type") == "rich_text_section":
                    for sub_elem in element.get("elements", []):
                        if sub_elem.get("type") == "link" and sub_elem.get("url"):
                            text_sources.append(sub_elem.get("url"))
        
        # Combine all text sources
        combined_text = " ".join(text_sources)
        
        if not combined_text:
            return

        # Check for Granola URL in all collected text
        granola_url = extract_granola_url(combined_text)
        if not granola_url:
            return

        channel = event.get("channel")
        if not channel:
            return

        # Clean the URL
        clean_granola_url = clean_url(granola_url)
        logger.info("=" * 60)
        logger.info("PROCESSING GRANOLA LINK")
        logger.info("URL: %s", clean_granola_url)
        logger.info("Channel: %s", channel)
        logger.info("=" * 60)

        # Scrape the content (this will wait for the full page to load)
        logger.info("Starting scraper (this may take up to 90 seconds)...")
        result = scrape_granola_page(
            clean_granola_url,
            timeout=self._config.request_timeout,
        )

        if not result.success:
            logger.error("Scrape FAILED: %s", result.error)
            
            # Check if login is required
            if result.requires_login:
                self._post_new_message(
                    channel=channel,
                    text=f"🔒 *Could not access the page*\n"
                         f"URL: `{clean_granola_url}`\n\n"
                         f"_Make the page public in Granola to share it._",
                )
            else:
                self._post_new_message(
                    channel=channel,
                    text=f"⚠️ *Could not fetch Granola content*\n"
                         f"URL: `{clean_granola_url}`\n"
                         f"Error: {result.error}",
                )
            return

        # Check for empty note
        if not result.content or len(result.content.strip()) < 50:
            logger.error("Scrape returned empty content")
            self._post_new_message(
                channel=channel,
                text=f"📭 *This Granola note is empty*\n"
                     f"URL: `{clean_granola_url}`",
            )
            return
        
        # Check for "no access" in content (backup check)
        if "don't have access" in result.content.lower() or "login to access" in result.content.lower():
            logger.error("Note requires authentication")
            self._post_new_message(
                channel=channel,
                text=f"🔒 *Could not access the page*\n"
                     f"URL: `{clean_granola_url}`\n\n"
                     f"_Make the page public in Granola to share it._",
            )
            return

        # Truncate if needed
        content = truncate_content(
            result.content,
            max_length=self._config.max_content_length,
        )

        # Post as a NEW message to the channel
        logger.info("Scrape SUCCESS - posting %d chars", len(content))
        self._post_new_message(
            channel=channel,
            text=content,
        )

    def _post_new_message(self, channel: str, text: str) -> None:
        """Post a NEW message to a channel.

        This uses a standalone WebClient and explicitly does NOT
        include thread_ts, ensuring the message is posted as a
        new message in the channel, NOT as a reply.

        Args:
            channel: Channel ID.
            text: Message text.
        """
        logger.info("-" * 40)
        logger.info("POSTING NEW MESSAGE")
        logger.info("Channel: %s", channel)
        logger.info("Text length: %d chars", len(text))
        logger.info("Thread_ts: NONE (posting as new message)")
        logger.info("-" * 40)
        
        try:
            response = self._client.chat_postMessage(
                channel=channel,
                text=text,
                unfurl_links=False,
                unfurl_media=False,
                mrkdwn=True,
                # IMPORTANT: No thread_ts parameter = new message
            )
            
            if response.get("ok"):
                logger.info("✓ SUCCESS: Message posted as ts=%s", response.get("ts"))
            else:
                logger.error("✗ FAILED: %s", response.get("error"))
                
        except SlackApiError as e:
            logger.error("✗ Slack API error: %s", e.response.get("error", str(e)))
        except Exception as e:
            logger.exception("✗ Failed to post: %s", e)

"""Message event handler for the Slack bot."""

import logging
from typing import Optional, Dict, Any

from slack_bolt import App
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from src.config import Config, DEALFLOW_CHANNELS
from src.scrapers.granola_scraper import (
    scrape_granola_page,
    truncate_content,
    extract_company_name,
    extract_team_member_from_title,
)
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
        self._own_bot_id: Optional[str] = None
        try:
            auth_response = self._client.auth_test()
            self._own_bot_id = auth_response.get("bot_id")
            logger.info("Own bot ID: %s", self._own_bot_id)
        except Exception as e:
            logger.warning("Could not fetch own bot ID: %s", e)

        # Cache for channel names (channel_id -> channel_name)
        self._channel_name_cache: Dict[str, str] = {}

    def _get_channel_name(self, channel_id: str) -> Optional[str]:
        """Get the channel name from a channel ID.

        Args:
            channel_id: The Slack channel ID.

        Returns:
            The channel name (without #), or None if lookup fails.
        """
        # Check cache first
        if channel_id in self._channel_name_cache:
            return self._channel_name_cache[channel_id]

        try:
            response = self._client.conversations_info(channel=channel_id)
            if response.get("ok"):
                channel_name = response.get("channel", {}).get("name")
                if channel_name:
                    self._channel_name_cache[channel_id] = channel_name
                    return channel_name
        except SlackApiError as e:
            logger.warning("Could not fetch channel name for %s: %s", channel_id, e)
        except Exception as e:
            logger.warning("Error fetching channel name: %s", e)

        return None

    def _get_user_display_name(self, user_id: str) -> Optional[str]:
        """Get a user's display name from their user ID.

        Args:
            user_id: The Slack user ID.

        Returns:
            The user's display name or real name, or None if lookup fails.
        """
        try:
            response = self._client.users_info(user=user_id)
            if response.get("ok"):
                user = response.get("user", {})
                profile = user.get("profile", {})
                # Prefer display name, fall back to real name
                return (
                    profile.get("display_name")
                    or profile.get("real_name")
                    or user.get("name")
                )
        except SlackApiError as e:
            logger.warning("Could not fetch user name for %s: %s", user_id, e)
        except Exception as e:
            logger.warning("Error fetching user name: %s", e)

        return None

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

        # Get the user who sent the message (for dealflow formatting)
        # When a human posts directly, event["user"] is set
        # When Granola's bot posts, we need to check for alternative sources
        user_id: Optional[str] = event.get("user")
        
        # Debug: log user info for dealflow troubleshooting
        if not user_id:
            logger.info("No user_id in event - checking for bot message metadata")
            logger.info("  bot_id: %s", event.get("bot_id"))
            logger.info("  bot_profile: %s", event.get("bot_profile", {}).get("name"))
            # Some integrations include the triggering user
            if event.get("username"):
                logger.info("  username field found: %s", event.get("username"))

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

        # Check if this is a dealflow channel (needs special formatting)
        channel_name = self._get_channel_name(channel)
        is_dealflow = channel_name and channel_name in DEALFLOW_CHANNELS

        # Build final content
        content = result.content
        
        if is_dealflow:
            # Add Company/On Call header for dealflow channels
            header_parts = []
            
            # Extract company name from title
            company = extract_company_name(result.title) if result.title else None
            if company:
                header_parts.append(f"*Company/Founder:* {company}")
            
            # Get "On Call" - first try to extract from title, then fall back to sender
            on_call_name = None
            
            # Try to find team member name in title (e.g., "Christian x Acme Corp")
            if result.title:
                on_call_name = extract_team_member_from_title(result.title)
                if on_call_name:
                    logger.info("Found team member in title: %s", on_call_name)
            
            # Fall back to message sender if no team member in title
            if not on_call_name and user_id:
                on_call_name = self._get_user_display_name(user_id)
                if on_call_name:
                    logger.info("Using sender name: %s", on_call_name)
            
            if on_call_name:
                header_parts.append(f"*On Call:* {on_call_name}")
            
            if header_parts:
                header = "\n".join(header_parts)
                content = f"{header}\n\n{content}"
                logger.info("Added dealflow header: %s", header.replace("\n", " | "))

        # Truncate if needed
        content = truncate_content(
            content,
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

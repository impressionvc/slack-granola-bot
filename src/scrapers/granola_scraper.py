"""Scraper for Granola meeting notes using Playwright."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from src.config import IMPRESSION_TEAM_NAMES, IMPRESSION_TEAM_MEMBERS

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    requires_login: bool = False
    title: Optional[str] = None  # Raw title for company name extraction


def extract_company_name(title: str) -> Optional[str]:
    """Extract company name from a meeting title by filtering out Impression team names.

    Args:
        title: The meeting note title (e.g., "Acme Corp x Impression Ventures").

    Returns:
        The company name with team names filtered out, or None if no company found.
    """
    if not title:
        return None

    # Common separators in meeting titles (including without spaces)
    separators = [" <> ", "<>", " x ", " X ", " - ", " | ", " / ", "/", " & ", " and ", " with "]
    
    # Common meeting words to filter out
    skip_words = {
        "intro", "introduction", "call", "meeting", "sync", "check-in", 
        "checkin", "follow-up", "followup", "chat", "discussion", "review",
        "demo", "presentation", "kickoff", "onboarding", "interview",
    }
    
    # Split by separators and collect parts
    parts = [title]
    for sep in separators:
        new_parts = []
        for part in parts:
            new_parts.extend(part.split(sep))
        parts = new_parts
    
    # Filter and find the company name
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        part_lower = part.lower()
        
        # Skip if it's just a meeting word (e.g., "Intro")
        if part_lower in skip_words:
            continue
        
        # Skip if it's a team name
        if part_lower in IMPRESSION_TEAM_NAMES:
            continue
        
        # Check if this part contains only team names and skip words
        part_words = re.findall(r'\w+', part_lower)
        remaining_words = [w for w in part_words if w not in IMPRESSION_TEAM_NAMES and w not in skip_words]
        
        if not remaining_words:
            continue
        
        # Return the cleaned-up part (just the meaningful words)
        # If the part has extra words mixed in, extract just the company name
        if len(remaining_words) == len(part_words):
            # All words are meaningful, return as-is
            return part
        else:
            # Some words were filtered, return just the remaining words
            return " ".join(word.capitalize() for word in remaining_words)
    
    return None


def extract_team_member_from_title(title: str) -> Optional[str]:
    """Extract Impression team member name from a meeting title.

    Args:
        title: The meeting note title (e.g., "Christian x Acme Corp").

    Returns:
        The team member's name (capitalized) if found, or None.
    """
    if not title:
        return None

    title_lower = title.lower()
    
    # Check if any team member name appears in the title
    for member in IMPRESSION_TEAM_MEMBERS:
        # Use word boundary check to avoid partial matches
        # e.g., "christian" shouldn't match "christiansen"
        import re
        if re.search(rf'\b{member}\b', title_lower):
            return member.capitalize()
    
    return None


def scrape_granola_page(url: str, timeout: int = 90) -> ScrapeResult:
    """Scrape content from a Granola meeting notes page.

    Args:
        url: The Granola URL to scrape.
        timeout: Page load timeout in seconds.

    Returns:
        ScrapeResult with the scraped content or error message.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            try:
                logger.info("Loading page: %s", url)
                page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
                
                logger.info("Waiting for h1 selector...")
                page.wait_for_selector("h1", timeout=30000)
                
                logger.info("Waiting 5 seconds for content to fully render...")
                page.wait_for_timeout(5000)
                
                # Check if this is a login-required page
                title = page.locator("h1").first.inner_text(timeout=5000).strip()
                
                login_indicators = [
                    "login to access",
                    "sign in to access", 
                    "you don't have access",
                    "you do not have access",
                    "access denied",
                ]
                
                if any(indicator in title.lower() for indicator in login_indicators):
                    logger.info("Page requires login: %s", title)
                    return ScrapeResult(
                        success=False,
                        error="This note is private. Make the page public to share it.",
                        requires_login=True,
                    )
                
                # Extract content with proper formatting
                logger.info("Extracting content...")
                content = _extract_formatted_content(page, title)

                if not content or len(content) < 50:
                    logger.error("Extracted content too short: %d chars", len(content) if content else 0)
                    return ScrapeResult(
                        success=False,
                        error="Could not extract content from the page.",
                    )

                logger.info("Successfully extracted %d characters", len(content))
                return ScrapeResult(success=True, content=content, title=title)

            except PlaywrightTimeout as e:
                logger.error("Page load timed out: %s", e)
                return ScrapeResult(
                    success=False,
                    error="Page load timed out.",
                )
            except Exception as e:
                logger.exception("Error during scraping: %s", e)
                return ScrapeResult(
                    success=False,
                    error=f"Scraping error: {str(e)}",
                )
            finally:
                browser.close()

    except Exception as e:
        logger.exception("Failed to initialize browser: %s", e)
        return ScrapeResult(
            success=False,
            error=f"Browser error: {str(e)}",
        )


def _extract_formatted_content(page, title: str) -> Optional[str]:
    """Extract content with proper section headings and bullet points.

    Args:
        page: Playwright page object.
        title: The main title already extracted.

    Returns:
        Formatted text content.
    """
    parts = []
    
    # Add main title
    if title:
        parts.append(f"📋 *{title}*")
        parts.append("")

    # Use JavaScript to extract content in proper order with headings
    try:
        content_data = page.evaluate("""
            () => {
                const results = [];
                const editor = document.querySelector('.ProseMirror');
                if (!editor) return results;
                
                const seen = new Set();
                
                // Walk through all elements in the editor
                const elements = editor.querySelectorAll('*');
                
                for (const el of elements) {
                    // Check if it's a section heading
                    const isHeading = el.classList.contains('viewSource_view-source-heading__sJegq') ||
                                     (el.className && typeof el.className === 'string' && el.className.includes('heading')) ||
                                     el.matches('[data-node-view-content] > div');
                    
                    if (isHeading && el.closest('.node-heading')) {
                        const text = el.innerText?.trim();
                        if (text && text.length > 2 && !seen.has(text)) {
                            seen.add(text);
                            results.push({type: 'heading', text: text});
                        }
                    }
                    
                    // Check if it's a list item paragraph
                    if (el.tagName === 'LI') {
                        const paragraph = el.querySelector('.viewSource_view-source-paragraph__SnPk6, [data-node-view-content]');
                        if (paragraph) {
                            const text = paragraph.innerText?.trim();
                            if (text && text.length > 2 && !seen.has(text)) {
                                seen.add(text);
                                // Check if this LI is nested (has parent LI)
                                const isNested = el.parentElement?.closest('li') !== null;
                                results.push({type: isNested ? 'subitem' : 'item', text: text});
                            }
                        }
                    }
                }
                
                return results;
            }
        """)

        for item in content_data:
            text = item.get("text", "").strip()
            if not text:
                continue
                
            # Skip UI elements
            skip_phrases = [
                "download", "new chat", "ask anything", 
                "list action", "write follow", "all recipes", 
                "list q&a", "click to", "sign in", "log in"
            ]
            if any(skip in text.lower() for skip in skip_phrases):
                continue

            item_type = item.get("type")
            
            if item_type == "heading":
                # Add blank line before headings (except first)
                if parts and parts[-1] != "":
                    parts.append("")
                parts.append(f"*{text}*")
            elif item_type == "subitem":
                parts.append(f"    ◦ {text}")  # Indented sub-item
            else:
                parts.append(f"• {text}")

        logger.info("Extracted %d items via JS", len(content_data))

    except Exception as e:
        logger.warning("JS extraction failed, using fallback: %s", e)
        return _fallback_extraction(page, title)

    if len(parts) <= 2:
        return _fallback_extraction(page, title)
        
    return "\n".join(parts)


def _fallback_extraction(page, title: str) -> Optional[str]:
    """Fallback extraction using simpler method.

    Args:
        page: Playwright page object.
        title: The main title.

    Returns:
        Extracted text or None.
    """
    logger.info("Using fallback extraction")
    parts = []
    
    if title:
        parts.append(f"📋 *{title}*")
        parts.append("")

    try:
        items = page.locator("li").all()
        seen = set()
        
        for item in items:
            try:
                full_text = item.inner_text(timeout=2000).strip()
                first_line = full_text.split("\n")[0].strip()
                
                if not first_line or len(first_line) < 3 or first_line in seen:
                    continue
                
                skip_phrases = ["download", "new chat", "ask anything", "sign in", "log in"]
                if any(skip in first_line.lower() for skip in skip_phrases):
                    continue
                
                seen.add(first_line)
                parts.append(f"• {first_line}")
            except:
                continue
                
    except Exception as e:
        logger.error("Fallback extraction failed: %s", e)

    if len(parts) <= 2:
        return None
        
    return "\n".join(parts)


def truncate_content(content: str, max_length: int = 4000) -> str:
    """Truncate content to fit Slack's message limit.

    Args:
        content: The content to truncate.
        max_length: Maximum character length (Slack limit is ~4000).

    Returns:
        Truncated content.
    """
    if len(content) <= max_length:
        return content

    truncated = content[:max_length]
    last_newline = truncated.rfind("\n")

    if last_newline > max_length * 0.7:
        truncated = truncated[:last_newline]

    return truncated.rstrip() + "\n\n... _(content truncated)_"

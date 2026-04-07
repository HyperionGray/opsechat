"""
Utilities module for opsechat

This module contains common utility functions extracted from runserver.py
to improve code organization and maintainability.
"""

import string
import random
import datetime
import textwrap
import re


def id_generator(size=6, chars=None):
    """
    Generate random IDs for ephemeral use.
    
    Note: Uses standard `random` module instead of `secrets` because:
    - All sessions are ephemeral (destroyed on server restart)
    - No persistent authentication or long-lived tokens
    - IDs are for temporary identification, not security-critical keys
    - Acceptable for the intended Tor hidden service use case
    
    If adding persistent sessions or authentication, consider using `secrets` module.
    """
    if chars is None:
        chars = string.ascii_uppercase + string.digits + string.ascii_lowercase
    return ''.join(random.choice(chars) for i in range(size))


def check_older_than(chat_dic, secs_to_live=180):
    """Check if a chat message is older than specified seconds (default 3 minutes)"""
    now = datetime.datetime.now()
    timestamp = chat_dic["timestamp"]
    diff = now - timestamp
    secs = diff.total_seconds()

    if secs >= secs_to_live:
        return True
    return False


def get_random_color():
    """Get a random color name for user identification"""
    colors = ["red", "blue", "green", "orange", "purple", "brown", "pink", "gray", "olive", "cyan"]
    return random.choice(colors)


def check_review_older_than(review_dic, secs_to_live=86400):  # 24 hours
    """Check if a review is older than specified seconds (default 24 hours)"""
    now = datetime.datetime.now()
    timestamp = review_dic["timestamp"]
    diff = now - timestamp
    secs = diff.total_seconds()
    
    if secs >= secs_to_live:
        return True
    return False


def cleanup_old_reviews(reviews):
    """Remove reviews older than 24 hours to prevent memory bloat"""
    to_delete = []
    
    for i, review in enumerate(reviews):
        if check_review_older_than(review):
            to_delete.append(i)
    
    # Remove in reverse order to maintain indices
    for i in reversed(to_delete):
        reviews.pop(i)
    
    return reviews


def add_review(reviews, user_id, rating, review_text):
    """Add a new review to the reviews list"""
    normalized_rating = int(rating)
    normalized_text = (review_text or "").strip()
    review = {
        'id': id_generator(size=16),
        'user_id': user_id,
        'rating': normalized_rating,
        # Keep both keys for compatibility with older callers.
        'text': normalized_text,
        'review_text': normalized_text,
        'timestamp': datetime.datetime.now()
    }
    
    reviews.append(review)
    return review


def sanitize_emojis(text):
    """
    Remove all emojis from text. Users are restricted to ASCII only.
    The skull emoji (💀) is reserved for system use only and will also be removed from user input.
    
    Args:
        text: Input text that may contain emojis
        
    Returns:
        Text with all emojis removed
    """
    # Emoji ranges in Unicode
    # This pattern matches most common emojis
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002600-\U000026FF"  # Miscellaneous Symbols
        "\U00002700-\U000027BF"  # Dingbats
        "]+",
        flags=re.UNICODE
    )
    
    # Remove all emojis from user input
    # The skull emoji (💀) is reserved for system notifications only
    return emoji_pattern.sub('', text)


def filter_to_ascii(text):
    """
    Filter text to only allow ASCII characters (and the system skull emoji).
    Users are limited to ASCII-only input.
    
    Args:
        text: Input text
        
    Returns:
        Text with non-ASCII characters removed
    """
    # Allow only ASCII printable characters and whitespace
    return ''.join(char for char in text if ord(char) < 128)


def process_chat(chat_dic):
    """
    Process chat messages for display, handling text wrapping and PGP preservation.
    
    Args:
        chat_dic: Dictionary containing chat message data with keys:
                  'message' (or 'msg'), 'user_id', 'color', 'timestamp'
        
    Returns:
        List of chat dictionaries (may be split for long messages)
    """
    chats = []
    max_chat_len = 69
    
    # Support both 'message' and 'msg' key names for compatibility
    msg_text = chat_dic["msg"] if "msg" in chat_dic else chat_dic.get("message", "")
    user_id = chat_dic["user_id"] if "user_id" in chat_dic else chat_dic.get("username", "")
    color = chat_dic.get("color", "")
    
    # Check if this is a PGP encrypted message - don't wrap it
    is_pgp = "-----BEGIN PGP MESSAGE-----" in msg_text
    
    if is_pgp:
        # Don't wrap PGP messages, keep them as single chat
        chats = [chat_dic]
    elif len(msg_text) > max_chat_len:
        # Split long messages into multiple parts
        for message in textwrap.wrap(msg_text, width=max_chat_len):
            partial_chat = {}
            partial_chat["msg"] = message.strip()
            partial_chat["timestamp"] = chat_dic.get("timestamp", datetime.datetime.now())
            partial_chat["username"] = user_id
            partial_chat["color"] = color
            chats.append(partial_chat)
    else:
        chats = [chat_dic]

    return chats
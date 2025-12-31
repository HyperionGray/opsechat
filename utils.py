"""
Utilities module for opsechat

This module contains common utility functions extracted from runserver.py
to improve code organization and maintainability.
"""

import string
import random
import datetime
import textwrap
from flask import session


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
    review = {
        'id': id_generator(size=16),
        'user_id': user_id,
        'rating': rating,
        'review_text': review_text,
        'timestamp': datetime.datetime.now()
    }
    
    reviews.append(review)
    return review


def process_chat(chat_dic):
    """
    Process chat messages for display, handling text wrapping and PGP preservation.
    
    Args:
        chat_dic: Dictionary containing chat message data
        
    Returns:
        List of chat dictionaries (may be split for long messages)
    """
    chats = []
    max_chat_len = 69
    
    # Check if this is a PGP encrypted message - don't wrap it
    is_pgp = "-----BEGIN PGP MESSAGE-----" in chat_dic["msg"]
    
    if is_pgp:
        # Don't wrap PGP messages, keep them as single chat
        chats = [chat_dic]
    elif len(chat_dic["msg"]) > max_chat_len:
        # Split long messages into multiple parts
        for message in textwrap.wrap(chat_dic["msg"], width=max_chat_len):
            partial_chat = {}
            partial_chat["msg"] = message.strip()
            partial_chat["timestamp"] = datetime.datetime.now()
            partial_chat["username"] = session["_id"]
            partial_chat["color"] = session["color"]
            chats.append(partial_chat)
    else:
        chats = [chat_dic]

    return chats
"""
State Manager for opsechat

This module manages global application state that needs to be shared
across different blueprint modules.
"""

# Global state variables
chatters = []
chatlines = []
reviews = []

def get_chatters():
    """Get the list of active chatters"""
    return chatters

def get_chatlines():
    """Get the list of chat messages"""
    return chatlines

def set_chatlines(new_chatlines):
    """Set the chat messages list"""
    global chatlines
    chatlines = new_chatlines

def get_reviews():
    """Get the list of reviews"""
    return reviews

def set_reviews(new_reviews):
    """Set the reviews list"""
    global reviews
    reviews = new_reviews
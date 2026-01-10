"""
Chat system routes for opsechat

This module contains Flask routes for the core chat functionality including:
- Chat message handling
- User session management
- Message cleanup and processing
- JavaScript and no-JavaScript chat interfaces
"""

import re
import datetime
from flask import render_template, request, session, jsonify


def register_chat_routes(app, chatlines, chatters, id_generator, get_random_color, 
                        check_older_than, process_chat, remove_headers):
    """Register all chat-related routes with the Flask app"""
    
    @app.route('/<string:url_addition>')
    def drop(url_addition):
        """Main chat landing page"""
        if url_addition != app.config["path"]:
            return ('', 404)
        return render_template("landing.html", 
                              hostname=app.config["hostname"], 
                              path=app.config["path"])

    @app.route('/<string:url_addition>/landing')
    def drop_landing(url_addition):
        """Chat landing page with explicit landing route"""
        if url_addition != app.config["path"]:
            return ('', 404)
        return render_template("landing.html", 
                              hostname=app.config["hostname"], 
                              path=app.config["path"])

    @app.route('/<string:url_addition>/landing/auto')
    def drop_landing_auto(url_addition):
        """Auto-redirect landing page for JavaScript detection"""
        if url_addition != app.config["path"]:
            return ('', 404)
        return render_template("landing_auto.html", 
                              hostname=app.config["hostname"], 
                              path=app.config["path"])

    @app.route('/<string:url_addition>/yesscript')
    def drop_yes(url_addition):
        """JavaScript-enabled chat interface"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        return render_template("chat.html", 
                              hostname=app.config["hostname"], 
                              path=app.config["path"], 
                              script_enabled=True)

    @app.route('/<string:url_addition>/noscript')
    def drop_noscript(url_addition):
        """No-JavaScript chat interface"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        return render_template("chat.html", 
                              hostname=app.config["hostname"], 
                              path=app.config["path"], 
                              script_enabled=False)

    @app.route('/<string:url_addition>/messages', methods=["GET", "POST"])
    def chat_messages(url_addition):
        """Handle chat messages for no-JavaScript interface"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        if request.method == "POST":
            # Process new message
            message_text = request.form.get("message", "").strip()
            if message_text:
                # Sanitize message
                message_text = re.sub(r'[<>&"\']', '', message_text)
                
                # Create message object
                message = {
                    "message": message_text,
                    "user_id": session["_id"],
                    "color": session["color"],
                    "timestamp": datetime.datetime.now()
                }
                
                # Add to chat
                chatlines.append(message)
                
                # Add user to chatters if not already present
                if session["_id"] not in [c["user_id"] for c in chatters]:
                    chatters.append({
                        "user_id": session["_id"],
                        "color": session["color"],
                        "timestamp": datetime.datetime.now()
                    })
        
        # Clean up old messages
        global chatlines
        chatlines = [msg for msg in chatlines if not check_older_than(msg)]
        
        # Process messages for display
        processed_messages = [process_chat(msg) for msg in chatlines]
        
        return render_template("messages.html",
                              messages=processed_messages,
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              script_enabled=False)

    @app.route('/<string:url_addition>/messages.json', methods=["GET", "POST"])
    def chat_messages_js(url_addition):
        """Handle chat messages for JavaScript interface"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        if request.method == "POST":
            # Get JSON data
            data = request.get_json()
            if data and "message" in data:
                message_text = data["message"].strip()
                if message_text:
                    # Sanitize message
                    message_text = re.sub(r'[<>&"\']', '', message_text)
                    
                    # Create message object
                    message = {
                        "message": message_text,
                        "user_id": session["_id"],
                        "color": session["color"],
                        "timestamp": datetime.datetime.now()
                    }
                    
                    # Add to chat
                    chatlines.append(message)
                    
                    # Add user to chatters if not already present
                    if session["_id"] not in [c["user_id"] for c in chatters]:
                        chatters.append({
                            "user_id": session["_id"],
                            "color": session["color"],
                            "timestamp": datetime.datetime.now()
                        })
        
        # Clean up old messages
        global chatlines
        chatlines = [msg for msg in chatlines if not check_older_than(msg)]
        
        # Process messages for JSON response
        processed_messages = [process_chat(msg) for msg in chatlines]
        
        response = jsonify({
            "messages": processed_messages,
            "user_id": session["_id"],
            "user_color": session["color"]
        })
        
        return remove_headers(response)

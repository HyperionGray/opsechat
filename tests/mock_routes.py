"""
Mock Route Handlers for opsechat testing

This module contains route handler implementations for the mock server,
extracted from mock_server.py for better organization and maintainability.
"""

import datetime
import re
from flask import render_template, session, request, jsonify, redirect


def create_mock_routes(app, chatters, chatlines, reviews, id_generator, get_random_color):
    """Create and register mock route handlers"""
    
    def check_older_than(chat_dic, secs_to_live=180):
        """Check if a chat message is older than specified seconds"""
        now = datetime.datetime.now()
        timestamp = chat_dic["timestamp"]
        diff = now - timestamp
        secs = diff.total_seconds()
        return secs >= secs_to_live
    
    @app.route('/<string:url_addition>', methods=["GET"])
    def drop_landing(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            chatters.append(session["_id"])
            session["color"] = get_random_color()
        
        try:
            return render_template("landing_auto.html",
                                  hostname=app.config["hostname"],
                                  path=app.config["path"])
        except Exception as e:
            print(f"Template rendering error: {e}")
            return f'''
            <html>
            <head><title>opsechat</title></head>
            <body>
                <h1>Welcome to opsechat</h1>
                <p>Path: {app.config["path"]}</p>
                <script>
                    setTimeout(function() {{
                        window.location.href = '/{app.config["path"]}/yes';
                    }}, 2000);
                </script>
                <noscript>
                    <meta http-equiv="refresh" content="2;url=/{app.config["path"]}/noscript">
                </noscript>
            </body>
            </html>
            ''', 200

    @app.route('/<string:url_addition>/auto', methods=["GET"])
    def drop_landing_auto(url_addition):
        return drop_landing(url_addition)

    @app.route('/<string:url_addition>/yes', methods=["GET"])
    @app.route('/<string:url_addition>/script', methods=["GET"])
    def drop_yes(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            chatters.append(session["_id"])
            session["color"] = get_random_color()
        
        try:
            return render_template("drop.html",
                                  hostname=app.config["hostname"],
                                  path=app.config["path"],
                                  script_enabled=True)
        except Exception as e:
            print(f"Template rendering error: {e}")
            return f'''
            <html>
            <head><title>opsechat - Script Mode</title></head>
            <body>
                <h1>opsechat - Script Enabled</h1>
                <form method="post" action="/{app.config["path"]}/chats">
                    <textarea name="dropdata" placeholder="Enter your message..."></textarea>
                    <button type="submit">Send</button>
                </form>
                <div id="messages"></div>
            </body>
            </html>
            ''', 200

    @app.route('/<string:url_addition>/noscript', methods=["GET"])
    def drop_noscript(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            chatters.append(session["_id"])
            session["color"] = get_random_color()
        
        try:
            return render_template("drop.html",
                                  hostname=app.config["hostname"],
                                  path=app.config["path"],
                                  script_enabled=False)
        except Exception as e:
            print(f"Template rendering error: {e}")
            return f'''
            <html>
            <head><title>opsechat - NoScript Mode</title></head>
            <body>
                <h1>opsechat - No Script</h1>
                <form method="post" action="/{app.config["path"]}/chats">
                    <textarea name="dropdata" placeholder="Enter your message..."></textarea>
                    <button type="submit">Send</button>
                </form>
            </body>
            </html>
            ''', 200

    @app.route('/<string:url_addition>/chats', methods=["GET", "POST"])
    def chat_messages(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        # Clean up old messages
        to_delete = []
        for i, chatline_dic in enumerate(chatlines):
            if check_older_than(chatline_dic):
                to_delete.append(i)
        
        for i in reversed(to_delete):
            chatlines.pop(i)
        
        if request.method == "POST":
            if request.form.get("dropdata", "").strip():
                chat = {
                    "msg": request.form["dropdata"].strip(),
                    "timestamp": datetime.datetime.now(),
                    "username": session.get("_id", "anonymous"),
                    "color": session.get("color", "black")
                }
                
                # Don't sanitize PGP messages
                if "-----BEGIN PGP MESSAGE-----" not in chat["msg"]:
                    chat["msg"] = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', chat["msg"])
                
                chatlines.append(chat)
                chatlines[:] = chatlines[-13:]  # Keep only last 13 messages
            
            return redirect(f'/{app.config["path"]}', code=302)
        
        try:
            return render_template("chats.html",
                                  chatlines=chatlines,
                                  num_people=len(chatters))
        except Exception as e:
            print(f"Template rendering error: {e}")
            return f'''
            <html>
            <head><title>Chat Messages</title></head>
            <body>
                <h1>Chat Messages ({len(chatters)} people)</h1>
                <div>
                    {"".join([f"<p><strong>{chat['username']}:</strong> {chat['msg']}</p>" for chat in chatlines[-10:]])}
                </div>
            </body>
            </html>
            ''', 200

    @app.route('/<string:url_addition>/chatsjs', methods=["GET", "POST"])
    def chat_messages_js(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        # Clean up old messages
        to_delete = []
        for i, chatline_dic in enumerate(chatlines):
            if check_older_than(chatline_dic):
                to_delete.append(i)
        
        for i in reversed(to_delete):
            chatlines.pop(i)
        
        if request.method == "POST":
            if request.form.get("dropdata", "").strip():
                chat = {
                    "msg": request.form["dropdata"].strip(),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "username": session.get("_id", "anonymous"),
                    "color": [255, 0, 0],  # Mock color as RGB tuple
                    "num_people": len(chatters)
                }
                
                # Don't sanitize PGP messages
                if "-----BEGIN PGP MESSAGE-----" not in chat["msg"]:
                    chat["msg"] = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', chat["msg"])
                
                chatlines.append(chat)
                chatlines[:] = chatlines[-13:]  # Keep only last 13 messages
        
        # Convert datetime objects to ISO format for JSON serialization
        json_chatlines = []
        for chat in chatlines:
            json_chat = chat.copy()
            if isinstance(json_chat.get("timestamp"), datetime.datetime):
                json_chat["timestamp"] = json_chat["timestamp"].isoformat()
            json_chatlines.append(json_chat)
        
        return jsonify(json_chatlines)

    # Email routes
    @app.route('/<string:url_addition>/email', methods=["GET"])
    def email_inbox(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        return '<html><body><h1>Email Inbox</h1></body></html>', 200

    @app.route('/<string:url_addition>/email/compose', methods=["GET", "POST"])
    def email_compose(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        if request.method == "POST":
            return redirect(f'/{app.config["path"]}/email')
        
        return '<html><body><h1>Compose Email</h1></body></html>', 200

    @app.route('/<string:url_addition>/email/config', methods=["GET", "POST"])
    def email_config(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        if request.method == "POST":
            return redirect(f'/{app.config["path"]}/email/config')
        
        return '<html><body><h1>Email Configuration</h1></body></html>', 200

    @app.route('/<string:url_addition>/email/burner', methods=["GET"])
    def email_burner(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        return '<html><body><h1>Burner Email</h1></body></html>', 200

    @app.route('/<string:url_addition>/email/burner/generate', methods=["POST"])
    def email_burner_generate(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify({"error": "No session"}), 401
        
        burner_email = f"burner_{id_generator(8)}@example.com"
        return jsonify({
            "success": True,
            "email": burner_email
        })

    # Simple chat routes
    @app.route('/chat', methods=["GET"])
    def chat_index():
        return '<html><body><h1>OpSecChat</h1><button id="createRoomBtn">Create Room</button></body></html>', 200

    @app.route('/chat/create', methods=["POST"])
    def chat_create():
        room_id = id_generator(16)
        return jsonify({
            "success": True,
            "room_id": room_id,
            "room_url": f"/chat/room/{room_id}"
        })

    @app.route('/chat/room/<string:room_id>', methods=["GET"])
    def chat_room(room_id):
        if "_id" not in session:
            session["_id"] = id_generator(16)
            session["username"] = f"User{id_generator(4)}"
            session["color"] = get_random_color()
        
        return f'<html><body><h1>OpSecChat Room {room_id}</h1></body></html>', 200

    @app.route('/chat/room/<string:room_id>/messages', methods=["GET", "POST"])
    def chat_room_messages(room_id):
        if "_id" not in session:
            session["_id"] = id_generator(16)
            session["username"] = f"User{id_generator(4)}"
            session["color"] = get_random_color()
        
        if request.method == "POST":
            return jsonify({"success": True})
        else:
            return jsonify({
                "messages": [],
                "user_count": 1,
                "my_username": session.get("username", "Anonymous"),
                "my_color": session.get("color", "blue")
            })

    # Additional routes for compatibility
    @app.route('/<string:url_addition>/landing', methods=["GET"])
    def drop_landing_explicit(url_addition):
        return drop_landing(url_addition)

    @app.route('/<string:url_addition>/yesscript', methods=["GET"])
    def drop_yesscript(url_addition):
        return drop_yes(url_addition)
    
    # Messages endpoint (used by updated chat_routes.py)
    @app.route('/<string:url_addition>/messages', methods=["GET", "POST"])
    def messages_noscript(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        if request.method == "POST":
            message_text = request.form.get("message", "").strip()
            if message_text:
                chat = {
                    "msg": message_text,
                    "timestamp": datetime.datetime.now(),
                    "username": session["_id"],
                    "color": session["color"]
                }
                chatlines.append(chat)
        
        return '<html><body><h1>Messages</h1></body></html>', 200
    
    # JSON messages endpoint
    @app.route('/<string:url_addition>/messages.json', methods=["GET", "POST"])
    def messages_json(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        if request.method == "POST":
            data = request.get_json()
            if data and "message" in data:
                message_text = data["message"].strip()
                if message_text:
                    chat = {
                        "msg": message_text,
                        "timestamp": datetime.datetime.now(),
                        "username": session["_id"],
                        "color": session["color"]
                    }
                    chatlines.append(chat)
        
        # Convert to JSON format
        json_chatlines = []
        for chat in chatlines:
            json_chat = chat.copy()
            if isinstance(json_chat.get("timestamp"), datetime.datetime):
                json_chat["timestamp"] = json_chat["timestamp"].isoformat()
            json_chatlines.append(json_chat)
        
        return jsonify({
            "messages": json_chatlines,
            "user_id": session["_id"],
            "user_color": session["color"]
        })

    return app
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

    return app
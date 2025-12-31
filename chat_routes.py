# Chat System Routes
def register_chat_routes(app, chatlines, chatters, check_older_than):
    """Register chat routes with the Flask app"""
    from flask import render_template, jsonify, request, session, redirect
    import datetime
    import re
    
    @app.route('/<string:url_addition>/chats', methods=["GET", "POST"])
    def chat_messages(url_addition):
        """Handle chat messages without JavaScript"""
        more_chats = False
        if url_addition != app.config["path"]:
            return ('', 404)

        to_delete = []
        c = 0
        if chatlines:
            for chatline_dic in chatlines:
                if check_older_than(chatline_dic):
                    to_delete.append(c)
                c += 1

        for _del in reversed(to_delete):
            chatlines.pop(_del)

        if request.method == "POST":
            if request.form["dropdata"].strip():
                chat = {}
                chat["msg"] = request.form["dropdata"].strip()
                # Don't sanitize PGP messages, only sanitize regular messages
                if "-----BEGIN PGP MESSAGE-----" not in chat["msg"]:
                    chat["msg"] = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', chat["msg"])
                chat["timestamp"] = datetime.datetime.now()
                chat["username"] = session["_id"]
                chat["color"] = session["color"]
                chats = [chat]
                chatlines.extend(chats)
                chatlines[:] = chatlines[-13:]  # Keep only last 13 messages
                more_chats = True

            return redirect(app.config["path"], code=302)
        
        return render_template("chats.html",
                               chatlines=chatlines, 
                               num_people=len(chatters))

    @app.route('/<string:url_addition>/chatsjs', methods=["GET", "POST"])
    def chat_messages_js(url_addition):
        """Handle chat messages with JavaScript (AJAX)"""
        more_chats = False
        if url_addition != app.config["path"]:
            return ('', 404)

        to_delete = []
        c = 0
        if chatlines:
            for chatline_dic in chatlines:
                if check_older_than(chatline_dic):
                    to_delete.append(c)
                c += 1

        for _del in reversed(to_delete):
            chatlines.pop(_del)

        if request.method == "POST":
            if request.form["dropdata"].strip():
                chat = {}
                chat["msg"] = request.form["dropdata"].strip()
                # Don't sanitize PGP messages, only sanitize regular messages
                if "-----BEGIN PGP MESSAGE-----" not in chat["msg"]:
                    chat["msg"] = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', chat["msg"])
                chat["timestamp"] = datetime.datetime.now()
                chat["username"] = session["_id"]
                chat["color"] = session["color"]
                chat["num_people"] = len(chatters)
                chats = [chat]
                chatlines.extend(chats)
                chatlines[:] = chatlines[-13:]  # Keep only last 13 messages
                more_chats = True

        return jsonify(chatlines)

import re
from flask import Flask
from flask import render_template, jsonify
from flask import request, session, url_for, redirect, abort
import traceback
import sys
import string
from stem.control import Controller
from hashlib import sha224
import datetime
from stem import SocketError
import textwrap
app = Flask(__name__)
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
import random


chatters = []
global chatlines
chatlines = []

def id_generator(size=6,
                 chars=string.ascii_uppercase + string.digits +
                 string.ascii_lowercase):
    
    return ''.join(random.choice(chars) for i in range(size))

app.secret_key = id_generator(size=64)

def check_older_than(chat_dic, secs_to_live = 180):
    now = datetime.datetime.now()
    timestamp = chat_dic["timestamp"]
    diff = now - timestamp
    secs = diff.total_seconds()

    if secs >= secs_to_live:
        return True
    return False

def get_random_color():
    r = lambda: random.randint(0,128)
    return (r(),r(),r())

# Remove headers that can be used to fingerprint this server
@app.after_request
def remove_headers(response):
    response.headers["Server"] = ""
    response.headers["Date"] = ""
    return response


# Empty Index page to avoid Flask fingerprinting
@app.route('/', methods=["GET"])
def index():
    return ('', 200)

@app.route('/<string:url_addition>/script', methods=["GET"])
def drop(url_addition):

    if url_addition != app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        chatters.append(session["_id"])
        session["color"] = get_random_color()

    if request.method == "GET":
        full_path = app.config["hostname"] + "/" + app.config["path"]
        return render_template("drop.html",
                               hostname=app.config["hostname"],
                               path=app.config["path"])


@app.route('/<string:url_addition>', methods=["GET"])
def drop_landing(url_addition):

    if url_addition != app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        chatters.append(session["_id"])
        session["color"] = get_random_color()

    if request.method == "GET":
        full_path = app.config["hostname"] + "/" + app.config["path"]
        return render_template("landing_auto.html",
                               hostname=app.config["hostname"],
                               path=app.config["path"])


@app.route('/<string:url_addition>/autolanding', methods=["GET"])
def drop_landing_auto(url_addition):

    if url_addition != app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        chatters.append(session["_id"])
        session["color"] = get_random_color()

    if request.method == "GET":
        full_path = app.config["hostname"] + "/" + app.config["path"]
        return render_template("landing_auto.html",
                               hostname=app.config["hostname"],
                               path=app.config["path"])

    
@app.route('/<string:url_addition>/yesscript', methods=["GET"])
def drop_yes(url_addition):

    if url_addition != app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        chatters.append(session["_id"])
        session["color"] = get_random_color()

    if request.method == "GET":
        full_path = app.config["hostname"] + "/" + app.config["path"]
        return render_template("drop.html",
                               hostname=app.config["hostname"],
                               path=app.config["path"])


@app.route('/<string:url_addition>/noscript', methods=["GET"])
def drop_noscript(url_addition):

    #if url_addition != app.config["path"]:
    #    return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        chatters.append(session["_id"])
        session["color"] = get_random_color()

    if request.method == "GET":
        full_path = app.config["hostname"] + "/" + app.config["path"]
        return render_template("drop.noscript.html",
                               hostname=app.config["hostname"],
                               path=app.config["path"])

@app.route('/<string:url_addition>/chats', methods=["GET", "POST"])
def chat_messages(url_addition):

    global chatlines
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

    for _del in to_delete:
        chatlines.pop(_del)

    if request.method == "POST":

        if request.form["dropdata"].strip():
            
            chat = {}
            chat["msg"] = request.form["dropdata"].strip()
            chat["msg"] = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', chat["msg"])
            chat["timestamp"] = datetime.datetime.now()
            chat["username"] = session["_id"]
            chat["color"] = session["color"]
            chats = [chat]
            chatlines = chatlines + chats
            chatlines = chatlines[-13:]
            more_chats = True

        return redirect(app.config["path"], code=302)

    #return jsonify(chatlines)
    
    return render_template("chats.html",
                           chatlines=chatlines, num_people = len(chatters))


@app.route('/<string:url_addition>/chatsjs', methods=["GET", "POST"])
def chat_messages_js(url_addition):

    global chatlines
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

    for _del in to_delete:
        chatlines.pop(_del)

    if request.method == "POST":

        if request.form["dropdata"].strip():
            
            chat = {}
            chat["msg"] = request.form["dropdata"].strip()
            chat["msg"] = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', chat["msg"])
            chat["timestamp"] = datetime.datetime.now()
            chat["username"] = session["_id"]
            chat["color"] = session["color"]
            chat["num_people"] = len(chatters)
            chats = [chat]
            chatlines = chatlines + chats
            chatlines = chatlines[-13:]
            more_chats = True

        #return redirect(app.config["path"], code=302)

    return jsonify(chatlines)
    

def main():

    try:
        controller = Controller.from_port()
    except SocketError:
        sys.stderr.write('[!] Tor proxy or Control Port are not running. Try starting the Tor Browser or Tor daemon and ensure the ControlPort is open.\n')
        sys.exit(1)
        
    
    print('[*] Connecting to tor')
    with controller:
        controller.authenticate()

        # Create ephemeral hidden service where visitors of port 80 get redirected to local
        # port 5000 (this is where Flask runs by default).
        print('[*] Creating ephemeral hidden service, this may take a minute or two')
        result = controller.create_ephemeral_hidden_service({80: 5000}, await_publication = True)

        print("[*] Started a new hidden service with the address of %s.onion" % result.service_id)
        ###result = controller.create_hidden_service(hidden_service_dir, 80, target_port = 5000)

        # The hostname is only available when we can read the hidden service
        # directory. This requires us to be running with the same user as tor.

        if not result:
            print("[*] Something went wrong, shutting down")
            ###controller.remove_hidden_service(hidden_service_dir)
            ###shutil.rmtree(hidden_service_dir)

        if result.service_id:
            app.config["hostname"] = result.service_id
            app.config["path"] = id_generator(size = 32)
            app.config["full_path"] = app.config["hostname"] + ".onion" + "/" + app.config["path"]
            print("[*] Your service is available at: %s , press ctrl+c to quit" % app.config["full_path"])
        else:
            print("[*] Unable to determine our ephemeral service's hostname")

        try:
            app.run(debug=False, threaded = True)
        finally:

            print(" * Shutting down our hidden service")
            controller.remove_ephemeral_hidden_service(result.service_id)

if __name__ == "__main__":
    main()

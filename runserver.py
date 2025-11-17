import re
from flask import Flask
from flask import render_template, jsonify
from flask import request, session, url_for, redirect, abort
import traceback
import sys
import string
import textwrap
from stem.control import Controller
from hashlib import sha224
import datetime
from stem import SocketError
app = Flask(__name__)
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
import random

# Import email system
from email_system import email_storage, burner_manager, EmailComposer, EmailValidator


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


def process_chat(chat_dic):

    chats = []
    max_chat_len = 69
    
    # Check if this is a PGP encrypted message - don't wrap it
    is_pgp = "-----BEGIN PGP MESSAGE-----" in chat_dic["msg"]
    
    if is_pgp:
        # Don't wrap PGP messages, keep them as single chat
        chats = [chat_dic]
    elif len(chat_dic["msg"]) > max_chat_len:
        
        for message in textwrap.wrap(chat_dic["msg"], width = max_chat_len):
            partial_chat = {}
            partial_chat["msg"] = message.strip()
            partial_chat["timestamp"] = datetime.datetime.now()
            partial_chat["username"] = session["_id"]
            partial_chat["color"] = session["color"]
            chats.append(partial_chat)

    else:
        chats = [chat_dic]

    return chats


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
                               path=app.config["path"],
                               script_enabled=True)


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
                               path=app.config["path"],
                               script_enabled=True)


@app.route('/<string:url_addition>/noscript', methods=["GET"])
def drop_noscript(url_addition):

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
                               path=app.config["path"],
                               script_enabled=False)

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
            # Don't sanitize PGP messages, only sanitize regular messages
            if "-----BEGIN PGP MESSAGE-----" not in chat["msg"]:
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
            # Don't sanitize PGP messages, only sanitize regular messages
            if "-----BEGIN PGP MESSAGE-----" not in chat["msg"]:
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
    

# Email System Routes
@app.route('/<string:url_addition>/email', methods=["GET"])
def email_inbox(url_addition):
    """Main email inbox page"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    # Initialize inbox for user
    email_storage.create_user_inbox(session["_id"])
    
    # Get emails
    emails = email_storage.get_emails(session["_id"])
    
    return render_template("email_inbox.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          emails=emails,
                          script_enabled=False)


@app.route('/<string:url_addition>/email/yesscript', methods=["GET"])
def email_inbox_script(url_addition):
    """Email inbox with JavaScript enabled"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    email_storage.create_user_inbox(session["_id"])
    emails = email_storage.get_emails(session["_id"])
    
    return render_template("email_inbox.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          emails=emails,
                          script_enabled=True)


@app.route('/<string:url_addition>/email/compose', methods=["GET", "POST"])
def email_compose(url_addition):
    """Compose and send email"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return redirect(f"/{app.config['path']}/email", code=302)
    
    if request.method == "POST":
        raw_mode = request.form.get("raw_mode") == "true"
        
        if raw_mode:
            # Parse raw email
            raw_content = request.form.get("raw_email", "")
            email = EmailComposer.parse_raw_email(raw_content)
        else:
            # Standard compose
            email = EmailComposer.create_email(
                from_addr=request.form.get("from", ""),
                to_addr=request.form.get("to", ""),
                subject=request.form.get("subject", ""),
                body=request.form.get("body", ""),
                headers={}
            )
        
        # For now, just add to our own inbox for testing
        # In full implementation, this would send via SMTP
        email_storage.add_email(session["_id"], email)
        
        return redirect(f"/{app.config['path']}/email", code=302)
    
    return render_template("email_compose.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          script_enabled=False)


@app.route('/<string:url_addition>/email/view/<string:email_id>', methods=["GET"])
def email_view(url_addition, email_id):
    """View specific email"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return redirect(f"/{app.config['path']}/email", code=302)
    
    email = email_storage.get_email(session["_id"], email_id)
    if not email:
        return ('Email not found', 404)
    
    return render_template("email_view.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          email=email,
                          script_enabled=False)


@app.route('/<string:url_addition>/email/edit/<string:email_id>', methods=["GET", "POST"])
def email_edit(url_addition, email_id):
    """Edit email in raw mode"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return redirect(f"/{app.config['path']}/email", code=302)
    
    email = email_storage.get_email(session["_id"], email_id)
    if not email:
        return ('Email not found', 404)
    
    if request.method == "POST":
        raw_content = request.form.get("raw_email", "")
        updated_email = EmailComposer.parse_raw_email(raw_content)
        email_storage.update_email(session["_id"], email_id, updated_email)
        return redirect(f"/{app.config['path']}/email/view/{email_id}", code=302)
    
    raw_email = EmailComposer.format_raw_email(email)
    
    return render_template("email_edit.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          email=email,
                          raw_email=raw_email,
                          script_enabled=False)


@app.route('/<string:url_addition>/email/delete/<string:email_id>', methods=["POST"])
def email_delete(url_addition, email_id):
    """Delete email"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return ('Unauthorized', 401)
    
    email_storage.delete_email(session["_id"], email_id)
    return redirect(f"/{app.config['path']}/email", code=302)


@app.route('/<string:url_addition>/email/burner', methods=["GET", "POST"])
def email_burner(url_addition):
    """Generate burner email address"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    if request.method == "POST":
        burner_email = burner_manager.generate_burner_email(session["_id"])
        email_storage.create_user_inbox(session["_id"])
        
        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              burner_email=burner_email,
                              script_enabled=False)
    
    return render_template("email_burner.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          burner_email=None,
                          script_enabled=False)


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

import re
from flask import Flask
from flask import render_template, jsonify
from flask import request, session, url_for, redirect, abort
import traceback
import sys
import string
import textwrap
import os
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
from email_security_tools import spoofing_tester, phishing_simulator
from email_transport import transport_manager
from domain_manager import domain_rotation_manager, PorkbunAPIClient


chatters = []
global chatlines
chatlines = []

# Review system storage
global reviews
reviews = []

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


def check_review_older_than(review_dic, secs_to_live = 86400):  # 24 hours
    """Check if a review is older than specified seconds (default 24 hours)"""
    now = datetime.datetime.now()
    timestamp = review_dic["timestamp"]
    diff = now - timestamp
    secs = diff.total_seconds()
    
    if secs >= secs_to_live:
        return True
    return False


def cleanup_old_reviews():
    """Remove reviews older than 24 hours to prevent memory bloat"""
    global reviews
    to_delete = []
    
    for i, review in enumerate(reviews):
        if check_review_older_than(review):
            to_delete.append(i)
    
    # Remove in reverse order to maintain indices
    for i in reversed(to_delete):
        reviews.pop(i)


def add_review(user_id, rating, review_text):
    """Add a new review to the global reviews list"""
    global reviews
    
    # Cleanup old reviews first
    cleanup_old_reviews()
    
    review = {
        "id": id_generator(size=16),
        "user_id": user_id,
        "rating": int(rating),
        "text": review_text.strip(),
        "timestamp": datetime.datetime.now()
    }
    
    reviews.append(review)
    return review["id"]


def get_reviews():
    """Get all current reviews, cleanup old ones first"""
    cleanup_old_reviews()
    return reviews


def get_review_stats():
    """Get review statistics"""
    cleanup_old_reviews()
    
    if not reviews:
        return {
            "total": 0,
            "average_rating": 0,
            "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        }
    
    total = len(reviews)
    total_rating = sum(review["rating"] for review in reviews)
    average_rating = round(total_rating / total, 1)
    
    rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for review in reviews:
        rating_distribution[review["rating"]] += 1
    
    return {
        "total": total,
        "average_rating": average_rating,
        "rating_distribution": rating_distribution
    }


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
        send_via_smtp = request.form.get("send_via_smtp") == "true"
        
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
        
        # Send via SMTP if configured and requested
        if send_via_smtp and transport_manager.is_configured()['smtp']:
            success = transport_manager.send_email(
                email['from'],
                email['to'],
                email['subject'],
                email['body'],
                email.get('headers', {})
            )
            if not success:
                # Could add flash message here
                pass
        
        # Always add to local inbox for reference
        email_storage.add_email(session["_id"], email)
        
        return redirect(f"/{app.config['path']}/email", code=302)
    
    # Check if SMTP is configured for the form
    smtp_configured = transport_manager.is_configured()['smtp']
    
    return render_template("email_compose.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          smtp_configured=smtp_configured,
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
    """Generate burner email address - Modern rotating interface"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    # Cleanup expired burners
    burner_manager.cleanup_expired()
    
    if request.method == "POST":
        action = request.form.get("action", "generate")
        
        if action == "generate":
            burner_email = burner_manager.generate_burner_email(session["_id"])
            email_storage.create_user_inbox(session["_id"])
        elif action == "rotate":
            old_email = request.form.get("old_email")
            burner_email = burner_manager.rotate_burner(session["_id"], old_email)
            email_storage.create_user_inbox(session["_id"])
    
    # Get all active burners for this user
    active_burners = burner_manager.get_user_burners(session["_id"])
    
    return render_template("email_burner.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          active_burners=active_burners,
                          script_enabled=False)


@app.route('/<string:url_addition>/email/burner/yesscript', methods=["GET"])
def email_burner_script(url_addition):
    """Burner email with JavaScript enabled"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    burner_manager.cleanup_expired()
    active_burners = burner_manager.get_user_burners(session["_id"])
    
    return render_template("email_burner.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          active_burners=active_burners,
                          script_enabled=True)


@app.route('/<string:url_addition>/email/burner/list', methods=["GET"])
def email_burner_list_json(url_addition):
    """Get active burners as JSON (for AJAX refresh)"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return jsonify([])
    
    burner_manager.cleanup_expired()
    active_burners = burner_manager.get_user_burners(session["_id"])
    
    return jsonify(active_burners)


@app.route('/<string:url_addition>/email/burner/expire/<string:email>', methods=["POST"])
def email_burner_expire(url_addition, email):
    """Expire a specific burner email"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return ('Unauthorized', 401)
    
    # Verify this burner belongs to the user
    burner_user = burner_manager.get_user_for_burner(email)
    if burner_user == session["_id"]:
        burner_manager.expire_burner(email)
    
    return redirect(f"/{app.config['path']}/email/burner", code=302)


# Email Security Testing Routes
@app.route('/<string:url_addition>/email/security/spoof-test', methods=["GET", "POST"])
def email_spoof_test(url_addition):
    """Test email spoofing detection"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    results = None
    variants = None
    
    if request.method == "POST":
        test_type = request.form.get("test_type", "detect")
        
        if test_type == "detect":
            # Test spoofing detection
            test_email = request.form.get("test_email", "")
            legitimate_domain = request.form.get("legitimate_domain", "")
            
            if test_email and legitimate_domain:
                results = spoofing_tester.test_spoofing_detection(test_email, legitimate_domain)
        
        elif test_type == "generate":
            # Generate spoofing variants
            target_domain = request.form.get("target_domain", "")
            
            if target_domain:
                variants = spoofing_tester.generate_spoof_variants(target_domain)
    
    return render_template("email_spoof_test.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          results=results,
                          variants=variants,
                          script_enabled=False)


@app.route('/<string:url_addition>/email/security/phishing-sim', methods=["GET", "POST"])
def email_phishing_sim(url_addition):
    """Phishing simulation and training"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return redirect(f"/{app.config['path']}/email", code=302)
    
    user_id = session["_id"]
    action_result = None
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "enable":
            phishing_simulator.enable_persist_mode(user_id)
            
        elif action == "disable":
            phishing_simulator.disable_persist_mode(user_id)
            
        elif action == "generate":
            template = request.form.get("template", "generic")
            phishing_email = phishing_simulator.create_phishing_email(user_id, template)
            # Add to inbox
            email_storage.add_email(user_id, phishing_email)
            action_result = {
                'type': 'generated',
                'message': 'Phishing simulation email added to your inbox'
            }
    
    # Get user stats
    stats = phishing_simulator.get_user_stats(user_id)
    
    return render_template("email_phishing_sim.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          stats=stats,
                          action_result=action_result,
                          script_enabled=False)


# Email Configuration Routes
@app.route('/<string:url_addition>/email/config', methods=["GET", "POST"])
def email_config(url_addition):
    """Configure SMTP/IMAP settings"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return redirect(f"/{app.config['path']}/email", code=302)
    
    message = None
    config_status = transport_manager.is_configured()
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "configure_smtp":
            smtp_server = request.form.get("smtp_server", "")
            smtp_port = int(request.form.get("smtp_port", "587"))
            smtp_username = request.form.get("smtp_username", "")
            smtp_password = request.form.get("smtp_password", "")
            use_tls = request.form.get("use_tls", "true") == "true"
            
            success = transport_manager.configure_smtp(
                smtp_server, smtp_port, smtp_username, smtp_password, use_tls
            )
            
            message = {
                'type': 'success' if success else 'error',
                'text': 'SMTP configured successfully' if success else 'SMTP configuration failed'
            }
        
        elif action == "configure_imap":
            imap_server = request.form.get("imap_server", "")
            imap_port = int(request.form.get("imap_port", "993"))
            imap_username = request.form.get("imap_username", "")
            imap_password = request.form.get("imap_password", "")
            use_ssl = request.form.get("use_ssl", "true") == "true"
            
            success = transport_manager.configure_imap(
                imap_server, imap_port, imap_username, imap_password, use_ssl
            )
            
            message = {
                'type': 'success' if success else 'error',
                'text': 'IMAP configured successfully' if success else 'IMAP configuration failed'
            }
        
        elif action == "configure_domain_api":
            api_key = request.form.get("api_key", "")
            api_secret = request.form.get("api_secret", "")
            monthly_budget = float(request.form.get("monthly_budget", "50.0"))
            
            if api_key and api_secret:
                porkbun_client = PorkbunAPIClient(api_key, api_secret)
                domain_rotation_manager.set_api_client(porkbun_client)
                domain_rotation_manager.monthly_budget = monthly_budget
                
                message = {
                    'type': 'success',
                    'text': 'Domain API configured successfully'
                }
            else:
                message = {
                    'type': 'error',
                    'text': 'API key and secret are required'
                }
        
        config_status = transport_manager.is_configured()
    
    budget_status = domain_rotation_manager.get_budget_status()
    active_domain = domain_rotation_manager.get_active_domain()
    
    return render_template("email_config.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          config_status=config_status,
                          budget_status=budget_status,
                          active_domain=active_domain,
                          message=message,
                          script_enabled=False)


@app.route('/<string:url_addition>/email/send', methods=["POST"])
def email_send_real(url_addition):
    """Actually send email via SMTP"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return ('Unauthorized', 401)
    
    # Get form data
    from_addr = request.form.get("from", "")
    to_addr = request.form.get("to", "")
    subject = request.form.get("subject", "")
    body = request.form.get("body", "")
    
    # Try to send via SMTP
    success = transport_manager.send_email(from_addr, to_addr, subject, body)
    
    if success:
        # Also add to local storage
        email = EmailComposer.create_email(from_addr, to_addr, subject, body)
        email_storage.add_email(session["_id"], email)
    
    return redirect(f"/{app.config['path']}/email", code=302)


@app.route('/<string:url_addition>/email/receive', methods=["POST"])
def email_receive_real(url_addition):
    """Fetch emails from IMAP"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return ('Unauthorized', 401)
    
    # Fetch from IMAP
    limit = int(request.form.get("limit", "10"))
    unread_only = request.form.get("unread_only", "false") == "true"
    
    emails = transport_manager.receive_emails(limit=limit, unread_only=unread_only)
    
    # Add to local storage
    for email in emails:
        email_storage.add_email(session["_id"], email)
    
    return redirect(f"/{app.config['path']}/email", code=302)


@app.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
def email_domain_rotate(url_addition):
    """Rotate to a new domain"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return ('Unauthorized', 401)
    
    # Attempt domain rotation
    new_domain = domain_rotation_manager.rotate_domain()
    
    if new_domain:
        # Update burner manager to use new domain
        burner_manager.set_custom_domain(new_domain)
    
    return redirect(f"/{app.config['path']}/email/config", code=302)


def main():
    # Get Tor control connection parameters from environment
    tor_host = os.environ.get('TOR_CONTROL_HOST', '127.0.0.1')
    tor_port = int(os.environ.get('TOR_CONTROL_PORT', '9051'))
    
    try:
        controller = Controller.from_port(address=tor_host, port=tor_port)
    except SocketError:
        sys.stderr.write(f'[!] Tor proxy or Control Port are not running at {tor_host}:{tor_port}. Try starting the Tor Browser or Tor daemon and ensure the ControlPort is open.\n')
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
            app.run(host='0.0.0.0', debug=False, threaded = True)
        finally:

            print(" * Shutting down our hidden service")
            controller.remove_ephemeral_hidden_service(result.service_id)

if __name__ == "__main__":
    main()

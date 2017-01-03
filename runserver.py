from flask import Flask
from flask import render_template
from flask import request, session, url_for, redirect, abort
import traceback
import sys
import string
from stem.control import Controller
from hashlib import sha224
import random
import datetime

app = Flask(__name__)
chatlines = []

def id_generator(size=6,
                   chars=string.ascii_uppercase + string.digits +
                   string.ascii_lowercase):

    return ''.join(random.choice(chars) for i in range(size))


app.secret_key = id_generator(size=64)


def check_older_than(chat_dic, secs_to_live = 300):
    now = datetime.datetime.now()
    timestamp = chat_dic["timestamp"]
    diff = now - timestamp
    secs = diff.total_seconds()
    print(secs)
    if secs >= secs_to_live:
        return True

    return False

def get_random_color():

    r = lambda: random.randint(0,128)
    return (r(),r(),r())

@app.route('/<string:url_addition>', methods=["GET"])
def drop(url_addition):

    if url_addition != app.config["path"]:
        abort(404)

    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()

    if request.method == "GET":
        return render_template("drop.html",
                               hostname=app.config["hostname"],
                               path=app.config["path"])


@app.route('/<string:url_addition>/chats', methods=["GET", "POST"])
def chat_messages(url_addition):

    more_chats = False
    if url_addition != app.config["path"]:
        abort(404)

    to_delete = []
    c = 0
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
            chat["timestamp"] = datetime.datetime.now()
            print(datetime.datetime.now())
            chat["username"] = session["_id"]
            chat["color"] = session["color"]
            chatlines.append(chat)
            more_chats = True

            return redirect(app.config["path"], code=302)

    return render_template("chats.html",
                           chatlines=chatlines)

def main():
    print(' * Connecting to tor')

    with Controller.from_port() as controller:
        controller.authenticate()

        # All hidden services have a directory on disk. Lets put ours in tor's data
        # directory.

        # Create ephemeral hidden service where visitors of port 80 get redirected to local
        # port 5000 (this is where Flask runs by default).
        print(' * Creating ephemeral hidden service, this may take a minute or two')
        result = controller.create_ephemeral_hidden_service({80: 5000}, await_publication = True)

        print(" * Started a new hidden service with the address of %s.onion" % result.service_id)
        ###result = controller.create_hidden_service(hidden_service_dir, 80, target_port = 5000)

        # The hostname is only available when we can read the hidden service
        # directory. This requires us to be running with the same user as tor.

        if not result:
            print(" * Something went wrong, shutting down")
            ###controller.remove_hidden_service(hidden_service_dir)
            ###shutil.rmtree(hidden_service_dir)

        if result.service_id:
            app.config["hostname"] = result.service_id
            app.config["path"] = id_generator(size = 64)
            app.config["full_path"] = app.config["hostname"] + ".onion" + "/" + app.config["path"]
            print(" * Our service is available at: %s , press ctrl+c to quit" % app.config["full_path"])
        else:
            print(" * Unable to determine our ephemeral service's hostname")

        try:
            app.run(debug=False, threaded = True)
        finally:

            print(" * Shutting down our hidden service")
            controller.remove_ephemeral_hidden_service(result.service_id)

            #TODO: Encryption
            #TODO: Message Lifetime
            #TODO: Message Truncation
            #could I use session tokens to send people to a URL to retrieve public keys for eachother?

if __name__ == "__main__":
    main()

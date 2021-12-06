Platform
========

To be a opsechat server host requires a Linux machine (any Linux should do), if this gets more popular we will create one for Windows.

To be a opsechat client requires a Tor Browser on any OS.


Install
=======

Install Tor, Open Tor browser to establish a Tor client port

Activate your favorite virtualenv e.g..

`$ git clone git@github.com:HyperionGray/opsechat.git`

`$ cd opsechat`

`$ sudo apt-get install python-virtualenv`

`$ virtualenv --python=python2 dropenv`

`$ source dropenv/bin/activate`


That's it!

How it works
============

You'll see this when it first loads up:

```
(venv) alejandrocaceres@Alejandros-MacBook-Pro ~/o/d/dropchat (master) [1]> python runserver.py
[*] Connecting to tor
[*] Creating ephemeral hidden service, this may take a minute or two
[*] Started a new hidden service with the address of l7k4f6ie2nr6nnfscxxh4e4wref5dgaelunx5mjctt66mhfyky4rv6id.onion
[*] Your service is available at: l7k4f6ie2nr6nnfscxxh4e4wref5dgaelunx5mjctt66mhfyky4rv6id.onion/wdLEcxKPd6ARir3m2t2bFlJfX0q5q6jP , press ctrl+c to quit
 * Serving Flask app 'runserver' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
 ```

Dropchat is a disposable mini-chat server that can be used to chat safely and anonymously through Tor. One
person is the host of the chat server (don't worry being a host only requires one command - no messing with
complex config files) and the others are the clients using only a Tor Browser. The host starts the server 
and shares a URL with the clients. They can then chat with each other safely and anonymously. Once you're 
done sharing the info you want, simply kill the server. No information is stored on disk.

Usage
=====

Share the drop URL with your friends to open in Tor Browser. Chat with them safely and securely! Chatting looks like this:

<img width="1194" alt="dropchat" src="https://user-images.githubusercontent.com/3106718/144932238-5363d4eb-40f8-451f-80f3-3bc8259c0475.png">


Javascript
==========

You have the option of using Javascript or not. In order to use it go to noscript -> options -> add the hostname
to the whitelist (not the url). Then click on the link at the top of the page to go to the script-allowed version
of dropchat if you are not redirected. This is for when you trust the people you are chatting with somewhat, the 
user experience is significantly improved with Javascript.

To not use javascript simply leave noscript on (or the "safest" setting in TBB).

Features
========

- As chat happens inside the Tor network via ephemeral hidden services, everything is encrypted and attribution of chatters is virtually impossible
- No JS required, use safely with NoScript
- *Nothing* touches disk, everything happens in-memory
- This chat is meant to help you with opsec, disappearing messages, randomized usernames, encrypted comms are the default (much more to come)
- No configuration required
- Low barrier to entry, few dependencies
- No need for a client
- Chats are deleted every 3 minutes
- Randomized usernames - this is for your own safety, so as to decrease chances of username reuse
- New chat service created every time the server is started
- No frills, no fancy CSS, code is easy to follow and review to ensure your safety

---

[![define hyperion gray](https://hyperiongray.s3.amazonaws.com/define-hg.svg)](https://www.hyperiongray.com/?pk_campaign=github&pk_kwd=dropchat "Hyperion Gray")

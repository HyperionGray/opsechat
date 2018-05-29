Platform
========

To be a dropchat server host requires a Linux machine (any Linux should do), if this gets more popular we will create one for Windows.

To be a dropchat client requires a Tor Browser on any OS.


Install
=======

Install Tor

Activate your favorite virtualenv e.g..

`$ git clone git@github.com:HyperionGray/dropchat.git`

`$ cd dropchat`

`$ sudo apt-get install python-virtualenv`

`$ virtualenv dropenv`

`$ source dropenv/bin/activate`


That's it!

How it works
============

Dropchat is a disposable mini-chat server that can be used to chat safely and anonymously through Tor. One
person is the host of the chat server (don't worry being a host only requires one command - no messing with
complex config files) and the others are the clients using only a Tor Browser. The host starts the server 
and shares a URL with the clients. They can then chat with each other safely and anonymously. Once you're 
done sharing the info you want, simply kill the server. No information is stored on disk.

Usage
=====

Start Tor or Tor Browser, make sure your Control Port is open and listening on the default port.

`$ dropchat`

Share the drop URL with your friends to open in Tor Browser. Chat with them safely and securely!


Javascript
==========

You have the option of using Javascript or not. In order to use it go to noscript -> options -> add the hostname
to the whitelist (not the url). Then click on the link at the top of the page to go to the script-allowed version
of dropchat if you are not redirected. This is for when you trust the people you are chatting with, the user experience
is significantly improved with Javascript.

To not use javascript simply leave noscript on.

Features
========

- As chat happens inside the Tor network via ephemeral hidden services, everything is encrypted and attribution of chatters is virtually impossible
- No JS required, use safely with NoScript
- *Nothing* touches disk, everything happens in-memory
- No configuration required
- Low barrier to entry, few dependencies
- No need for a client
- Chats are deleted every 3 minutes
- Randomized usernames - this is for your own safety, so as to decrease chances of username reuse
- New chat service created every time the server is started
- No frills, no fancy CSS, code is easy to follow and review to ensure your safety

---

[![define hyperion gray](https://hyperiongray.s3.amazonaws.com/define-hg.svg)](https://www.hyperiongray.com/?pk_campaign=github&pk_kwd=dropchat "Hyperion Gray")

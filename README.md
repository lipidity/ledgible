# ledgible

ledgible is a fully-featured web interface for the [ledger-cli](http://ledger-cli.org) accounting program.

If you use already use ledger-cli:

- **ease data entry** with adaptive autocompletion that learns from your existing data; add transactions in mere seconds with no wasted keystrokes.

- **visualize your finances** to understand your cash flow, see your account balances, and track your net worth over time

- **add transactions immediately** as they occur; your data are available anywhere in the world

* * * *

ledgible is usable by **normal people** (my parents, siblings, and spouse use it) if some trustworthy sysadmin hosts it for them

[See it in action here](https://lipidity.com/cgi/ledgible/app.py/) (login as demo/demo; changes not permitted)

## Installation

### 0. Install dependencies

- git
- python2-flask
- ledger-cli compiled with python support (cmake flag -DUSE_PYTHON:BOOL=TRUE)
- any web server - ledgible must be run as CGI application due to limitation of ledger-cli's python bindings

### 1. Create a git repository for your data

    $ mkdir finances
    $ cd finances
    $ touch ledger.dat
    $ git init

Note: Your CGI process will need permission to modify your git repository. For easiest set up, run the above commands under the user account of your web server. You are of course free to set up more advanced configurations using shared repositories and/or git hooks if you have the inclination or know-how.

### 2. Install and configure ledgible

    $ cd /srv/http
    $ wget https://lipidity.com/pub/ledgible/ledgible-latest.tar.xz
    $ tar xf ledgible-latest.tar.xz
    $ cd ledgible
    $ python2 gen_settings.py
    username: john
    password: letmein
    ledger file: /srv/http/finances/ledger.dat

### 3. Start your server

Set up `ledgible/app.py` to be run as a CGI application.

Refer to instructions of your selected web server.

Note: ledger-cli compiled with python support allows arbitrary code execution by design. Safeguard your ledgible login details.


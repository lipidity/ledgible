from flask import Flask, session, redirect, url_for, request, render_template, Response, jsonify, abort

import ledger

from os import path

app = Flask(__name__)
app.config.from_object('settings')

@app.before_request
def csrf_protect():
    if request.method == 'POST':
        token = session.pop('csrf_token', None)
        if not token or token != request.form.get('csrf_token'):
            abort(400)

@app.before_request
def check_valid_login():
    if request.endpoint not in ('login', 'logout', 'static') and 'user' not in session:
        return redirect(url_for('login', next=request.url))

def generate_csrf_token():
    if 'csrf_token' not in session:
        from uuid import uuid4
        session['csrf_token'] = uuid4().hex
    return session['csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token
app.jinja_env.globals['commonprefix'] = path.commonprefix

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True


# Helper functions


def journal_file():
    return app.config['USERS'][session['user']]['ledger_file']

def query_journal(q):
    journal = ledger.read_journal(journal_file())
    return journal.query(q)

def iso_date(stri):
    from datetime import datetime
    return datetime.strptime(stri, '%Y-%m-%d').date()

def posts():
    from re import escape
    q = request.args
    s = escape(q.get('s', '-date'))
    b = q.get('b', '1962-01-01', type=iso_date)
    e = q.get('e', '3000-10-10', type=iso_date)
    a = ' '.join(escape(x) for x in q.getlist('a'))
    cmd = '-S {} -b {} -e {} {}'.format(s, b, e, a)
    return query_journal(cmd)

def account_tree(account):
    a = []
    while account != None:
        a.append(account.name)
        account = account.parent
    a.reverse()
    return tuple(a)

def minimize_hierarchy(a, counter):
    # filter out accounts without any postings
    ks = sorted(a.keys())
    for i in xrange(len(ks)):
        if not counter[ks[i]]:
            # no postings in this account
            # only show if multiple children accounts to be shown
            ch = 0
            j = i + 1
            while j < len(ks) and path.commonprefix((ks[i], ks[j])) == ks[i]:
                if counter[ks[j]]:
                    ch += 1
                j += 1
            if ch <= 1:
                del a[ks[i]]

def usd_amount(amount):
    usd = ledger.commodities.find_or_create('$')
    am = amount.value(usd)
    if am:
        return am.to_double()
    else:
        return 0

def check_file(f):
    try:
        j = ledger.read_journal(f)
    except RuntimeError:
        raise abort(400)

# http://www.evanmiller.org/rank-hotness-with-newtons-law-of-cooling.html
# for ranking autocomplete suggestions of accounts
exp = None
def cool(last_temp, time_elapsed, cooling_rate):
    global exp
    if exp is None:
        from math import exp
    return last_temp * exp(cooling_rate * time_elapsed)

def f2p(data, Posting):
    from re import escape
    postings = []
    for i in xrange(len(data.getlist('account'))):
        amount = data.getlist('amount')[i]
        commodity = data.getlist('commodity')[i]
        sign = data.getlist('dir')[i]
        if amount:
            if commodity and (commodity != '$'):
                amount = amount + ' ' + escape(commodity)
            else:
                amount = '$' + amount
            amount = ledger.Amount(amount)
            if sign == 'from':
                amount = - amount
        postings.append(Posting(data.getlist('account')[i], amount))
    return postings

def git_cmd(*args):
    # USER and HOME need to be set so git can find it's config files
    # but they're not set when run under CGI
    from os import geteuid
    from pwd import getpwuid
    from subprocess import check_output
    pw = getpwuid(geteuid())
    return check_output(["git", "-C", path.dirname(journal_file())] + list(args),
            universal_newlines=True,
            env={'USER': pw[0], 'HOME': pw[5]})


# Flask


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    user = None
    if request.method == 'POST':
        from werkzeug.security import check_password_hash
        u = app.config['USERS'].get(request.form['user'])
        if (u is not None) and check_password_hash(u['password'], request.form['password']):
            session['user'] = request.form['user']
            return redirect(request.args.get('next', url_for('index'))) # TODO MUST CHECK if query string in this
        error = 'Invalid username/password'
    if 'user' in session:
        return redirect(url_for('index'))
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))


@app.route('/')
def index():
    return redirect(url_for('balance'))


@app.route('/xacts')
def xacts():
    last_xact = None
    counts = []
    all_posts = posts()
    for post in all_posts:
        if post.xact == last_xact:
            counts[-1] += 1
        else:
            counts.append(1)
        last_xact = post.xact
    counts.reverse()
    return render_template('xacts.html', posts=all_posts, counts=counts)


@app.route('/balance')
def balance():
    from collections import defaultdict
    a = defaultdict(lambda: ledger.Value(0))
    counter = defaultdict(bool)
    for post in posts():
        account = post.account
        at = account_tree(account)
        counter[at] = True
        for i in xrange(1, len(at)+1):
            a[at[:i]] += post.amount
    # Expenses and Income accounts rolled up into a change in equity
    # MAYBE only if len(request.form.getlist('a')) == 0:
    change = a[('', 'Expenses')] + a[('', 'Income')]
    a[('', 'Equity')] += change
    a[('', 'Equity', 'Change')] += change
    counter[('', 'Equity', 'Change')] = True
    minimize_hierarchy(a, counter)
    rows = sorted([(x,y) for x,y in a.items()
        if len(x) < 2 or (x[1] not in ('Income','Expenses') and y.is_nonzero())])
    return render_template('balance.html', rows=rows)


@app.route('/income')
def income():
    from collections import defaultdict
    a = defaultdict(lambda: defaultdict(lambda: ledger.Value(0)))
    ds = set() # TODO compute all months between min and max
    counter = defaultdict(bool)
    for post in posts():
        account = post.account
        ym = post.date.strftime('%Y%m')
        ds.add(ym)
        at = account_tree(account)
        counter[at] = True
        for i in xrange(1, len(at)+1):
            a[at[:i]][ym] -= post.amount
    minimize_hierarchy(a, counter)
    ds = sorted(list(ds))
    return render_template('income.html', months=ds, rows=sorted(a.items()))


@app.route('/sunburst')
def sunburst():
    return render_template('sunburst.html')


@app.route('/equity')
def equity():
    return render_template('net.html')


@app.route('/posts.json')
def plotjson():
    postings = posts()
    data = [
            dict(date=post.date.strftime('%Y-%m-%d'),
                 account=account_tree(post.account)[1:],
                 amount=usd_amount(post.amount))
            for post in postings
           ]
    return jsonify(dict(posts=data))


@app.route('/accounts')
def json_accounts():
    from collections import defaultdict
    a = defaultdict(lambda: ledger.Value(0))
    postings = posts()
    usd = ledger.commodities.find_or_create('$')
    for post in postings:
        at = account_tree(post.account)
        val = post.amount.value(usd)
        a[at] += val if val else ledger.Value(0)
    p = dict(name='', children=[])
    for account, total in sorted(a.items()):
        q = p
        for component in account:
            n = next((x for x in q['children'] if x['name'] == component), False)
            if not n:
                n = dict(name=component, children=[])
                q['children'].append(n)
            q = n
        q['size'] = str(abs(total).number())
    return jsonify(p['children'][0])


# returns a score for each account that was used for specific payee(s)
# used to sort autocomplete suggestions in add transaction form
@app.route('/accounts/<sign>/<payee>')
def accounts_for_payee(sign, payee):
    from datetime import date
    from re import escape
    from collections import defaultdict
    postings = query_journal('@"{}"'.format(escape(payee)))
    a = defaultdict(dict)
    factor = -1 / 30.0
    for post in postings:
        if (sign == 'from' and post.amount < 0) or (sign == 'to' and post.amount > 0):
            n = post.account.fullname()
            last = a[n].setdefault('last', post.date)
            a[n]['T'] = cool(a[n].get('T',0), (post.date - last).days, factor)
            a[n]['T'] += 100.0
            a[n]['last'] = post.date
    for n,info in a.items():
        last = info.pop('last')
        # plus one when truncating
        # so that old accounts will be 1, above never used accounts which will be 0
        a[n] = int(cool(info['T'], (date.today()-last).days, factor)+1)
    return jsonify(a)


@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'GET':
        return render_template('add.html')
    elif request.method == 'POST':
        from tempfile import NamedTemporaryFile
        from collections import namedtuple
        data = request.form
        Posting = namedtuple('Posting', ['account', 'amount'])
        postings = f2p(data, Posting)
        if len(postings) == 0:
            abort(400)
        entry = render_template('entry.dat', date=data['realdate'], payee=data['payee'], note=data['note'], postings=postings)
        j_file = journal_file()
        with NamedTemporaryFile() as tmp:
            from shutil import copyfileobj
            with open(j_file, 'rb') as f:
                copyfileobj(f, tmp)
            tmp.write(entry)
            tmp.seek(0)
            check_file(tmp.name)
        with open(j_file, 'a') as f:
            f.write(entry)
        git_cmd('add', '.')
        git_cmd('commit', '-m', 'add xact from website')
        return redirect(url_for('xacts', b=data['realdate']))


@app.route('/edit', methods=['GET', 'POST'])
def edit():
    if request.method == 'GET':
        with open(journal_file(), 'r') as f:
            return render_template('edit.html', content=f.read())
    elif request.method == 'POST':
        from tempfile import NamedTemporaryFile
        data = '\n'.join(request.form['f'].splitlines()) + '\n'
        with NamedTemporaryFile() as tmp:
            tmp.write(data)
            tmp.seek(0)
            check_file(tmp.name)
        with open(journal_file(), 'w') as f:
            f.write(data)
        git_cmd('add', '.')
        git_cmd('commit', '-m', 'edit ledger from website')
        return redirect(url_for('xacts'))


@app.route('/js')
def js():
    a = set()
    q = posts()
    for post in q:
        account = post.account
        while account != None:
            a.add(account.fullname())
            account = account.parent
    accounts = sorted(list(a))
    a = set()
    for post in q:
        a.add(post.xact.payee)
    payees = sorted(list(a))
    return jsonify(dict(account=accounts[1:], payee=payees))


if __name__ == "__main__":
    app.run()


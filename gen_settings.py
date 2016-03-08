from werkzeug.security import generate_password_hash
from os import urandom, path

if path.exists('settings.py'):
    raise IOError('settings.py: file exists')

u = raw_input('username: ')
p = raw_input('password: ')
l = raw_input('ledger file: ')

us = dict()
us[u] = dict(password=generate_password_hash(p), ledger_file=l)

with open('settings.py', 'w') as fout:
    fout.write('SECRET_KEY = {}\n'.format(repr(urandom(24))))
    fout.write('USERS = {}\n'.format(repr(us)))


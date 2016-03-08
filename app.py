#!/usr/bin/python2
from wsgiref.handlers import CGIHandler
from ledgible import app

CGIHandler().run(app)

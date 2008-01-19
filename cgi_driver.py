#!/usr/bin/env python

import sys, cgitb
cgitb.enable()
sys.path.append('/path/to/here')

import tedium.Tedium, tedium.Cgi
t = tedium.Tedium.Tedium()
driver = tedium.Cgi.Driver(t)
driver.process_request()

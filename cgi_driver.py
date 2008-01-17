#!/usr/bin/env python
import sys
sys.path.append('/path/to/here')
import tedium.Tedium, tedium.Cgi
t = tedium.Tedium.Tedium()
cgi = tedium.Cgi.TediumCgi(t)
cgi.do_get()

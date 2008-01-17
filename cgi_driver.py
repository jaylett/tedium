#!/usr/bin/env python
import sys
sys.path.append('/path/to/here')
import tedium
t = tedium.Tedium()
cgi = tedium.Cgi.TediumCgi(t)
cgi.do_get()

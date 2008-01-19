#!/usr/bin/env python
import sys
sys.path.append('/path/to/here')
import tedium.Tedium, tedium.Cgi
t = tedium.Tedium.Tedium()
driver = tedium.Cgi.Driver(t)
driver.do_get()

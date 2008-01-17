# Tedium CGI interface
#
# (c) Copyright James Aylett 2008
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA

import tedium

import re, os, sys

class TediumCgi:
    def __init__(self, tedium):
        self.tedium = tedium
        pass

    def auth(self):
        if self.tedium.is_test:
            return
        if os.environ.get('REMOTE_USER')!=self.tedium.username:
            print "Content-Type: text/html; charset=utf-8\r\n"
            print '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "">'
            print "<html lang='en' xml:lang='en' xmlns='http://www.w3.org/1999/xhtml'><head><title>Permission denied</title>"
            print self.stylesheet();
            print "</head><body><h1>Permission denied</h1><p>You <em>must</em> set tedium up so it's sitting behind HTTP authentication. If you know what you're doing and disagree, change the source code. If not, set it up. I can't easily police whether you only access it encrypted, or across otherwise-secured transports, so there you're on your own. Sorry.</p>"
            print self.address()
            print "</body></html>"
            sys.exit(0)

    def address(self):
        return (u"<address>tedium v%s copyright <a href='http://tartarus.org/james/'>James Aylett</a>.</address>" % (tedium.VERSION,)).encode('utf-8')

    def stylesheet(self):
        cssfile = None
        for file in os.listdir('.'):
            if file[-4:]=='.css':
                cssfile = file
                break
        if cssfile!=None:
            return "<link type='text/css' rel='stylesheet' href='%s' />" % cssfile
        else:
            return ""

    def htmlify(self, text):
        import re
        # link anything using common URI
        linkifier = re.compile('[^ :/?#]+://[^ /?#]*[^ ?#]*(\?[^ #]*)?(#[^ ]*)?')
        return re.sub(linkifier, '<a target="_new" href="\g<0>">\g<0></a>', text)

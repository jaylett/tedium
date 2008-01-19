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

"""
Tedium's CGI driver.
"""

import tedium

import re, os, sys, cgi, cgitb

class Driver:
    """Tedium's CGI driver; construct with a Tedium object, then call do_get()."""
    def __init__(self, tedium, is_test=False):
        """Initialise driver with a given Tedium object."""
        self.tedium = tedium
        self.is_test = is_test
        self.linkifier = re.compile('[^ :/?#]+://[^ /?#]*[^ ?#]*(\?[^ #]*)?(#[^ ]*)?')
        self.user_linkifier = re.compile('@([A-Za-z0-9_]+)')

    def _auth(self):
        if self.is_test:
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

    def _address(self):
        return (u"<address>tedium v%s copyright <a href='http://tartarus.org/james/'>James Aylett</a>.</address>" % (tedium.VERSION,)).encode('utf-8')

    def _stylesheet(self):
        cssfile = None
        for file in os.listdir('.'):
            if file[-4:]=='.css':
                cssfile = file
                break
        if cssfile!=None:
            return "<link type='text/css' rel='stylesheet' href='%s' />" % cssfile
        else:
            return ""

    def _htmlify(self, text):
        # link anything using common URI
        text = re.sub(self.linkifier, '<a target="_new" href="\g<0>">\g<0></a>', text)
        # link @username
        text = re.sub(self.user_linkifier, '<a target="_new" href="http://twitter.com/\g<1>">\g<0></a>', text)
        return text

    def do_get(self):
        """Process a GET request."""
        self._auth()
        cgitb.enable()
        form = cgi.FieldStorage()

        # replies is one of 'all' or 'digest'
        # all shows all replies; digest has the same behaviour as for
        # digest emails, ie we show replies to *you* and to any contact
        # in the tedium database marked for replies
        reset_viewed = None
        reset_digest = None
        params = cgi.FieldStorage()
        if form.has_key('replies'):
            old_replies = self.tedium.get_conf('view_replies')
            replies = form.getfirst('replies')
            if replies!=old_replies:
                self.tedium.set_conf('view_replies', replies)
            reset_viewed = form.getfirst('last_viewed', None)
            reset_digest = form.getfirst('last_digest', None)
        else:
            replies = self.tedium.get_conf('view_replies')

        if not self.is_test and reset_viewed!=None:
            self.tedium.update_to_now('last_viewed', reset_viewed)
        if not self.is_test and reset_digest!=None:
            self.tedium.update_to_now('last_digest', reset_digest)

        print "Content-Type: text/html; charset=utf-8\r\n"
        print '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "">'
        print (u"<html lang='en' xml:lang='en' xmlns='http://www.w3.org/1999/xhtml'><head><title>Tweets for %s</title>" % self.tedium.username).encode('utf-8')
        print self._stylesheet();
        print "</head><body>"
        tweets = self.tedium.tweets_to_view(40, replies) # 40 is min to display
        last_viewed = self.tedium.get_conf('last_viewed')
        last_digest = self.tedium.get_conf('last_digest')

        if len(tweets)>0:
            print "<ol>"
            for tweet in tweets:
                author = tweet['author']
                rowstyle=""
                if tweet['published']>self.tedium.last_viewed:
                    rowstyle+=" new"
                if tweet['published']>self.tedium.last_digest:
                    rowstyle+=" notindigest"
                if author['protected']:
                    rowstyle+=" protected"
                print (u"<li class='%s'><span class='time'>%s</span> <span class='author'><a href='http://twitter.com/%s'>%s</a></span> <span class='tweet'>%s</span></li>" % (rowstyle, tweet['date'], author['nick'], author['fn'], self._htmlify(tweet['tweet']))).encode('utf-8')
            print "</ol>"
        if self.tedium.last_digest!=None:
            digestinfo = ' Digest emails appear to be running.'
        else:
            digestinfo = ''

        if replies=='digest':
            repliesinfo = 'Showing some replies. <a href="?replies=all&amp;last_viewed=%s&amp;last_digest=%s">Show all replies</a>.' % (last_viewed, last_digest)
        else:
            repliesinfo = 'Showing all replies. <a href="?replies=digest&amp;last_viewed=%s&amp;last_digest=%s">Show fewer replies</a>.' % (last_viewed, last_digest)

        print (u"<p><a href='http://twitter.com/'>Twitter</a> updates for <a href='http://twitter.com/%s'>%s</a>. %s%s</p>" % (self.tedium.username, self.tedium.username, repliesinfo, digestinfo)).encode('utf-8')
        print self._address()
        print "</body></html>"
        if not self.is_test:
            max_published = max(map(lambda x: x['published'], tweets))
            self.tedium.update_to_now('last_viewed', max_published)
            self.tedium.update_to_now('last_digest', max_published)

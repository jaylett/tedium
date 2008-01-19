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

import re, os, sys, cgi, cgitb, urllib

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
            print self._stylesheet();
            print "</head><body><h1>Permission denied</h1><p>You <em>must</em> set tedium up so it's sitting behind HTTP authentication. If you know what you're doing and disagree, change the source code. If not, set it up. I can't easily police whether you only access it encrypted, or across otherwise-secured transports, so there you're on your own. Sorry.</p>"
            print self._address()
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

    def _safe_attribute(self, text):
        # make it safe to put into an attribute...
        text = text.replace('&', '&amp;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text

    def _headers(self):
        print "Content-Type: text/html; charset=utf-8\r\n"

    def _html_head(self, title):
        print '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "">'
        print (u"<html lang='en' xml:lang='en' xmlns='http://www.w3.org/1999/xhtml'><head><title>%s</title>" % title).encode('utf-8')
        print self._stylesheet();
        print "</head>"

    def process_request(self):
        """Process an HTTP request."""
        self._auth()
        cgitb.enable()
        form = cgi.FieldStorage(keep_blank_values=True)

        method = os.environ.get('REQUEST_METHOD', 'GET')
        if method == 'GET':
            self.do_get(form)
        elif method == 'POST':
            self.do_post(form)
        else:
            sys.exit(1)

    def do_post(self, form):
        """Process a POST request."""
        self._auth()
        cgitb.enable()

        if form.getfirst('set-author-include-replies')!=None:
            # author-<aid> = <include|>
            for ak in form.keys():
                if ak.startswith('author-'):
                    bits = ak.split('-')
                    aid = int(bits[1])
                    if form.getfirst(ak)=='show':
                        include = 1
                    else:
                        include = 0
                    self.tedium.update_author_include_replies(aid, include)
                    
            authors = form.getlist('author-include-replies')
            self.tedium.save_changes()
        elif form.getfirst('update-status')!=None:
            new_status = form.getfirst('status')
            self.tedium.set_status(new_status)

        print "Location: %s" % os.environ.get('HTTP_REFERER', 'http://tartarus.org/james/')
        print

    def do_get(self, form=None):
        """Process a GET request."""
        self._auth()
        cgitb.enable()
        if form==None:
            form = cgi.FieldStorage()

        if os.environ.get('REQUEST_METHOD')=='POST':
            self.do_post(form)

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
            self.tedium.set_conf('last_viewed', reset_viewed)
        if not self.is_test and reset_digest!=None:
            self.tedium.set_conf('last_digest', reset_digest)

        self._headers()
        self._html_head('Tweets for %s' % self.tedium.username)
        print "<body>"
        last_viewed = self.tedium.get_conf('last_viewed')
        last_digest = self.tedium.get_conf('last_digest')
        tweets = self.tedium.tweets_to_view(20, replies) # min to display

        my_status = self.tedium.get_conf('current_status')
        if my_status!=None:
            print (u"<form id='status-form' method='post'><label for='status'>Current status</label>: <input type='text' name='status' value='%s' id='status' width='140' size='140' /><input type='submit' name='update-status' value='&gt;&gt; Update!' /></form>" % (self._safe_attribute(my_status))).encode('utf-8')

        if len(tweets)>0:
            print "<ol>"
            for tweet in tweets:
                author = tweet['author']
                rowstyle=""
                if tweet['published']>last_viewed:
                    rowstyle+=" new"
                if tweet['published']>last_digest:
                    rowstyle+=" notindigest"
                if author['protected']:
                    rowstyle+=" protected"
                print (u"<li class='%s'><span class='time'>%s</span> " % (rowstyle, tweet['date'])).encode('utf-8')
                if author['nick']==self.tedium.username:
                    print (u"<span class='author'><a href='http://twitter.com/%s'>%s</a></span>" % (author['nick'], author['fn'])).encode('utf-8')
                else:
                    if author['include_replies']==1:
                        a_r_flip = 'hide'
                        a_r_flip_text = 'hide replies'
                    else:
                        a_r_flip = 'show'
                        a_r_flip_text = 'show replies'
                    print (u"<span class='author'><form method='post'><input type='hidden' name='author-%i' value='%s' /><a href='http://twitter.com/%s'>%s</a> [<input type='submit' name='set-author-include-replies' value='%s' />]</form></span>" % (author['id'], a_r_flip, author['nick'], author['fn'], a_r_flip_text)).encode('utf-8')
                print (u"<span class='tweet'>%s</span></li>" % self._htmlify(tweet['tweet'])).encode('utf-8')
            print "</ol>"
        
        if replies=='digest':
            repliesinfo = 'Showing some replies. <a href="?replies=all&amp;last_viewed=%s&amp;last_digest=%s">Show all replies</a>.' % (last_viewed, last_digest)
        else:
            repliesinfo = 'Showing all replies. <a href="?replies=digest&amp;last_viewed=%s&amp;last_digest=%s">Show fewer replies</a>.' % (last_viewed, last_digest)

        print (u"<p><a href='http://twitter.com/'>Twitter</a> interface for <a href='http://twitter.com/%s'>%s</a>. %s</p>" % (self.tedium.username, self.tedium.username, repliesinfo)).encode('utf-8')
        print self._address()
        print "</body></html>"
        if not self.is_test and len(tweets)>0:
            max_published = max(map(lambda x: x['published'], tweets))
            self.tedium.set_conf('last_viewed', max_published)
            self.tedium.set_conf('last_digest', max_published)

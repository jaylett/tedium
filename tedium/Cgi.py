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

import re, os, os.path, sys, cgi, cgitb, urllib
from jinja import Template, Context, FileSystemLoader
from jinja.filters import stringfilter
from jinja.lib import stdlib

linkifier = re.compile('[a-zA-Z]+://[a-zA-Z0-9\.-]*[^ )?#]*(\?[^ )#]*)?(#[^ )]*)?')
user_linkifier = re.compile('@([A-Za-z0-9_]+)')

def htmlify(text):
    # link anything using common URI
    text = re.sub(linkifier, '<a target="_new" href="\g<0>">\g<0></a>', text)
    # link @username
    text = re.sub(user_linkifier, '<a target="_new" href="http://twitter.com/\g<1>">\g<0></a>', text)
    return text

def safe_attribute(text):
    # make it safe to put into an attribute...
    text = text.replace('&', '&amp;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text

stdlib.register_filter('htmlify', stringfilter(htmlify))
stdlib.register_filter('safe_attribute', stringfilter(safe_attribute))

class Driver:
    """Tedium's CGI driver; construct with a Tedium object, then call do_get()."""
    def __init__(self, _tedium, is_test=False):
        """Initialise driver with a given Tedium object."""
        self.tedium = _tedium
        self.is_test = is_test
        self.templates_dir = os.path.join(os.path.dirname(tedium.__file__), '../templates')

    def _auth(self):
        if self.is_test:
            return
        if os.environ.get('REMOTE_USER')!=self.tedium.username:
            print "Content-Type: text/html; charset=utf-8\r\n"
            tmpl = Template('auth_required', FileSystemLoader(self.templates_dir))
            c = Context({'tedium': self.tedium, 'cssfile':self._ponder_stylesheet()})
            print tmpl.render(c).encode('utf-8')
            sys.exit(0)

    def _ponder_stylesheet(self):
        cssfile = None
        for file in os.listdir('.'):
            if file[-4:]=='.css':
                cssfile = file
                break
        return cssfile

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

        if form.getfirst('set-author-include-replies-to')!=None:
            # author-<aid> = <include|>
            for ak in form.keys():
                if ak.startswith('author-'):
                    bits = ak.split('-')
                    aid = int(bits[1])
                    if form.getfirst(ak)=='show':
                        include = 1
                    else:
                        include = 0
                    self.tedium.update_author_include_replies_to(aid, include)
                    
            authors = form.getlist('author-include-replies-to')
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

        print "Content-Type: text/html; charset=utf-8\r\n"
        last_viewed = self.tedium.get_conf('last_viewed')
        last_digest = self.tedium.get_conf('last_digest')
        tweets = self.tedium.tweets_to_view(20, replies) # min to display

        my_status = self.tedium.get_conf('current_status')

        if len(tweets)>0:
            for tweet in tweets:
                author = tweet['author']
                if tweet['published']>last_viewed:
                    tweet['_is_new'] = True
                if tweet['published']>last_digest:
                    tweet['_is_notindigest'] = True
                if author['protected']:
                    tweet['_is_protected'] = True

        tmpl = Template('main', FileSystemLoader(self.templates_dir))
        c = Context({
            'my_status': my_status,
            'tedium': self.tedium,
            'tweets': tweets,
            'last_viewed': last_viewed,
            'last_digest': last_digest,
            'replies': replies,
            'cssfile': self._ponder_stylesheet()
            })
        print tmpl.render(c).encode('utf-8')
        
        if not self.is_test and len(tweets)>0:
            max_published = max(map(lambda x: x['published'], tweets))
            self.tedium.set_conf('last_viewed', max_published)
            self.tedium.set_conf('last_digest', max_published)
            self.tedium.save_changes()

# Tedium CGI interface
#
# (c) Copyright James Aylett 2009
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

import re, os, os.path, sys, cgi, cgitb, urllib, urllib2, urlparse, time
from jinja2 import Environment, FileSystemLoader

linkifier = re.compile('[a-zA-Z]+://[a-zA-Z0-9\.-]*[^ )?#]*[^ )?#.,](\?[^ )#]*)?(#[^ )]*)?')
user_linkifier = re.compile('@([A-Za-z0-9_]+)')

def htmlify(text):
    # link anything using common URI
    text = re.sub(linkifier, '<a target="_blank" href="\g<0>">\g<0></a>', text)
    # link @username
    text = re.sub(user_linkifier, '<a target="_blank" href="http://twitter.com/\g<1>">\g<0></a>', text)
    return text

def safe_attribute(text):
    # make it safe to put into an attribute...
    text = text.replace('&', '&amp;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text

def max_tweet_length(text):
    return 140 - len(text) - 2 # ': '

def escape_apos(text):
    return text.replace("'", '&apos;')

class Driver:
    """Tedium's CGI driver; construct with a Tedium object, then call do_get()."""
    def __init__(self, _tedium, is_test=False):
        """Initialise driver with a given Tedium object."""
        self.tedium = _tedium
        self.is_test = is_test
        template_dir = os.path.join(os.path.dirname(tedium.__file__), '../templates')
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.env.filters['htmlify'] = htmlify
        self.env.filters['safe_attribute'] = safe_attribute
        self.env.filters['max_tweet_length'] = max_tweet_length
        self.env.filters['escape_apos'] = escape_apos

    def _auth(self):
        if self.is_test:
            return
        if os.environ.get('REMOTE_USER')!=self.tedium.username:
            print "Content-Type: text/html; charset=utf-8\r\n"
            tmpl = self.env.get_template('auth_required.html')
            print tmpl.render(
                tedium=self.tedium,
                cssfile=self._ponder_stylesheet()
            )
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
        do_save = False

        if form.getfirst('long-uri')!=None:
            res = urllib2.urlopen('http://is.gd/api.php?%s' % urllib.urlencode({'longurl': form.getfirst('long-uri')}))
            print "Content-Type: text/plain"
            print
            print res.read()
            res.close()
            return

        if form.getfirst('set-author-include-replies-to')!=None:
            # author-<aid> = <show|>
            for ak in form.keys():
                if ak.startswith('author-'):
                    bits = ak.split('-')
                    aid = int(bits[1])
                    if form.getfirst(ak)=='show':
                        include = 1
                    else:
                        include = 0
                    self.tedium.update_author_include_replies_to(aid, include)
            do_save = True
        if form.getfirst('set-author-include-replies-from')!=None:
            # author-<aid> = <show|>
            for ak in form.keys():
                if ak.startswith('author-'):
                    bits = ak.split('-')
                    aid = int(bits[1])
                    if form.getfirst(ak)=='show':
                        include = 1
                    else:
                        include = 0
                    self.tedium.update_author_include_replies_from(aid, include)
            do_save = True
        if form.getfirst('set-author-ignore-until-now-plus')!=None:
            # author-<aid> = <seconds>
            for ak in form.keys():
                if ak.startswith('author-'):
                    bits = ak.split('-')
                    aid = int(bits[1])
                    until = int(time.time()) + int(form.getfirst(ak))
                    self.tedium.update_author_ignore_until(aid, until)
            do_save = True
        if form.getfirst('classify')!=None:
            # tweet-<tid> = <0|1|2>
            for tk in form.keys():
                if tk.startswith('tweet-'):
                    bits = tk.split('-')
                    tid = int(bits[1])
                    try:
                        self.tedium.update_tweet_spamminess(tid, int(form.getfirst(tk)))
                    except:
                        pass
            do_save = True
        if form.getfirst('update-filter')!=None:
            self.tedium.set_conf('fixed_filter', form.getfirst('fixed-filter'))
            do_save = True

        if do_save:
            self.tedium.save_changes()
        if form.getfirst('update-status')!=None:
            new_status = form.getfirst('status')
            in_reply_to = form.getfirst('in-reply-to')
            self.tedium.set_status(new_status, in_reply_to)

        next_uri = os.environ.get('HTTP_REFERER', 'http://tartarus.org/james/tedium/')
        bits = urlparse.urlparse(next_uri)
        query = dict(cgi.parse_qsl(bits[4]))
        reset_viewed = form.getfirst('last_viewed', None)
        reset_digest = form.getfirst('last_digest', None)
        if reset_viewed!=None:
            query['last_viewed'] = reset_viewed
        if reset_digest!=None:
            query['last_digest'] = reset_digest
        if reset_digest!=None or reset_viewed!=None:
            query['last_sequence'] = self.tedium.get_conf('last_sequence', 1)
        new_bits = list(bits)
        new_bits[4] = urllib.urlencode(query)
        next_uri = urlparse.urlunparse(new_bits)

        print "Location: %s" % next_uri
        print

    def manage(self, form):
        if os.environ.get('REQUEST_METHOD')=='POST':
            return self.manage_post(form)
        else:
            return self.manage_get(form)

    def manage_post(self, form):
        return

    def manage_get(self, form):
        print "Content-Type: text/html; charset=utf-8\r\n"
        tmpl = self.env.get_template('manage.html')
        authors = self.tedium.get_authors()
        authors.sort(lambda x, y: -cmp(x['priority'], y['priority']))
        print tmpl.render(
            tedium  = self.tedium,
            cssfile = self._ponder_stylesheet(),
            authors = authors[0:10],
            ).encode('utf-8')

    def do_get(self, form=None):
        """Process a GET request."""
        self._auth()
        cgitb.enable()
        if form==None:
            form = cgi.FieldStorage()

        if form.has_key('manage'):
            return self.manage(form)

        if os.environ.get('REQUEST_METHOD')=='POST':
            return self.do_post(form)

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
        else:
            replies = self.tedium.get_conf('view_replies')
        if form.has_key('spam'):
            old_spam = self.tedium.get_conf('view_spam')
            spam = form.getfirst('spam')
            if spam!=old_spam:
                self.tedium.set_conf('view_spam', spam)
        else:
            spam = self.tedium.get_conf('view_spam')
        
        reset_viewed = form.getfirst('last_viewed', None)
        reset_digest = form.getfirst('last_digest', None)

        # If the sequence number fed into the CGI doesn't match
        # the one in the database, it means that the page has been
        # refreshed, so we should *ignore* the last_* inputs.
        #
        # When generating a URL with last_*, remember to include
        # last_sequence :-)
        last_sequence = int(form.getfirst('last_sequence', 0))
        sequence = self.tedium.get_conf('last_sequence', 1)
        if last_sequence != sequence:
            reset_viewed = None
            reset_digest = None
        if reset_viewed!=None or reset_digest!=None:
            # Update the stored configuration so that picking it up
            # and dropping it into a URL will match *next* time.
            # Only bother doing this when resetting. (Conservation.)
            self.tedium.set_conf('last_sequence', sequence + 1)

        if not self.is_test and reset_viewed!=None:
            self.tedium.set_conf('last_viewed', reset_viewed)
        if not self.is_test and reset_digest!=None:
            self.tedium.set_conf('last_digest', reset_digest)

        print "Content-Type: text/html; charset=utf-8\r\n"
        last_viewed = self.tedium.get_conf('last_viewed')
        last_digest = self.tedium.get_conf('last_digest')
        last_sequence = self.tedium.get_conf('last_sequence')
        try:
            num_to_get = int(form.getfirst('tweets'))
        except:
            num_to_get = 10
        try:
            min_priority = int(form.getfirst('priority'))
        except:
            min_priority = 0
        tweets = self.tedium.tweets_to_view(num_to_get, replies, spam, min_priority)

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
                if self.tedium.is_tweet_spam(tweet['id']):
                    tweet['_is_spam'] = True
                tweet['_spam_score'] = self.tedium.tweet_spam_score(tweet['id'])

        tmpl = self.env.get_template('main.html')
        # WARNING: *ensure* that tweets.tweet is entity escapes wrt XML
        # builtins. my_status carries the same warning. (Use the escape_apos
        # filter to put my_status in a '-delimited attribute, eg for <input>.)
        print tmpl.render(
            my_status = my_status,
            tedium = self.tedium,
            tweets = tweets,
            last_viewed = last_viewed,
            last_digest = last_digest,
            last_sequence = last_sequence,
            replies = replies,
            spam = spam,
            cssfile = self._ponder_stylesheet(),
            fixed_filter = self.tedium.get_conf('fixed_filter')
            ).encode('utf-8')
        
        if not self.is_test and len(tweets)>0:
            max_published = max(map(lambda x: x['published'], tweets))
            self.tedium.set_conf('last_viewed', max_published)
            if min_priority==0:
                self.tedium.set_conf('last_digest', max_published)
            self.tedium.save_changes()

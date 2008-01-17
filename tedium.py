#!/usr/bin/python
#
# Copyright (C) 2008 James Aylett
#
# tedium: a natural result of too much twitter
#                     or
# tedium: the Twitter Digest Manager
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
#
# Run once to set up username/password, run on cron to grab latest
# tweets, run as CGI to see recent activity, run with an email address
# to get a digest. It figures out the context.
#
# If you run it as a CGI, it'll choose the first CSS file in the same
# directory (assuming the CGI process can read that
# directory). The bulk is a simple <ol>. Classnames used are:
#
#   time, author, tweet       layout of the tweet (three <span>s inside <li>)
#   protected	              applied to <li> if updates are protected
#   new                       applied to <li> if tweet after last CGI view
#   notindigest               applied to <li> if tweet after last email digest
#
# When you view the CGI, anything on there won't appear on a future
# email digest.
#
# For CGI it's *strongly* advised that you run under suexec or via
# userv, so it's running as you rather than as the web user. You might
# also prefer to use cgi_driver.py instead of copying everything into
# your web space.
#
# Everything is stored in ~/.tedium, or somewhere else if you pass in
# a directory to the Tedium class constructor. (See down the bottom,
# and above in the sample CGI launcher.) You should change the
# permissions on the directory so they aren't readable by anyone other
# than you (hence suexec/userv for CGI) since it will contain your
# twitter login credentials.
#
# For CGI access, you must run behind some sort of HTTP authentication.
# Either use digest, or basic behind HTTPS, or anything over a local
# connection, or something like that. Connections to twitter use HTTPS.
#
# Currently there is no way of editing this, but if you want to see
# replies to a particular user in the digest, set
# author_include_replies to 1 in the authors table for them (use the
# sqlite3 client). Otherwise, only replies to you are shown.
#
# FEATURE: CGI option to restrict replies as digest
# FEATURE: link @username targets
# FEATURE: CGI mechanisms for post & reply
# FIXME: when we mark last_*, we use max(tweet_published) from too late
# FIXME: assumes UTC coming out of twitter
# FIXME: change to Atom to avoid HTML entities (JSON is lovely, twitter not)
# FIXME: should probably store the id of a tweet as the tweet PK

import urllib, urllib2, os, os.path, sys, json
import datetime, time, smtplib, textwrap, pwd, getopt

from pysqlite2 import dbapi2 as sqlite
from email.MIMEText import MIMEText
import email.Charset

import tedium

class Tedium:
    def __init__(self, configpath=None):
        if configpath==None:
            try:
                userdir = os.environ['HOME']
            except KeyError:
                pwent = pwd.getpwuid(os.getuid())
                userdir = pwent[5]
            except:
                raise tedium.TediumError("Cannot determine home directory.")
            configpath = os.path.join(userdir, '.tedium')
            if not os.path.exists(configpath):
                os.mkdir(configpath)
            if not os.path.isdir(configpath):
                raise tedium.TediumError('~/.tedium exists and is not a directory')
        elif not os.path.isdir(configpath):
            raise tedium.TediumError("%s is not a directory" % configpath)

        self.configpath = configpath
        self.dbpath = os.path.join(self.configpath, 'db')
        self.db = sqlite.connect(self.dbpath)

        c = self.db.cursor()
        self.username = ''
        self.password = ''
        self.ensure_database(c)

        c.execute("SELECT last_updated, last_digest, last_viewed, username, password, digest_format FROM metadata LIMIT 1")
        row = c.fetchone()
        self.last_updated = row[0]
        self.last_digest = row[1]
        self.last_viewed = row[2]
        self.username = row[3]
        self.password = row[4]
        self.digest_format = row[5]
        if self.username==None or self.password==None:
            self.configure(c)
        self.db.commit()
        c.close()

        auth_handler = urllib2.HTTPBasicAuthHandler()
        auth_handler.add_password('Twitter API', 'twitter.com', self.username, self.password)
        opener = urllib2.build_opener(auth_handler)
        urllib2.install_opener(opener)

    def ensure_database(self, cursor):
        self.create_if_no_metadata_table(cursor)
        cursor.execute("SELECT version FROM metadata")
        row = cursor.fetchone()
        if row==None:
            # if nothing in the metadata table, we don't know what
            # version the database is, so we can't upgrade it reliably.
            # Instead, drop the whole lot and start again (there shouldn't
            # be any data in it anyway). This allows people to run tedium
            # once, fail to get their password right, upgrade, and run again
            # without death doom and destruction.
            print "Nothing in metadata, rebuilding db."
            cursor.execute("DROP TABLE IF EXISTS metadata")
            cursor.execute("DROP TABLE IF EXISTS tweets")
            cursor.execute("DROP TABLE IF EXISTS authors")
            self.create_if_no_metadata_table(cursor)
            cursor.execute("INSERT INTO metadata(version) VALUES (?)", [tedium.DB_VERSION])
            self.initialise_database(cursor)
        else:
            if row[0] < tedium.DB_VERSION:
                print "Upgrading db."
                self.upgrade_database(row[0], cursor)

    def create_if_no_metadata_table(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS metadata (version INTEGER NOT NULL DEFAULT %i, last_updated DATETIME, username VARCHAR(30), password VARCHAR(30), last_digest DATETIME, last_viewed DATETIME, digest_format VARCHAR(20))" % tedium.DB_VERSION)

    def initialise_database(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS tweets (tweet_id INTEGER NOT NULL PRIMARY KEY, tweet_text VARCHAR(150) NOT NULL, tweet_author INTEGER NOT NULL, tweet_published DATETIME NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS authors (author_id INTEGER NOT NULL PRIMARY KEY, author_fn VARCHAR(30) NOT NULL, author_nick VARCHAR(30) NOT NULL, author_protected INTEGER(1), author_avatar VARCHAR(255), author_include_replies INTEGER(1) NOT NULL DEFAULT 0)")
        self.configure(cursor)

    def reconfigure(self):
        cursor = self.db.cursor()
        self.configure(cursor)
        self.db.commit()
        cursor.close()

    def configure(self, cursor):
        if sys.stdin.isatty():
            if self.username:
                sys.stdout.write('Enter your twitter username [%s]: ' % self.username)
            else:
                sys.stdout.write('Enter your twitter username: ')
            username = sys.stdin.readline()
            username = username.strip()
            if username!='':
                self.username = username
            if self.username:
                sys.stdout.write('Enter your twitter password [%s]: ' % self.password)
            else:
                sys.stdout.write('Enter your twitter password: ')
            password = sys.stdin.readline()
            password = password.strip()
            if password!='':
                self.password = password
            sys.stdout.write('Enter digest format string (Return for default): ')
            self.digest_format = sys.stdin.readline()
            self.digest_format = digest_format.strip()
            cursor.execute("UPDATE metadata SET username=?, password=?, digest_format=?", [self.username, self.password, self.digest_format])
        else:
            raise tedium.TediumError('You must configure Tedium before it will work.\nJust run it from the command line to get things started.')

    def delete_credentials(self, cursor):
        cursor.execute("UPDATE metadata SET username=NULL, password=NULL")
        self.db.commit()

    def upgrade_database(self, old_version, cursor):
        if old_version<2:
            cursor.execute("ALTER TABLE authors ADD COLUMN author_include_replies INTEGER(1) NOT NULL DEFAULT 0")
            cursor.execute("UPDATE metadata SET version=2")

    def update(self):
        if self.last_updated==None:
            uri = 'https://twitter.com/statuses/friends_timeline.json'
        else:
            # HTTP formatted date
            uri = 'https://twitter.com/statuses/friends_timeline.json?since=%s' % urllib.quote_plus(self.last_updated)
        try:
            c = self.db.cursor()
            f = urllib2.urlopen(uri)
            #f = open('test.json', 'r')
            data = f.read()
            f.close()
            j = json.JsonReader()
            tweets = j.read(data)
            for tweet in tweets:
                self.process_tweet(tweet, c)
            self.update_to_now('last_updated', None, c)
            self.db.commit()
            c.close()
        except urllib2.URLError, e:
            if e.code==401:
                self.delete_credentials(c)
                c.close()
                raise tedium.TediumError('Username/password incorrect!', e)
            c.close()
            if e.code==304:
                # Not modified, don't kick up a fuss
                return
            #print e.read()
            raise tedium.TediumError('Could not fetch updates from Twitter', e)

    # not strictly 'now', but the most recent tweet we've found
    # note that this can go wrong if you use the automatic version
    # (now=None)
    def update_to_now(self, field, now, cursor):
        if now==None:
            cursor.execute("SELECT MAX(tweet_published) FROM tweets")
            row = cursor.fetchone()
            if row[0]!=None:
                now = row[0]
        if now!=None:
            cursor.execute("UPDATE metadata SET %s=?" % field, [now])
            if cursor.rowcount==0:
                cursor.execute("INSERT INTO metadata (%s) VALUES (?)" % field, [now])
            else:
                cursor.execute("SELECT %s FROM metadata LIMIT 1" % field)
                rows = cursor.fetchall()
                if len(rows)==0:
                    cursor.execute("INSERT INTO metadata (%s) VALUES (?)" % field, [now])

    _author_cache = {}
    def get_author(self, id, cursor):
        u = self._author_cache.get(id)
        if u!=None:
            return u
        cursor.execute("SELECT author_fn, author_nick, author_avatar, author_protected, author_include_replies FROM authors WHERE author_id=?", [int(id)])
        row = cursor.fetchone()
        if row==None:
            return None
        else:
            u = { 'fn': row[0], 'nick': row[1], 'avatar': row[2], 'include_replies': row[4] }
            if row[3]:
                u['protected'] = True
            else:
                u['protected'] = False
            self._author_cache[id] = u
            return u

    def digest_line(self, keys):
        if self.digest_format!=None:
            return self.digest_format % keys
        else:
            return tedium.DEFAULT_DIGEST_FORMAT % keys

    def get_author_by_username(self, username, cursor):
        cursor.execute("SELECT author_id FROM authors WHERE author_nick=?", [username])
        row = cursor.fetchone()
        if row!=None:
            return self.get_author(row[0], cursor)

    def find_author(self, id, cursor):
        cursor.execute("SELECT author_id FROM authors WHERE author_id=?", [int(id)])
        row = cursor.fetchone()
        if row==None:
            return None
        else:
            return row[0]

    def update_author(self, info, cursor):
        cursor.execute("UPDATE authors SET author_nick=?, author_fn=?, author_avatar=?, author_protected=? WHERE author_id=?", (info['screen_name'], info['name'], info['profile_image_url'], info['protected'], info['id']))
        return int(info['id'])

    def make_author(self, info, cursor):
        cursor.execute("INSERT INTO authors (author_id, author_nick, author_fn, author_avatar, author_protected) VALUES (?, ?, ?, ?, ?)", [info['id'], info['screen_name'], info['name'], info['profile_image_url'], info['protected']])
        return int(info['id'])

    def make_tweet(self, author_id, text, dt_in, cursor):
        # If we used Atom, this would be easier (but still not trivial,
        # as SQLite can't cope with the TZ part of the RFC 3339 date-time).
        #
        # This assumes we're in UTC (let's hope twitter did something
        # sensible - I've observed this correctly for non-UTC authors,
        # but that may be because *I'm* in UTC...)
        dt_in = dt_in.replace(' +0000', '')
        #print dt_in
        ds_obj = datetime.datetime(*time.strptime(dt_in, "%a %b %d %H:%M:%S %Y")[0:6])
        timestring = ds_obj.isoformat()
        cursor.execute("INSERT INTO tweets (tweet_author, tweet_text, tweet_published) VALUES (?, ?, ?)", [author_id, text, timestring])
        #print "Inserted tweet from %i" % author_id

    def process_tweet(self, tweet, cursor):
        #print tweet
        author_id = self.find_author(tweet['user']['id'], cursor)
        if author_id==None:
            author_id = self.make_author(tweet['user'], cursor)
        else:
            author_id = self.update_author(tweet['user'], cursor)
        self.make_tweet(author_id, tweet['text'], tweet['created_at'], cursor)

    def digest(self, email_address, real=None):
        c = self.db.cursor()
        if self.last_digest==None:
            self.last_digest = '1970-01-01 00:00:00'
        c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author FROM tweets WHERE tweet_published > ? ORDER BY tweet_published DESC", [self.last_digest])
        rows = c.fetchall()
        if len(rows)>0:
            digest = ''
            tw = textwrap.TextWrapper(initial_indent = ' '*8, subsequent_indent = ' '*8)
            for row in rows:
                text = row[1].strip()
                # ignore replies not to us
                if text[0]=='@':
                    if text[1:len(self.username)+1]!=self.username:
                        replyname = text[1:].replace(':', ' ').split()[0]
                        if replyname!='':
                            a = self.get_author_by_username(replyname, c)
                            if a==None or not a['include_replies']:
                                continue
                        else:
                            continue
                author = self.get_author(row[2], c)
                if author==None:
                    print "Skipping %s" % row[1]
                    continue
                digest_keys = {'time': row[0], 'nick': author['nick'], 'fn': author['fn'], 'tweet': row[1], 'wrapped_tweet': tw.fill(row[1])}
                digest += self.digest_line(digest_keys)
            if digest!='':
                digest = "Hi %s. Here's your twitter digest:\n\n%s" % (self.username, digest)

            if email_address=='show':
                print digest.encode('utf8')
                c.close()
                return
            else:
                msg = MIMEText(digest.encode('utf8'), 'plain', 'utf8')
                msg['Subject'] = 'Twitter digest'
                if real!=None:
                    format_email = '%s <%s>' % (real, email_address)
                else:
                    format_email = email_address
                msg['From'] = format_email
                msg['To'] = format_email
                s = smtplib.SMTP()
                s.connect()
                s.sendmail(email_address, [email_address], msg.as_string())
                s.close()
        self.update_to_now('last_digest', None, c)
        self.db.commit()
        c.close()

    def cgi_auth(self):
        if os.environ.get('REMOTE_USER')!=self.username:
            print "Content-Type: text/html; charset=utf-8\r\n"
            print '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "">'
            print "<html lang='en' xml:lang='en' xmlns='http://www.w3.org/1999/xhtml'><head><title>Permission denied</title>"
            print self.cgi_stylesheet();
            print "</head><body><h1>Permission denied</h1><p>You <em>must</em> set tedium up so it's sitting behind HTTP authentication. If you know what you're doing and disagree, change the source code. If not, set it up. I can't easily police whether you only access it encrypted, or across otherwise-secured transports, so there you're on your own. Sorry.</p>"
            print self.cgi_address()
            print "</body></html>"
            sys.exit(0)

    def cgi_address(self):
        return (u"<address>tedium v%s copyright <a href='http://tartarus.org/james/'>James Aylett</a>.</address>" % (tedium.VERSION,)).encode('utf-8')

    def cgi_stylesheet(self):
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

    def cgi(self):
        import cgi
        opts = cgi.FieldStorage()
        self.cgi_auth()

        print "Content-Type: text/html; charset=utf-8\r\n"
        print '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "">'
        print (u"<html lang='en' xml:lang='en' xmlns='http://www.w3.org/1999/xhtml'><head><title>Tweets for %s</title>" % self.username).encode('utf-8')
        print self.cgi_stylesheet();
        print "</head><body>"
        c = self.db.cursor()
        if self.last_viewed==None:
            self.last_viewed = '1970-01-01 00:00:00'
        if self.last_digest==None:
            self.last_digest = '1970-01-01 00:00:00'
        c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author, tweet_published FROM tweets WHERE tweet_published > ? ORDER BY tweet_published DESC", [self.last_viewed])
        rows = c.fetchall()
        number_to_fetch = 40 - len(rows)
        if number_to_fetch > 0:
            c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author, tweet_published FROM tweets WHERE tweet_published <= ? ORDER BY tweet_published DESC LIMIT ?", [self.last_viewed, number_to_fetch])
            rows1 = c.fetchall()
            rows.extend(rows1)
            rows.sort(lambda x,y: -cmp(x[3],y[3]))
        if len(rows)>0:
            print "<ol>"
            for row in rows:
                author = self.get_author(row[2], c)
                rowstyle=""
                if row[3]>self.last_viewed:
                    rowstyle+=" new"
                if row[3]>self.last_digest:
                    rowstyle+=" notindigest"
                if author['protected']:
                    rowstyle+=" protected"
                print (u"<li class='%s'><span class='time'>%s</span><span class='author'><a href='http://twitter.com/%s'>%s</a></span><span class='tweet'>%s</span></li>" % (rowstyle, row[0], author['nick'], author['fn'], self.htmlify(row[1]))).encode('utf-8')
            print "</ol>"
        if self.last_digest!=None and self.last_digest!=self.last_viewed:
            digestinfo = ' Digest emails appear to be running.'
        else:
            digestinfo = ''
        print (u"<p><a href='http://twitter.com/'>Twitter</a> updates for <a href='http://twitter.com/%s'>%s</a>. Including all replies.%s</p>" % (self.username, self.username, digestinfo)).encode('utf-8')
        print self.cgi_address()
        print "</body></html>"
        self.update_to_now('last_viewed', None, c)
        self.update_to_now('last_digest', None, c)
        self.db.commit()
        c.close()

def usage():
    print u"Usage: %s [options] [email [name]]" % sys.argv[0]
    print u"Options:"
    print u"\t--help\t\tThis message"
    print u"\t--confdir d\tUse ``d'' instead of ~/.tedium"
    print u"\t--reconfigure\tReconfigure tedium"
    print
    print u"Will force configuration the first time."
    print u"Subsequent runs will update from Twitter."
    print u"Call with email address and optional name to generate digest."
    print u"Run as CGI for web interface."

if __name__ == '__main__':
    try:
        try:
            optlist, args = getopt.getopt(sys.argv[1:], 'hc:r', ['help', 'confdir=', 'reconfigure'])
        except getopt.GetoptError:
            usage()
            sys.exit(2)

        confdir = None
        reconfigure = False

        for opt, arg in optlist:
            if opt in ('-h', '--help'):
                usage()
                sys.exit()
            if opt in ('-c', '--confdir'):
                confdir = arg
            if opt in ('r', '--reconfigure'):
                reconfigure = True

        t = Tedium(confdir)
        if reconfigure:
            t.reconfigure()
            sys.exit()

        if len(args)>0:
            if len(args)>1:
                t.digest(args[0], args[1])
            else:
                t.digest(args[0])
        elif os.environ.get('GATEWAY_INTERFACE')=='CGI/1.1':
            t.cgi()
        else:
            # Get latest tweets (possibly prompt for configuration first)
            t.update()
    except tedium.TediumError, e:
        sys.stdout.write(str(e))
        sys.stdout.write("\n")
        print e.aux

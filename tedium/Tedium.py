# Tedium core
#
# Copyright (C) 2008 James Aylett
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

"""Core; currently, everything except CGI and invocation."""

import urllib, urllib2, os, os.path, sys
import datetime, time, smtplib, textwrap, pwd, getopt

try:
    from xml.etree.ElementTree import fromstring as etree_fromstring # python 2.5
except:
    from elementtree.ElementTree import fromstring as etree_fromstring # python 2.4

from pysqlite2 import dbapi2 as sqlite
from email.MIMEText import MIMEText
import email.Charset

import tedium

DB_VERSION = 5

class Tedium:
    def __init__(self, configpath=None):
        self.VERSION = tedium.VERSION
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
        self._ensure_database(c)

        c.execute("SELECT last_updated, username, password, digest_format FROM metadata LIMIT 1")
        row = c.fetchone()
        self.last_updated = row[0]
        self.username = row[1]
        self.password = row[2]
        self.digest_format = row[3]
        if self.username==None or self.password==None:
            self._configure(c)
        self.db.commit()
        c.close()

        auth_handler = urllib2.HTTPBasicAuthHandler()
        auth_handler.add_password('Twitter API', 'twitter.com', self.username, self.password)
        opener = urllib2.build_opener(auth_handler)
        urllib2.install_opener(opener)

    def _ensure_database(self, cursor):
        self._create_if_no_metadata_table(cursor)
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
            self._create_if_no_metadata_table(cursor)
            cursor.execute("INSERT INTO metadata(version) VALUES (?)", [DB_VERSION])
            self._initialise_database(cursor)
        else:
            if row[0] < DB_VERSION:
                #print "Upgrading db."
                self._upgrade_database(row[0], cursor)

    def _create_if_no_metadata_table(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS metadata (version INTEGER NOT NULL DEFAULT %i, last_updated DATETIME, username VARCHAR(30), password VARCHAR(30), last_digest DATETIME, last_viewed DATETIME, digest_format VARCHAR(20), current_status VARCHAR(140), view_replies VARCHAR(10))" % DB_VERSION)

    def _initialise_database(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS tweets (tweet_id INTEGER NOT NULL PRIMARY KEY, tweet_text VARCHAR(150) NOT NULL, tweet_author INTEGER NOT NULL, tweet_published DATETIME NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS authors (author_id INTEGER NOT NULL PRIMARY KEY, author_fn VARCHAR(30) NOT NULL, author_nick VARCHAR(30) NOT NULL, author_protected INTEGER(1), author_avatar VARCHAR(255), author_include_replies INTEGER(1) NOT NULL DEFAULT 0, author_include_replies_from INTEGER(1) NOT NULL DEFAULT 0)")
        self._configure(cursor)

    def reconfigure(self):
        cursor = self.db.cursor()
        self._configure(cursor)
        self.db.commit()
        cursor.close()

    def _configure(self, cursor):
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
            self.digest_format = self.digest_format.strip()
            cursor.execute("UPDATE metadata SET username=?, password=?, digest_format=?", [self.username, self.password, self.digest_format])
        else:
            raise tedium.TediumError('You must configure Tedium before it will work.\nJust run it from the command line to get things started.')

    def delete_credentials(self, cursor):
        cursor.execute("UPDATE metadata SET username=NULL, password=NULL")
        self.db.commit()

    def _upgrade_database(self, old_version, cursor):
        if old_version<2:
            cursor.execute("ALTER TABLE authors ADD COLUMN author_include_replies INTEGER(1) NOT NULL DEFAULT 0")
            cursor.execute("UPDATE metadata SET version=2")
        if old_version<3:
            cursor.execute("ALTER TABLE metadata ADD COLUMN view_replies VARCHAR(10)")
            cursor.execute("UPDATE metadata SET version=3, view_replies='all'")
        if old_version<4:
            cursor.execute("ALTER TABLE metadata ADD COLUMN current_status VARCHAR(140)")
            cursor.execute("UPDATE metadata SET version=4")
        if old_version<5:
            cursor.execute("ALTER TABLE authors ADD COLUMN author_include_replies_from INTEGER(1) NOT NULL DEFAULT 0")
            cursor.execute("UPDATE metadata SET version=5")

    def update(self):
        # get our latest tweet
        try:
            uri = "https://twitter.com/users/show/%s.xml" % self.username
            f = urllib2.urlopen(uri)
            data = f.read()
            f.close()
            status = etree_fromstring(data)
            if status.tag!='user':
                raise tedium.TediumError('Twitter response was not an XML doc with root user')
            status = self._extract_from_xml(status)
            my_status = status.get('status', {}).get('text')
            if my_status!=None:
                self.set_conf('current_status', my_status)
        except urllib2.URLError:
            pass
        
        if self.last_updated==None:
            uri = 'https://twitter.com/statuses/friends_timeline.xml'
        else:
            # HTTP formatted date
            uri = 'https://twitter.com/statuses/friends_timeline.xml?since=%s' % urllib.quote_plus(self.last_updated)
        try:
            c = self.db.cursor()
            f = urllib2.urlopen(uri)
            data = f.read()
            f.close()
            tweets = etree_fromstring(data)
            max_published = None
            if tweets.tag!='statuses':
              raise tedium.TediumError('Twitter response was not an XML doc with root statuses')
            for tweet in tweets:
                if tweet.tag!='status':
                  raise tedium.TedimuError('Twitter response was not a list of statuses')
                published = self.process_tweet(tweet, c)
                if published > max_published or max_published==None:
                    max_published = published
            c.close()
            if max_published!=None:
                self.set_conf('last_updated', max_published)
            self.save_changes()
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

    def get_conf(self, confname, default=None):
        """Get a config option."""
        cursor = self.db.cursor()
        cursor.execute("SELECT %s FROM metadata" % confname)
        row = cursor.fetchone()
        value = row[0]
        if value==None:
            value = default
        cursor.close()
        return value

    def set_conf(self, confname, value):
        """Set a config option."""
        cursor = self.db.cursor()
        cursor.execute("UPDATE metadata SET %s=?" % confname, [value])
        cursor.close()

    def set_status(self, new_status):
        """Send a tweet."""
        try:
            uri = 'https://twitter.com/statuses/update.xml'
            f = urllib2.urlopen(uri, 'status=%s' % urllib.quote_plus(new_status))
            data = f.read()
            f.close()
            status = etree_fromstring(data)
            if status.tag!='status':
                raise tedium.TediumError('Twitter response was not an XML doc with root status')
            status = self._extract_from_xml(status)
            if status['text']==new_status:
                self.set_conf('current_status', new_status)
                self.save_changes()
            else:
                raise tedium.TediumError("Came back with different status: %s" % status['text'])
        except tedium.TediumError:
            raise
        except Exception, e:
            raise tedium.TediumError("Could not post new tweet", e)

    _author_cache = {}
    def get_author(self, id, cursor):
        u = self._author_cache.get(id)
        if u!=None:
            return u
        cursor.execute("SELECT author_fn, author_nick, author_avatar, author_protected, author_include_replies, author_id, author_include_replies_from FROM authors WHERE author_id=?", [int(id)])
        row = cursor.fetchone()
        if row==None:
            return None
        else:
            u = { 'id': row[5], 'fn': row[0], 'nick': row[1], 'avatar': row[2], 'include_replies_to': row[4], 'include_replies_from': row[6] }
            if row[3]=='true':
                u['protected'] = True
            else:
                u['protected'] = False
            if u['nick'] == self.username:
                u['is_me'] = True
            else:
                u['is_me'] = False
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

    def save_changes(self):
        """Save all changes that have been processed recently."""
        self.db.commit()

    def update_author_include_replies_to(self, aid, include):
        """Set whether we should include replies to this author in digest mode."""
        cursor = self.db.cursor()
        cursor.execute("UPDATE authors SET author_include_replies=? WHERE author_id=?", (include, aid))
        try:
            del self._author_cache[aid]
        except KeyError:
            pass
        cursor.close()

    def update_author_include_replies_from(self, aid, include):
        """Set whether we should include replies from this author in digest mode."""
        cursor = self.db.cursor()
        cursor.execute("UPDATE authors SET author_include_replies_from=? WHERE author_id=?", (include, aid))
        try:
            del self._author_cache[aid]
        except KeyError:
            pass
        cursor.close()

    def update_author(self, info, cursor):
        cursor.execute("UPDATE authors SET author_nick=?, author_fn=?, author_avatar=?, author_protected=? WHERE author_id=?", (info['screen_name'], info['name'], info['profile_image_url'], info['protected'], info['id']))
        try:
            del self._author_cache[info['id']]
        except KeyError:
            pass
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
        return timestring
        #print "Inserted tweet from %i" % author_id

    def _extract_from_xml(self, xml):
        res = {}
        for e in xml:
          if len(e)==0:
            res[e.tag] = e.text
          else:
            res[e.tag] = self._extract_from_xml(e)
        return res

    def process_tweet(self, tweet_xml, cursor):
        tweet = self._extract_from_xml(tweet_xml)
        #print tweet
        author_id = self.find_author(tweet['user']['id'], cursor)
        if author_id==None:
            author_id = self.make_author(tweet['user'], cursor)
        else:
            author_id = self.update_author(tweet['user'], cursor)
        return self.make_tweet(author_id, tweet['text'], tweet['created_at'], cursor)

    def digest(self, email_address, real=None):
        c = self.db.cursor()
        last_digest = self.get_conf('last_digest', '1970-01-01 00:00:00')
        c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author, tweet_published FROM tweets WHERE tweet_published > ? ORDER BY tweet_published ASC", [last_digest])
        rows = c.fetchall()
        if len(rows)>0:
            digest = ''
            tw = textwrap.TextWrapper(initial_indent = ' '*8, subsequent_indent = ' '*8)
            for row in rows:
                text = row[1].strip()
                # ignore replies not to us or to/from a marked author
                author = self.get_author(row[2], c)
                if author['include_replies_from']==0 and text[0]=='@':
                    if text[1:len(self.username)+1]!=self.username:
                        replyname = text[1:].replace(':', ' ').split()[0]
                        if replyname!='':
                            a = self.get_author_by_username(replyname, c)
                            if a==None or not a['include_replies_to']:
                                continue
                        else:
                            continue
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

            max_published = max(map(lambda x: x[3], rows))
            self.set_conf('last_digest', max_published)
            self.save_changes()
        c.close()

    def tweets_to_view(self, min_to_display, replies='all'):
        c = self.db.cursor()
        last_viewed = self.get_conf('last_viewed')
        if last_viewed==None:
            last_viewed = '1970-01-01 00:00:00'
        c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author, tweet_published FROM tweets WHERE tweet_published > ? ORDER BY tweet_published DESC", [last_viewed])
        rows = c.fetchall()
        number_to_fetch = min_to_display - len(rows)
        if number_to_fetch > 0:
            c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author, tweet_published FROM tweets WHERE tweet_published <= ? ORDER BY tweet_published DESC LIMIT ?", [last_viewed, number_to_fetch])
            rows1 = c.fetchall()
            rows.extend(rows1)
            rows.sort(lambda x,y: -cmp(x[3],y[3]))
        out_rows = []
        for row in rows:
            # ignore replies not to us or to/from a marked author
            text = row[1]
            author = self.get_author(row[2], c)
            if author['include_replies_from']==0 and replies=='digest' and text[0]=='@':
                if text[1:len(self.username)+1]!=self.username:
                    replyname = text[1:].replace(':', ' ').split()[0]
                    if replyname!='':
                        a = self.get_author_by_username(replyname, c)
                        if a==None or not a['include_replies_to']:
                            continue
                    else:
                        continue
            out_rows.append({ 'date': row[0],
                              'tweet': text,
                              'author': author,
                              'published': row[3]})
        c.close()
        return out_rows

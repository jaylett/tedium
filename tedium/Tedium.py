# Tedium core
#
# Copyright (C) 2009 James Aylett
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

import httplib, urllib, urllib2, os, os.path, sys, spambayes.storage
import datetime, time, smtplib, textwrap, pwd, getopt, xml.parsers.expat

try:
    from xml.etree.ElementTree import fromstring as etree_fromstring # python 2.5
except:
    from elementtree.ElementTree import fromstring as etree_fromstring # python 2.4

from pysqlite2 import dbapi2 as sqlite
from email.MIMEText import MIMEText
import email.Charset

import tedium

DB_VERSION = 13

def de_attributify(t):
    t = t.replace('&quot;', '"')
    t = t.replace('&apos;', "'")
    t = t.replace('&lt;', '<')
    t = t.replace('&gt;', '>')
    t = t.replace('&amp;', '&')
    return t

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
        self.bayespath = os.path.join(self.configpath, 'bayes')
        self.bayes = spambayes.storage.DBDictClassifier(self.bayespath)

        c = self.db.cursor()
        self.username = ''
        self.password = ''
        self._ensure_database(c)

        c.execute("SELECT last_updated, last_replies, username, password, digest_format FROM metadata LIMIT 1")
        row = c.fetchone()
        self.last_updated = row[0]
        self.last_replies = row[1]
        self.username = row[2]
        self.password = row[3]
        self.digest_format = row[4]
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
        cursor.execute("CREATE TABLE IF NOT EXISTS metadata (version INTEGER NOT NULL DEFAULT %i, last_updated DATETIME, username VARCHAR(30), password VARCHAR(30), last_digest DATETIME, last_viewed DATETIME, digest_format VARCHAR(20), current_status VARCHAR(140), view_replies VARCHAR(10), last_sequence INTEGER NOT NULL DEFAULT 1, fixed_filter VARCHAR(140), view_spam VARCHAR(10) DEFAULT 'all', last_replies DATETIME)" % DB_VERSION)

    def _initialise_database(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS tweets (tweet_id INTEGER NOT NULL PRIMARY KEY, tweet_text VARCHAR(150) NOT NULL, tweet_author INTEGER NOT NULL, tweet_published DATETIME NOT NULL, tweet_spam INTEGER DEFAULT 0, tweet_digested INTEGER(1) NOT NULL DEFAULT 0)")
        cursor.execute("CREATE TABLE IF NOT EXISTS authors (author_id INTEGER NOT NULL PRIMARY KEY, author_fn VARCHAR(30) NOT NULL, author_nick VARCHAR(30) NOT NULL, author_protected INTEGER(1), author_avatar VARCHAR(255), author_include_replies INTEGER(1) NOT NULL DEFAULT 0, author_include_replies_from INTEGER(1) NOT NULL DEFAULT 0, author_ignore_until DATETIME, author_priority INTEGER NOT NULL DEFAULT 0)")
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
        if old_version<6:
            cursor.execute("ALTER TABLE metadata ADD COLUMN last_sequence INTEGER NOT NULL DEFAULT 1")
            cursor.execute("UPDATE metadata SET version=6")
        if old_version<7:
            cursor.execute("DELETE FROM tweets")
            cursor.execute("UPDATE metadata SET version=7")
        if old_version<8:
            cursor.execute("ALTER TABLE tweets ADD COLUMN tweet_spam INTEGER DEFAULT 0")
            cursor.execute("UPDATE metadata SET version=8")
        if old_version<9:
            cursor.execute("ALTER TABLE metadata ADD COLUMN fixed_filter VARCHAR(140) DEFAULT ''")
            cursor.execute("ALTER TABLE metadata ADD COLUMN view_spam VARCHAR(10) DEFAULT 'all'")
            cursor.execute("UPDATE metadata SET version=9")
        if old_version<10:
            cursor.execute("ALTER TABLE authors ADD COLUMN author_ignore_until DATETIME")
            cursor.execute("UPDATE metadata SET version=10")
        if old_version<11:
            cursor.execute("ALTER TABLE authors ADD COLUMN author_priority INTEGER NOT NULL DEFAULT 0")
            cursor.execute("UPDATE metadata SET version=11")
        if old_version<12:
            cursor.execute("ALTER TABLE tweets ADD COLUMN tweet_digested INTEGER(1) NOT NULL DEFAULT 0")
            cursor.execute("UPDATE metadata SET version=12")
        if old_version<13:
            cursor.execute("ALTER TABLE metadata ADD COLUMN last_replies DATETIME")
            cursor.execute("UPDATE metadata SET version=13")
            
    def update(self):
        # get our latest tweet
	data = None
        try:
            uri = "https://twitter.com/users/show/%s.xml" % self.username
            f = urllib2.urlopen(uri)
            data = f.read()
            f.close()
            status = etree_fromstring(data)
            if status.tag=='error':
                return
            if status.tag!='user':
                raise tedium.TediumError('Twitter response was not an XML doc with root user')
            status = self._extract_from_xml(status)
            my_status = status.get('status', {}).get('text')
            if my_status!=None:
                self.set_conf('current_status', my_status)
        except urllib2.URLError:
            pass
        except httplib.BadStatusLine: # naughty Twitter
            pass
        except:
            if data!=None:
		print "Failed to cope with '%s'" % data
            raise
        
        if self.last_updated==None:
            uri = 'https://twitter.com/statuses/friends_timeline.xml?count=200'
        else:
            # HTTP formatted date
            uri = 'https://twitter.com/statuses/friends_timeline.xml?since=%s&count=200' % urllib.quote_plus(self.last_updated)
        data = None
        try:
            f = urllib2.urlopen(uri)
            data = f.read()
            f.close()
            max_published = self.process_tweets(data)
            if max_published!=None:
                self.set_conf('last_updated', max_published)
            # Because if the next bit goes wrong we don't want to lose this
            # date and have to do it again.
            self.save_changes()

            # And do the same for replies (which will sometimes be duplicates)
            if self.last_replies==None:
                uri = 'https://twitter.com/statuses/replies.xml'
            else:
                # HTTP formatted date
                uri = 'https://twitter.com/statuses/replies.xml?since=%s' % urllib.quote_plus(self.last_replies)
            f = urllib2.urlopen(uri)
            data = f.read()
            f.close()
            max_published = self.process_tweets(data)
            if max_published!=None:
                self.set_conf('last_replies', max_published)
            self.save_changes()
        except xml.parsers.expat.ExpatError, e:
            # Twitter are just lame. Apparently they don't know how to
            # program their load balancers (amongst, you know,
            # everything else).
            # raise tedium.TediumError('Could not fetch updates from Twitter', e)
            pass
        except urllib2.URLError, e:
            try:
                if e.code==401:
                    self.delete_credentials(c)
                    c.close()
                    raise tedium.TediumError('Username/password incorrect!', e)
                c.close()
                if e.code==304:
                    # Not modified, don't kick up a fuss
                    return
                #print e.read()
                #raise tedium.TediumError('Could not fetch updates from Twitter', e)
            except:
                raise tedium.TediumError('Error handling failed', e)
        except:
            if data!=None:
		print "Failed to cope with '%s'" % data
            raise

    def process_tweets(self, tweet_data):
        try:
            c = self.db.cursor()
            tweets = etree_fromstring(tweet_data)
            max_published = None
            if tweets.tag!='statuses':
                raise tedium.TediumError('Twitter response was not an XML doc with root statuses')
            for tweet in tweets:
                if tweet.tag!='status':
                    raise tedium.TedimuError('Twitter response was not a list of statuses')
                try:
                    published = self.process_tweet(tweet, c)
                    if published!=None and (published > max_published or max_published==None):
                        max_published = published
                except sqlite.IntegrityError:
                    # it's already in there because of a previous reply
                    # weirdness or something
                    pass
            return max_published
        finally:
            c.close()
        
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
            res_status = de_attributify(status['text'])
            if type(res_status) is unicode:
                res_status = res_status.encode('utf-8')
            if res_status==new_status:
                self.set_conf('current_status', new_status)
                self.save_changes()
            else:
                if status['truncated']!='true':
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
        cursor.execute("SELECT author_fn, author_nick, author_avatar, author_protected, author_include_replies, author_id, author_include_replies_from, author_ignore_until, author_priority FROM authors WHERE author_id=?", [int(id)])
        row = cursor.fetchone()
        if row==None:
            return None
        else:
            u = { 'id': row[5], 'fn': row[0], 'nick': row[1], 'avatar': row[2], 'include_replies_to': row[4], 'include_replies_from': row[6], 'ignore_until': row[7], 'priority': row[8] }
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

    def update_author_ignore_until(self, aid, ignore_until):
        """Set when we should ignore this user until."""
        cursor = self.db.cursor()
        cursor.execute("UPDATE authors SET author_ignore_until=? WHERE author_id=?", (ignore_until, aid))
        try:
            del self._author_cache[aid]
        except KeyError:
            pass
        cursor.close()

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

    def _tokenise_tweet(self, id):
        cursor = self.db.cursor()
        cursor.execute("SELECT tweet_text, tweet_author FROM tweets WHERE tweet_id=?", (id,))
        row = cursor.fetchone()
        if row!=None:
            tweet = row[0]
            aid = row[1]
            author = self.get_author(aid, cursor)
            tweet.replace(':', ' ')
            words = tweet.split()
            for w in words:
                yield w
            for w in words:
                yield author['nick'] + ':' + w
            yield ':' + author['nick']
        cursor.close()

    def tweet_spam_score(self, tweet_id):
        return self.bayes.spamprob(self._tokenise_tweet(tweet_id))

    def is_tweet_spam(self, tweet_id, threshold=0.9):
        return self.tweet_spam_score(tweet_id) > threshold

    def update_tweet_spamminess(self, tweet_id, is_spammy):
        cursor = self.db.cursor()
        cursor.execute("SELECT tweet_spam FROM tweets WHERE tweet_id=?", (tweet_id,))
        row = cursor.fetchone()
        if row!=None:
            was_spammy = row[0]
            if is_spammy != was_spammy and was_spammy>0:
                self.bayes.unlearn(self._tokenise_tweet(tweet_id), was_spammy==2)
        else:
            was_spammy = 0
        if is_spammy != was_spammy and is_spammy>0:
            self.bayes.learn(self._tokenise_tweet(tweet_id), is_spammy==2)
        cursor.execute("UPDATE tweets SET tweet_spam=? WHERE tweet_id=?", (is_spammy, tweet_id))
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

    def make_tweet(self, id, author_id, text, dt_in, cursor):
        # If we used Atom, this would be easier (but still not trivial,
        # as SQLite can't cope with the TZ part of the RFC 3339 date-time).
        #
        # This assumes we're in UTC (let's hope twitter did something
        # sensible - I've observed this correctly for non-UTC authors,
        # but that may be because *I'm* in UTC -- although it still works
        # during BST.)
        dt_in = dt_in.replace(' +0000', '')
        #print dt_in
        ds_obj = datetime.datetime(*time.strptime(dt_in, "%a %b %d %H:%M:%S %Y")[0:6])
        timestring = ds_obj.isoformat()
        cursor.execute("INSERT INTO tweets (tweet_id, tweet_author, tweet_text, tweet_published) VALUES (?, ?, ?, ?)", [id, author_id, text, timestring])
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
        try:
            return self.make_tweet(tweet['id'], author_id, tweet['text'], tweet['created_at'], cursor)
        except sqlite.IntegrityError:
            #print "Already had that tweet (%s, %s: '%s' by %i)? Huh..." % (tweet['id'], tweet['created_at'], tweet['text'], author_id)
            return None
        except:
            print "Could not make tweet..."
            traceback.print_exc()
            return None

    def _should_skip_tweet(self, tweet_row, skip_spam=False, skip_replies=False, cursor=None, min_author_priority=0):
        fixed_filter = self.get_conf('fixed_filter').strip()
        text = tweet_row[1].strip()
        if fixed_filter!='':
            filter_words = map(lambda x: x.lower().strip(), fixed_filter.split(','))
            for word in filter_words:
                if word in text.lower():
                    return True;
        if skip_spam and self.is_tweet_spam(tweet_row[5]):
            return True
        if cursor==None:
            c = self.db.cursor()
        else:
            c = cursor
        author = self.get_author(tweet_row[2], c)
        if author['ignore_until']>time.time():
            return True
        reply_to_me = False
        if skip_replies and author['include_replies_from']==0 and text[0]=='@':
            replyname = text[1:].replace(':', ' ').split()[0]
            if replyname==self.username or self.username==author['nick']:
                reply_to_me = True
            else:
                if replyname!='':
                    a = self.get_author_by_username(replyname, c)
                    if a==None or not a['include_replies_to']:
                        if cursor==None:
                            c.close()
                        return True
        if author['priority'] < min_author_priority and not reply_to_me:
            return True
        if cursor==None:
            c.close()
        return False

    def digest(self, email_address, real=None, min_author_priority=0):
        c = self.db.cursor()
        last_digest = self.get_conf('last_digest', '1970-01-01 00:00:00')
        c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author, tweet_published, tweet_spam, tweet_id, tweet_digested FROM tweets WHERE tweet_published > ? ORDER BY tweet_published ASC", [last_digest])
        rows = c.fetchall()
        if len(rows)>0:
            digest = ''
            tw = textwrap.TextWrapper(initial_indent = ' '*8, subsequent_indent = ' '*8)
            for row in rows:
                if row[6]==1 or self._should_skip_tweet(row, skip_spam=True, skip_replies=True, cursor=c, min_author_priority=min_author_priority):
                    continue
                author = self.get_author(row[2], c)
                digest_keys = {'time': row[0], 'nick': author['nick'], 'fn': author['fn'], 'tweet': row[1].strip(), 'wrapped_tweet': tw.fill(row[1])}
                digest += self.digest_line(digest_keys)
                if min_author_priority>1:
                    c.execute("UPDATE tweets SET tweet_digested=1 WHERE tweet_id=?", [row[5]])
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
                        format_email = '%s <%s>' % ('Tedium', email_address)
                    msg['From'] = format_email
                    msg['To'] = format_email
                    s = smtplib.SMTP()
                    s.connect()
                    s.sendmail(email_address, [email_address], msg.as_string())
                    s.close()

            max_published = max(map(lambda x: x[3], rows))
            # Don't update the last digest time unless we were showing
            # replies from all users. This means you'll see some
            # multiple times, but is much more efficient than recording
            # whether we've shown each tweet individually in the database
            if min_author_priority==0:
                self.set_conf('last_digest', max_published)
            self.save_changes()
        c.close()

    def tweets_to_view(self, min_to_display, replies='all', spam='all'):
        c = self.db.cursor()
        last_digest = self.get_conf('last_digest')
        if last_digest!=None:
            c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author, tweet_published, tweet_spam, tweet_id FROM tweets WHERE tweet_published > ? ORDER BY tweet_published DESC", [last_digest])
            rows = c.fetchall()
        else:
            rows = []
            
        number_to_fetch = 2*min_to_display - len(rows)
        if number_to_fetch > 0:
            last_viewed = self.get_conf('last_viewed')
            if last_viewed==None:
                last_viewed = '1970-01-01 00:00:00'
            if last_digest!=None:
                c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author, tweet_published, tweet_spam, tweet_id FROM tweets WHERE tweet_published > ? AND tweet_published < ? ORDER BY tweet_published DESC LIMIT ?", [last_viewed, last_digest, number_to_fetch])
            else:
                c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author, tweet_published, tweet_spam, tweet_id FROM tweets WHERE tweet_published > ? ORDER BY tweet_published DESC LIMIT ?", [last_viewed, number_to_fetch])
            rows1 = c.fetchall()
            rows.extend(rows1)

        number_to_fetch = min_to_display - len(rows)
        if number_to_fetch > 0:
            c.execute("SELECT STRFTIME('%H:%M', tweet_published), tweet_text, tweet_author, tweet_published, tweet_spam, tweet_id FROM tweets WHERE tweet_published <= ? ORDER BY tweet_published DESC LIMIT ?", [last_viewed, number_to_fetch])
            rows1 = c.fetchall()
            rows.extend(rows1)
        rows.sort(lambda x,y: -cmp(x[3],y[3]))

        out_rows = []
        for row in rows:
        
            # ignore replies not to/from us or to/from a marked author
            if self._should_skip_tweet(row, skip_spam=(spam=='none'), skip_replies=(replies=='digest'), cursor=c):
                continue
            author = self.get_author(row[2], c)
            out_rows.append({ 'date': row[0],
                              'tweet': row[1].strip(),
                              'author': author,
                              'classified_spamminess': row[4],
                              'id': row[5],
                              # 0 = unclassified
                              # 1 = classified as ham
                              # 2 = classified as spam
                              'published': row[3]})
        c.close()
        return out_rows

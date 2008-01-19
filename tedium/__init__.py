# Tedium library
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
tedium: a natural result of too much twitter
                    or
tedium: the Twitter Digest Manager

Run once to set up username/password, run on cron to grab latest
tweets, run as CGI to see recent activity, run with an email address
to get a digest. It figures out the context.

If you run it as a CGI, it'll choose the first CSS file in the same
directory (assuming the CGI process can read that
directory). The bulk is a simple <ol>. Classnames used are:

  time, author, tweet   layout of the tweet (three <span>s inside <li>)
  protected	        applied to <li> if updates are protected
  new                   applied to <li> if tweet after last CGI view
  notindigest           applied to <li> if tweet after last email digest

When you view the CGI, anything on there won't appear on a future
email digest.

For CGI it's *strongly* advised that you run under suexec or via
userv, so it's running as you rather than as the web user. You might
also prefer to use cgi_driver.py instead of copying everything into
your web space. (You'll need to edit it slightly.)

Everything is stored in ~/.tedium, or somewhere else if you pass in
a directory to the Tedium class constructor. (See down the bottom,
and above in the sample CGI launcher.) You should change the
permissions on the directory so they aren't readable by anyone other
than you (hence suexec/userv for CGI) since it will contain your
twitter login credentials.

For CGI access, you must run behind some sort of HTTP authentication.
Either use digest, or basic behind HTTPS, or anything over a local
connection, or something like that. Connections to twitter use HTTPS.

Currently there is no way of editing this, but if you want to see
replies to a particular user in the digest, set
author_include_replies to 1 in the authors table for them (use the
sqlite3 client). Otherwise, only replies to you are shown.

Invoke as: tedium.main().
"""

import getopt, sys, os

import tedium.Tedium, tedium.Cgi

__all__ = ['Cgi', 'Tedium']

VERSION = '0.2'
DB_VERSION = 2
#DEFAULT_DIGEST_FORMAT = u'(%(time)5.5s) %(nick)12.12s: %(tweet)-48.48s \u00bb\n'
#DEFAULT_DIGEST_FORMAT = '(%(time)5.5s) %(nick)12.12s: %(tweet)s\n'
DEFAULT_DIGEST_FORMAT = '(%(time)5.5s) %(fn)s: \n%(wrapped_tweet)s\n\n'

class TediumError(RuntimeError):
    def __init__(self, message, aux=None):
        RuntimeError.__init__(self, message)
        self.aux = aux

def usage():
    print u"Usage: %s [options] [email [name]]" % sys.argv[0]
    print u"Options:"
    print u"\t--help\t\tThis message"
    print u"\t--confdir d\tUse ``d'' instead of ~/.tedium"
    print u"\t--reconfigure\tReconfigure tedium"
    print u"\t--test\t\tdon't require auth, don't update timestamps"
    print
    print u"Will force configuration the first time."
    print u"Subsequent runs will update from Twitter."
    print u"Call with email address and optional name to generate digest."
    print u"Run as CGI for web interface."

def main():
    """
    Actually run tedium, in whatever way you need.
    It auto-detects whether it should configure, update, digest or act as
    a CGI, based on invocation parameters and current state.
    """
    try:
        try:
            optlist, args = getopt.getopt(sys.argv[1:], 'hc:rt', ['help', 'confdir=', 'reconfigure', 'test'])
        except getopt.GetoptError:
            usage()
            sys.exit(2)

        confdir = None
        reconfigure = False
        is_test = False

        for opt, arg in optlist:
            if opt in ('-h', '--help'):
                usage()
                sys.exit()
            if opt in ('-c', '--confdir'):
                confdir = arg
            if opt in ('r', '--reconfigure'):
                reconfigure = True
            if opt in ('t', '--test'):
                is_test = True

        t = Tedium.Tedium(confdir)
        if reconfigure:
            t.reconfigure()
            sys.exit()

        if len(args)>0:
            if len(args)>1:
                t.digest(args[0], args[1])
            else:
                t.digest(args[0])
        elif os.environ.get('GATEWAY_INTERFACE')=='CGI/1.1':
            driver = Cgi.Driver(t, is_test)
            driver.do_get()
        else:
            # Get latest tweets (possibly prompt for configuration first)
            t.update()
    except TediumError, e:
        sys.stdout.write(str(e))
        sys.stdout.write("\n")
        print e.aux
